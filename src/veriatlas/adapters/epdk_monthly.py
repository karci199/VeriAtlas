"""EPDK monthly market reports: province series month by month.

Natural gas (`dogalgaz_resmi`, Word, 2015-2025): Tablo 5.2, consumption by province and
supply form, million Sm3 to two decimals. `scripts/extract_epdk_docx_tables.py` flattens
the reports into `raw/epdk/docx_gaz_aylik_cells.parquet`. The month is read from the table's
own caption ("Ocak 2025 Doğal Gaz Tüketiminin İllere ..."); a month found twice stops the
load. Every table is checked row by row against its printed total and nationally.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .epdk_history import GAS_SUPPLY, wide_table
from .kgm import fold

GAS_MONTHLY_CELLS = RAW / "epdk" / "docx_gaz_aylik_cells.parquet"
MONTHS = [
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
]
MONTH_IN_CAPTION = re.compile(r"(" + "|".join(MONTHS) + r")\s+(20\d\d)")

#: Months with no Word report on the EPDK page, filled in when a source is found.
MISSING_MONTHS: list[str] = []
#: Months whose report has no supply-form breakdown (province totals only).
TOTAL_ONLY_MONTHS: list[str] = []


def grids(cells: pl.DataFrame, caption: str):
    """One grid per report: a table split over pages is two Word tables under one caption."""
    tables = cells.filter(pl.col("caption").str.contains(caption, literal=True))
    for (file,), per_file in tables.group_by(["file"]):
        grid: list[list[str]] = []
        for (_table,), group in sorted(
            per_file.group_by(["table"]), key=lambda x: x[0]
        ):
            rows: dict[int, dict[int, str]] = {}
            for r, c, t in group.select("row", "col", "text").iter_rows():
                rows.setdefault(r, {})[c] = t
            grid += [
                [rows[r].get(c, "") for c in range(max(rows[r]) + 1)]
                for r in sorted(rows)
            ]
        yield file, per_file["caption"][0], grid


class GasConsumptionMonthly:
    source_id = "epdk"
    indicator_id = "epdk_natural_gas_consumption_monthly"

    def fetch(self) -> Path:
        return GAS_MONTHLY_CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        cells = pl.read_parquet(GAS_MONTHLY_CELLS)
        seen: dict[dt.date, str] = {}
        seen_grids: dict[dt.date, list] = {}
        records = []
        for file, caption, grid in grids(cells, "Tablo 5.2 "):
            found = MONTH_IN_CAPTION.search(caption)
            if not found:
                raise ValueError(f"doğalgaz aylık {file}: ay okunamadı: {caption}")
            month = dt.date(int(found.group(2)), MONTHS.index(found.group(1)) + 1, 1)
            if month in seen:
                # EPDK lists one September 2017 report twice (under two months, same
                # bytes): an identical copy is skipped, a different one stops the load.
                if seen_grids[month] != grid:
                    raise ValueError(
                        f"doğalgaz aylık {month}: iki farklı rapor {seen[month]} {file}"
                    )
                continue
            seen[month] = file
            seen_grids[month] = grid
            # The header is repeated after each page break; provinces with no gas that
            # month are left out of the table, so the count is taken from the table itself.
            # July 2019 opens with a "YIL / AY" block above the header.
            start = next(
                (
                    i
                    for i, line in enumerate(grid)
                    if any("boru" in c.lower() for c in line)
                ),
                None,
            )
            if start is None:
                # January 2015 prints each province's total only, against January 2014.
                if month == dt.date(2015, 1, 1):
                    TOTAL_ONLY_MONTHS.append(f"{month:%Y-%m}")
                    continue
                raise ValueError(f"doğalgaz aylık {month}: başlık yok {grid[0]}")
            grid = grid[start:]
            grid = [grid[0]] + [
                [clean(c) for c in line] for line in grid[1:] if line != grid[0]
            ]
            table = wide_table(
                grid,
                GAS_SUPPLY,
                f"doğalgaz aylık {month:%Y-%m}",
                rounding=0.02,
                provinces=len(_province_ids(grid)),
            )
            if len(table) < 70 or not all(table.values()):
                raise ValueError(
                    f"doğalgaz aylık {month}: sütunlar okunamadı {grid[0]}"
                )
            for area, kinds in table.items():
                for kind, value in kinds.items():
                    records.append(
                        {
                            "area_id": area,
                            "period_start": month,
                            "dims": f"gas_supply={kind}",
                            "value": value * 1e6,
                        }
                    )
        start, end = min(seen), max(seen)
        expected = {
            dt.date(y, m, 1)
            for y in range(start.year, end.year + 1)
            for m in range(1, 13)
            if dt.date(y, m, 1) <= end
        }
        MISSING_MONTHS[:] = sorted(
            f"{d:%Y-%m}"
            for d in expected - set(seen)
            if f"{d:%Y-%m}" not in TOTAL_ONLY_MONTHS
        )
        if len(MISSING_MONTHS) > 3:
            raise ValueError(f"doğalgaz aylık: çok ay eksik {MISSING_MONTHS}")
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("monthly").alias("frequency"),
            pl.lit("m3").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit("epdk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
        )


def clean(cell: str) -> str:
    """Footnote stars off; a stray "-0.02" (dot decimal, a correction) to Turkish "-0,02"."""
    cell = cell.strip().rstrip("*")
    if re.fullmatch(r"-\s+[\d.,]+", cell):
        cell = "-" + cell[1:].strip()
    if re.fullmatch(r"-?0\.\d+", cell):
        cell = cell.replace(".", ",")
    return cell


def _province_ids(grid) -> set[str]:
    from .epdk_history import province_or_none

    return {p for line in grid[1:] if line and (p := province_or_none(line[0]))}


EPDK_MONTHLY_ADAPTERS = {
    "epdk_natural_gas_consumption_monthly": GasConsumptionMonthly,
}

PETROL_MONTHLY_CELLS = RAW / "epdk" / "docx_petrol_aylik_cells.parquet"


def report_month(path: Path) -> dt.date:
    """The month a monthly Word report covers, from its cover ("PETROL PİYASASI ... MART 2015")."""
    import zipfile
    from xml.etree import ElementTree as ET

    from .kgm import fold

    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    body = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml")).find(
        w + "body"
    )
    head = " ".join(
        "".join(t.text or "" for t in p.iter(w + "t"))
        for p in list(body)[:80]
        if p.tag == w + "p"
    )
    words = re.findall(r"\w+", head)
    months = {fold(name): i + 1 for i, name in enumerate(MONTHS)}
    for i, word in enumerate(words[:-1]):
        if fold(word) in months and re.fullmatch(r"20\d\d", words[i + 1]):
            return dt.date(int(words[i + 1]), months[fold(word)], 1)
    raise ValueError(f"{path.name}: rapor ayı okunamadı")


class FuelSalesMonthly:
    """Petrol monthly reports, Tablo 3.1: domestic sales by province and product (tonnes).

    The table is the month's own sales, not the year to date: the twelve months of 2017 add
    up to 28.45 million tonnes against 28.46 in the yearly report.
    """

    source_id = "epdk"
    indicator_id = "epdk_fuel_sales_monthly"

    def fetch(self) -> Path:
        return PETROL_MONTHLY_CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        from .epdk_history import FILES, PETROL_PRODUCTS

        cells = pl.read_parquet(PETROL_MONTHLY_CELLS)
        seen: dict[dt.date, tuple[str, list]] = {}
        records = []
        for file, _caption, grid in grids(cells, "Tablo 3.1. İllere Göre Yurtiçi"):
            month = report_month(FILES / "petrol_resmi" / file)
            if month in seen:
                if seen[month][1] != grid:
                    raise ValueError(
                        f"akaryakıt aylık {month}: iki farklı rapor {seen[month][0]} {file}"
                    )
                continue  # October 2016 is listed twice, same bytes
            seen[month] = (file, grid)
            table = wide_table(grid, PETROL_PRODUCTS, f"akaryakıt aylık {month:%Y-%m}")
            for area, kinds in table.items():
                for kind, value in kinds.items():
                    records.append(
                        {
                            "area_id": area,
                            "period_start": month,
                            "dims": f"fuel_product={kind}",
                            "value": value,
                        }
                    )
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("monthly").alias("frequency"),
            pl.lit("tonne").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit("epdk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
        )


EPDK_MONTHLY_ADAPTERS["epdk_fuel_sales_monthly"] = FuelSalesMonthly


LPG_MONTHLY_CELLS = RAW / "epdk" / "docx_lpg_aylik_cells.parquet"
#: (month, printed national total, sum of provinces) where the TOPLAM row is not theirs.
LPG_TOTAL_SLIPS: list[tuple[str, float, float]] = []


class LpgSalesMonthly:
    """LPG monthly reports, Tablo 3.9 (3.6 in some): sales by province and product (tonnes).

    Two header rows: the product names, then "Satış (ton) | Pay (%)" under each. The share
    columns are dropped; the month comes from the caption ("Temmuz 2017 Döneminde").
    Total columns are printed to two decimals, so rows are checked to within 0.05 t.
    """

    source_id = "epdk"
    indicator_id = "epdk_lpg_sales_monthly"

    def fetch(self) -> Path:
        return LPG_MONTHLY_CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        from .epdk import LPG_PRODUCTS
        from .epdk_history import number_tr

        cells = pl.read_parquet(LPG_MONTHLY_CELLS)
        seen: dict[dt.date, tuple[str, list]] = {}
        records = []
        found_grids = [
            *grids(cells, "LPG Satışlarının İllere ve Ürün Türüne Göre"),
            # 2015-2016 wording; the caption can sit over a monthly summary table first.
            *grids(cells, "satışlarının illere ve ürünlere göre"),
        ]
        for file, caption, grid in found_grids:
            start = next(
                (i for i, line in enumerate(grid) if line and fold(line[0]) == "il"),
                None,
            )
            if start is None:
                raise ValueError(f"LPG aylık {file}: il tablosu yok: {caption}")
            grid = grid[start:]
            found = MONTH_IN_CAPTION.search(caption)
            if not found or "-" in caption.lower().split("dönem")[0]:
                raise ValueError(f"LPG aylık {file}: tek ay değil: {caption}")
            month = dt.date(int(found.group(2)), MONTHS.index(found.group(1)) + 1, 1)
            if month in seen:
                if seen[month][1] != grid:
                    raise ValueError(
                        f"LPG aylık {month}: iki farklı rapor {seen[month][0]} {file}"
                    )
                continue
            seen[month] = (file, grid)
            header = ["İl"]
            for name in grid[0][1:]:
                header += [name, ""]  # sales, then its share column
            rows = [
                [clean(c) for c in line]
                for line in grid[1:]
                if line
                and line[0].strip()
                and line != grid[0]
                and "Satış" not in " ".join(line)
            ]
            totals = [
                r for r in rows if r[0].strip().lower() in ("toplam", "genel toplam")
            ]
            body = [r for r in rows if r not in totals]
            table = wide_table(
                [header, *body],
                LPG_PRODUCTS,
                f"LPG aylık {month:%Y-%m}",
                rounding=0.05,
                provinces=len(_province_ids([header, *body])),
            )
            # The printed TOPLAM row is sometimes another month's (April 2021: 320,987 t
            # against 285,572 t of provinces). The share column is the check that holds:
            # each province's printed share of the total must match its share of the sum.
            national = sum(sum(v.values()) for v in table.values())
            for r in body:
                share = number_tr(r[8]) if len(r) > 8 else None
                total = number_tr(r[7]) if len(r) > 7 else None
                if share is not None and total and share >= 1:
                    if (
                        abs(total / national * 100 - share) > 0.06
                    ):  # shares printed to 1-2 decimals
                        raise ValueError(
                            f"LPG aylık {month}: {r[0]} payı {share} ama hesap "
                            f"{total / national * 100:.2f}"
                        )
            if totals and abs((number_tr(totals[0][7]) or 0) - national) > 1:
                LPG_TOTAL_SLIPS.append(
                    (f"{month:%Y-%m}", number_tr(totals[0][7]), national)
                )
            if len(table) < 75:
                raise ValueError(f"LPG aylık {month}: {len(table)} il")
            for area, kinds in table.items():
                for kind, value in kinds.items():
                    records.append(
                        {
                            "area_id": area,
                            "period_start": month,
                            "dims": f"lpg_product={kind}",
                            "value": value,
                        }
                    )
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("monthly").alias("frequency"),
            pl.lit("tonne").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit("epdk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
        )


EPDK_MONTHLY_ADAPTERS["epdk_lpg_sales_monthly"] = LpgSalesMonthly
