r"""Muhasebat: general budget revenue by province, accrued and collected, 2004-2025.

`scripts/fetch_muhasebat.py` keeps one workbook per province and year (plus 00-Merkez, revenue
booked centrally, not written) in `C:\veri-ham\muhasebat\genel_butce_gelirleri\<year>\`. Folder
2008 also holds the 2006 and 2007 files; the year is read from the file name. 2026 is a year to
date and is not loaded.

Each workbook has one sheet a month, cumulative; ARALIK (December) is the year. Where a file has
no ARALIK sheet (2007 Bitlis stops at KASIM) the year is not written for that province.

The label column is the one left of the "Tahakkuk" header (2015 and 2020 files start a column
later). Kept lines, by their label: the general budget total, tax revenue, income tax, corporate
tax, domestic VAT, special consumption tax (ÖTV) and motor vehicle tax (from 2006; 2004-2005
print no such line). A label can recur further down (2018 Çankırı: "Gelir Vergisi" again in
another block); the first printing is kept. 2004-2005 print "Dahilde Alınan Katma Değer Vergisi"
twice before ÖTV, the group and the tax itself indented under it: the later one is kept.

Units: thousand lira throughout ("Milyar TL" in 2004-2005 is a thousand new lira, "Bin YTL"
2005-2008 likewise).

Checks: every province has one file a year; each kept line appears; tax ≤ total and
income + corporate tax ≤ tax, on accruals (collections net off refunds, so a part can exceed the
whole: 2018 Çankırı collected 92,906 of tax and 138,504 of income and corporate tax). A
province-year that breaks the check is left out whole; more than MAX_PROBLEMS stops the load.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold

FOLDER = (
    RAW / "muhasebat" / "genel_butce_gelirleri"
    if (RAW / "muhasebat").exists()
    else Path("C:/veri-ham/muhasebat/genel_butce_gelirleri")
)
LAST_YEAR = 2025
#: revenue line -> folded label, optional roman or letter prefix
LINES = {
    "total": r"genelbutcegelirleri",
    "tax": r"i?vergigelirleri",
    "income_tax": r"a?gelirvergisi",
    "corporate_tax": r"b?kurumlarvergisi",
    "domestic_vat": r"a?dahildealinankatmadegervergisi",
    "special_consumption_tax": r"b?ozeltuketimvergisi",
    "motor_vehicle_tax": r"b?motorlutasitlarvergisi",
}
OPTIONAL = {"motor_vehicle_tax"}  # not printed in 2004-2005
MEASURES = ("accrued", "collected")
#: province-years left out because the file contradicts itself (see load_all)
PROBLEMS: list[str] = []
MAX_PROBLEMS = 20


def files() -> dict[tuple[str, int], Path]:
    out: dict[tuple[str, int], Path] = {}
    for path in FOLDER.glob("*/*.xls*"):
        found = re.match(r"(\d{2}).*?[-_](20\d\d)", path.name)
        if not found:
            raise ValueError(f"Muhasebat: dosya adı okunamadı {path.name}")
        code, year = found.group(1), int(found.group(2))
        if code == "00" or year > LAST_YEAR:
            continue
        key = (f"TR-{code}", year)
        if key in out:
            raise ValueError(f"Muhasebat: {key} iki dosya")
        out[key] = path
    return out


def read(path: Path) -> dict[tuple[str, str], float] | None:
    """{(line, measure): thousand lira} from the December sheet, None if there is none."""
    from python_calamine import CalamineWorkbook

    book = CalamineWorkbook.from_path(path)
    december = [n for n in book.sheet_names if fold(n) == "aralik"]
    if not december:
        return None
    rows = book.get_sheet_by_name(december[0]).to_python()
    header = next(
        (i, j)
        for i, row in enumerate(rows)
        for j, cell in enumerate(row)
        if fold(str(cell)) == "tahakkuk"
    )
    label_col = header[1] - 1
    matches: dict[str, list[tuple[int, list]]] = {}
    for i, row in enumerate(rows[header[0] + 1 :]):
        label = re.sub(r"^\d+", "", fold(str(row[label_col])))
        for line, pattern in LINES.items():
            if re.fullmatch(pattern, label):
                matches.setdefault(line, []).append((i, row))
    out: dict[tuple[str, str], float] = {}
    for line, found in matches.items():
        # The first printing, except domestic VAT: 2004-2005 print the group and, indented
        # under it and before the special consumption tax, the tax itself.
        chosen = found[0][1]
        if line == "domestic_vat" and "special_consumption_tax" in matches:
            before = [
                r for i, r in found if i < matches["special_consumption_tax"][0][0]
            ]
            chosen = before[-1] if before else chosen
        for k, measure in enumerate(MEASURES):
            cell = chosen[header[1] + k]
            out[(line, measure)] = float(cell) if cell not in ("", None) else 0.0
    missing = {line for line in LINES if (line, "accrued") not in out} - OPTIONAL
    if missing:
        raise ValueError(f"Muhasebat {path.name}: satır yok {sorted(missing)}")
    # Collections net off refunds (VAT refunds turn lines negative), so a part can exceed its
    # whole there; the check is made on accruals.
    for measure in ("accrued",):
        total, tax = out[("total", measure)], out[("tax", measure)]
        parts = out[("income_tax", measure)] + out[("corporate_tax", measure)]
        if tax > total + 1 or parts > tax + 1:
            PROBLEMS.append(
                f"{path.name} {measure}: toplam {total:,.0f}, vergi {tax:,.0f}, "
                f"gelir+kurumlar {parts:,.0f}"
            )
            return None
    return out


def load_all() -> list[dict]:
    found = files()
    years = {year for _, year in found}
    for year in years:
        have = {area for area, y in found if y == year}
        if len(have) != 81:
            raise ValueError(f"Muhasebat {year}: {len(have)} il")
    rows = []
    PROBLEMS.clear()
    for (area, year), path in sorted(found.items()):
        values = read(path)
        if values is None:
            continue
        for (line, measure), value in values.items():
            rows.append(
                {
                    "area_id": area,
                    "period_start": dt.date(year, 1, 1),
                    "dims": f"budget_measure={measure};revenue_line={line}",
                    "value": value,
                }
            )
    if len(PROBLEMS) > MAX_PROBLEMS:
        raise ValueError(f"Muhasebat: {len(PROBLEMS)} tutarsız il-yıl: {PROBLEMS[:5]}")
    return rows


class MuhasebatRevenue:
    source_id = "muhasebat"
    indicator_id = "budget_revenue_by_province"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        return pl.DataFrame(
            load_all(), schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("thousand_try").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


MUHASEBAT_ADAPTERS = {"budget_revenue_by_province": MuhasebatRevenue}
