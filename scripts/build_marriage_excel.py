"""Marriage and divorce with the denominator that belongs to them.

The published rate for both is *crude*: the year's marriages over the whole population,
divorces over the whole population. That answers a question nobody asks. Nobody in a
province is at risk of marrying except the people who are not already married, and nobody
is at risk of divorcing except the people who are. A province full of children and a
province full of pensioners will differ on the crude rate without differing at all on
what the rate is supposed to measure.

So the rates here take the population **at risk**:

* **Rafine evlenme hızı** — marriages ÷ never-married women aged 15 and over
* **Rafine boşanma hızı** — divorces ÷ married women aged 15 and over

Women rather than "people" or "couples", and that is not a preference: TÜİK records one
bride per marriage and one wife per divorce, so a count of women is a count of events'
worth of people, with no doubling and no halving to argue about.

**Two mismatches are real and stated rather than smoothed over.** Marriages and divorces
are counted where the *event happened* — the register office, the court — and the
population is counted where people *live*. In a province whose district courthouse serves
its neighbours, or whose coast marries people from elsewhere, the two do not describe the
same set of people. And the divorce of a given year belongs to marriages made in years
whose numbers are not in that year's denominator.

Levels: **province and country only**. TÜİK publishes marital status no finer than
province, so the denominators do not exist below it — the crude rate could be computed
per district and the refined one could not, and a sheet mixing the two would be a sheet
where the same column means two things.

Run:  uv run python scripts/build_marriage_excel.py
"""

from __future__ import annotations

import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.areas import load_areas
from veriatlas.config import OUTPUT, PUBLIC

TARGET = OUTPUT / "evlenme" / "evlenme-bosanma-rafine.xlsx"


def facts() -> pl.DataFrame:
    return pl.read_parquet(PUBLIC / "fact.parquet").with_columns(
        pl.col("period_start").dt.year().alias("yil"),
        pl.col("dims").str.extract(r"age=([^;]+)").alias("yas"),
        pl.col("dims").str.extract(r"sex=([^;]+)").alias("cinsiyet"),
        pl.col("dims").str.extract(r"marital=([^;]+)").alias("medeni"),
    )


def risk_altindaki(fact: pl.DataFrame, durum: str) -> pl.DataFrame:
    """Women aged 15+ in a given marital status, per area-year — the denominators.

    The marital table starts at 15, so no age filter is needed and none is applied: an
    `age >= 15` written here would look like a safeguard and would silently become a lie
    the day TÜİK publishes a younger band.
    """
    return (
        fact.filter(
            (pl.col("indicator_id") == "marital_status")
            & (pl.col("medeni") == durum)
            & (pl.col("cinsiyet") == "female")
        )
        .group_by("area_id", "area_level", "yil")
        .agg(pl.col("value").sum().alias("payda"))
    )


def sayim(fact: pl.DataFrame, indicator_id: str, ad: str) -> pl.DataFrame:
    return (
        fact.filter(pl.col("indicator_id") == indicator_id)
        .group_by("area_id", "area_level", "yil")
        .agg(pl.col("value").sum().alias(ad))
    )


def nufus(fact: pl.DataFrame) -> pl.DataFrame:
    """Total population, for the crude rates the refined ones are compared against."""
    return (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("yas").str.contains(r"^\d+$") | (pl.col("yas") == "75+"))
        )
        .group_by("area_id", "area_level", "yil")
        .agg(pl.col("value").sum().alias("nufus"))
    )


def rates(fact: pl.DataFrame) -> pl.DataFrame:
    keys = ["area_id", "area_level", "yil"]
    frame = (
        sayim(fact, "marriages", "evlenme")
        .join(sayim(fact, "divorces", "bosanma"), on=keys, how="full", coalesce=True)
        .join(
            risk_altindaki(fact, "never_married").rename({"payda": "bekar_kadin"}),
            on=keys,
            how="left",
        )
        .join(
            risk_altindaki(fact, "married").rename({"payda": "evli_kadin"}),
            on=keys,
            how="left",
        )
        .join(nufus(fact), on=keys, how="left")
    )
    return frame.with_columns(
        (pl.col("evlenme") / pl.col("bekar_kadin") * 1000).alias("rafine_evlenme"),
        (pl.col("bosanma") / pl.col("evli_kadin") * 1000).alias("rafine_bosanma"),
        (pl.col("evlenme") / pl.col("nufus") * 1000).alias("kaba_evlenme"),
        (pl.col("bosanma") / pl.col("nufus") * 1000).alias("kaba_bosanma"),
        # Not "what share of marriages end": this year's divorces belong to marriages made
        # in other years. It is a ratio of two flows in one year and nothing more, which is
        # why it is named for what it is.
        (pl.col("bosanma") / pl.col("evlenme") * 100).alias("yuz_evlenmeye_bosanma"),
    )


def genis(
    frame: pl.DataFrame, sutun: str, adlar: pl.DataFrame, basamak: int
) -> pl.DataFrame:
    """A province per row, a year per column, then the two changes.

    Both changes, because they answer different questions: the difference is in the rate's
    own unit and says how many events per thousand were gained or lost; the percent says
    how far the province moved from where it started. A province going 40‰ → 30‰ and one
    going 8‰ → 6‰ have the same percent and a five-fold difference in weddings.
    """
    dolu = frame.filter(pl.col(sutun).is_not_null())
    yillar = sorted(dolu["yil"].unique().to_list())
    ilk, son = yillar[0], yillar[-1]
    tablo = (
        dolu.pivot(values=sutun, index="area_id", on="yil")
        .join(adlar, on="area_id", how="left")
        .with_columns(
            (pl.col(str(son)) - pl.col(str(ilk))).round(basamak).alias("fark"),
            pl.when(pl.col(str(ilk)) != 0)
            .then(pl.col(str(son)) / pl.col(str(ilk)) - 1)
            .alias("degisim"),
        )
        .with_columns([pl.col(str(y)).round(basamak) for y in yillar])
    )
    return tablo.select(["il", *[str(y) for y in yillar], "fark", "degisim"]).sort(
        str(son), descending=True
    )


def main() -> None:
    fact = facts()
    adlar = load_areas().select("area_id", pl.col("name_tr").alias("il"))
    hepsi = rates(fact)
    iller = hepsi.filter(pl.col("area_level") == "province")
    turkiye = hepsi.filter(pl.col("area_level") == "country").sort("yil")

    sayfalar = {
        "Rafine evlenme": genis(iller, "rafine_evlenme", adlar, 2),
        "Rafine boşanma": genis(iller, "rafine_bosanma", adlar, 2),
        "Kaba evlenme": genis(iller, "kaba_evlenme", adlar, 2),
        "Kaba boşanma": genis(iller, "kaba_bosanma", adlar, 2),
        "100 evlenmeye boşanma": genis(iller, "yuz_evlenmeye_bosanma", adlar, 1),
    }

    son_yil = int(iller.filter(pl.col("rafine_evlenme").is_not_null())["yil"].max())
    son = (
        iller.filter(pl.col("yil") == son_yil)
        .join(adlar, on="area_id", how="left")
        .select(
            "il",
            pl.col("kaba_evlenme").round(2),
            pl.col("rafine_evlenme").round(2),
            pl.col("kaba_bosanma").round(2),
            pl.col("rafine_bosanma").round(2),
            pl.col("yuz_evlenmeye_bosanma").round(1),
        )
    )
    # The point of the whole file, in one sheet: the two rankings side by side. A province
    # that moves twenty places between them is a province whose crude rate was mostly a
    # statement about how many of its people were already married.
    son = (
        son.with_columns(
            pl.col("kaba_evlenme")
            .rank(descending=True)
            .cast(pl.Int32)
            .alias("kaba_ev_sira"),
            pl.col("rafine_evlenme")
            .rank(descending=True)
            .cast(pl.Int32)
            .alias("rafine_ev_sira"),
            pl.col("kaba_bosanma")
            .rank(descending=True)
            .cast(pl.Int32)
            .alias("kaba_bo_sira"),
            pl.col("rafine_bosanma")
            .rank(descending=True)
            .cast(pl.Int32)
            .alias("rafine_bo_sira"),
        )
        .with_columns(
            (pl.col("kaba_ev_sira") - pl.col("rafine_ev_sira")).alias(
                "evlenme_sira_farki"
            ),
            (pl.col("kaba_bo_sira") - pl.col("rafine_bo_sira")).alias(
                "bosanma_sira_farki"
            ),
        )
        .sort("rafine_evlenme", descending=True)
    )

    tr = turkiye.select(
        "yil",
        pl.col("evlenme").cast(pl.Int64),
        pl.col("bosanma").cast(pl.Int64),
        pl.col("bekar_kadin").cast(pl.Int64),
        pl.col("evli_kadin").cast(pl.Int64),
        pl.col("kaba_evlenme").round(2),
        pl.col("rafine_evlenme").round(2),
        pl.col("kaba_bosanma").round(2),
        pl.col("rafine_bosanma").round(2),
        pl.col("yuz_evlenmeye_bosanma").round(1),
    )

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
    sol = book.add_format({"align": "left", "valign": "vcenter"})
    orta = book.add_format({"align": "center", "valign": "vcenter"})
    tam = book.add_format(
        {"num_format": "#,##0", "align": "center", "valign": "vcenter"}
    )
    ondalik = book.add_format(
        {"num_format": "0.00", "align": "center", "valign": "vcenter"}
    )
    yuzde = book.add_format(
        {"num_format": "0.0%", "align": "center", "valign": "vcenter"}
    )

    def yaz(frame: pl.DataFrame, baslik: str, bicimler: dict) -> None:
        page = book.add_worksheet(baslik)
        page.freeze_panes(1, 1)
        page.set_row(0, 28)
        for index, column in enumerate(frame.columns):
            stil = bicimler.get(column, orta)
            page.write(0, index, column, head)
            page.set_column(index, index, 18 if index == 0 else 11, stil)
            for row, value in enumerate(frame[column].to_list(), start=1):
                if value is not None:
                    page.write(row, index, value, stil)
        page.autofilter(0, 0, len(frame), len(frame.columns) - 1)

    yaz(
        son,
        "Özet " + str(son_yil),
        {
            "il": sol,
            "yuz_evlenmeye_bosanma": ondalik,
            **{c: ondalik for c in son.columns if "evlenme" in c or "bosanma" in c},
            **{c: orta for c in son.columns if c.endswith(("sira", "farki"))},
        },
    )
    yaz(
        tr,
        "Türkiye",
        {
            "yil": orta,
            "evlenme": tam,
            "bosanma": tam,
            "bekar_kadin": tam,
            "evli_kadin": tam,
            **{
                c: ondalik
                for c in tr.columns
                if "hiz" in c
                or "kaba" in c
                or "rafine" in c
                or c == "yuz_evlenmeye_bosanma"
            },
        },
    )
    for baslik, frame in sayfalar.items():
        yaz(
            frame,
            baslik,
            {
                "il": sol,
                "degisim": yuzde,
                **{c: ondalik for c in frame.columns if c != "il" and c != "degisim"},
            },
        )

    notlar = book.add_worksheet("Notlar")
    notlar.set_column(0, 0, 106, book.add_format({"text_wrap": True, "valign": "top"}))
    satirlar = [
        "VeriAtlas — evlenme ve boşanma, risk altındaki nüfusa göre",
        "",
        "Kaynak: TÜİK MEDAS. Çekim: 2026-08.",
        f"Evlenme ve boşanma sayısı 2001'den, medeni durum 2008'den. Rafine hızlar {son_yil}'e kadar.",
        "",
        "PAYDA NEDEN DEĞİŞTİ",
        "· Kaba hız, olayı bütün nüfusa böler. Ama evlenme riski yalnız hiç evlenmemişlerde,",
        "  boşanma riski yalnız evlilerdedir. Çocuk nüfusu kalabalık bir ilde kaba evlenme",
        "  hızı, o ilde daha az evlenildiği için değil, paydada evlenemeyecek çok kişi",
        "  olduğu için düşük çıkar.",
        "· Rafine evlenme hızı = evlenme ÷ 15+ hiç evlenmemiş KADIN × 1000",
        "· Rafine boşanma hızı = boşanma ÷ 15+ EVLİ KADIN × 1000",
        "· Kadın seçilmesi tercih değil: her evlenmede bir gelin, her boşanmada bir eş",
        "  vardır. Kişi sayarsak ikiye katlar, çift sayarsak ikiye böleriz; kadın sayınca",
        "  olay sayısıyla payda birebir eşleşir.",
        "",
        "İKİ UYUŞMAZLIK, ÖRTÜLMEDİ",
        "· Evlenme ve boşanma OLAYIN YERİNE göre sayılır (nikâhın kıyıldığı, kararın",
        "  verildiği il); nüfus ise İKAMETGAHA göre. Adliyesi çevre illere hizmet eden ya da",
        "  turistik ilçelerinde çok nikâh kıyılan illerde pay ile payda aynı insanları",
        "  anlatmaz. Bu, rafine hızın düzeltemediği bir sapmadır.",
        "· Bir yılın boşanmaları başka yılların evliliklerinden gelir. '100 evlenmeye kaç",
        "  boşanma' sütunu bu yüzden 'evliliklerin yüzde kaçı bitiyor' DEĞİLDİR: evlenmenin",
        "  düştüğü bir yılda hiçbir şey değişmeden yükselir.",
        "",
        "İLÇE NEDEN YOK",
        "· TÜİK medeni durumu il düzeyinden aşağıda yayımlamıyor, yani paydalar ilçede yok.",
        "  İlçe için kaba hız hesaplanabilir, rafine hız hesaplanamaz; ikisini aynı sütunda",
        "  toplamak sütunun iki ayrı şey anlatması olurdu.",
        "",
        "SÜTUNLAR",
        "· 'fark' = son yıl − ilk yıl, binde cinsinden.",
        "· 'degisim' = son yıl / ilk yıl − 1.",
        "· 'sira_farki' = kaba sıradaki yeri − rafine sıradaki yeri. Artı değer, ilin kaba",
        "  hızda olduğundan daha üst sırada göründüğü anlamına gelir; o fark ilin medeni",
        "  durum yapısıdır, evlenme davranışı değil.",
    ]
    for row, satir in enumerate(satirlar):
        notlar.write(row, 0, satir)

    book.close()
    print("yazildi:", TARGET)
    print("  il:", len(son), "· yil:", son_yil, "· sayfa:", len(sayfalar) + 3)


if __name__ == "__main__":
    main()
