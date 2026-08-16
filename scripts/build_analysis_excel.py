"""Where a province's population change came from, and who is in it.

Two questions, one file, because they are asked together and answered from the same
table.

**Where the change came from.** A province's resident population moves for exactly four
reasons and we hold all four:

    Δresidents = natural increase + net internal migration + net foreign + naturalisation

The fourth is not fetched, it is the remainder — and it checks out: summed over 81
provinces it equals the registry gain beyond births and deaths to the person. The
registry does not move with internal migration, so nothing else can explain it.

Net foreign is measured as the change in the stock of foreign nationals. `migration_from_
abroad` would be the direct measure and starts in 2016, too late for a 2009 base.

The base year is 2009 because that is when the last of the four series starts (births).
Not a preference — the earliest year all four can be asked about.

**Contribution shares come in two flavours and the sheet carries both.** The obvious one,
component ÷ net change, is only readable when every component points the same way — 21
provinces. Elsewhere it passes 100% (Hatay: natural 229%, migration −156%) and where the
net change is negative it stops meaning anything (Sivas: −3.092%). So each component is
also divided by the sum of the absolute components, which keeps its sign, stays inside
±100 and can be read in all 81. The first is truer where it works; the second always
works. Sorting a column that silently switches meaning halfway down is worse than having
two columns.

**Who is in it** — two age bands, both chosen rather than inherited:

* **women 15-49**, the fertile ages: falling from 54,0% to 51,0% of all women while the
  population grows. Part of the drop in births is composition, not fertility.
* **men 25-54**: thirty years, and the two noisy edges left out. 20-24 grew 0,0% in
  sixteen years (education, conscription) and 60-64 grew 93,1% (retirement widening).
  Where the boundary is put decides what is being measured, so 20-59 and 15-64 are
  carried alongside as references.

The band is a demographic choice, not a behavioural one: we hold no labour force
participation data. That would turn the boundary from an argument into a measurement.

**Districts get shares and no growth rates.** Age by sex is there, 2007-2025, 917
districts. But law 6360 split the central districts in 2013 and we have no successor
mapping, so Pamukkale reads +6.311% and Zonguldak −51% — administrative, not
demographic. A share is computed inside one district-year and survives that; a change
between two years does not. The district sheet therefore has no change column, and the
Notlar sheet says why.

Run:  uv run python scripts/build_analysis_excel.py
"""

from __future__ import annotations

import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

TARGET = PUBLIC.parent / "cikti" / "nufus-analizi.xlsx"

#: The first year all four components of the identity exist. Births start here.
BASE = 2009

#: Districts below this are dropped from the ranking sheets, not from the data: a prison
#: or a garrison moves a small district's age profile more than its demography does.
#: Çukurca, 14 thousand people on the border, reads 45,1% prime-age men.
RANK_FLOOR = 50_000

BANDS = {
    "k1549": ("female", 15, 49),
    "e2554": ("male", 25, 54),
    "e2059": ("male", 20, 59),
    "e1564": ("male", 15, 64),
}

#: District population is published in five-year groups, so a band is a set of them. The
#: two headline bands fall on group boundaries; that is why they can be asked here at all.
GROUPS = {
    "k1549": (
        "female",
        ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49"],
    ),
    "e2554": ("male", ["25-29", "30-34", "35-39", "40-44", "45-49", "50-54"]),
    "e2059": (
        "male",
        ["20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59"],
    ),
}


def facts() -> pl.DataFrame:
    return pl.read_parquet(PUBLIC / "fact.parquet").with_columns(
        pl.col("period_start").dt.year().alias("year")
    )


def totals(fact: pl.DataFrame, indicator: str, level: str) -> pl.DataFrame:
    """One number per area-year: every breakdown summed away."""
    return (
        fact.filter(
            (pl.col("indicator_id") == indicator) & (pl.col("area_level") == level)
        )
        .group_by("area_id", "year")
        .agg(pl.col("value").sum().alias(indicator))
    )


def stock_change(frame: pl.DataFrame, column: str, last: int) -> pl.DataFrame:
    """Last year minus base year — for a stock, which is a level at a point in time."""
    return (
        frame.filter(pl.col("year") == last)
        .select("area_id", pl.col(column).alias(column + "_son"))
        .join(
            frame.filter(pl.col("year") == BASE).select(
                "area_id", pl.col(column).alias(column + "_ilk")
            ),
            on="area_id",
            how="left",
        )
        .with_columns(
            (pl.col(column + "_son") - pl.col(column + "_ilk")).alias(column + "_fark")
        )
    )


def flow_sum(frame: pl.DataFrame, column: str, last: int) -> pl.DataFrame:
    """Years after the base summed — for a flow, which happens during a year.

    Base year excluded on purpose: its flow produced the base stock, and counting it
    would explain a change that had already happened.
    """
    return (
        frame.filter(pl.col("year").is_between(BASE + 1, last))
        .group_by("area_id")
        .agg(pl.col(column).sum().alias(column))
    )


def province_names() -> pl.DataFrame:
    data = PUBLIC.parent / "src" / "veriatlas" / "data"
    return pl.read_csv(data / "areas_tr.csv").select(
        "area_id", pl.col("name_tr").alias("il")
    )


def district_names() -> pl.DataFrame:
    data = PUBLIC.parent / "src" / "veriatlas" / "data"
    provinces = province_names()
    return (
        pl.read_csv(data / "areas_tr_districts.csv")
        .select("area_id", pl.col("name_tr").alias("ilce"), "parent_id")
        .join(provinces, left_on="parent_id", right_on="area_id", how="left")
        .select("area_id", "il", "ilce")
    )


def decomposition(fact: pl.DataFrame, last: int) -> pl.DataFrame:
    """The identity, per province, with both flavours of contribution share."""
    residents = stock_change(totals(fact, "population", "province"), "population", last)
    registry = stock_change(
        totals(fact, "registry_population", "province"), "registry_population", last
    )
    foreign = stock_change(
        totals(fact, "foreign_population", "province"), "foreign_population", last
    )
    natural = flow_sum(
        totals(fact, "natural_increase", "province"), "natural_increase", last
    )
    internal = flow_sum(
        totals(fact, "migration_net", "province"), "migration_net", last
    )

    frame = (
        residents.join(registry, on="area_id")
        .join(foreign, on="area_id")
        .join(natural, on="area_id")
        .join(internal, on="area_id")
        .rename(
            {
                "population_ilk": "nufus_ilk",
                "population_son": "nufus_son",
                "population_fark": "degisim",
                "natural_increase": "dogal",
                "migration_net": "ic_goc",
                "foreign_population_fark": "dis_goc",
                "registry_population_fark": "kutuk_fark",
            }
        )
        .with_columns(
            (
                pl.col("degisim")
                - pl.col("dogal")
                - pl.col("ic_goc")
                - pl.col("dis_goc")
            ).alias("vatandaslik")
        )
        .with_columns(
            (pl.col("degisim") / pl.col("nufus_ilk")).alias("degisim_oran"),
            (pl.col("dis_goc") + pl.col("vatandaslik")).alias("disardan"),
            (pl.col("kutuk_fark") - pl.col("degisim")).alias("kutuk_makas"),
        )
    )

    parts = ["dogal", "ic_goc", "dis_goc", "vatandaslik"]
    gross = pl.sum_horizontal([pl.col(p).abs() for p in parts])
    frame = frame.with_columns(
        [(pl.col(p) / pl.col("degisim")).alias(p + "_pay") for p in parts]
        + [(pl.col(p) / gross).alias(p + "_bpay") for p in parts]
        + [(pl.col("disardan") / pl.col("degisim")).alias("disardan_pay")]
    )

    # Flagging where the plain share is safe to read, so a reader sorting that column
    # knows which rows are the ones that mean what they look like.
    same_sign = (pl.min_horizontal([pl.col(p) for p in parts]) >= 0) | (
        pl.max_horizontal([pl.col(p) for p in parts]) <= 0
    )
    frame = frame.with_columns(
        pl.when(pl.col("degisim") <= 0)
        .then(pl.lit("nüfus azaldı — pay okunamaz"))
        .when(same_sign)
        .then(pl.lit("okunur"))
        .otherwise(pl.lit("bileşenler ters yönde — pay 100'ü aşar"))
        .alias("pay_notu")
    )
    return frame.join(province_names(), on="area_id", how="left")


def single_age_bands(fact: pl.DataFrame, last: int) -> pl.DataFrame:
    """Province bands from single years of age — the boundary lands exactly."""
    rows = (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == "province")
            & pl.col("year").is_in([BASE, last])
        )
        .with_columns(
            pl.col("dims").str.extract(r"age=([^;]*)").alias("age"),
            pl.col("dims").str.extract(r"sex=([^;]*)").alias("sex"),
        )
        .with_columns(pl.col("age").str.replace(r"\+", "").cast(pl.Int32).alias("yas"))
    )

    frames = [
        rows.group_by("area_id", "year").agg(pl.col("value").sum().alias("toplam")),
        rows.filter(pl.col("sex") == "female")
        .group_by("area_id", "year")
        .agg(pl.col("value").sum().alias("kadin")),
    ]
    for name, (sex, low, high) in BANDS.items():
        frames.append(
            rows.filter((pl.col("sex") == sex) & pl.col("yas").is_between(low, high))
            .group_by("area_id", "year")
            .agg(pl.col("value").sum().alias(name))
        )

    frame = frames[0]
    for other in frames[1:]:
        frame = frame.join(other, on=["area_id", "year"], how="left")
    return frame


def group_age_bands(fact: pl.DataFrame, last: int) -> pl.DataFrame:
    """District bands from five-year groups."""
    rows = fact.filter(
        (pl.col("indicator_id") == "population")
        & (pl.col("area_level") == "district")
        & pl.col("year").is_in([BASE, last])
    ).with_columns(
        pl.col("dims").str.extract(r"age=([^;]*)").alias("age"),
        pl.col("dims").str.extract(r"sex=([^;]*)").alias("sex"),
    )
    frames = [
        rows.group_by("area_id", "year").agg(pl.col("value").sum().alias("toplam")),
        rows.filter(pl.col("sex") == "female")
        .group_by("area_id", "year")
        .agg(pl.col("value").sum().alias("kadin")),
    ]
    for name, (sex, ages) in GROUPS.items():
        frames.append(
            rows.filter((pl.col("sex") == sex) & pl.col("age").is_in(ages))
            .group_by("area_id", "year")
            .agg(pl.col("value").sum().alias(name))
        )
    frame = frames[0]
    for other in frames[1:]:
        frame = frame.join(other, on=["area_id", "year"], how="left")
    return frame


def wide_bands(frame: pl.DataFrame, last: int, names: list[str]) -> pl.DataFrame:
    """Base year and last year side by side, with shares."""

    def at(year: int, tag: str) -> pl.DataFrame:
        picked = frame.filter(pl.col("year") == year)
        columns = [pl.col(c).alias(c + tag) for c in ["toplam", "kadin"] + names]
        return picked.select(["area_id"] + columns)

    joined = at(last, "_son").join(at(BASE, "_ilk"), on="area_id", how="inner")
    shares = []
    for name in names:
        shares += [
            (pl.col(name + "_son") / pl.col("toplam_son")).alias(name + "_pay_son"),
            (pl.col(name + "_ilk") / pl.col("toplam_ilk")).alias(name + "_pay_ilk"),
        ]
    shares += [
        (pl.col("k1549_son") / pl.col("kadin_son")).alias("k1549_kadinda_son"),
        (pl.col("k1549_ilk") / pl.col("kadin_ilk")).alias("k1549_kadinda_ilk"),
    ]
    return joined.with_columns(shares)


HEADERS = {
    "il": "İl",
    "ilce": "İlçe",
    "kimlik": "Kimlik",
    "nufus_ilk": f"Nüfus {BASE}",
    "degisim": "Nüfus değişimi",
    "degisim_oran": "Nüfus değişimi %",
    "dogal": "Doğal artış",
    "ic_goc": "Net iç göç",
    "dis_goc": "Net dış göç (yabancı)",
    "vatandaslik": "Vatandaşlığa geçiş",
    "disardan": "Yurt dışı kaynaklı",
    "dogal_pay": "Doğal — payı",
    "ic_goc_pay": "İç göç — payı",
    "dis_goc_pay": "Dış göç — payı",
    "vatandaslik_pay": "Vatandaşlık — payı",
    "disardan_pay": "Yurt dışı kaynaklı — payı",
    "dogal_bpay": "Doğal — hareket payı",
    "ic_goc_bpay": "İç göç — hareket payı",
    "dis_goc_bpay": "Dış göç — hareket payı",
    "vatandaslik_bpay": "Vatandaşlık — hareket payı",
    "pay_notu": "Pay okunur mu",
    "kutuk_makas": "Kütük − ikamet makası",
    "kutuk_fark": "Kütük değişimi",
    "olcut": "Ölçüt",
    "sira": "Sıra",
    "yer": "Yer",
    "deger": "Değer",
}


def band_header(column: str, last: int) -> str:
    labels = {
        "k1549": "Kadın 15-49",
        "e2554": "Erkek 25-54",
        "e2059": "Erkek 20-59",
        "e1564": "Erkek 15-64",
        "toplam": "Toplam nüfus",
        "kadin": "Kadın nüfus",
    }
    for key, label in labels.items():
        if not column.startswith(key):
            continue
        tail = column[len(key) :]
        year = last if tail.endswith("_son") else BASE
        if tail in ("_son", "_ilk"):
            return f"{label} {year}"
        if tail.startswith("_pay"):
            return f"{label} payı {year}"
        if tail.startswith("_kadinda"):
            return f"{label} — kadınlarda {year}"
    return column


def header_of(column: str, last: int) -> str:
    if column in HEADERS:
        return HEADERS[column]
    band = band_header(column, last)
    if band != column:
        return band
    return column[:1].upper() + column[1:].replace("_", " ")


def sheet(book, frame, title, formats, last, widths=None) -> None:
    page = book.add_worksheet(title)
    page.freeze_panes(1, 0)
    page.set_row(0, 38)
    widths = widths or {}
    for index, column in enumerate(frame.columns):
        page.write(0, index, header_of(column, last), formats["head"])
        page.set_column(
            index, index, widths.get(column, 15), formats.get(column, formats["text"])
        )
    page.autofilter(0, 0, len(frame), len(frame.columns) - 1)
    for index, column in enumerate(frame.columns):
        style = formats.get(column, formats["text"])
        for row, value in enumerate(frame[column].to_list(), start=1):
            if value is not None:
                page.write(row, index, value, style)


def main() -> None:
    fact = facts()
    last = int(
        fact.filter(pl.col("indicator_id") == "population").select("year").max().item()
    )

    parts = decomposition(fact, last)
    bilesenler = parts.select(
        "il",
        "nufus_ilk",
        "degisim",
        "degisim_oran",
        "dogal",
        "ic_goc",
        "dis_goc",
        "vatandaslik",
        "disardan",
        "disardan_pay",
        "pay_notu",
        "dogal_pay",
        "ic_goc_pay",
        "dis_goc_pay",
        "vatandaslik_pay",
        "dogal_bpay",
        "ic_goc_bpay",
        "dis_goc_bpay",
        "vatandaslik_bpay",
        "kutuk_fark",
        "kutuk_makas",
        pl.col("area_id").alias("kimlik"),
    ).sort("degisim", descending=True)

    names = list(BANDS)
    il_bands = (
        wide_bands(single_age_bands(fact, last), last, names)
        .join(province_names(), on="area_id", how="left")
        .select(
            ["il"]
            + [c for n in names for c in (n + "_son", n + "_pay_son", n + "_pay_ilk")]
            + ["k1549_kadinda_son", "k1549_kadinda_ilk"]
            + [pl.col("area_id").alias("kimlik")]
        )
        .sort("e2554_son", descending=True)
    )

    district_names_frame = district_names()
    ilce_bands = (
        wide_bands(group_age_bands(fact, last), last, list(GROUPS))
        .join(district_names_frame, on="area_id", how="left")
        .select(
            ["il", "ilce", "toplam_son"]
            + [c for n in GROUPS for c in (n + "_son", n + "_pay_son", n + "_pay_ilk")]
            + ["k1549_kadinda_son"]
            + [pl.col("area_id").alias("kimlik")]
        )
        .sort("toplam_son", descending=True)
    )

    # region Summary

    def top(frame, column, label, place, rising=True, take=10):
        ordered = frame.drop_nulls(column).sort(column, descending=rising).head(take)
        return pl.DataFrame(
            {
                "olcut": [label] * len(ordered),
                "sira": list(range(1, len(ordered) + 1)),
                "yer": ordered[place].to_list(),
                "deger": ordered[column].to_list(),
            }
        )

    big = ilce_bands.filter(pl.col("toplam_son") >= RANK_FLOOR)
    ozet = pl.concat(
        [
            top(bilesenler, "degisim", "Nüfusu en çok artan il", "il"),
            top(bilesenler, "degisim", "Nüfusu en çok azalan il", "il", False),
            top(bilesenler, "degisim_oran", "Oransal en çok büyüyen il", "il"),
            top(bilesenler, "disardan", "Yurt dışı kaynaklı artışı en büyük il", "il"),
            top(
                bilesenler, "disardan_pay", "Artışı en çok yurt dışından gelen il", "il"
            ),
            top(bilesenler, "ic_goc", "En çok iç göç alan il", "il"),
            top(bilesenler, "ic_goc", "En çok iç göç veren il", "il", False),
            top(bilesenler, "kutuk_makas", "Kütük–ikamet makası en geniş il", "il"),
            top(il_bands, "e2554_pay_son", "Erkek 25-54 payı en yüksek il", "il"),
            top(il_bands, "e2554_pay_son", "Erkek 25-54 payı en düşük il", "il", False),
            top(il_bands, "k1549_kadinda_son", "Doğurgan çağ payı en yüksek il", "il"),
            top(
                il_bands,
                "k1549_kadinda_son",
                "Doğurgan çağ payı en düşük il",
                "il",
                False,
            ),
            top(big, "e2554_pay_son", "Erkek 25-54 payı en yüksek ilçe", "ilce"),
            top(big, "e2554_pay_son", "Erkek 25-54 payı en düşük ilçe", "ilce", False),
            top(big, "k1549_kadinda_son", "Doğurgan çağ payı en yüksek ilçe", "ilce"),
            top(
                big,
                "k1549_kadinda_son",
                "Doğurgan çağ payı en düşük ilçe",
                "ilce",
                False,
            ),
        ]
    )

    # endregion

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
    yuzde = book.add_format(
        {"num_format": "0,0%", "align": "center", "valign": "vcenter"}
    )

    numeric = {"sira": middle, "deger": sayi}
    for column in bilesenler.columns + il_bands.columns + ilce_bands.columns:
        if column.endswith(("_pay", "_bpay", "_pay_son", "_pay_ilk", "_oran")):
            numeric[column] = yuzde
        elif column.endswith(("_son", "_ilk", "_fark", "_makas")) or column in (
            "degisim",
            "dogal",
            "ic_goc",
            "dis_goc",
            "vatandaslik",
            "disardan",
        ):
            numeric[column] = sayi
    for column in ("k1549_kadinda_son", "k1549_kadinda_ilk"):
        numeric[column] = yuzde

    formats = {
        **numeric,
        "head": head,
        "text": middle,
        "il": text,
        "ilce": text,
        "olcut": text,
        "yer": text,
        "pay_notu": text,
        "kimlik": middle,
    }
    widths = {
        "il": 15,
        "ilce": 20,
        "olcut": 40,
        "yer": 18,
        "pay_notu": 34,
        "kimlik": 12,
    }

    sheet(book, ozet, "Özet", formats, last, widths)
    sheet(book, bilesenler, "Bileşenler", formats, last, widths)
    sheet(book, il_bands, "Yaş bantları — il", formats, last, widths)
    sheet(book, ilce_bands, "Yaş bantları — ilçe", formats, last, widths)

    notes = book.add_worksheet("Notlar")
    notes.set_column(0, 0, 112, book.add_format({"text_wrap": True, "valign": "top"}))
    lines = [
        f"VeriAtlas — nüfus değişiminin bileşenleri ve yaş bantları, {BASE}-{last}",
        "",
        "Kaynak: TÜİK MEDAS. Çekim: 2026-08. Yöntem notu: docs/analiz-2026-08-16.md",
        "",
        "ÖZDEŞLİK",
        "· Nüfus değişimi = doğal artış + net iç göç + net dış göç + vatandaşlığa geçiş.",
        "· Doğal artış ve iç göç akıştır: taban yıldan sonraki yıllar toplanır.",
        "  İkamet, kütük ve yabancı nüfus stoktur: iki yılın farkı alınır.",
        f"· Taban {BASE}, çünkü dört seriden en geç başlayanı (doğum) o yıl başlıyor.",
        "· Vatandaşlığa geçiş ölçülmedi, artıktır. Doğruluğunun kanıtı: 81 ilde toplamı,",
        "  kütük artışının doğal artışı aşan kısmına birebir eşit (363.649 kişi).",
        "· Net dış göç, yabancı uyruklu nüfus stokundaki değişimdir. Doğrudan ölçü olan",
        "  'yurt dışından gelen göç' 2016'da başlıyor, taban yıla yetişmiyor.",
        "· 81 ilin net iç göçü toplamda tam sıfırdır; iç göç kapalı bir sistemdir.",
        "",
        "İKİ AYRI PAY SÜTUNU — HANGİSİ NE ZAMAN",
        "· '— payı': bileşen / net değişim. Sezgisel olan bu, ama yalnız bütün bileşenler",
        "  aynı yöndeyken okunur (21 il). Ters yöndeyse pay 100'ü aşar: Hatay'da doğal",
        "  artış %229, iç göç −%156 — yanlış değil, o il doğumla kazandığının bir kısmını",
        "  göçle geri vermiş demek. Nüfusu azalan 11 ilde ise ölçü tamamen anlamsızdır.",
        "· '— hareket payı': bileşen / bileşenlerin mutlak değerleri toplamı. İşareti",
        "  korur, ±100 arasında kalır, 81 ilin hepsinde okunur. Sıralama için bunu kullan.",
        "· 'Pay okunur mu' sütunu her il için hangisinin geçerli olduğunu yazar.",
        "",
        "YAŞ BANTLARI",
        "· Erkek 25-54: tam otuz yıl. Alt ve üst uçlar bilerek dışarıda — 20-24 on altı",
        "  yılda %0,0 büyüdü (okul, askerlik), 60-64 ise %93 (emekliliğin genişlemesi).",
        "  Bant seçimi ölçülen şeyi değiştirir; 20-59 ve 15-64 referans olarak yanındadır.",
        "· Bu bir demografi tercihidir, davranış ölçüsü değil: işgücüne katılım verimiz",
        "  yok. Katılım oranı çekilirse sınır tahmin edilmek yerine ölçülebilir.",
        "· Kadın 15-49 doğurgan çağdır. İki payla verilir: toplam nüfusta ve kadınlar",
        f"  içinde. Türkiye'de kadınların %54,0'ından %51,0'ına düştü ({BASE}-{last});",
        "  sayı artarken pay düşüyor, yani doğum sayısındaki azalmanın bir kısmı",
        "  doğurganlık değil, nüfusun yaş bileşimi.",
        "· İl bantları tek yaş verisinden hesaplandı: sınır tam yerine oturuyor. İlçede",
        "  veri beşer yaş grubudur; 15-49 ve 25-54 grup sınırlarına denk geldiği için",
        "  ilçede de sorulabiliyor, başka bir bant sorulamaz.",
        "",
        "İLÇEDE NEDEN DEĞİŞİM SÜTUNU YOK",
        "· 6360 sayılı yasa 2013'te merkez ilçeleri böldü ve elimizde ardıl eşlemesi yok.",
        "  Ham hesap Pamukkale'yi %+6.311, Zonguldak'ı %−51 gösteriyor: bunlar demografi",
        "  değil, idari bölünme. O yüzden ilçe sayfasında yalnız oran vardır.",
        "· Oran her yıl kendi içinde hesaplandığı için bu bozulmadan etkilenmez.",
        f"· Özet sayfasındaki ilçe sıralamaları {RANK_FLOOR:,} nüfus eşiğinin üstündedir.".replace(
            ",", "."
        ),
        "  Küçük ilçede kurumsal nüfus profili tek başına bozuyor: Çukurca'da (14 bin,",
        "  sınır garnizonu) erkek 20-59 payı %45,1 çıkıyor.",
        "",
        "SINIRLAR",
        "· Vatandaşlık sütunu artık olduğu için TÜİK revizyonlarını da içerir. İzmir'in",
        "  eksi değeri muhtemelen budur.",
        "· Net göç yılı, o yıl içinde gerçekleşen hareketi gösterir; iki yıl arasındaki",
        "  dönemdir, yıl sonu stoğu değildir.",
    ]
    for row, line in enumerate(lines):
        notes.write(row, 0, line)

    book.close()
    # endregion

    print("yazildi:", TARGET)
    print(
        "  Bileşenler:",
        len(bilesenler),
        "| İl bantları:",
        len(il_bands),
        "| İlçe bantları:",
        len(ilce_bands),
        "| Özet:",
        len(ozet),
    )


if __name__ == "__main__":
    main()
