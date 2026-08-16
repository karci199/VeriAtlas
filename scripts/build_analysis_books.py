"""One workbook per question, so a sheet can be read without being decoded.

The first version of this put four analyses in one file and the file won. Twenty-two
columns on a sheet is not a table, it is a search problem: to compare two provinces you
scroll sideways past three answers you did not ask for. Here each question gets its own
file and each file's sheet is narrow enough to see at once.

The five questions:

* `analiz-1-bilesenler.xlsx` — where a province's population change came from. The
  identity is Δresidents = natural + internal + foreign + naturalisation, and the fourth
  is the remainder, which checks out against the registry to the person.
* `analiz-2-kohort.xlsx` — a cohort cannot grow. Follow the people who were 20-24 in the
  base year to the year they are 36-40 and the change is migration minus death, with no
  model in between. Nationally internal migration cancels, so the country sheet reads as
  foreign migration against mortality; the province sheet reads as internal migration.
* `analiz-3-evlilik.xlsx` — women and men 30-49 who are not married, then and now.
* `analiz-4-dogurganlik.xlsx` — women of fertile age against births. Births fall for two
  separable reasons and this splits them: how many women there are, and how many children
  each has.
* `analiz-5-yas-bantlari.xlsx` — the fertile band and the prime working band, province and
  district.

Formatting is not decoration here. A colour scale over a ratio column answers "who is
high and who is low" before the reader sorts anything, and the ranking column survives
sorting so a row can be found again after the reader has rearranged the sheet. Where a
number can mislead — a district growth rate that is really an administrative split, a
contribution share whose components point in opposite directions — the sheet carries a
column that says so rather than a note nobody opens.

Run:  uv run python scripts/build_analysis_books.py
"""

from __future__ import annotations

import sys

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

OUT = PUBLIC.parent / "cikti"

#: The first year all four components of the decomposition exist. Births start here.
BASE = 2009

#: Marital status starts a year earlier than everything else and is asked on its own.
MARITAL_BASE = 2008

#: Districts under this are kept in the sheet and dropped from the rankings: a garrison
#: or a prison moves a small district's age profile more than its demography does.
RANK_FLOOR = 50_000

#: Years between the two ends of the cohort walk, filled in from the data.
COHORT_BANDS = [(low, low + 4) for low in range(0, 55, 5)]

FERTILE = ("female", 15, 49)
PRIME = ("male", 25, 54)
WIDE_PRIME = ("male", 20, 59)

#: Five-year groups, for the levels published that way.
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


# region Reading


def facts() -> pl.DataFrame:
    return pl.read_parquet(PUBLIC / "fact.parquet").with_columns(
        pl.col("period_start").dt.year().alias("year")
    )


def names(kind: str) -> pl.DataFrame:
    data = PUBLIC.parent / "src" / "veriatlas" / "data"
    provinces = pl.read_csv(data / "areas_tr.csv").select(
        "area_id", pl.col("name_tr").alias("il")
    )
    if kind == "province":
        return provinces
    return (
        pl.read_csv(data / "areas_tr_districts.csv")
        .select("area_id", pl.col("name_tr").alias("ilce"), "parent_id")
        .join(provinces, left_on="parent_id", right_on="area_id", how="left")
        .select("area_id", "il", "ilce")
    )


def with_dims(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.col("dims").str.extract(r"age=([^;]*)").alias("age"),
        pl.col("dims").str.extract(r"sex=([^;]*)").alias("sex"),
    )


def single_ages(fact: pl.DataFrame, level: str, years: list[int]) -> pl.DataFrame:
    """Population by single year of age. The open-ended top band cannot be an age."""
    return (
        with_dims(
            fact.filter(
                (pl.col("indicator_id") == "population")
                & (pl.col("area_level") == level)
                & pl.col("year").is_in(years)
            )
        )
        .filter(pl.col("age") != "75+")
        .with_columns(pl.col("age").cast(pl.Int32).alias("yas"))
    )


def totals(fact: pl.DataFrame, indicator: str, level: str) -> pl.DataFrame:
    return (
        fact.filter(
            (pl.col("indicator_id") == indicator) & (pl.col("area_level") == level)
        )
        .group_by("area_id", "year")
        .agg(pl.col("value").sum().alias(indicator))
    )


def band_sum(rows: pl.DataFrame, band: tuple, alias: str) -> pl.DataFrame:
    sex, low, high = band
    return (
        rows.filter((pl.col("sex") == sex) & pl.col("yas").is_between(low, high))
        .group_by("area_id", "year")
        .agg(pl.col("value").sum().alias(alias))
    )


# endregion

# region Writing

#: Header wording lives here rather than in the frames: the column name is a key, the
#: header is a sentence to a reader, and the two should be free to differ.
HEADERS = {
    "sira": "Sıra",
    "il": "İl",
    "ilce": "İlçe",
    "kusak": "Kuşak",
    "olcut": "Ölçüt",
    "not": "Not",
}


def sheet(
    book,
    frame: pl.DataFrame,
    title: str,
    headers: dict,
    formats: dict,
    widths: dict,
    scales: dict | None = None,
) -> None:
    """One sheet: banded table, frozen header, colour scales where a ratio is compared.

    Written as a real Excel table so the banding, the filter and the header stay attached
    to the data when the reader sorts — a sheet that loses its shape on the first sort is
    a screenshot, not a table.
    """
    page = book.add_worksheet(title)
    page.freeze_panes(1, 1)
    page.set_row(0, 40)

    columns = frame.columns
    for index, column in enumerate(columns):
        page.set_column(
            index, index, widths.get(column, 14), formats.get(column, formats["text"])
        )

    rows = frame.rows()
    page.add_table(
        0,
        0,
        max(len(rows), 1),
        len(columns) - 1,
        {
            "data": [list(row) for row in rows] or [[None] * len(columns)],
            "columns": [
                {
                    "header": headers.get(c, HEADERS.get(c, c)),
                    "header_format": formats["head"],
                    "format": formats.get(c, formats["text"]),
                }
                for c in columns
            ],
            "style": "Table Style Light 1",
            "banded_rows": True,
            "autofilter": True,
        },
    )

    for column, kind in (scales or {}).items():
        if column not in columns:
            continue
        index = columns.index(column)
        # Green where high is good, red where high is bad; the reader should not have to
        # learn a palette per sheet.
        low, high = ("#F8696B", "#63BE7B") if kind == "up" else ("#63BE7B", "#F8696B")
        page.conditional_format(
            1,
            index,
            len(rows),
            index,
            {
                "type": "3_color_scale",
                "min_color": low,
                "mid_color": "#FFEB84",
                "max_color": high,
            },
        )


def styles(book) -> dict:
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
    return {
        "head": head,
        "text": book.add_format({"align": "center", "valign": "vcenter"}),
        "left": book.add_format({"align": "left", "valign": "vcenter"}),
        "count": book.add_format(
            {"num_format": "#,##0", "align": "center", "valign": "vcenter"}
        ),
        # Two decimals everywhere a ratio is shown: %29 and %29,22 are different answers
        # once a column is being sorted, and the second one is the one that was asked.
        "percent": book.add_format(
            {"num_format": "0,00%", "align": "center", "valign": "vcenter"}
        ),
        "points": book.add_format(
            {"num_format": "+0,00;-0,00;0", "align": "center", "valign": "vcenter"}
        ),
        "rate": book.add_format(
            {"num_format": "0,00", "align": "center", "valign": "vcenter"}
        ),
        "fine": book.add_format(
            {"num_format": "0,00", "align": "center", "valign": "vcenter"}
        ),
    }


def notes_sheet(book, lines: list[str]) -> None:
    page = book.add_worksheet("Nasıl okunur")
    page.set_column(0, 0, 108, book.add_format({"text_wrap": True, "valign": "top"}))
    bold = book.add_format({"bold": True, "font_size": 12})
    for row, line in enumerate(lines):
        page.write(row, 0, line, bold if row == 0 else None)


def ranked(frame: pl.DataFrame, by: str, descending=True) -> pl.DataFrame:
    """Sorted, with the rank written down so it survives the reader's own sorting."""
    ordered = frame.sort(by, descending=descending, nulls_last=True)
    return ordered.with_columns(pl.int_range(1, len(ordered) + 1).alias("sira")).select(
        ["sira"] + [c for c in ordered.columns]
    )


# endregion

# region Analyses


def components(fact: pl.DataFrame, last: int):
    """Δresidents = natural + internal + foreign + naturalisation, per province."""

    def stock(indicator: str) -> pl.DataFrame:
        frame = totals(fact, indicator, "province")
        return (
            frame.filter(pl.col("year") == last)
            .select("area_id", pl.col(indicator).alias("son"))
            .join(
                frame.filter(pl.col("year") == BASE).select(
                    "area_id", pl.col(indicator).alias("ilk")
                ),
                on="area_id",
            )
            .with_columns((pl.col("son") - pl.col("ilk")).alias(indicator + "_fark"))
            .rename({"ilk": indicator + "_ilk"})
            .drop("son")
        )

    def flow(indicator: str) -> pl.DataFrame:
        return (
            totals(fact, indicator, "province")
            .filter(pl.col("year").is_between(BASE + 1, last))
            .group_by("area_id")
            .agg(pl.col(indicator).sum().alias(indicator))
        )

    frame = (
        stock("population")
        .join(stock("registry_population"), on="area_id")
        .join(stock("foreign_population"), on="area_id")
        .join(flow("natural_increase"), on="area_id")
        .join(flow("migration_net"), on="area_id")
        .rename(
            {
                "population_ilk": "nufus_ilk",
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
            (pl.col("kutuk_fark") - pl.col("degisim")).alias("makas"),
        )
        .join(names("province"), on="area_id")
    )

    parts = ["dogal", "ic_goc", "dis_goc", "vatandaslik"]
    gross = pl.sum_horizontal([pl.col(p).abs() for p in parts])
    frame = frame.with_columns([(pl.col(p) / gross).alias(p + "_pay") for p in parts])

    same = (pl.min_horizontal([pl.col(p) for p in parts]) >= 0) | (
        pl.max_horizontal([pl.col(p) for p in parts]) <= 0
    )
    frame = frame.with_columns(
        pl.when(pl.col("degisim") <= 0)
        .then(pl.lit("nüfusu azaldı"))
        .when(same)
        .then(pl.lit("tek yönlü"))
        .otherwise(pl.lit("doğumla kazandı, göçle verdi"))
        .alias("not")
    )

    main = ranked(
        frame.select(
            "il",
            "nufus_ilk",
            "degisim",
            "degisim_oran",
            "dogal",
            "ic_goc",
            "dis_goc",
            "vatandaslik",
            "dogal_pay",
            "ic_goc_pay",
            "dis_goc_pay",
            "vatandaslik_pay",
            "not",
        ),
        "degisim",
    )
    outside = ranked(
        frame.with_columns(
            (pl.col("dis_goc") + pl.col("vatandaslik")).alias("disardan")
        )
        .with_columns((pl.col("disardan") / pl.col("degisim")).alias("disardan_pay"))
        .select("il", "degisim", "dis_goc", "vatandaslik", "disardan", "disardan_pay"),
        "disardan",
    )
    registry = ranked(
        frame.select("il", "degisim", "kutuk_fark", "makas"), "makas", descending=False
    )
    return main, outside, registry


def cohorts(fact: pl.DataFrame, last: int):
    """A cohort followed from one year to the other. It cannot grow on its own."""
    step = last - BASE

    def walk(level: str) -> pl.DataFrame:
        rows = single_ages(fact, level, [BASE, last])
        pieces = []
        for low, high in COHORT_BANDS:
            if high + step > 74:
                break
            label = f"{low}-{high} → {low + step}-{high + step}"
            start = (
                rows.filter(
                    (pl.col("year") == BASE) & pl.col("yas").is_between(low, high)
                )
                .group_by("area_id")
                .agg(pl.col("value").sum().alias("ilk"))
            )
            end = (
                rows.filter(
                    (pl.col("year") == last)
                    & pl.col("yas").is_between(low + step, high + step)
                )
                .group_by("area_id")
                .agg(pl.col("value").sum().alias("son"))
            )
            pieces.append(
                start.join(end, on="area_id").with_columns(pl.lit(label).alias("kusak"))
            )
        return pl.concat(pieces).with_columns(
            (pl.col("son") - pl.col("ilk")).alias("fark"),
            (pl.col("son") / pl.col("ilk") - 1).alias("oran"),
        )

    country = walk("country")
    rows = single_ages(fact, "country", [BASE, last])

    def by_sex(sex: str) -> pl.DataFrame:
        pieces = []
        for low, high in COHORT_BANDS:
            if high + step > 74:
                break
            label = f"{low}-{high} → {low + step}-{high + step}"
            picked = rows.filter(pl.col("sex") == sex)
            ilk = picked.filter(
                (pl.col("year") == BASE) & pl.col("yas").is_between(low, high)
            )["value"].sum()
            son = picked.filter(
                (pl.col("year") == last)
                & pl.col("yas").is_between(low + step, high + step)
            )["value"].sum()
            pieces.append({"kusak": label, sex: son / ilk - 1})
        return pl.DataFrame(pieces)

    turkiye = (
        country.select("kusak", "ilk", "son", "fark", "oran")
        .join(by_sex("male").rename({"male": "erkek"}), on="kusak")
        .join(by_sex("female").rename({"female": "kadin"}), on="kusak")
    )

    provinces = (
        walk("province")
        .join(names("province"), on="area_id")
        .select("il", "kusak", "oran")
        .pivot(values="oran", index="il", on="kusak")
    )
    young = provinces.columns[1:4]
    provinces = ranked(
        provinces.with_columns(
            pl.mean_horizontal([pl.col(c) for c in young]).alias("genc_ortalama")
        ),
        "genc_ortalama",
    )
    return turkiye, provinces


def marriage(fact: pl.DataFrame, last: int, sex: str) -> pl.DataFrame:
    """Never married and not married, ages 30-49, then and now."""
    ages = ["30-34", "35-39", "40-44", "45-49"]
    rows = (
        with_dims(
            fact.filter(
                (pl.col("indicator_id") == "marital_status")
                & (pl.col("area_level") == "province")
                & pl.col("year").is_in([MARITAL_BASE, last])
            )
        )
        .with_columns(pl.col("dims").str.extract(r"marital=([^;]*)").alias("durum"))
        .filter((pl.col("sex") == sex) & pl.col("age").is_in(ages))
        .group_by("area_id", "year")
        .agg(
            pl.col("value").sum().alias("nufus"),
            pl.col("value")
            .filter(pl.col("durum") == "never_married")
            .sum()
            .alias("hic"),
            pl.col("value")
            .filter(pl.col("durum") != "married")
            .sum()
            .alias("evli_degil"),
        )
        .with_columns(
            (pl.col("hic") / pl.col("nufus")).alias("hic_pay"),
            (pl.col("evli_degil") / pl.col("nufus")).alias("evli_degil_pay"),
        )
    )
    wide = (
        rows.filter(pl.col("year") == last)
        .select(
            "area_id",
            pl.col("nufus").alias("nufus_son"),
            pl.col("hic_pay").alias("hic_son"),
            pl.col("evli_degil_pay").alias("ed_son"),
        )
        .join(
            rows.filter(pl.col("year") == MARITAL_BASE).select(
                "area_id",
                pl.col("hic_pay").alias("hic_ilk"),
                pl.col("evli_degil_pay").alias("ed_ilk"),
            ),
            on="area_id",
        )
        .with_columns(
            ((pl.col("hic_son") - pl.col("hic_ilk")) * 100).alias("hic_puan"),
            ((pl.col("ed_son") - pl.col("ed_ilk")) * 100).alias("ed_puan"),
        )
        .join(names("province"), on="area_id")
    )
    return ranked(
        wide.select(
            "il",
            "nufus_son",
            "hic_ilk",
            "hic_son",
            "hic_puan",
            "ed_ilk",
            "ed_son",
            "ed_puan",
        ),
        "ed_son",
    )


def fertility(fact: pl.DataFrame, last: int) -> pl.DataFrame:
    """Women of fertile age against births: the two halves of a birth count."""
    rows = single_ages(fact, "province", [BASE, last])
    women = band_sum(rows, FERTILE, "kadin")
    births = totals(fact, "births", "province").rename({"births": "dogum"})
    tfr = totals(fact, "tfr", "province").rename({"tfr": "tfh"})
    frame = (
        women.join(births, on=["area_id", "year"])
        .join(tfr, on=["area_id", "year"], how="left")
        .with_columns((1000 * pl.col("dogum") / pl.col("kadin")).alias("gdh"))
    )
    wide = (
        frame.filter(pl.col("year") == last)
        .select(
            "area_id",
            pl.col("kadin").alias("kadin_son"),
            pl.col("dogum").alias("dogum_son"),
            pl.col("gdh").alias("gdh_son"),
            pl.col("tfh").alias("tfh_son"),
        )
        .join(
            frame.filter(pl.col("year") == BASE).select(
                "area_id",
                pl.col("kadin").alias("kadin_ilk"),
                pl.col("dogum").alias("dogum_ilk"),
                pl.col("gdh").alias("gdh_ilk"),
            ),
            on="area_id",
        )
        .with_columns(
            (pl.col("kadin_son") / pl.col("kadin_ilk") - 1).alias("kadin_oran"),
            (pl.col("dogum_son") / pl.col("dogum_ilk") - 1).alias("dogum_oran"),
            (pl.col("gdh_son") / pl.col("gdh_ilk") - 1).alias("gdh_oran"),
            (pl.col("gdh_son") - pl.col("gdh_ilk")).alias("gdh_puan"),
        )
        .join(names("province"), on="area_id")
    )
    return ranked(
        wide.select(
            "il",
            "kadin_ilk",
            "kadin_son",
            "kadin_oran",
            "dogum_ilk",
            "dogum_son",
            "dogum_oran",
            "gdh_ilk",
            "gdh_son",
            "gdh_puan",
            "gdh_oran",
            "tfh_son",
        ),
        "gdh_oran",
    )


def age_bands(fact: pl.DataFrame, last: int):
    """The fertile band and the prime band, as shares. Provinces exact, districts binned."""
    rows = single_ages(fact, "province", [BASE, last])
    whole = (
        rows.group_by("area_id", "year")
        .agg(pl.col("value").sum().alias("toplam"))
        .join(
            rows.filter(pl.col("sex") == "female")
            .group_by("area_id", "year")
            .agg(pl.col("value").sum().alias("kadin")),
            on=["area_id", "year"],
        )
        .join(band_sum(rows, FERTILE, "k1549"), on=["area_id", "year"])
        .join(band_sum(rows, PRIME, "e2554"), on=["area_id", "year"])
        .join(band_sum(rows, WIDE_PRIME, "e2059"), on=["area_id", "year"])
    )

    district_rows = with_dims(
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == "district")
            & pl.col("year").is_in([BASE, last])
        )
    )
    pieces = [
        district_rows.group_by("area_id", "year").agg(
            pl.col("value").sum().alias("toplam")
        ),
        district_rows.filter(pl.col("sex") == "female")
        .group_by("area_id", "year")
        .agg(pl.col("value").sum().alias("kadin")),
    ]
    for alias, (sex, ages) in GROUPS.items():
        pieces.append(
            district_rows.filter((pl.col("sex") == sex) & pl.col("age").is_in(ages))
            .group_by("area_id", "year")
            .agg(pl.col("value").sum().alias(alias))
        )
    binned = pieces[0]
    for other in pieces[1:]:
        binned = binned.join(other, on=["area_id", "year"], how="left")

    def shaped(frame: pl.DataFrame, keys: pl.DataFrame, key_columns: list[str]):
        wide = (
            frame.filter(pl.col("year") == last)
            .drop("year")
            .join(
                frame.filter(pl.col("year") == BASE)
                .drop("year")
                .select(
                    "area_id",
                    (pl.col("k1549") / pl.col("toplam")).alias("k1549_pay_ilk"),
                    (pl.col("k1549") / pl.col("kadin")).alias("k1549_kadinda_ilk"),
                    (pl.col("e2554") / pl.col("toplam")).alias("e2554_pay_ilk"),
                ),
                on="area_id",
            )
            .with_columns(
                (pl.col("k1549") / pl.col("toplam")).alias("k1549_pay_son"),
                (pl.col("k1549") / pl.col("kadin")).alias("k1549_kadinda_son"),
                (pl.col("e2554") / pl.col("toplam")).alias("e2554_pay_son"),
                (pl.col("e2059") / pl.col("toplam")).alias("e2059_pay_son"),
            )
            .join(keys, on="area_id")
        )
        return wide.select(
            key_columns
            + [
                "toplam",
                "k1549",
                "k1549_kadinda_ilk",
                "k1549_kadinda_son",
                "e2554",
                "e2554_pay_ilk",
                "e2554_pay_son",
                "e2059_pay_son",
            ]
        )

    province = ranked(shaped(whole, names("province"), ["il"]), "e2554_pay_son")
    district = shaped(binned, names("district"), ["il", "ilce"]).with_columns(
        pl.when(pl.col("toplam") >= RANK_FLOOR)
        .then(pl.lit(""))
        .otherwise(pl.lit("küçük ilçe — profili kurumsal nüfus bozabilir"))
        .alias("not")
    )
    return province, ranked(district, "e2554_pay_son")


# endregion


def main() -> None:
    fact = facts()
    last = int(
        fact.filter(pl.col("indicator_id") == "population").select("year").max().item()
    )
    OUT.mkdir(parents=True, exist_ok=True)
    written = []

    def book(filename: str) -> tuple:
        target = OUT / filename
        workbook = xlsxwriter.Workbook(str(target))
        written.append(target.name)
        return workbook, styles(workbook)

    count, percent, points, rate, fine, left = (
        "count",
        "percent",
        "points",
        "rate",
        "fine",
        "left",
    )

    # region 1 — components
    main_frame, outside, registry = components(fact, last)
    workbook, style = book("analiz-1-bilesenler.xlsx")
    formats = {
        **style,
        **{
            c: style[count]
            for c in (
                "nufus_ilk",
                "degisim",
                "dogal",
                "ic_goc",
                "dis_goc",
                "vatandaslik",
                "kutuk_fark",
                "makas",
                "disardan",
            )
        },
        **{
            c: style[percent]
            for c in (
                "degisim_oran",
                "dogal_pay",
                "ic_goc_pay",
                "dis_goc_pay",
                "vatandaslik_pay",
                "disardan_pay",
            )
        },
        "il": style[left],
        "not": style[left],
    }
    widths = {"il": 16, "not": 28, "sira": 6, "nufus_ilk": 13, "degisim": 13}
    sheet(
        workbook,
        main_frame,
        "Bileşenler",
        {
            "nufus_ilk": f"Nüfus {BASE}",
            "degisim": f"Nüfus değişimi {BASE}-{last}",
            "degisim_oran": "Değişim %",
            "dogal": "Doğal artış",
            "ic_goc": "Net iç göç",
            "dis_goc": "Net dış göç",
            "vatandaslik": "Vatandaşlığa geçiş",
            "dogal_pay": "Doğal — payı",
            "ic_goc_pay": "İç göç — payı",
            "dis_goc_pay": "Dış göç — payı",
            "vatandaslik_pay": "Vatandaşlık — payı",
        },
        formats,
        widths,
        {"degisim_oran": "up", "ic_goc_pay": "up"},
    )
    sheet(
        workbook,
        outside,
        "Yurt dışı kaynaklı",
        {
            "degisim": "Nüfus değişimi",
            "dis_goc": "Net dış göç (yabancı)",
            "vatandaslik": "Vatandaşlığa geçiş",
            "disardan": "Yurt dışı kaynaklı toplam",
            "disardan_pay": "Artışın yüzde kaçı",
        },
        formats,
        widths,
        {"disardan_pay": "up"},
    )
    sheet(
        workbook,
        registry,
        "Kütük makası",
        {
            "degisim": "İkamet değişimi",
            "kutuk_fark": "Kütük değişimi",
            "makas": "Kütük − ikamet",
        },
        formats,
        {**widths, "makas": 18},
        {"makas": "down"},
    )
    notes_sheet(
        workbook,
        [
            f"Bir ilin nüfusu neden değişti — {BASE}-{last}",
            "",
            "Nüfus değişimi = doğal artış + net iç göç + net dış göç + vatandaşlığa geçiş.",
            "Dördü de ayrı ölçülmedi: vatandaşlık artıktır. Doğruluğunun kanıtı, 81 ilde",
            "toplamının kütük artışının doğal artışı aşan kısmına birebir eşit olması.",
            "",
            f"Taban {BASE}: dört seriden en geç başlayanı (doğum) o yıl başlıyor.",
            "Doğal artış ve iç göç akıştır, taban yıldan sonrası toplanır. İkamet, kütük ve",
            "yabancı nüfus stoktur, iki yılın farkı alınır.",
            "",
            "PAY SÜTUNLARI bileşenin mutlak değerler toplamına oranıdır. Net değişime bölen",
            "sezgisel ölçü 60 ilde 100'ü aşıyor ya da işaret değiştiriyor; bu ölçü ±100",
            "arasında kalır ve 81 ilin hepsinde okunur. 'Not' sütunu ilin hangi tipte",
            "olduğunu yazar: tek yönlü mü, yoksa doğumla kazanıp göçle mi vermiş.",
            "",
            "Net dış göç, yabancı uyruklu nüfus stokundaki değişimdir. Doğrudan ölçü olan",
            "'yurt dışından gelen göç' 2016'da başlıyor, taban yıla yetişmiyor.",
            "81 ilin net iç göçü toplamda tam sıfırdır: iç göç kapalı bir sistemdir.",
            "",
            "KÜTÜK MAKASI = kütük değişimi − ikamet değişimi. Eksi olması ilin dışarıdan",
            "insan çektiğini, artı olması kütüğünün büyüyüp kendisinin büyümediğini gösterir.",
        ],
    )
    workbook.close()
    # endregion

    # region 2 — cohorts
    turkiye, province_cohorts = cohorts(fact, last)
    workbook, style = book("analiz-2-kohort.xlsx")
    formats = {
        **style,
        **{c: style[count] for c in ("ilk", "son", "fark")},
        **{c: style[percent] for c in ("oran", "erkek", "kadin", "genc_ortalama")},
        **{c: style[percent] for c in province_cohorts.columns if "→" in c},
        "il": style[left],
        "kusak": style[left],
    }
    widths = {"kusak": 22, "il": 16, "sira": 6, "genc_ortalama": 14}
    sheet(
        workbook,
        turkiye,
        "Türkiye",
        {
            "ilk": f"{BASE}",
            "son": f"{last}",
            "fark": "Fark",
            "oran": "Değişim %",
            "erkek": "Erkek %",
            "kadin": "Kadın %",
        },
        formats,
        widths,
        {"oran": "up", "erkek": "up", "kadin": "up"},
    )
    sheet(
        workbook,
        province_cohorts,
        "İller",
        {"genc_ortalama": "Genç kuşaklar ortalaması"},
        formats,
        {**widths, **{c: 15 for c in province_cohorts.columns if "→" in c}},
        {
            **{c: "up" for c in province_cohorts.columns if "→" in c},
            "genc_ortalama": "up",
        },
    )
    notes_sheet(
        workbook,
        [
            f"Kuşakları izlemek — {BASE}'da şu yaşta olanlar {last}'te",
            "",
            "Bir kuşak kendiliğinden büyüyemez: sonradan kimse o yaşa doğmaz. O yüzden",
            "kuşaktaki değişim yalnız iki şeyden gelir — göç ve ölüm. Arada model yok.",
            "",
            "TÜRKİYE sayfasında iç göç yoktur (ülke içinde yer değiştirmek toplamı",
            "değiştirmez), geriye net dış göç eksi ölüm kalır. Genç kuşakların artıda",
            "olması dışarıdan gelen insandır; yaşlı kuşakların eksisi ölümdür.",
            "Erkek ile kadın sütunu arasındaki fark erkek fazla ölümlülüğüdür.",
            "",
            "İLLER sayfasında aynı hesap iç göçü ölçer: bir ilin kuşağı erimişse o kuşak",
            "başka ile gitmiştir. 'Genç kuşaklar ortalaması' ilk üç kuşağın ortalamasıdır",
            "— o yaşlarda ölüm ihmal edilebilir, yani okuduğun şey neredeyse arı göçtür.",
            "",
            "Üst yaş sınırı: kaynak dosyada en yüksek yaş açık uçlu (75+) olduğu için",
            f"{BASE}'da 55 ve üstündeki kuşaklar izlenemiyor. Eksik değil, sorulamaz.",
        ],
    )
    workbook.close()
    # endregion

    # region 3 — marriage
    women = marriage(fact, last, "female")
    men = marriage(fact, last, "male")
    workbook, style = book("analiz-3-evlilik.xlsx")
    formats = {
        **style,
        "nufus_son": style[count],
        **{c: style[percent] for c in ("hic_ilk", "hic_son", "ed_ilk", "ed_son")},
        **{c: style[points] for c in ("hic_puan", "ed_puan")},
        "il": style[left],
    }
    headers = {
        "nufus_son": f"30-49 nüfus {last}",
        "hic_ilk": f"Hiç evlenmemiş {MARITAL_BASE}",
        "hic_son": f"Hiç evlenmemiş {last}",
        "hic_puan": "Hiç evlenmemiş — fark (puan)",
        "ed_ilk": f"Evli değil {MARITAL_BASE}",
        "ed_son": f"Evli değil {last}",
        "ed_puan": "Evli değil — fark (puan)",
    }
    widths = {"il": 16, "sira": 6, "nufus_son": 14}
    sheet(
        workbook,
        women,
        "Kadın 30-49",
        headers,
        formats,
        widths,
        {"ed_son": "up", "hic_son": "up"},
    )
    sheet(
        workbook,
        men,
        "Erkek 30-49",
        headers,
        formats,
        widths,
        {"ed_son": "up", "hic_son": "up"},
    )
    notes_sheet(
        workbook,
        [
            f"Evli olmayanlar, 30-49 yaş — {MARITAL_BASE} ve {last}",
            "",
            "'Hiç evlenmemiş' hiç nikâh kıymamış olanlardır. 'Evli değil' bunlara boşanmış",
            "ve dul olanları ekler; yani şu an evli olmayan herkes.",
            "Fark sütunları yüzde değil PUAN farkıdır: %15,6'dan %19,6'ya çıkış +4,0 puandır.",
            "",
            "DİKKAT — iki farklı şey aynı sütunda görünüyor:",
            "· Batı illerindeki artış davranış değişimidir (geç evlenme, evlenmeme).",
            "· Güneydoğu'daki yüksek başlangıç seviyesi bununla açıklanamaz; resmî nikâhı",
            "  olmayan evlilikler kayıtta 'hiç evlenmemiş' görünür.",
            "· Hatay ve Şanlıurfa gibi illerdeki DÜŞÜŞ de davranış değil, büyük olasılıkla",
            "  nüfus bileşiminin değişmesidir.",
            "Bu yüzden iller arası seviye karşılaştırması değil, aynı ilin kendi değişimi",
            "daha güvenli okunur.",
            "",
            f"Medeni durum {MARITAL_BASE}'de başlıyor; diğer analizlerin tabanı {BASE}.",
            "'Bilinmeyen' medeni durum, evli olmayanların içinde sayılır.",
        ],
    )
    workbook.close()
    # endregion

    # region 4 — fertility
    frame = fertility(fact, last)
    workbook, style = book("analiz-4-dogurganlik.xlsx")
    formats = {
        **style,
        **{
            c: style[count]
            for c in ("kadin_ilk", "kadin_son", "dogum_ilk", "dogum_son")
        },
        **{c: style[percent] for c in ("kadin_oran", "dogum_oran", "gdh_oran")},
        **{c: style[rate] for c in ("gdh_ilk", "gdh_son")},
        "gdh_puan": style[points],
        "tfh_son": style[fine],
        "il": style[left],
    }
    sheet(
        workbook,
        frame,
        "İller",
        {
            "kadin_ilk": f"Kadın 15-49 · {BASE}",
            "kadin_son": f"Kadın 15-49 · {last}",
            "kadin_oran": "Kadın değişimi",
            "dogum_ilk": f"Doğum · {BASE}",
            "dogum_son": f"Doğum · {last}",
            "dogum_oran": "Doğum değişimi",
            "gdh_ilk": f"GDH {BASE}",
            "gdh_son": f"GDH {last}",
            "gdh_puan": "GDH farkı",
            "gdh_oran": "GDH değişimi",
            "tfh_son": f"TFH {last}",
        },
        formats,
        {"il": 16, "sira": 6, "kadin_ilk": 14, "kadin_son": 14},
        {"gdh_oran": "up", "gdh_son": "up", "dogum_oran": "up", "tfh_son": "up"},
    )
    notes_sheet(
        workbook,
        [
            f"Doğurgan çağdaki kadın ve doğum — {BASE}-{last}",
            "",
            "GDH = genel doğurganlık hızı: bin kadın (15-49) başına doğum. Doğum sayısı iki",
            "şeyin çarpımıdır — kaç kadın var, ve kadın başına kaç çocuk. Bu sayfa ikisini",
            "ayırır. Türkiye'de kadın sayısı %12,6 arttı, kadın başına doğum %37,2 düştü;",
            "çarpımları doğumdaki %29,3'lük düşüşü tam olarak verir.",
            "",
            "Yani kompozisyon düşüşü frenledi, davranış düşürdü. Bu fren şimdi bitiyor:",
            "doğurgan çağa girecek kuşaklar artık küçük.",
            "",
            "Sıralama GDH değişimine göredir — en az düşen il başta. 'GDH farkı' puan",
            "cinsindendir (bin kadın başına kaç doğum eksildi), 'GDH değişimi' orandır.",
            "İkisi farklı sorulardır: yüksekten düşen il puanda çok, oranda az kaybeder.",
            "",
            "TFH (toplam doğurganlık hızı) TÜİK'in yayımladığı seridir, buradan",
            "hesaplanmadı. GDH ile birlikte okunur: TFH yaş yapısından arındırılmıştır,",
            "GDH arındırılmamıştır, ikisinin ayrışması yaş bileşiminin etkisidir.",
        ],
    )
    workbook.close()
    # endregion

    # region 5 — age bands
    province_bands, district_bands = age_bands(fact, last)
    workbook, style = book("analiz-5-yas-bantlari.xlsx")
    formats = {
        **style,
        **{c: style[count] for c in ("toplam", "k1549", "e2554")},
        **{
            c: style[percent]
            for c in (
                "k1549_kadinda_ilk",
                "k1549_kadinda_son",
                "e2554_pay_ilk",
                "e2554_pay_son",
                "e2059_pay_son",
            )
        },
        "il": style[left],
        "ilce": style[left],
        "not": style[left],
    }
    headers = {
        "toplam": f"Nüfus {last}",
        "k1549": f"Kadın 15-49 · {last}",
        "k1549_kadinda_ilk": f"Kadınlarda payı {BASE}",
        "k1549_kadinda_son": f"Kadınlarda payı {last}",
        "e2554": f"Erkek 25-54 · {last}",
        "e2554_pay_ilk": f"Nüfustaki payı {BASE}",
        "e2554_pay_son": f"Nüfustaki payı {last}",
        "e2059_pay_son": f"Erkek 20-59 payı {last}",
    }
    widths = {"il": 15, "ilce": 20, "sira": 6, "not": 32, "toplam": 13}
    scales = {
        "k1549_kadinda_son": "up",
        "e2554_pay_son": "up",
        "e2059_pay_son": "up",
    }
    sheet(workbook, province_bands, "İller", headers, formats, widths, scales)
    sheet(workbook, district_bands, "İlçeler", headers, formats, widths, scales)
    notes_sheet(
        workbook,
        [
            f"Doğurgan çağ ve çalışma çağı — {BASE} ve {last}",
            "",
            "Kadın 15-49 doğurgan çağdır ve payı kadınlar içinde verilir: Türkiye'de",
            "%54,0'tan %51,0'a düştü. Sayı artarken pay düşüyor, yani doğum sayısındaki",
            "azalmanın bir kısmı doğurganlık değil, nüfusun yaş bileşimi.",
            "",
            "Erkek 25-54 çalışma çağı olarak seçildi: tam otuz yıl, iki gürültülü uç",
            "dışarıda. 20-24 on altı yılda %0,0 büyüdü (okul, askerlik), 60-64 ise %93",
            "(emekliliğin genişlemesi). Bant seçimi ölçülen şeyi değiştirir; 20-59 payı",
            "referans olarak yanındadır.",
            "Bu bir demografi tercihidir: işgücüne katılım verimiz yok. Katılım oranı",
            "çekilirse sınır tahmin edilmek yerine ölçülebilir.",
            "",
            "İL sayfası tek yaş verisinden hesaplandı, sınır tam yerine oturuyor.",
            "İLÇE sayfasında veri beşer yaş grubudur; 15-49 ve 25-54 grup sınırlarına denk",
            "geldiği için ilçede de sorulabiliyor, başka bir bant sorulamaz.",
            "",
            "İLÇEDE NEDEN DEĞİŞİM SÜTUNU YOK: 6360 sayılı yasa 2013'te merkez ilçeleri",
            "böldü ve ardıl eşlemesi elimizde yok. Ham hesap Pamukkale'yi %+6.311,",
            "Zonguldak'ı %−51 gösteriyor; bunlar demografi değil, idari bölünme. Oran her",
            "yıl kendi içinde hesaplandığı için bundan etkilenmez, değişim etkilenir.",
            "",
            f"'Not' sütunu {RANK_FLOOR:,} altındaki ilçeleri işaretler: küçük ilçede bir".replace(
                ",", "."
            ),
            "garnizon ya da cezaevi yaş profilini demografiden çok bozar (Çukurca'da",
            "erkek 20-59 payı %45,1).",
        ],
    )
    workbook.close()
    # endregion

    print("yazildi:", OUT)
    for name in written:
        print("  ", name)


if __name__ == "__main__":
    main()
