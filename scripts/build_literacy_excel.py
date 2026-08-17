"""Literacy status (okuma yazma durumu) — province time series, district snapshot,
age-band breakdown, in one spreadsheet.

Three sources, three sheets:

* **İller** — `literacy` (15+, 2008-2025, il+Türkiye). The illiteracy rate (okuma yazma
  bilmeyen ÷ toplam) is computed here, not stored: the fact table keeps counts, and a
  rate is a reading of them, the same K12 rule every other screen ratio follows.
* **İlçeler** — `literacy_district` (15+, 2008 and 2025 only). Same rate, at the finer
  level the time series does not reach.
* **Yaş Grubu** — `literacy_by_age` (6+, 2008 and 2025, Türkiye toplamı): where
  illiteracy actually sits in the age structure, which the 15+ total cannot show —
  a high overall rate could be old-cohort concentration or spread evenly, and only
  the age bands say which.

Run:  uv run python scripts/build_literacy_excel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import xlsxwriter

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

TARGET = Path("cikti/okuma-yazma-analizi.xlsx")


def illiteracy_rate(df: pl.DataFrame, group: list[str]) -> pl.DataFrame:
    """Okuma yazma bilmeyen ÷ toplam (Bilinmeyen dahil), grouped by `group` + year."""
    totals = df.group_by([*group, "year"]).agg(pl.col("value").sum().alias("toplam"))
    illiterate = (
        df.filter(pl.col("literacy_status") == "illiterate")
        .group_by([*group, "year"])
        .agg(pl.col("value").sum().alias("bilmeyen"))
    )
    return totals.join(illiterate, on=[*group, "year"], how="left").with_columns(
        (pl.col("bilmeyen") / pl.col("toplam")).alias("oran")
    )


def main() -> None:
    province = pl.read_csv(PUBLIC / "literacy.csv.gz")
    district = pl.read_csv(PUBLIC / "literacy-15-district.csv.gz")
    by_age = pl.read_csv(PUBLIC / "literacy-yas.csv.gz")

    il = illiteracy_rate(
        province.filter(pl.col("level") == "province"), ["area_id", "area"]
    )
    il_wide = (
        il.pivot(
            values=["toplam", "bilmeyen", "oran"], index=["area", "area_id"], on="year"
        )
        .rename(
            {
                "toplam_2008": "nufus_2008",
                "toplam_2025": "nufus_2025",
                "oran_2008": "oran_2008",
                "oran_2025": "oran_2025",
            }
        )
        .with_columns((pl.col("oran_2025") - pl.col("oran_2008")).alias("fark"))
        .sort("oran_2025", descending=True)
    )

    ilce = illiteracy_rate(district, ["area_id", "area"])
    ilce_wide = (
        ilce.pivot(values=["toplam", "oran"], index=["area", "area_id"], on="year")
        .with_columns((pl.col("oran_2025") - pl.col("oran_2008")).alias("fark"))
        .sort("oran_2025", descending=True)
        .drop_nulls(["oran_2008", "oran_2025"])
    )

    yas = (
        by_age.filter(pl.col("level") == "country")
        .group_by(["age", "year"])
        .agg(
            pl.col("value").sum().alias("toplam"),
            pl.col("value")
            .filter(pl.col("literacy_status") == "illiterate")
            .sum()
            .alias("bilmeyen"),
        )
        .with_columns((pl.col("bilmeyen") / pl.col("toplam")).alias("oran"))
        .pivot(values=["toplam", "bilmeyen", "oran"], index="age", on="year")
        .sort("age")
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
    yuzde = book.add_format(
        {"num_format": "0.00%", "align": "center", "valign": "vcenter"}
    )
    fark_fmt = book.add_format(
        {"num_format": "+0.00%;-0.00%", "align": "center", "valign": "vcenter"}
    )

    def write_sheet(name, table, columns):
        sheet = book.add_worksheet(name)
        for col, (_, label, width, fmt) in enumerate(columns):
            sheet.write(0, col, label, head)
            sheet.set_column(col, col, width, fmt)
        sheet.freeze_panes(1, 1)
        for row_index, row in enumerate(table.iter_rows(named=True), start=1):
            for col, (key, _, _, _) in enumerate(columns):
                sheet.write(row_index, col, row[key])

    write_sheet(
        "İller",
        il_wide,
        [
            ("area", "İl", 16, text),
            ("nufus_2008", "15+ nüfus (2008)", 14, sayi),
            ("nufus_2025", "15+ nüfus (2025)", 14, sayi),
            ("oran_2008", "Okuma yazma bilmeyen oranı (2008)", 18, yuzde),
            ("oran_2025", "Okuma yazma bilmeyen oranı (2025)", 18, yuzde),
            ("fark", "Fark (2025 − 2008)", 14, fark_fmt),
        ],
    )

    write_sheet(
        "İlçeler",
        ilce_wide,
        [
            ("area", "İlçe", 24, text),
            ("toplam_2008", "15+ nüfus (2008)", 14, sayi),
            ("toplam_2025", "15+ nüfus (2025)", 14, sayi),
            ("oran_2008", "Okuma yazma bilmeyen oranı (2008)", 18, yuzde),
            ("oran_2025", "Okuma yazma bilmeyen oranı (2025)", 18, yuzde),
            ("fark", "Fark (2025 − 2008)", 14, fark_fmt),
        ],
    )

    write_sheet(
        "Yaş Grubu",
        yas,
        [
            ("age", "Yaş bandı", 12, text),
            ("toplam_2008", "Nüfus (2008)", 14, sayi),
            ("toplam_2025", "Nüfus (2025)", 14, sayi),
            ("oran_2008", "Okuma yazma bilmeyen oranı (2008)", 18, yuzde),
            ("oran_2025", "Okuma yazma bilmeyen oranı (2025)", 18, yuzde),
        ],
    )

    notes = book.add_worksheet("Notlar")
    notes.set_column(0, 0, 110, book.add_format({"text_wrap": True, "valign": "top"}))
    lines = [
        "VeriAtlas — okuma yazma durumu analizi",
        "",
        "Kaynak: TÜİK MEDAS, Ulusal Eğitim İstatistikleri, Okuma Yazma Durumu.",
        "",
        (
            "İller ve İlçeler sayfaları 15 yaş ve üzeri nüfusu kapsıyor. Yaş Grubu "
            "sayfası 6 yaş ve üzerini kapsıyor (farklı popülasyon, karıştırılmamalı)."
        ),
        "",
        (
            "Oran = okuma yazma bilmeyen / toplam (Bilinmeyen kategorisi paydada, "
            "payda değil — küçük ama gerçek bir pay, düşürülmedi)."
        ),
        "",
        (
            "İlçeler sayfası yalnız her iki yılda da (2008 ve 2025) veri olan ilçeleri "
            "listeliyor — 6360 sayılı yasayla değişen ilçe haritası yüzünden bazı "
            "kodlar yalnız bir yılda karşılık buluyor, onlar burada yok."
        ),
        "",
        "İller ve İlçeler zaman serisi değil, iki kesit: 2008 ve 2025.",
    ]
    for i, line in enumerate(lines):
        notes.write(i, 0, line)

    book.close()
    print("yazildi:", TARGET, "· il:", il_wide.height, "· ilce:", ilce_wide.height)


if __name__ == "__main__":
    main()
