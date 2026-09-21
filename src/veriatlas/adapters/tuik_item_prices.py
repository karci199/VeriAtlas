r"""TÜİK's average item prices: what a kilo of rice actually cost, month by month.

The consumer price index says how much prices moved; this says what the price *was*, in
lira, for 409 items from January 2003 to April 2022 — rice, bread, a haircut, a litre of
petrol. It is the table behind the index, published as "Madde Sepeti ve Ortalama Madde
Fiyatları (Türkiye)" and downloaded with the rest of the portal's files
(`scripts/fetch_tuik_portal_files.py`, `docs/tuik-portal.md`).

Türkiye-level only, and that is the whole table — TÜİK does not publish item prices by
province. A price series with no geography is still worth having: it is the only long run
of actual lira amounts we have, and the user asked for exactly that (2026-09-19).

**Two currencies live in the same row.** On 1 January 2005 six zeros were struck off the
lira, and this table carries both sides of it without saying so: rice is `2.545.872` in
December 2004 and `2,55` in January 2005. Columns before 2005 are divided by a million.
Without that the series would show prices collapsing a millionfold in one month, and every
chart built on it would be wrong in the same place.

**The file's extension lies twice over.** The portal serves `.xls` names; some are real
BIFF files and some are zipped `xlsx`. This one is a real `.xls`, but its sibling
(`Tüketici fiyat endeksi seçilmiş maddelere ait ortalama fiyatlar`) is an `xlsx` wearing
the same suffix — so the format is decided by the first two bytes, not the name.
"""

from __future__ import annotations

import datetime as dt
import re
from functools import cache
from pathlib import Path

import polars as pl
import xlrd

from ..config import RAW

FOLDER = RAW / "tuik_portal" / "dosya"
SOURCE = "tuik_portal"

#: The file, by the number the portal download gave it.
PATTERN = "**/*01839*"

#: Header rows in the sheet: year on row 4, month name on row 5 (1-indexed).
YEAR_ROW = 3
MONTH_ROW = 4
CODE_COLUMN = 0
NAME_TR = 1
NAME_EN = 2
FIRST_DATA_COLUMN = 3

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

#: The redenomination: everything before this is old lira and is divided by a million.
NEW_LIRA = dt.date(2005, 1, 1)
OLD_LIRA_FACTOR = 1_000_000

RETRIEVED = dt.date(2026, 9, 18)
VINTAGE = "2026-09"

ITEM_CODE = re.compile(r"\d{6,8}")


def source_file() -> Path:
    found = sorted(FOLDER.glob(PATTERN))
    if not found:
        raise FileNotFoundError(
            f"TÜİK madde fiyatları dosyası yok: {FOLDER / PATTERN} "
            "(scripts/fetch_tuik_portal_files.py)"
        )
    return found[0]


@cache
def table() -> tuple[list[tuple[str, str]], list[tuple[dt.date, float]]]:
    """(items, rows) — items as (code, Turkish name), rows as (month, price) per item."""
    sheet = xlrd.open_workbook(source_file()).sheet_by_index(0)
    years = sheet.row_values(YEAR_ROW)
    months = sheet.row_values(MONTH_ROW)

    # **The year changes type halfway through the sheet.** Up to December 2008 it is a
    # number (`2008.0`) and the unit above it reads YTL; from January 2009 it is text
    # (`"2009"`) and the unit reads TL. A reader that asks `isinstance(year, float)`
    # keeps 2003-2008 and 2016-2022 and drops the 84 months in between — and the result
    # looks healthy, because what survives is contiguous at both ends. The year is read
    # as text either way.
    columns: list[tuple[int, dt.date]] = []
    for column in range(FIRST_DATA_COLUMN, sheet.ncols):
        raw_year, month = years[column], str(months[column]).strip()
        year = str(raw_year).strip()
        year = year.removesuffix(".0")
        if year.isdigit() and month in MONTHS:
            columns.append((column, dt.date(int(year), MONTHS.index(month) + 1, 1)))
    if not columns:
        raise ValueError("TÜİK madde fiyatları: ay sütunu bulunamadı, düzen değişmiş")

    items: list[tuple[str, str]] = []
    values: list[tuple[str, dt.date, float]] = []
    for row in range(sheet.nrows):
        code = str(sheet.cell_value(row, CODE_COLUMN)).strip()
        if not ITEM_CODE.fullmatch(code):
            continue
        # The name cell holds Turkish and English on two lines; only the first is ours.
        name = str(sheet.cell_value(row, NAME_TR)).split("\n")[0].strip()
        items.append((code, name))
        for column, period in columns:
            price = sheet.cell_value(row, column)
            if not isinstance(price, float) or not price:
                continue
            if period < NEW_LIRA:
                price /= OLD_LIRA_FACTOR
            values.append((code, period, price))
    return items, values


class AverageItemPrices:
    """One indicator, one row per item and month."""

    indicator_id = "average_item_price"
    source_id = SOURCE

    def fetch(self) -> Path:
        return source_file()

    def parse(self, raw: Path) -> pl.DataFrame:
        _, values = table()
        return pl.DataFrame(
            {
                "indicator_id": self.indicator_id,
                "area_id": "TR",
                "area_level": "country",
                "period_start": [period for _, period, _ in values],
                "frequency": "monthly",
                "dims": [f"cpi_item={code}" for code, _, _ in values],
                "value": [price for _, _, price in values],
                "unit": "try",
                "quality_flag": "measured",
                "vintage": VINTAGE,
                "source_id": self.source_id,
                "retrieved_at": RETRIEVED,
            }
        )


TUIK_ITEM_PRICE_ADAPTERS = {"average_item_price": AverageItemPrices}
