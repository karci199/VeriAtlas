"""One spreadsheet of every neighbourhood in Türkiye: total, 0-17 and 18+.

Why a file and not a screen: 32.681 rows sorted by "which neighbourhood has the most
adults" is a spreadsheet question. The explorer answers "how does this place compare to
that one over time"; it would need a menu of 32.681 entries to answer this one, and the
menu would be worse than the question.

What is in it, one sheet at a time:

* **Mahalleler** — a row per neighbourhood. The newest year in full, the first year for
  comparison, and the share of adults. Sort by any column, filter by province.
* **İlçeler**, **İller** — the same three numbers rolled up. These are exact sums: a
  neighbourhood belongs to exactly one district and each is counted once.
* **Yıllar** — the total per neighbourhood per year, wide, for anyone who wants the whole
  series in one place.
* **Notlar** — what the numbers do and do not cover, in Turkish, in the file itself.
  A spreadsheet travels away from whoever made it; the caveats have to travel with it.

The one caveat that matters most: this is **mahalle** data, which after the 2012 law means
the neighbourhoods of municipalities. Villages that were not turned into neighbourhoods
are not here, and TÜİK does not publish 18+ for them at all.

Run:  uv run python scripts/build_neighbourhood_excel.py
"""

from __future__ import annotations

import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

TARGET = PUBLIC.parent / "cikti" / "mahalle-nufus.xlsx"

CHILD = "0-17"
ADULT = "18+"


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
    hoods = pl.read_csv(
        PUBLIC.parent / "src/veriatlas/data/areas_tr_neighbourhoods.csv"
    )
    districts = pl.read_csv(
        PUBLIC.parent / "src/veriatlas/data/areas_tr_districts.csv"
    ).select("area_id", pl.col("name_tr").alias("ilce"))
    provinces = pl.read_csv(PUBLIC.parent / "src/veriatlas/data/areas_tr.csv").select(
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


def sheet(book, frame: pl.DataFrame, title: str, widths: dict, formats: dict) -> None:
    """One sheet with a frozen, filtered header row.

    Frozen and filtered on purpose: a table of 32.681 rows whose header scrolls away is a
    table nobody can read past the first screen.
    """
    page = book.add_worksheet(title)
    page.freeze_panes(1, 0)
    page.set_row(0, 30, formats["head"])
    for index, column in enumerate(frame.columns):
        page.write(0, index, column, formats["head"])
        page.set_column(index, index, widths.get(column, 12), formats.get(column))
    page.autofilter(0, 0, len(frame), len(frame.columns) - 1)

    for index, column in enumerate(frame.columns):
        values = frame[column].to_list()
        for row, value in enumerate(values, start=1):
            if value is None:
                continue
            page.write(row, index, value, formats.get(column))


def main() -> None:
    wide = named(neighbourhoods())
    years = sorted(wide["yil"].unique().to_list())
    first, last = years[0], years[-1]

    latest = wide.filter(pl.col("yil") == last)
    earliest = wide.filter(pl.col("yil") == first).select(
        "area_id", pl.col("toplam").alias("ilk_toplam")
    )

    mahalleler = (
        latest.join(earliest, on="area_id", how="left")
        .with_columns(
            (pl.col("yetiskin") / pl.col("toplam")).alias("yetiskin_payi"),
            pl.when(pl.col("ilk_toplam") > 0)
            .then(pl.col("toplam") / pl.col("ilk_toplam") - 1)
            .otherwise(None)
            .alias("degisim"),
        )
        .select(
            pl.col("il"),
            pl.col("ilce"),
            pl.col("belediye"),
            pl.col("mahalle"),
            pl.col("toplam").alias("toplam_" + str(last)),
            pl.col("cocuk").alias("cocuk_" + str(last)),
            pl.col("yetiskin").alias("yetiskin_" + str(last)),
            pl.col("yetiskin_payi"),
            pl.col("ilk_toplam").alias("toplam_" + str(first)),
            pl.col("degisim"),
            pl.col("first_seen").alias("ilk_gorulen"),
            pl.col("last_seen").alias("son_gorulen"),
            pl.col("area_id").alias("kimlik"),
        )
        .sort("yetiskin_" + str(last), descending=True)
    )

    def rolled(keys: list[str], area: str) -> pl.DataFrame:
        """The three numbers summed, and how much of the real place they cover.

        The coverage column is the point of this sheet. A province total here is *not*
        the province: it is the part of it that lives in a municipality neighbourhood.
        In Şanlıurfa and Van that is everybody, because every village became a mahalle;
        in Ardahan it is 47%, and the missing half is villages TÜİK does not publish this
        way at all. Without the column the sheet would quietly under-report a third of the
        country and look complete doing it.
        """
        whole = area_totals(area, last)
        summed = (
            latest.group_by(keys)
            .agg(
                pl.len().alias("mahalle_sayisi"),
                pl.col("toplam").sum().alias("toplam_" + str(last)),
                pl.col("cocuk").sum().alias("cocuk_" + str(last)),
                pl.col("yetiskin").sum().alias("yetiskin_" + str(last)),
                pl.col(area + "_id").first().alias("kimlik"),
            )
            .with_columns(
                (pl.col("yetiskin_" + str(last)) / pl.col("toplam_" + str(last))).alias(
                    "yetiskin_payi"
                )
            )
        )
        return (
            summed.join(whole, left_on="kimlik", right_on="area_id", how="left")
            .with_columns(
                (pl.col("toplam_" + str(last)) / pl.col("nufus")).alias("kapsam")
            )
            .rename({"nufus": "gercek_nufus_" + str(last)})
            .sort("toplam_" + str(last), descending=True)
        )

    ilceler = rolled(["il", "ilce"], "ilce")
    iller = rolled(["il"], "il")

    # Keyed by id, with the names alongside. Names are not unique enough to pivot on:
    # forty-odd neighbourhoods share a province-district-name triple, and pivoting by name
    # fails outright rather than merging them — which is the better failure, and the
    # reason the id is what identifies a place everywhere in this project (K15).
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

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET), {"constant_memory": False})

    head = book.add_format(
        {
            "bold": True,
            "valign": "vcenter",
            "bg_color": "#1F3864",
            "font_color": "white",
            "border": 1,
        }
    )
    sayi = book.add_format({"num_format": "#,##0"})
    yuzde = book.add_format({"num_format": "0,0%"})
    metin = book.add_format({})

    counts = {
        "toplam_" + str(last): sayi,
        "cocuk_" + str(last): sayi,
        "yetiskin_" + str(last): sayi,
        "toplam_" + str(first): sayi,
        "mahalle_sayisi": sayi,
        "gercek_nufus_" + str(last): sayi,
        "yetiskin_payi": yuzde,
        "kapsam": yuzde,
        "degisim": yuzde,
        "head": head,
    }
    widths = {"il": 14, "ilce": 18, "belediye": 22, "mahalle": 26, "kimlik": 18}

    sheet(book, mahalleler, "Mahalleler", widths, counts)
    sheet(book, ilceler, "İlçeler", widths, counts)
    sheet(book, iller, "İller", widths, counts)
    sheet(
        book,
        seri,
        "Yıllar",
        widths,
        {**{str(y): sayi for y in years}, "head": head},
    )

    notes = book.add_worksheet("Notlar")
    notes.set_column(0, 0, 110, book.add_format({"text_wrap": True, "valign": "top"}))
    lines = [
        "VeriAtlas — mahalle nüfusu",
        "",
        "Kaynak: TÜİK MEDAS, adrese dayalı nüfus kayıt sistemi. Çekim 2026-08.",
        f"Kapsam: {first}-{last}, {len(mahalleler)} mahalle, 81 il.",
        "",
        "NE VAR",
        "· Her mahalle için toplam, 0-17 ve 18+ nüfus. Kaynak zaten yalnız bu iki yaş",
        "  grubunu veriyor; daha ince yaş kırılımı mahalle düzeyinde yayımlanmıyor.",
        "· 'Yıllar' sayfasında her mahallenin yıl yıl toplam nüfusu.",
        "· İlçe ve il sayfaları bu satırların tam toplamıdır: bir mahalle tek bir ilçeye",
        "  bağlıdır ve bir kez sayılır.",
        "",
        "NE YOK — DİKKAT",
        "· Bunlar BELEDİYE MAHALLELERİDİR. 2012'deki büyükşehir yasasından sonra pek çok",
        "  köy mahalleye dönüştü; dönüşmeyen köyler bu dosyada yoktur. Dolayısıyla bir ilin",
        "  buradaki toplamı, ilin nüfusundan küçüktür — eksik olan kırsal nüfustur.",
        "· Köyler için TÜİK 18+ ayrımını hiç yayımlamıyor; oradan yalnız toplam nüfus",
        "  alınabilir.",
        "· İlçe ve il sayfalarındaki 'kapsam' sütunu bunu sayıyla gösterir: mahallelerin",
        "  toplamı, yayımlanan gerçek nüfusun yüzde kaçı. Türkiye genelinde %95; Şanlıurfa",
        "  ve Van'da %100 (her köy mahalle olmuş), Ardahan'da %47 (yarısı köyde yaşıyor).",
        f"· {len(seri) - len(mahalleler)} mahalle bu dosyada hiç görünmüyor: {last} yılında verisi olan mahalle sayısı",
        f"  {len(mahalleler)}, oysa {first}-{last} arasında toplam {len(seri)} ayrı mahalle görüldü. Aradaki fark",
        "  birleşen, kapanan ya da kimliği değişenlerdir; 'Yıllar' sayfasında hepsi var.",
        "· Kent/kır ayrımı bu dosyada yok. Ayrı bir çalışmada, seçim verisindeki (7H)",
        "  kent-kır etiketiyle birleştirilecek.",
        "· Semt bilgisi kaynakta yok. Belediye sütunu en yakın karşılıktır.",
        "",
        "İSİMLER",
        "· Kimlik MEDAS kodudur, ad değildir. Aynı il içinde yüzlerce mahalle aynı adı",
        "  taşıyor ('Merkez', 'Yeni'), ve adlar yıldan yıla değişiyor. Bu dosyadaki ad,",
        "  görülen EN YENİ addır.",
        "· 2013-2025 arasında 846 ad değişikliği görüldü; hepsi docs/mahalle-adlari.md",
        "  dosyasında eski adıyla birlikte kayıtlı.",
        "· 'İlk görülen' / 'son görülen' sütunları, mahallenin verisinin hangi yıllarda",
        "  bulunduğunu söyler. İdari kuruluş/kapanış tarihi değildir: 2013'ten önce",
        "  kurulmuş olabilir, elimizdeki seri 2013'te başlıyor.",
        "",
        "YÜZDELER",
        "· 'Yetişkin payı' = 18+ / toplam.",
        "· 'Değişim' = son yılın toplamı / ilk yılın toplamı − 1. Mahalle o aralıkta",
        "  bölündüyse ya da birleştiyse bu oran o değişimi de içerir.",
    ]
    for row, line in enumerate(lines):
        notes.write(row, 0, line)

    book.close()
    print("yazildi:", TARGET)
    print(
        "  Mahalleler:",
        len(mahalleler),
        "| İlçeler:",
        len(ilceler),
        "| İller:",
        len(iller),
        "| Yıllar:",
        len(seri),
    )


if __name__ == "__main__":
    main()
