r"""Turnover indices for industry, construction and trade, monthly, 2015 = 100.

TÜİK's short-term turnover statistics, from the data-portal download
(`C:\veri-ham\tuik_portal\dosya\tablo`, fetched 2026-09-18):

    00104  toplam sanayi ciro endeksi   → industry_turnover_index      2005-01 →
    00102  inşaat ciro endeksi          → construction_turnover_index  2009-01 →
    00103  ticaret ciro endeksi         → trade_turnover_index         2009-01 →

Each at current prices, by NACE activity, in three versions: raw, calendar-adjusted,
seasonally-and-calendar-adjusted. Retail turnover (NACE 47 in more detail) is its own
indicator, `retail_turnover_index`; the trade file's `47` column is the same activity at
a coarser cut and is kept here only as part of trade.

The activity row mixes levels: a section (`F`, `G`, `B-C`), its divisions (`41`, `45`,
`10` ...) and, for industry, the main industrial groupings (intermediate, energy ...).
They sit side by side in one breakdown and are never added up: an index does not sum.

Layout, the same in all three files:

    row 4   activity, written once over its block
    row 6   adjustment, written once over its columns
    row 7   the measure — `Endeks`, `Yıllık değişim`, `Aylık değişim`
    row 8 → data; the year is written once per year, the month on every row

Only index columns are read; the change columns are their own arithmetic. An activity
or adjustment label the table below does not know stops the load.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl
import xlrd

from ..config import RAW
from ..schema import format_dims

FOLDER = RAW / "tuik_portal" / "dosya" / "tablo"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 18)

FILES = {
    "industry_turnover_index": "00104_Toplam Sanayi Ciro Endeksi 2015100.xls",
    "construction_turnover_index": "00102_İnşaat Ciro Endeksi 2015100.xls",
    "trade_turnover_index": "00103_Ticaret Ciro Endeksi 2015100.xls",
}
ACTIVITY_ROW, ADJUST_ROW, MEASURE_ROW, FIRST_ROW = 4, 6, 7, 8

#: Leading code of the activity label -> stored value. Main industrial groupings get a
#: `mig_` prefix so they cannot be read as NACE codes.
MIG = {
    "ARM": "mig_intermediate",
    "DLT": "mig_durable_consumer",
    "DZT": "mig_nondurable_consumer",
    "ENJ": "mig_energy",
    "SEM": "mig_capital",
}
ADJUSTMENTS = {
    "Arındırılmamış": "none",
    "Takvim etkilerinden": "calendar",
    "Mevsim ve takvim": "seasonal_calendar",
}


def activity_code(label: str) -> str:
    """`B-C - Sanayi ...` -> `b_c`, `41 - Bina inşaatı` -> `41`, `ARM-Ara malı` -> MIG id."""
    head = label.split(" ", 1)[0].split("-")
    code = label.split(" - ")[0].strip() if " - " in label else head[0]
    if code in MIG:
        return MIG[code]
    if code.isdigit() and len(code) == 2:
        return code
    if code.replace("-", "").isalpha() and len(code) <= 3:
        return code.lower().replace("-", "_")
    raise KeyError("tanınmayan ciro faaliyeti: " + label)


def first_line(cell: object) -> str:
    return str(cell).split("\n")[0].strip()


def columns_of(sheet) -> dict[int, tuple[str, str]]:
    found: dict[int, tuple[str, str]] = {}
    activity = adjustment = None
    for column in range(2, sheet.ncols):
        head = first_line(sheet.cell_value(ACTIVITY_ROW, column))
        if head:
            activity, adjustment = activity_code(head), None
        block = first_line(sheet.cell_value(ADJUST_ROW, column))
        if block:
            key = next((k for k in ADJUSTMENTS if block.startswith(k)), None)
            if key is None:
                raise KeyError("tanınmayan arındırma: " + block)
            adjustment = ADJUSTMENTS[key]
        measure = first_line(sheet.cell_value(MEASURE_ROW, column))
        if measure.startswith("Endeks") and activity and adjustment:
            found[column] = (activity, adjustment)
    if not found:
        raise ValueError("endeks sütunu bulunamadı")
    return found


def read(path: Path) -> list[tuple[str, str, dt.date, float]]:
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    columns = columns_of(sheet)
    out, year = [], None
    for row in range(FIRST_ROW, sheet.nrows):
        label = str(sheet.cell_value(row, 0)).strip()
        if label:
            try:
                year = int(float(label))
            except ValueError:
                break  # the source note under the table
        month_cell = str(sheet.cell_value(row, 1)).strip()
        if not month_cell or year is None:
            continue
        period = dt.date(year, int(float(month_cell)), 1)
        for column, (activity, adjustment) in columns.items():
            value = sheet.cell_value(row, column)
            if isinstance(value, float):
                out.append((activity, adjustment, period, value))
    return out


class TurnoverIndex:
    source_id = "tuik_portal"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER / FILES[self.indicator_id]

    def parse(self, raw: Path) -> pl.DataFrame:
        rows = read(raw)
        if not rows:
            raise ValueError(f"{self.indicator_id}: satır yok")
        frame = pl.DataFrame(
            {
                "indicator_id": self.indicator_id,
                "area_id": "TR",
                "area_level": "country",
                "period_start": [r[2] for r in rows],
                "frequency": "monthly",
                "dims": [
                    format_dims({"turnover_activity": r[0], "adjustment": r[1]})
                    for r in rows
                ],
                "value": [r[3] for r in rows],
                "unit": "index",
                "quality_flag": "measured",
                "vintage": VINTAGE,
                "source_id": self.source_id,
                "retrieved_at": RETRIEVED,
            }
        )
        if frame.select("period_start", "dims").is_duplicated().any():
            raise ValueError(f"{self.indicator_id}: aynı ay-kırılım iki kez")
        return frame


TURNOVER_ADAPTERS = {
    "tuik_" + name: type(
        "Tuik" + name.title().replace("_", ""),
        (TurnoverIndex,),
        {"indicator_id": name},
    )
    for name in FILES
}
