"""Registered vehicles by province, alongside population and households.

A file, not a screen: the underlying indicator (`vehicles`) is a single snapshot, so
the explorer has nowhere to put a per-capita or per-household ratio (K12/K13 — only
people and their events divide by the population, and a vehicle is neither). Those
ratios are real questions with a right answer, they just live in a spreadsheet instead
of a screen mode.

Sheet **İller**: total vehicles, population, vehicles per 1.000 people, the tractor
count on its own, the tractor's share of the province's own fleet, households, and
vehicles per household. Sorted by vehicles per 1.000 people, which is the number the
2026-08-17 session's finding turned on.

Two more sheets rank the province list by each ratio on its own, with a sıra column —
**Nüfusa göre** by vehicles per 1.000 people, **Haneye göre** by vehicles per household.
Both numbers already sit in İller; these exist because the two rankings do not agree
(Manisa's tractor fleet moves it up the household ranking and not the population one),
and a reader comparing two sheets side by side sees that faster than sorting one column
twice.

Run:  uv run python scripts/build_vehicle_excel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

TARGET = Path("cikti/tasit-analizi.xlsx")


def main() -> None:
    vehicles = pl.read_csv(PUBLIC / "vehicles.csv.gz")
    population = pl.read_csv(PUBLIC / "population.csv.gz")
    households = pl.read_csv(PUBLIC / "household-count.csv.gz")

    total_vehicles = (
        vehicles.filter(pl.col("level") == "province")
        .group_by("area_id", "area")
        .agg(pl.col("value").sum().alias("tasit_toplam"))
    )
    tractors = vehicles.filter(
        (pl.col("level") == "province") & (pl.col("vehicle_type") == "tractor")
    ).select("area_id", pl.col("value").alias("traktor"))

    pop_year = population.filter(pl.col("level") == "province")["year"].max()
    pop = (
        population.filter(
            (pl.col("level") == "province") & (pl.col("year") == pop_year)
        )
        .group_by("area_id")
        .agg(pl.col("value").sum().alias("nufus"))
    )

    hh_year = households.filter(pl.col("level") == "province")["year"].max()
    hh = households.filter(
        (pl.col("level") == "province") & (pl.col("year") == hh_year)
    ).select("area_id", pl.col("value").alias("hane"))

    table = (
        total_vehicles.join(tractors, on="area_id", how="left")
        .join(pop, on="area_id", how="left")
        .join(hh, on="area_id", how="left")
        .with_columns(
            (pl.col("tasit_toplam") / pl.col("nufus") * 1000).alias("bin_kisi_basina"),
            (pl.col("traktor") / pl.col("tasit_toplam")).alias("traktor_payi"),
            (pl.col("tasit_toplam") / pl.col("hane")).alias("hane_basina"),
        )
        .rename({"area": "il"})
        .select(
            "il",
            "tasit_toplam",
            "nufus",
            "bin_kisi_basina",
            "traktor",
            "traktor_payi",
            "hane",
            "hane_basina",
        )
        .sort("bin_kisi_basina", descending=True)
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
    text = book.add_format({"align": "left", "valign": "vcenter"})
    sayi = book.add_format(
        {"num_format": "#,##0", "align": "center", "valign": "vcenter"}
    )
    oran = book.add_format(
        {"num_format": "#,##0.0", "align": "center", "valign": "vcenter"}
    )
    yuzde = book.add_format(
        {"num_format": "0.0%", "align": "center", "valign": "vcenter"}
    )

    columns = [
        ("il", "İl", 16, text),
        ("tasit_toplam", "Toplam taşıt", 14, sayi),
        ("nufus", "Nüfus (" + str(pop_year) + ")", 12, sayi),
        ("bin_kisi_basina", "Bin kişi başına taşıt", 16, oran),
        ("traktor", "Traktör (mutlak)", 14, sayi),
        ("traktor_payi", "Traktörün il filosundaki payı", 18, yuzde),
        ("hane", "Hane sayısı (" + str(hh_year) + ")", 14, sayi),
        ("hane_basina", "Hane başına taşıt", 14, oran),
    ]

    def write_sheet(name: str, rows: pl.DataFrame, cols: list[tuple]) -> None:
        sheet = book.add_worksheet(name)
        for col, (_, label, width, fmt) in enumerate(cols):
            sheet.write(0, col, label, head)
            sheet.set_column(col, col, width, fmt)
        sheet.freeze_panes(1, 1)
        for row_index, row in enumerate(rows.iter_rows(named=True), start=1):
            for col, (key, _, _, _) in enumerate(cols):
                sheet.write(row_index, col, row[key])

    write_sheet("İller", table, columns)

    sira = book.add_format({"num_format": "0", "align": "center", "valign": "vcenter"})

    write_sheet(
        "Nüfusa göre",
        table.sort("bin_kisi_basina", descending=True).with_row_index("sira", offset=1),
        [
            ("sira", "Sıra", 8, sira),
            ("il", "İl", 16, text),
            ("bin_kisi_basina", "Bin kişi başına taşıt", 16, oran),
            ("tasit_toplam", "Toplam taşıt", 14, sayi),
            ("nufus", "Nüfus (" + str(pop_year) + ")", 12, sayi),
        ],
    )

    write_sheet(
        "Haneye göre",
        table.sort("hane_basina", descending=True).with_row_index("sira", offset=1),
        [
            ("sira", "Sıra", 8, sira),
            ("il", "İl", 16, text),
            ("hane_basina", "Hane başına taşıt", 14, oran),
            ("tasit_toplam", "Toplam taşıt", 14, sayi),
            ("hane", "Hane sayısı (" + str(hh_year) + ")", 14, sayi),
        ],
    )

    notes = book.add_worksheet("Notlar")
    notes.set_column(0, 0, 110, book.add_format({"text_wrap": True, "valign": "top"}))
    lines = [
        "VeriAtlas — taşıt analizi",
        "",
        "Kaynak: TÜİK, İllere göre motorlu kara taşıtları sayısı, Temmuz 2026.",
        "Tek kesit — zaman serisi yok, yalnız bu ayın fotoğrafı.",
        "",
        (
            "İller sayfası her iki oranı da taşır; Nüfusa göre ve Haneye göre "
            "sayfaları aynı oranları tek başına sıralar, sıra numarasıyla — iki "
            "sıralama aynı değil (Manisa hanede öne çıkıyor, nüfusta çıkmıyor)."
        ),
        "",
        "Bin kişi başına taşıt = toplam taşıt / il nüfusu ("
        + str(pop_year)
        + ") × 1.000.",
        (
            "Turizm ve sera tarımı yoğun illerde (Muğla, Burdur, Antalya, Aydın, Isparta) "
            "bu oran 500'ün üzerine çıkıyor — muhtemelen mevsimlik/ikinci konut "
            "sahiplerinin aracı o ile kayıtlı ama nüfusa dahil değil, ve tarım "
            "işletmelerinin filosu kişi başına değil işletme başına."
        ),
        "",
        (
            "Traktörün il filosundaki payı = traktör sayısı / o ilin toplam taşıt "
            "sayısı. Mutlak sayı da ayrı sütunda: pay yüksek görünse de küçük bir "
            "ilde küçük bir sayı olabilir, ikisi birlikte okunmalı."
        ),
        "",
        (
            "Hane başına taşıt = toplam taşıt / hane sayısı (" + str(hh_year) + "). "
            "Nüfus yerine hane kullanmak turizm/ikinci-konut çarpıtmasını azaltmaz — "
            "ikinci konutlar da ayrı hane sayılmıyor MEDAS'ta — ama aile büyüklüğü "
            "farkını (doğuda daha büyük hane) devre dışı bırakıyor."
        ),
        "",
        (
            "per_capita ekranda kasıtlı kapalı (indicators.toml, unit.vehicle): proje "
            "kuralı yalnız insan ve insanların başına gelen olayları (doğum, ölüm, "
            "evlenme, boşanma) nüfusa bölmeye izin veriyor. Bu yüzden bu oranlar "
            "ekranda değil, burada."
        ),
    ]
    for i, line in enumerate(lines):
        notes.write(i, 0, line)

    book.close()
    print("yazildi:", TARGET, len(table), "il")


if __name__ == "__main__":
    main()
