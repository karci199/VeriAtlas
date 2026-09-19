r"""Retail trade, monthly: the volume of what is sold and the lira it is sold for.

TÜİK publishes both as indices on 2015 = 100, by NACE retail group, each in three
versions — raw, calendar-adjusted, and seasonally-and-calendar-adjusted. The files sit in
the data-portal download (`C:\veri-ham\tuik_portal\dosya\tablo`, fetched 2026-09-18):

    00216  perakende satış hacim endeksi, sabit fiyatlarla   → retail_volume_index
    00258  perakende ciro endeksi, cari fiyatlarla           → retail_turnover_index

Volume and turnover are the same trade measured two ways: turnover carries the price rise
with it, volume does not. Kept apart, never added.

**The series stops in 2023-12** because TÜİK rebased retail trade to 2021 = 100 and these
two tables were closed on the old base. The newer base is a separate series and belongs in
its own indicator; splicing them would put a break in the middle and call it a trend.

The sheet is three header rows deep and the blocks repeat:

    row 3   sector, written once over its block
    row 4   adjustment, written once over its columns
    row 5   the measure — `Endeks`, `Yıllık değişim`, `Aylık değişim`

Only the index columns are read. The two change columns are that column's own arithmetic,
and storing a number the store can compute is how two versions of one series end up
disagreeing after a revision.

Two traps, both silent:

* **The year is written once per year, the month on every row.** A reader that takes the
  year from its own row gets twelve values for 2010 and blanks for everything after it.
* **The footer is a row like any other.** `TurkStat, Retail sales...` sits in the year
  column under the data; parsed as a year it raises, which is the good case — the bad one
  is a reader that skips silently and never says how many rows it dropped.
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
    "retail_volume_index": "00216_Perakende Satış Hacim Endeksi ve Değişim Oranları Sabit Fiyatlarla 2015100.xls",
    "retail_turnover_index": "00258_Perakende Ciro Endeksi ve Değişim Oranları Cari Fiyatlarla 2015100.xls",
}

SECTOR_ROW, ADJUST_ROW, MEASURE_ROW, FIRST_ROW = 3, 4, 5, 6

#: The source's own sector names, shortened to ids. Anything not in here stops the run:
#: TÜİK adds groups between revisions and a new one must be named, not dropped.
SECTORS = {
    "Perakende ticaret": "total",
    "Gıda, içecek ve tütün": "food",
    "Gıda dışı (otomotiv yakıtı hariç)": "non_food",
    "Bilgisayar, bilgisayar donanım ve yazılımları, kitap, iletişim aygıtları vb.": "computers_books",
    "Ses ve görüntü cihazları, hırdavat, boya ve cam, elektrikli ev aletleri, mobilya vb.": "household_goods",
    "Tekstil, giyim ve ayakkabı": "textiles_clothing",
    "Eczacılık ürünleri,  tıbbi ve ortopedik ürünler, kozmetik ve kişisel bakım malzemeleri": "pharmacy_cosmetics",
    "Posta yoluyla veya internet üzerinden": "mail_internet",
    "Otomotiv yakıtı": "automotive_fuel",
}
ADJUSTMENTS = {
    "Arındırılmamış": "none",
    "Takvim etkilerinden": "calendar",
    "Mevsim ve takvim": "seasonal_calendar",
}


def first_line(cell: object) -> str:
    return str(cell).split("\n")[0].strip()


def columns_of(sheet) -> dict[int, tuple[str, str]]:
    """Column → (sector, adjustment), for the index columns only."""
    found: dict[int, tuple[str, str]] = {}
    sector = adjustment = None
    for column in range(2, sheet.ncols):
        head = first_line(sheet.cell_value(SECTOR_ROW, column))
        if head:
            if head not in SECTORS:
                raise KeyError("tanınmayan perakende grubu: " + head)
            sector, adjustment = SECTORS[head], None
        block = first_line(sheet.cell_value(ADJUST_ROW, column))
        if block:
            if block not in ADJUSTMENTS:
                raise KeyError("tanınmayan arındırma: " + block)
            adjustment = ADJUSTMENTS[block]
        if (
            first_line(sheet.cell_value(MEASURE_ROW, column)).startswith("Endeks")
            and sector
            and adjustment
        ):
            found[column] = (sector, adjustment)
    if not found:
        raise ValueError("endeks sütunu bulunamadı")
    return found


def read(path: Path):
    """(sector, adjustment, period, value) for every filled index cell."""
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
        month = int(float(month_cell))
        period = dt.date(year, month, 1)
        for column, (sector, adjustment) in columns.items():
            value = sheet.cell_value(row, column)
            if not isinstance(value, float):
                continue
            out.append((sector, adjustment, period, value))
    return out


class RetailIndex:
    source_id = "tuik_portal"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER / FILES[self.indicator_id]

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "indicator_id": self.indicator_id,
                "area_id": "TR",
                "area_level": "country",
                "period_start": period,
                "frequency": "monthly",
                "dims": format_dims(
                    {"retail_sector": sector, "adjustment": adjustment}
                ),
                "value": value,
                "unit": "index",
                "quality_flag": "measured",
                "vintage": VINTAGE,
                "source_id": self.source_id,
                "retrieved_at": RETRIEVED,
            }
            for sector, adjustment, period, value in read(raw)
        ]
        if not records:
            raise ValueError(f"{self.indicator_id}: satır yok")
        return pl.DataFrame(records)


RETAIL_ADAPTERS = {
    name: type(
        "Retail" + name.title().replace("_", ""), (RetailIndex,), {"indicator_id": name}
    )
    for name in FILES
}
