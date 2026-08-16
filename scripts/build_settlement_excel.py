"""One spreadsheet of every settlement in Türkiye: neighbourhoods, villages, and the
urban/rural split that falls out of having both.

Why a file and not a screen: 32.681 rows sorted by "which neighbourhood has the most
adults" is a spreadsheet question. The explorer answers "how does this place compare to
that one over time"; it would need a menu of 32.681 entries to answer this one, and the
menu would be worse than the question.

The sheets:

* **Mahalleler** — a row per neighbourhood, first year and last year side by side, with
  the growth of the total, the children and the adults separately. A neighbourhood whose
  population grew 40% while its children fell is a different place from one where both
  grew; one column cannot say that, three can.
* **Köyler** — a row per village, total only. TÜİK publishes the 18+ split for
  municipality neighbourhoods and not for villages: tick the age breakdown in MEDAS and
  `Köy` disappears from the level box. So the village sheet compares populations, never
  ages, and says so.
* **İlçeler**, **İller** — the same numbers rolled up, plus the urban/rural split.
* **Özet** — the ten highest and lowest of what people actually ask for.
* **Yıllar** — every settlement's total, year by year, wide.
* **Notlar** — what the numbers do and do not cover, in Turkish, inside the file. A
  spreadsheet travels away from whoever made it; the caveats have to travel with it.

The urban/rural split only exists for **51 provinces**. Law 6360 turned every village in
the 30 metropolitan provinces into a neighbourhood in 2014, so there they are all "kent"
by definition and the ratio would be 100% everywhere — true and useless. Where villages
survive, the split is the real thing: the belediye population against the village
population, both counted the same way.

Run:  uv run python scripts/build_settlement_excel.py
"""

from __future__ import annotations

import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

TARGET = PUBLIC.parent / "cikti" / "mahalle-nufus.xlsx"
DATA = PUBLIC.parent / "src" / "veriatlas" / "data"

CHILD = "0-17"
ADULT = "18+"


def villages() -> pl.DataFrame:
    """Every village-year, from the warehouse and the village registry.

    Read here rather than parsed here. The exports have their own trap — the bucak stops
    being written in 2017, so a village's label loses a path segment mid-series — and that
    belongs in the adapter with the rest of the reading, not in a second copy that can
    drift from it. Since `tuik_villages` loads them, this script does what everything else
    does: asks the fact table.
    """
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    rows = (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == "village")
        )
        .with_columns(pl.col("period_start").dt.year().alias("yil"))
        .select("area_id", "yil", pl.col("value").alias("nufus"))
    )
    if rows.is_empty():
        raise ValueError("depoda koy satiri yok — once load.py tuik_villages")

    registry = pl.read_csv(DATA / "areas_tr_villages.csv").select(
        "area_id",
        pl.col("name_tr").alias("koy"),
        pl.col("bucak"),
        pl.col("parent_id"),
        pl.col("medas_code").alias("kod"),
    )
    districts = pl.read_csv(DATA / "areas_tr_districts.csv").select(
        "area_id", pl.col("name_tr").alias("ilce")
    )
    provinces = pl.read_csv(DATA / "areas_tr.csv").select(
        "area_id", pl.col("name_tr").alias("il")
    )
    return (
        rows.join(registry, on="area_id")
        .join(districts, left_on="parent_id", right_on="area_id", how="left")
        .with_columns(pl.col("area_id").str.slice(0, 5).alias("il_id"))
        .join(provinces, left_on="il_id", right_on="area_id", how="left")
    )


def neighbourhoods() -> pl.DataFrame:
    """Every neighbourhood-year, wide: total, child, adult."""
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    rows = (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == "neighbourhood")
        )
        .with_columns(
            pl.col("period_start").dt.year().alias("yil"),
            pl.col("dims").str.extract(r"age=([^;]*)").alias("yas"),
        )
        .group_by("area_id", "yil", "yas")
        .agg(pl.col("value").sum().alias("kisi"))
    )
    wide = rows.pivot(values="kisi", index=["area_id", "yil"], on="yas").with_columns(
        (pl.col(CHILD).fill_null(0) + pl.col(ADULT).fill_null(0)).alias("toplam")
    )
    return wide.rename({CHILD: "cocuk", ADULT: "yetiskin"})


def named(wide: pl.DataFrame) -> pl.DataFrame:
    """Attach province, district, municipality and neighbourhood names."""
    hoods = pl.read_csv(DATA / "areas_tr_neighbourhoods.csv")
    districts = pl.read_csv(DATA / "areas_tr_districts.csv").select(
        "area_id", pl.col("name_tr").alias("ilce")
    )
    provinces = pl.read_csv(DATA / "areas_tr.csv").select(
        "area_id", pl.col("name_tr").alias("il")
    )
    return (
        wide.join(
            hoods.select(
                "area_id",
                pl.col("name_tr").alias("mahalle"),
                pl.col("municipality").alias("belediye"),
                "parent_id",
                "first_seen",
                "last_seen",
            ),
            on="area_id",
            how="left",
        )
        .join(districts, left_on="parent_id", right_on="area_id", how="left")
        .with_columns(
            pl.col("area_id").str.slice(0, 5).alias("il_id"),
            pl.col("parent_id").alias("ilce_id"),
        )
        .join(provinces, left_on="il_id", right_on="area_id", how="left")
    )


def area_totals(level: str, year: int) -> pl.DataFrame:
    """Published population per area at a level, for the coverage column."""
    wanted = {"il": "province", "ilce": "district"}[level]
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    return (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == wanted)
            & (pl.col("period_start").dt.year() == year)
        )
        .group_by("area_id")
        .agg(pl.col("value").sum().alias("nufus"))
    )


def growth(now: str, before: str, name: str) -> pl.Expr:
    """Growth from one year to another, as a proportion, or nothing when there is no base.

    Nothing, not zero: a settlement that appears after the first year has no growth to
    report, and printing 0% would say it stood still.
    """
    return (
        pl.when(pl.col(before) > 0)
        .then(pl.col(now) / pl.col(before) - 1)
        .otherwise(None)
        .alias(name)
    )


#: Column name to the words shown in the header. Capitalised, spaced, and said in Turkish
#: — the sheet is read by people, and `yetiskin_payi` is not a phrase in any language.
HEADERS = {
    "il": "İl",
    "ilce": "İlçe",
    "bucak": "Bucak",
    "belediye": "Belediye",
    "mahalle": "Mahalle",
    "koy": "Köy",
    "kimlik": "Kimlik",
    "kod": "MEDAS kodu",
    "mahalle_sayisi": "Mahalle sayısı",
    "koy_sayisi": "Köy sayısı",
    "yetiskin_payi": "Yetişkin payı",
    "kapsam": "Kapsam",
    "ilk_gorulen": "İlk görülen",
    "son_gorulen": "Son görülen",
    "kent": "Kent (belediye)",
    "kir": "Kır (köy)",
    "kir_payi": "Kır payı",
    "kent_artis": "Kent artışı",
    "kir_artis": "Kır artışı",
    "sira": "Sıra",
    "olcut": "Ölçüt",
    "deger": "Değer",
}


def header_of(column: str, first: int, last: int) -> str:
    if column in HEADERS:
        return HEADERS[column]
    words = {
        "toplam": "Toplam",
        "cocuk": "Çocuk (0-17)",
        "yetiskin": "Yetişkin (18+)",
        "nufus": "Nüfus",
        "gercek": "Gerçek nüfus",
        "kir": "Kır (köy)",
        "kent": "Kent (belediye)",
    }
    for key, word in words.items():
        if column.startswith(key + "_"):
            tail = column[len(key) + 1 :]
            if tail.isdigit():
                return word + " " + tail
            if tail == "artis":
                return word + " artışı"
    return column[:1].upper() + column[1:].replace("_", " ")


def sheet(book, frame, title, formats, first, last, widths=None) -> None:
    """One sheet: frozen header, filter on, every cell centred but the names."""
    page = book.add_worksheet(title)
    page.freeze_panes(1, 0)
    page.set_row(0, 34)

    widths = widths or {}
    for index, column in enumerate(frame.columns):
        page.write(0, index, header_of(column, first, last), formats["head"])
        page.set_column(
            index,
            index,
            widths.get(column, 16),
            formats.get(column, formats["text"]),
        )
    page.autofilter(0, 0, len(frame), len(frame.columns) - 1)

    for index, column in enumerate(frame.columns):
        style = formats.get(column, formats["text"])
        for row, value in enumerate(frame[column].to_list(), start=1):
            if value is None:
                continue
            page.write(row, index, value, style)


def main() -> None:
    wide = named(neighbourhoods())
    years = sorted(wide["yil"].unique().to_list())
    first, last = years[0], years[-1]

    koy = villages()
    koy_years = sorted(koy["yil"].unique().to_list())
    koy_first, koy_last = koy_years[0], koy_years[-1]

    # region Neighbourhoods

    def at(year: int) -> pl.DataFrame:
        return wide.filter(pl.col("yil") == year).select(
            "area_id",
            pl.col("toplam").alias("toplam_" + str(year)),
            pl.col("cocuk").alias("cocuk_" + str(year)),
            pl.col("yetiskin").alias("yetiskin_" + str(year)),
        )

    base = (
        wide.filter(pl.col("yil") == last)
        .join(at(first), on="area_id", how="left")
        .with_columns((pl.col("yetiskin") / pl.col("toplam")).alias("yetiskin_payi"))
        .rename(
            {
                "toplam": "toplam_" + str(last),
                "cocuk": "cocuk_" + str(last),
                "yetiskin": "yetiskin_" + str(last),
                "first_seen": "ilk_gorulen",
                "last_seen": "son_gorulen",
            }
        )
        .with_columns(
            growth("toplam_" + str(last), "toplam_" + str(first), "toplam_artis"),
            growth("cocuk_" + str(last), "cocuk_" + str(first), "cocuk_artis"),
            growth("yetiskin_" + str(last), "yetiskin_" + str(first), "yetiskin_artis"),
        )
    )

    mahalleler = base.select(
        "il",
        "ilce",
        "belediye",
        "mahalle",
        "toplam_" + str(last),
        "cocuk_" + str(last),
        "yetiskin_" + str(last),
        "yetiskin_payi",
        "toplam_" + str(first),
        "cocuk_" + str(first),
        "yetiskin_" + str(first),
        "toplam_artis",
        "cocuk_artis",
        "yetiskin_artis",
        "ilk_gorulen",
        "son_gorulen",
        pl.col("area_id").alias("kimlik"),
    ).sort("yetiskin_" + str(last), descending=True)

    # endregion

    # region Villages

    def koy_at(year: int) -> pl.DataFrame:
        return koy.filter(pl.col("yil") == year).select(
            "kod", pl.col("nufus").alias("nufus_" + str(year))
        )

    koyler = (
        koy_at(koy_last)
        .join(koy_at(koy_first), on="kod", how="left")
        .join(
            koy.group_by("kod").agg(
                pl.col("il").last(),
                pl.col("ilce").last(),
                pl.col("bucak").last(),
                pl.col("koy").last(),
            ),
            on="kod",
        )
        .with_columns(
            growth("nufus_" + str(koy_last), "nufus_" + str(koy_first), "nufus_artis")
        )
        .select(
            "il",
            "ilce",
            "bucak",
            "koy",
            "nufus_" + str(koy_last),
            "nufus_" + str(koy_first),
            "nufus_artis",
            "kod",
        )
        .sort("nufus_" + str(koy_last), descending=True)
    )

    # endregion

    # region Roll-ups

    def rolled(keys: list[str], area: str) -> pl.DataFrame:
        whole = area_totals(area, last)
        summed = (
            base.group_by(keys)
            .agg(
                pl.len().alias("mahalle_sayisi"),
                pl.col("toplam_" + str(last)).sum(),
                pl.col("cocuk_" + str(last)).sum(),
                pl.col("yetiskin_" + str(last)).sum(),
                pl.col("toplam_" + str(first)).sum(),
                pl.col("cocuk_" + str(first)).sum(),
                pl.col("yetiskin_" + str(first)).sum(),
                pl.col(area + "_id").first().alias("kimlik"),
            )
            .with_columns(
                (pl.col("yetiskin_" + str(last)) / pl.col("toplam_" + str(last))).alias(
                    "yetiskin_payi"
                ),
                growth("toplam_" + str(last), "toplam_" + str(first), "toplam_artis"),
                growth("cocuk_" + str(last), "cocuk_" + str(first), "cocuk_artis"),
                growth(
                    "yetiskin_" + str(last), "yetiskin_" + str(first), "yetiskin_artis"
                ),
            )
        )
        return summed.join(
            whole, left_on="kimlik", right_on="area_id", how="left"
        ).with_columns(
            (pl.col("toplam_" + str(last)) / pl.col("nufus")).alias("kapsam")
        )

    ilceler = (
        rolled(["il", "ilce"], "ilce")
        .rename({"nufus": "gercek_" + str(last)})
        .sort("toplam_" + str(last), descending=True)
    )

    # The urban/rural split, per province, for the 51 that still have villages.
    kir = koy.group_by("il", "yil").agg(pl.col("nufus").sum().alias("kir"))
    kir_wide = (
        kir.filter(pl.col("yil") == koy_last)
        .select("il", pl.col("kir").alias("kir_" + str(koy_last)))
        .join(
            kir.filter(pl.col("yil") == koy_first).select(
                "il", pl.col("kir").alias("kir_" + str(koy_first))
            ),
            on="il",
            how="left",
        )
        .with_columns(
            growth("kir_" + str(koy_last), "kir_" + str(koy_first), "kir_artis")
        )
    )

    iller = (
        rolled(["il"], "il")
        .rename({"nufus": "gercek_" + str(last)})
        .join(kir_wide, on="il", how="left")
        .with_columns(
            pl.col("toplam_" + str(last)).alias("kent_" + str(last)),
            growth("toplam_" + str(last), "toplam_" + str(first), "kent_artis"),
        )
        .with_columns(
            pl.when(pl.col("kir_" + str(koy_last)).is_not_null())
            .then(
                pl.col("kir_" + str(koy_last))
                / (pl.col("kir_" + str(koy_last)) + pl.col("kent_" + str(last)))
            )
            .otherwise(None)
            .alias("kir_payi")
        )
        .select(
            "il",
            "mahalle_sayisi",
            "toplam_" + str(last),
            "cocuk_" + str(last),
            "yetiskin_" + str(last),
            "yetiskin_payi",
            "toplam_artis",
            "cocuk_artis",
            "yetiskin_artis",
            "gercek_" + str(last),
            "kapsam",
            "kir_" + str(koy_last),
            "kir_payi",
            "kir_artis",
            "kent_artis",
        )
        .sort("toplam_" + str(last), descending=True)
    )

    # endregion

    # region Summary

    def top(frame: pl.DataFrame, column: str, label: str, rising=True, take=10):
        ordered = frame.drop_nulls(column).sort(column, descending=rising).head(take)
        return pl.DataFrame(
            {
                "olcut": [label] * len(ordered),
                "sira": list(range(1, len(ordered) + 1)),
                "il": ordered["il"].to_list(),
                "deger": ordered[column].to_list(),
            }
        )

    ozet = pl.concat(
        [
            top(iller, "toplam_artis", "En çok büyüyen il (belediye nüfusu)"),
            top(iller, "toplam_artis", "En çok küçülen il (belediye nüfusu)", False),
            top(iller, "cocuk_artis", "Çocuk nüfusu en çok düşen il", False),
            top(iller, "cocuk_artis", "Çocuk nüfusu en çok artan il"),
            top(iller, "yetiskin_artis", "Yetişkin nüfusu en çok artan il"),
            top(iller, "yetiskin_payi", "Yetişkin payı en yüksek il"),
            top(iller, "yetiskin_payi", "Yetişkin payı en düşük il", False),
            top(iller, "kir_payi", "Kır payı en yüksek il (51 il içinde)"),
            top(iller, "kir_artis", "Kır nüfusu en çok düşen il", False),
        ]
    )

    # endregion

    seri = (
        wide.select("area_id", "il", "ilce", "mahalle", "yil", "toplam")
        .pivot(values="toplam", index=["area_id", "il", "ilce", "mahalle"], on="yil")
        .select(
            ["il", "ilce", "mahalle"]
            + [str(y) for y in years]
            + [pl.col("area_id").alias("kimlik")]
        )
        .sort(str(last), descending=True)
    )

    # region Writing

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))

    head = book.add_format(
        {
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
            "bg_color": "#1F3864",
            "font_color": "#FFFFFF",
            "border": 1,
        }
    )
    text = book.add_format({"align": "left", "valign": "vcenter"})
    middle = book.add_format({"align": "center", "valign": "vcenter"})
    sayi = book.add_format(
        {"num_format": "#,##0", "align": "center", "valign": "vcenter"}
    )
    # Two decimals, as asked: a growth of 4,7% and one of 4,74% are different answers when
    # the sheet is being sorted by that column.
    #
    # The decimal mark in a format code is a dot even though the reader sees a comma: the
    # code is stored in one canonical syntax and rendered with the machine's separators.
    # "0,00%" is not the Turkish spelling of this, it is thousands grouping with no
    # decimals at all — which turned 4,74% into "005%" until it was noticed.
    yuzde = book.add_format(
        {"num_format": "0.00%", "align": "center", "valign": "vcenter"}
    )

    numeric = {}
    for column in (
        ["mahalle_sayisi", "koy_sayisi", "kod", "ilk_gorulen", "son_gorulen", "sira"]
        + ["gercek_" + str(last), "deger"]
        + ["toplam_" + str(y) for y in (first, last)]
        + ["cocuk_" + str(y) for y in (first, last)]
        + ["yetiskin_" + str(y) for y in (first, last)]
        + ["nufus_" + str(y) for y in (koy_first, koy_last)]
        + ["kir_" + str(y) for y in (koy_first, koy_last)]
        + ["kent_" + str(last)]
        + [str(y) for y in years]
    ):
        numeric[column] = sayi
    for column in (
        "yetiskin_payi",
        "kapsam",
        "kir_payi",
        "toplam_artis",
        "cocuk_artis",
        "yetiskin_artis",
        "nufus_artis",
        "kir_artis",
        "kent_artis",
    ):
        numeric[column] = yuzde

    formats = {
        **numeric,
        "head": head,
        "text": middle,
        "il": text,
        "ilce": text,
        "bucak": text,
        "belediye": text,
        "mahalle": text,
        "koy": text,
        "olcut": text,
        "kimlik": middle,
    }
    widths = {
        "il": 15,
        "ilce": 20,
        "bucak": 18,
        "belediye": 24,
        "mahalle": 28,
        "koy": 24,
        "kimlik": 20,
        "olcut": 38,
        "yetiskin_payi": 14,
        "kapsam": 12,
    }

    # The summary first: it is the sheet that answers a question without being asked one.
    sheet(book, ozet, "Özet", formats, first, last, widths)
    sheet(book, mahalleler, "Mahalleler", formats, first, last, widths)
    sheet(book, koyler, "Köyler", formats, first, last, widths)
    sheet(book, ilceler, "İlçeler", formats, first, last, widths)
    sheet(book, iller, "İller", formats, first, last, widths)
    sheet(book, seri, "Yıllar", formats, first, last, widths)

    notes = book.add_worksheet("Notlar")
    notes.set_column(0, 0, 112, book.add_format({"text_wrap": True, "valign": "top"}))
    kayip = len(seri) - len(mahalleler)
    lines = [
        "VeriAtlas — yerleşim nüfusu (mahalle ve köy)",
        "",
        "Kaynak: TÜİK MEDAS, adrese dayalı nüfus kayıt sistemi. Çekim: 2026-08.",
        f"Mahalleler: {first}-{last}, {len(mahalleler)} mahalle, 81 il.",
        "Köyler: {}-{}, {} köy, {} il.".format(
            koy_first, koy_last, len(koyler), koy["il"].n_unique()
        ),
        "",
        "MAHALLE / KÖY AYRIMI",
        "· 6360 sayılı yasa 2014'te 30 büyükşehir ilindeki bütün köyleri mahalleye",
        "  çevirdi. O illerde köy yok — eksik değil, gerçekten yok.",
        "· Kalan 51 ilde ikisi bir arada: belediye mahalleleri (kent) ve köyler (kır).",
        "  'İller' sayfasındaki kır payı, kır artışı ve kent artışı yalnız bu 51 il için",
        "  doludur. Büyükşehirlerde bu hücreler boştur; sıfır değildir, hesaplanamaz.",
        "",
        "YAŞ AYRIMI YALNIZ MAHALLEDE",
        "· TÜİK 18+ kırılımını yalnız belediye mahalleleri için yayımlıyor: MEDAS'ta yaş",
        "  kırılımı işaretlenince Köy düzeyi seçeneklerden kayboluyor.",
        "· Bu yüzden köyler yalnız toplam nüfusla karşılaştırılıyor. Köy sayfasında çocuk",
        "  ve yetişkin sütunu yoktur — boş bırakılmamıştır, sorulamaz.",
        "",
        "KAPSAM",
        "· 'Kapsam' sütunu: mahallelerin toplamı, yayımlanan gerçek nüfusun yüzde kaçı.",
        "  Türkiye genelinde %95. Şanlıurfa ve Van'da %100 (her köy mahalle olmuş),",
        "  Ardahan'da %47 — aradaki fark köylerde yaşayanlardır ve o kısım 'Köyler'",
        "  sayfasındadır.",
        f"· {kayip} mahalle 'Mahalleler' sayfasında yok: {last} yılında verisi olan {len(mahalleler)} mahalle",
        f"  var, oysa {first}-{last} arasında {len(seri)} ayrı mahalle görüldü. Fark; birleşen, kapanan",
        "  ya da kimliği değişenlerdir. Hepsi 'Yıllar' sayfasında, son görüldüğü yılla.",
        "",
        "İSİMLER",
        "· Kimlik MEDAS kodudur, ad değildir. Aynı il içinde yüzlerce mahalle aynı adı",
        "  taşıyor ('Merkez', 'Yeni'); köylerde de 'Merkez Bucağı' altında aynı adlar",
        "  tekrarlanıyor. Bu yüzden hiçbir eşleştirme ada göre yapılmadı.",
        "· Gösterilen ad, görülen EN YENİ addır. 2013-2025 arasında 846 mahalle adı",
        "  değişti; eski adlarıyla birlikte docs/mahalle-adlari.md dosyasında.",
        "· 'İlk görülen' / 'son görülen', verinin bulunduğu yıllardır — idari kuruluş ya",
        "  da kapanış tarihi değildir.",
        "",
        "ORANLAR",
        "· Artış oranları son yıl / ilk yıl − 1 biçimindedir, iki ondalıkla.",
        "· Yetişkin payı = 18+ / toplam. Kır payı = köy / (köy + belediye).",
        "· Bir yerleşim aradaki yıllarda bölündüyse ya da birleştiyse, oran o idari",
        "  değişimi de içerir; nüfusun kendi hareketi değildir.",
    ]
    for row, line in enumerate(lines):
        notes.write(row, 0, line)

    book.close()
    # endregion

    print("yazildi:", TARGET)
    print(
        "  Mahalleler:",
        len(mahalleler),
        "| Köyler:",
        len(koyler),
        "| İlçeler:",
        len(ilceler),
        "| İller:",
        len(iller),
        "| Özet:",
        len(ozet),
    )


if __name__ == "__main__":
    main()
