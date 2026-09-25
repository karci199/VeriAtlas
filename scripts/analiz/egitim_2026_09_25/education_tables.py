"""Education tables workbook: national series, province time series, 2024-25 snapshot.

Reads the warehouse only (schools/students/teachers/classrooms *_by_type from the MEB
portal, class_sections and net_enrollment_rate from MEDAS, population for per-child
ratios) and writes one Excel file with a sheet per table.

Conventions that matter when reading the output:
* year Y = school year Y-(Y+1); population is taken at 1 January Y+1, the ADNKS count
  closest to the middle of that school year.
* pre-school includes kindergarten classes inside primary schools (anasınıfı), which
  MEDAS leaves out of schools, classrooms and teachers.
* open education (açık ortaokul/lise) has students but no teachers or classrooms; per
  teacher and per classroom ratios use formal (örgün) students only.

Run from the main checkout root:
    .venv/Scripts/python.exe scripts/analiz/egitim_2026_09_25/education_tables.py
Out: C:/veri-ham/analiz/2026_09_25/egitim_tablolari.xlsx
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import polars as pl
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

sys.path.insert(0, "src")

from veriatlas.areas import load_areas
from veriatlas.config import WAREHOUSE

OUT = Path("C:/veri-ham/analiz/2026_09_25/egitim_tablolari.xlsx")

LEVEL = {
    "kindergarten": "Okul öncesi",
    "kindergarten_class": "Okul öncesi",
    "primary": "İlkokul",
    "basic_education": "İlköğretim",
    "lower_secondary": "Ortaokul",
    "imam_hatip_lower_secondary": "Ortaokul",
    "open_lower_secondary": "Ortaokul",
    "upper_secondary_general": "Lise",
    "upper_secondary_vocational": "Lise",
    "imam_hatip_upper_secondary": "Lise",
    "open_upper_secondary": "Lise",
}
TYPE_TR = {
    "kindergarten": "Anaokulu",
    "kindergarten_class": "Anasınıfı",
    "primary": "İlkokul",
    "basic_education": "İlköğretim (2002)",
    "lower_secondary": "Ortaokul",
    "imam_hatip_lower_secondary": "İmam hatip ortaokulu",
    "open_lower_secondary": "Açık ortaokul",
    "upper_secondary_general": "Genel lise",
    "upper_secondary_vocational": "Mesleki lise",
    "imam_hatip_upper_secondary": "İmam hatip lisesi",
    "open_upper_secondary": "Açık lise",
}
OPEN = {"open_lower_secondary", "open_upper_secondary"}
MEASURE_TR = {
    "schools_by_type": "Okul",
    "students_by_type": "Öğrenci",
    "teachers_by_type": "Öğretmen",
    "classrooms_by_type": "Derslik",
}


def long_frame(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    frame = pl.from_arrow(
        con.execute(
            """
            select indicator_id, area_id, year(period_start) as year, dims, value
            from fact where indicator_id in
              ('schools_by_type','students_by_type','teachers_by_type','classrooms_by_type')
            """
        ).arrow()
    )
    return frame.with_columns(
        pl.col("dims").str.extract(r"meb_school_type=([a-z_]+)").alias("type"),
        pl.col("dims").str.extract(r"school_ownership=([a-z]+)").alias("owner"),
        pl.col("dims").str.extract(r"sex=([a-z]+)").alias("sex"),
        pl.col("indicator_id").replace(MEASURE_TR).alias("measure"),
    ).with_columns(
        pl.col("type").replace(LEVEL).alias("level"),
        pl.col("type").is_in(OPEN).alias("open"),
    )


def population(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Total and 5-17 (school-age) population per province and year; year = ADNKS year - 1."""
    frame = pl.from_arrow(
        con.execute(
            """
            select area_id, year(period_start) - 1 as year,
                   sum(value) as nufus,
                   sum(case when try_cast(regexp_extract(dims, 'age=([0-9]+);', 1) as int)
                             between 5 and 17 then value end) as cocuk_5_17
            from fact
            where indicator_id = 'population' and area_level = 'province'
              and dims like 'age=%;sex=%'
            group by 1, 2
            """
        ).arrow()
    )
    return frame


def province_names() -> dict[str, str]:
    areas = load_areas().filter(pl.col("area_level") == "province")
    return dict(zip(areas["area_id"], areas["name_tr"], strict=True))


def safe_div(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    return pl.when(b > 0).then(a / b).otherwise(None)


def indicators_by_province(data: pl.DataFrame, pop: pl.DataFrame) -> pl.DataFrame:
    """One row per province-year with the ratios the tables use."""
    d = data.filter(pl.col("year") >= 2012)

    def total(measure, cond=True):
        return (
            d.filter((pl.col("measure") == measure) & cond)
            .group_by("area_id", "year")
            .agg(pl.col("value").sum())
        )

    def named(frame, name):
        return frame.rename({"value": name})

    parts = [
        named(total("Okul", pl.col("type") != "kindergarten_class"), "okul"),
        named(total("Öğrenci"), "ogrenci"),
        named(total("Öğrenci", ~pl.col("open")), "ogrenci_orgun"),
        named(total("Öğretmen"), "ogretmen"),
        named(total("Derslik"), "derslik"),
        named(
            total(
                "Okul",
                (pl.col("owner") == "private")
                & (pl.col("type") != "kindergarten_class"),
            ),
            "okul_ozel",
        ),
        named(
            total("Öğrenci", (pl.col("owner") == "private") & ~pl.col("open")),
            "ogrenci_ozel",
        ),
        named(total("Öğretmen", pl.col("owner") == "private"), "ogretmen_ozel"),
        named(total("Öğretmen", pl.col("sex") == "female"), "ogretmen_kadin"),
        named(total("Öğrenci", pl.col("sex") == "female"), "ogrenci_kiz"),
        named(total("Öğrenci", pl.col("type") == "imam_hatip_lower_secondary"), "iho"),
        named(
            total(
                "Öğrenci",
                pl.col("type").is_in(["lower_secondary", "imam_hatip_lower_secondary"]),
            ),
            "ortaokul_orgun",
        ),
        named(total("Öğrenci", pl.col("type") == "imam_hatip_upper_secondary"), "ihl"),
        named(
            total(
                "Öğrenci",
                pl.col("type").is_in(
                    [
                        "upper_secondary_general",
                        "upper_secondary_vocational",
                        "imam_hatip_upper_secondary",
                    ]
                ),
            ),
            "lise_orgun",
        ),
        named(total("Öğrenci", pl.col("type") == "open_upper_secondary"), "acik_lise"),
        named(
            total("Öğrenci", pl.col("type") == "kindergarten_class"), "anasinifi_ogr"
        ),
        named(total("Öğrenci", pl.col("level") == "Okul öncesi"), "okuloncesi_ogr"),
    ]
    out = parts[0]
    for part in parts[1:]:
        out = out.join(part, on=["area_id", "year"], how="full", coalesce=True)
    out = out.join(pop, on=["area_id", "year"], how="left")
    return out.with_columns(
        safe_div(pl.col("ogrenci_orgun"), pl.col("ogretmen")).alias(
            "ogretmen_basina_ogrenci"
        ),
        safe_div(pl.col("ogrenci_orgun"), pl.col("derslik")).alias(
            "derslik_basina_ogrenci"
        ),
        safe_div(pl.col("ogrenci_orgun"), pl.col("okul")).alias("okul_basina_ogrenci"),
        (100 * safe_div(pl.col("okul_ozel"), pl.col("okul"))).alias("ozel_okul_payi"),
        (100 * safe_div(pl.col("ogrenci_ozel"), pl.col("ogrenci_orgun"))).alias(
            "ozel_ogrenci_payi"
        ),
        (100 * safe_div(pl.col("ogretmen_ozel"), pl.col("ogretmen"))).alias(
            "ozel_ogretmen_payi"
        ),
        (100 * safe_div(pl.col("ogretmen_kadin"), pl.col("ogretmen"))).alias(
            "kadin_ogretmen_payi"
        ),
        (100 * safe_div(pl.col("ogrenci_kiz"), pl.col("ogrenci"))).alias(
            "kiz_ogrenci_payi"
        ),
        (100 * safe_div(pl.col("iho"), pl.col("ortaokul_orgun"))).alias("iho_payi"),
        (100 * safe_div(pl.col("ihl"), pl.col("lise_orgun"))).alias("ihl_payi"),
        (
            100
            * safe_div(pl.col("acik_lise"), pl.col("acik_lise") + pl.col("lise_orgun"))
        ).alias("acik_lise_payi"),
        (100 * safe_div(pl.col("anasinifi_ogr"), pl.col("okuloncesi_ogr"))).alias(
            "anasinifi_payi"
        ),
        (1000 * safe_div(pl.col("ogretmen"), pl.col("nufus"))).alias(
            "bin_kisiye_ogretmen"
        ),
        (10000 * safe_div(pl.col("okul"), pl.col("cocuk_5_17"))).alias(
            "on_bin_cocuga_okul"
        ),
        (100 * safe_div(pl.col("ogrenci"), pl.col("cocuk_5_17"))).alias(
            "ogrenci_5_19_nufusa_orani"
        ),
    )


def write_sheet(
    book: Workbook, title: str, header: list[str], rows: list[list], note: str = ""
):
    sheet = book.create_sheet(title[:31])
    start = 1
    if note:
        sheet.cell(row=1, column=1, value=note).font = Font(italic=True)
        start = 3
    for column, name in enumerate(header, 1):
        sheet.cell(row=start, column=column, value=name).font = Font(bold=True)
    for r, row in enumerate(rows, start + 1):
        for column, value in enumerate(row, 1):
            if isinstance(value, float):
                value = round(value, 2)
            sheet.cell(row=r, column=column, value=value)
    sheet.freeze_panes = sheet.cell(row=start + 1, column=2)
    for column in range(1, len(header) + 1):
        sheet.column_dimensions[get_column_letter(column)].width = (
            14 if column > 1 else 22
        )


def main() -> None:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    data = long_frame(con)
    pop = population(con)
    names = province_names()
    book = Workbook()
    book.remove(book.active)

    # 1. National counts by measure × type × ownership.
    national = (
        data.group_by("measure", "type", "owner", "year")
        .agg(pl.col("value").sum())
        .pivot(on="owner", index=["measure", "type", "year"], values="value")
        .fill_null(0)
        .with_columns((pl.col("public") + pl.col("private")).alias("toplam"))
        .with_columns((100 * pl.col("private") / pl.col("toplam")).alias("ozel_pay"))
        .sort("measure", "type", "year")
    )
    years = sorted(national["year"].unique().to_list())
    rows = []
    for (measure, kind), group in national.group_by(
        ["measure", "type"], maintain_order=True
    ):
        by_year = {r["year"]: r for r in group.iter_rows(named=True)}
        rows.append(
            [
                measure,
                TYPE_TR[kind],
                "toplam",
                *[by_year.get(y, {}).get("toplam") for y in years],
            ]
        )
        rows.append(
            [
                measure,
                TYPE_TR[kind],
                "özel %",
                *[by_year.get(y, {}).get("ozel_pay") for y in years],
            ]
        )
    write_sheet(
        book,
        "TR_tur_yillik",
        ["Ölçü", "Okul türü", "Değer", *[f"{y}-{str(y + 1)[2:]}" for y in years]],
        rows,
        "Türkiye, okul türü × yıl. 'özel %' = özel okuldaki payı. Toplam satırları portalda yok, türlerden toplandı.",
    )

    # 2. National ratios by year.
    ratios = indicators_by_province(data, pop)
    sums = (
        ratios.group_by("year")
        .agg(pl.all().exclude("area_id", "year").sum())
        .sort("year")
    )
    national_ratio = indicators_by_province(
        data.with_columns(pl.lit("TR").alias("area_id")),
        pop.group_by("year")
        .agg(pl.col("nufus").sum(), pl.col("cocuk_5_17").sum())
        .with_columns(pl.lit("TR").alias("area_id")),
    ).sort("year")
    cols = [
        ("okul", "Okul"),
        ("ogrenci", "Öğrenci (açık dahil)"),
        ("ogrenci_orgun", "Örgün öğrenci"),
        ("ogretmen", "Öğretmen"),
        ("derslik", "Derslik"),
        ("ogretmen_basina_ogrenci", "Öğretmen başına örgün öğrenci"),
        ("derslik_basina_ogrenci", "Derslik başına örgün öğrenci"),
        ("okul_basina_ogrenci", "Okul başına örgün öğrenci"),
        ("ozel_okul_payi", "Özel okul %"),
        ("ozel_ogrenci_payi", "Özel örgün öğrenci %"),
        ("ozel_ogretmen_payi", "Özel öğretmen %"),
        ("kadin_ogretmen_payi", "Kadın öğretmen %"),
        ("kiz_ogrenci_payi", "Kız öğrenci %"),
        ("iho_payi", "İmam hatip ortaokulu öğrenci %"),
        ("ihl_payi", "İmam hatip lisesi öğrenci % (örgün)"),
        ("acik_lise_payi", "Açık lise %"),
        ("anasinifi_payi", "Okul öncesinde anasınıfı %"),
        ("bin_kisiye_ogretmen", "Bin kişiye öğretmen"),
        ("on_bin_cocuga_okul", "10 bin 5-17 yaş çocuğa okul"),
        ("ogrenci_5_19_nufusa_orani", "Öğrenci / 5-17 yaş nüfus %"),
    ]
    rows = [
        [label, *[r[col] for r in national_ratio.iter_rows(named=True)]]
        for col, label in cols
    ]
    ylabels = [f"{y}-{str(y + 1)[2:]}" for y in national_ratio["year"].to_list()]
    write_sheet(
        book,
        "TR_oranlar",
        ["Gösterge", *ylabels],
        rows,
        "Türkiye yıllık oranlar. Öğretmen/derslik oranlarında açıköğretim öğrencisi yok. Nüfus: öğretim yılının ortasındaki ADNKS.",
    )
    del sums

    # 3. Province time series, one sheet per ratio.
    series = [
        ("ogretmen_basina_ogrenci", "İl_ogretmen_basina_ogr"),
        ("derslik_basina_ogrenci", "İl_derslik_basina_ogr"),
        ("ozel_ogrenci_payi", "İl_ozel_ogrenci_%"),
        ("ozel_okul_payi", "İl_ozel_okul_%"),
        ("kadin_ogretmen_payi", "İl_kadin_ogretmen_%"),
        ("iho_payi", "İl_imam_hatip_ortaokul_%"),
        ("ihl_payi", "İl_imam_hatip_lise_%"),
        ("acik_lise_payi", "İl_acik_lise_%"),
        ("anasinifi_payi", "İl_anasinifi_%"),
        ("ogrenci_5_19_nufusa_orani", "İl_ogrenci_cocuk_nufus_%"),
        ("on_bin_cocuga_okul", "İl_10bin_cocuga_okul"),
        ("ogretmen", "İl_ogretmen_sayisi"),
        ("ogrenci", "İl_ogrenci_sayisi"),
    ]
    ys = sorted(ratios["year"].unique().to_list())
    label_of = dict(cols)
    for col, title in series:
        wide = ratios.select("area_id", "year", col).pivot(
            on="year", index="area_id", values=col
        )
        rows = []
        for r in wide.iter_rows(named=True):
            values = [r.get(str(y)) for y in ys]
            change = (
                values[-1] - values[0]
                if values[0] is not None and values[-1] is not None
                else None
            )
            rows.append([names[r["area_id"]], *values, change])
        rows.sort(key=lambda row: -(row[-2] or 0))
        write_sheet(
            book,
            title,
            ["İl", *[f"{y}-{str(y + 1)[2:]}" for y in ys], "Değişim 2012→2024"],
            rows,
            f"{label_of.get(col, col)} — il × yıl, son yıla göre büyükten küçüğe.",
        )

    # 4. Province snapshot 2024-25 by level.
    snap = data.filter(pl.col("year") == 2024)
    level_rows = (
        snap.group_by("area_id", "measure", "level")
        .agg(pl.col("value").sum())
        .pivot(on=["measure", "level"], index="area_id", values="value")
    )
    snap_cols = [c for c in level_rows.columns if c != "area_id"]
    r24 = ratios.filter(pl.col("year") == 2024)
    extra = [c for c, _ in cols[5:]]
    merged = level_rows.join(
        r24.select("area_id", "nufus", "cocuk_5_17", *extra), on="area_id"
    )
    rows = [
        [
            names[r["area_id"]],
            *[r[c] for c in snap_cols],
            r["nufus"],
            r["cocuk_5_17"],
            *[r[c] for c in extra],
        ]
        for r in merged.sort("area_id").iter_rows(named=True)
    ]
    header = [
        "İl",
        *[
            c.replace('{"', "").replace('"}', "").replace('","', " / ")
            for c in snap_cols
        ],
        "Nüfus",
        "5-17 yaş",
        *[label_of[c] for c in extra],
    ]
    write_sheet(
        book, "İl_2024-25", header, rows, "2024-25, il × kademe sayıları ve oranlar."
    )

    # 5. MEDAS extras: sections and net enrolment.
    medas = pl.from_arrow(
        con.execute(
            """
            select indicator_id, area_id, year(period_start) as year, dims, value from fact
            where indicator_id in ('class_sections','section_size','net_enrollment_rate')
              and area_level in ('province','country')
            """
        ).arrow()
    )
    rows = []
    for (ind, dims), group in medas.sort("year").group_by(
        ["indicator_id", "dims"], maintain_order=True
    ):
        if ind == "net_enrollment_rate":
            per_year = group.group_by("year").agg(pl.col("value").mean()).sort("year")
            label = "Net okullaşma % (il ortalaması)"
        elif ind == "section_size":
            per_year = group.group_by("year").agg(pl.col("value").mean()).sort("year")
            label = "Şube başına öğrenci (il ortalaması)"
        else:
            per_year = group.group_by("year").agg(pl.col("value").sum()).sort("year")
            label = "Şube sayısı"
        mapping = dict(per_year.iter_rows())
        rows.append([label, dims, *[mapping.get(y) for y in range(2007, 2025)]])
    write_sheet(
        book,
        "MEDAS_ek",
        ["Gösterge", "Kırılım", *[str(y) for y in range(2007, 2025)]],
        rows,
        "MEDAS'ta olup portal dosyalarında olmayanlar: şube ve net okullaşma. Oranlar il ortalaması (ağırlıksız).",
    )

    # 6. Students per classroom by type (formal only), national and province x year.
    rooms = (
        data.filter(
            (pl.col("year") >= 2012)
            & ~pl.col("open")
            & pl.col("measure").is_in(["Öğrenci", "Derslik"])
        )
        .group_by("area_id", "year", "type", "measure")
        .agg(pl.col("value").sum())
        .pivot(on="measure", index=["area_id", "year", "type"], values="value")
        .filter(pl.col("Derslik") > 0)
    )
    tr_rooms = (
        rooms.group_by("year", "type")
        .agg(pl.col("Öğrenci").sum(), pl.col("Derslik").sum())
        .with_columns((pl.col("Öğrenci") / pl.col("Derslik")).alias("r"))
    )
    ys2 = sorted(tr_rooms["year"].unique().to_list())
    rows = []
    for kind in TYPE_TR:
        by = {
            r["year"]: r["r"]
            for r in tr_rooms.filter(pl.col("type") == kind).iter_rows(named=True)
        }
        if by:
            rows.append([label, *[by.get(y) for y in ys2]])
    write_sheet(
        book,
        "TR_derslik_basina_tur",
        ["Okul türü", *[f"{y}-{str(y + 1)[2:]}" for y in ys2]],
        rows,
        "Derslik başına örgün öğrenci, tür × yıl. 2012-14 ortaokul: ilkokul binası paylaşımı nedeniyle yüksek; ilk+orta birlikte okunmalı.",
    )
    by_il = rooms.with_columns((pl.col("Öğrenci") / pl.col("Derslik")).alias("r"))
    rows = [
        [
            names[r["area_id"]],
            r["year"],
            f"{r['year']}-{str(r['year'] + 1)[2:]}",
            TYPE_TR[r["type"]],
            r["Öğrenci"],
            r["Derslik"],
            r["r"],
        ]
        for r in by_il.sort("r", descending=True).iter_rows(named=True)
    ]
    write_sheet(
        book,
        "İl_derslik_tur_uzun",
        [
            "İl",
            "Yıl",
            "Öğretim yılı",
            "Okul türü",
            "Öğrenci",
            "Derslik",
            "Derslik başına",
        ],
        rows,
        "İl × yıl × tür, en kalabalıktan seyreğe. Küçük paydalı (az derslikli) satırlar oynaktır.",
    )

    # 7. Enrolment against school-age (6-17) population and deviation from Türkiye.
    k12 = [
        "primary",
        "lower_secondary",
        "imam_hatip_lower_secondary",
        "upper_secondary_general",
        "upper_secondary_vocational",
        "imam_hatip_upper_secondary",
    ]
    enrol = (
        data.filter((pl.col("measure") == "Öğrenci") & pl.col("type").is_in(k12))
        .group_by("area_id", "year")
        .agg(pl.col("value").sum().alias("ogr"))
    )
    age = pl.from_arrow(
        con.execute(
            """select area_id, year(period_start) - 1 as year, sum(value) as cocuk from fact
           where indicator_id = 'population' and area_level = 'province'
             and try_cast(regexp_extract(dims, 'age=([0-9]+);', 1) as int) between 6 and 17 group by 1, 2"""
        ).arrow()
    )
    enrol = enrol.join(age, on=["area_id", "year"])
    tr_rate = enrol.group_by("year").agg(
        (100 * pl.col("ogr").sum() / pl.col("cocuk").sum()).alias("tr")
    )
    enrol = (
        enrol.join(tr_rate, on="year")
        .with_columns((100 * pl.col("ogr") / pl.col("cocuk")).alias("oran"))
        .with_columns((pl.col("oran") - pl.col("tr")).alias("sapma"))
    )
    ys3 = sorted(enrol["year"].unique().to_list())
    wide = enrol.pivot(on="year", index="area_id", values="sapma")
    rows = [
        [names[r["area_id"]], *[r.get(str(y)) for y in ys3]]
        for r in wide.iter_rows(named=True)
    ]
    rows.sort(key=lambda row: -(row[-1] or 0))
    trs = dict(tr_rate.iter_rows())
    rows.insert(0, ["TÜRKİYE oranı %", *[trs.get(y) for y in ys3]])
    write_sheet(
        book,
        "İl_okullasma_sapma",
        ["İl", *[f"{y}-{str(y + 1)[2:]}" for y in ys3]],
        rows,
        "İlkokul+ortaokul+örgün lise öğrencisi / 6-17 yaş ADNKS nüfusu; ilk satır Türkiye oranı, diğerleri ilin Türkiye'den puan farkı.",
    )

    # 8. Comparison with Syrians under temporary protection (snapshot).
    tp = pl.from_arrow(
        con.execute(
            "select area_id, value as suriyeli from fact where indicator_id = 'temporary_protection_syrians' and area_level = 'province'"
        ).arrow()
    )
    if tp.height:
        last = (
            enrol.filter(pl.col("year") == max(ys3))
            .join(tp, on="area_id")
            .join(
                pop.filter(pl.col("year") == max(ys3)).select("area_id", "nufus"),
                on="area_id",
            )
        )
        share_5_17 = 773094 / 2210644
        last = last.with_columns(
            (100 * pl.col("suriyeli") / pl.col("nufus")).alias("pay"),
            (pl.col("ogr") - pl.col("tr") / 100 * pl.col("cocuk")).alias("fazla"),
            (pl.col("suriyeli") * share_5_17).alias("suriyeli_cocuk"),
        )
        rows = [
            [
                names[r["area_id"]],
                r["ogr"],
                r["cocuk"],
                r["oran"],
                r["sapma"],
                r["suriyeli"],
                r["pay"],
                r["fazla"],
                r["suriyeli_cocuk"],
            ]
            for r in last.sort("pay", descending=True).iter_rows(named=True)
        ]
        write_sheet(
            book,
            "Göç_Suriyeli_karsilastirma",
            [
                "İl",
                "Öğrenci (K12 örgün)",
                "6-17 yaş ADNKS",
                "Oran %",
                "Sapma (puan)",
                "Geçici koruma Suriyeli",
                "Suriyeli / ADNKS %",
                "TR oranına göre fazla öğrenci",
                "Tahmini 5-17 yaş Suriyeli",
            ],
            rows,
            "2024-25 öğrenci vs Göç İdaresi 17.09.2026. 5-17 yaş Suriyeli = il toplamı × ülke payı (773.094/2.210.644). 81 ilde korelasyon 0,90.",
        )

    # 9. Upper-secondary composition by province, latest year.
    lise = [
        "upper_secondary_general",
        "upper_secondary_vocational",
        "imam_hatip_upper_secondary",
        "open_upper_secondary",
    ]
    comp = (
        data.filter(
            (pl.col("measure") == "Öğrenci")
            & (pl.col("year") == max(ys3))
            & pl.col("type").is_in(lise)
        )
        .group_by("area_id", "type")
        .agg(pl.col("value").sum())
        .pivot(on="type", index="area_id", values="value")
    )
    comp = comp.with_columns(pl.sum_horizontal(lise).alias("top"))
    rows = []
    for r in comp.iter_rows(named=True):
        shares = [100 * r[k] / r["top"] for k in lise]
        rows.append(
            [
                names[r["area_id"]],
                *[r[k] for k in lise],
                r["top"],
                *shares,
                100
                * r["imam_hatip_upper_secondary"]
                / (r["top"] - r["open_upper_secondary"]),
            ]
        )
    rows.sort(key=lambda row: -row[8])
    write_sheet(
        book,
        "İl_lise_bilesimi",
        [
            "İl",
            "Genel",
            "Mesleki",
            "İmam hatip",
            "Açık",
            "Toplam",
            "Genel %",
            "Mesleki %",
            "İmam hatip %",
            "Açık %",
            "İmam hatip % (örgün içinde)",
        ],
        rows,
        f"{max(ys3)}-{str(max(ys3) + 1)[2:]} lise öğrencisi, tür payları (açık dahil toplam içinde); imam hatip payına göre sıralı.",
    )

    notes = [
        [
            "Kaynak",
            "MEB istatistik portalı (elle indirilen Excel'ler) + TÜİK MEDAS; depo göstergeleri *_by_type, class_sections, net_enrollment_rate, population.",
        ],
        ["Yıl", "2024 = 2024-25 öğretim yılı. Nüfus: 1 Ocak 2025 ADNKS."],
        [
            "Okul öncesi",
            "Anaokulu + anasınıfı. MEDAS okul/derslik/öğretmende anasınıfını saymaz; burada sayılır.",
        ],
        [
            "Açıköğretim",
            "Öğrencide ayrı tür; öğretmen ve derslik oranlarında paya girmez.",
        ],
        [
            "Portal hataları",
            "2014-15 okul öncesi öğrenci: düzeltilmiş kopya. 2013-14 (2 il) ve 2014-15 (9 il) lise öğretmen tür kırılımı atlandı; il toplamı MEDAS'ta doğru.",
        ],
        [
            "Açık okullar",
            "Portal okul dosyalarında açık ortaokul/lise okulu yok; MEDAS'tan 1-3 okul eksik (Ankara, İstanbul).",
        ],
        [
            "5-17 yaş",
            "ADNKS tek yaş, 5-17 toplamı. Öğrenci açıköğretim dahil olduğundan oran %100'ü aşabilir (yaş dışı açık lise öğrencileri).",
        ],
        [
            "Okul",
            "Anasınıfları okul sayılmaz (ilkokul içinde); derslik ve öğretmende anasınıfı dahildir. Öğretmen toplamı bu yüzden MEB'in açıkladığından ~47 bin fazla.",
        ],
    ]
    write_sheet(book, "Notlar", ["Konu", "Açıklama"], notes)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    book.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
