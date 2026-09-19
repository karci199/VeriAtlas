r"""Turkcell and Türk Telekom, from the two companies' own investor workbooks.

BTK publishes the market in total; it does not break it down by operator. These two files
do — quarterly subscriber counts straight from the companies that count them:

    C:\veri-ham\telekom\tt_ozet_2c26.xlsx    Türk Telekom, 2014Ç1-     ("Abone Verileri")
    C:\veri-ham\telekom\2C26-FO-Veri.xlsx    Turkcell, 2021Ç1-         ("Operasyonel Veriler")

Vodafone has no comparable public file, so two of the three operators are here and the
indicator says "operator", never "market".

Three things the files do that quietly produce wrong numbers:

* **The unit is in the row label, not the cell.** Türk Telekom counts in millions
  throughout; Turkcell mixes — subscribers in `milyon`, fibre and IPTV in `bin`. Every row
  is mapped with its own multiplier, and a row whose label stops saying its unit raises
  rather than loading a number a thousand times too small.
* **Two spellings of a quarter.** Türk Telekom writes `2014 1Ç`, Turkcell writes `1Ç22`.
  Both are parsed explicitly; a single regex that happened to match one of them would
  drop the other company's series entirely.
* **The totals are not comparable across the two.** Türk Telekom's mobile total includes
  M2M lines, Turkcell prints M2M separately inside its postpaid figure. Each operator's
  own definition is kept and the reader is told, rather than forcing a single definition
  neither company publishes.

ARPU is deliberately left out: Turkcell restates it under inflation accounting (IAS 29)
and Türk Telekom does not, so the two numbers are not the same measurement.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import openpyxl
import polars as pl

from ..config import RAW
from ..schema import format_dims

FOLDER = RAW / "telekom"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 19)

MILLION, THOUSAND = 1_000_000, 1_000

#: Türk Telekom, sheet "Abone Verileri": row label → (indicator, multiplier). Labels are
#: matched on their start, because the file hangs footnote marks on the end of some.
TT_ROWS = {
    "Mobil Toplam Abone Sayısı": ("telecom_mobile_subscribers", MILLION),
    "Mobil Faturalı Abone Sayısı": ("telecom_postpaid_subscribers", MILLION),
    "Mobil Ön Ödemeli Abone Sayısı": ("telecom_prepaid_subscribers", MILLION),
    "Fiber Abone Sayısı": ("telecom_fibre_subscribers", MILLION),
    "Genişbant Toplam Abone Sayısı": ("telecom_broadband_subscribers", MILLION),
    "Toplam TV Abone Sayısı": ("telecom_tv_subscribers", MILLION),
}
#: Turkcell, sheet "Operasyonel Veriler". Its fixed broadband is not published as one
#: figure, so no total is invented here — only the lines the company prints.
TURKCELL_ROWS = {
    "Abone (milyon)": ("telecom_mobile_subscribers", MILLION),
    "Faturalı Hat Abone Sayısı": ("telecom_postpaid_subscribers", MILLION),
    "Ön Ödemeli Hat Abone Sayısı": ("telecom_prepaid_subscribers", MILLION),
    "Turkcell Fiber (bin)": ("telecom_fibre_subscribers", THOUSAND),
    "IPTV (bin)": ("telecom_tv_subscribers", THOUSAND),
}

#: `2014 1Ç` (Türk Telekom) and `1Ç22` (Turkcell).
TT_PERIOD = re.compile(r"^(\d{4})\s*([1-4])Ç$")
TURKCELL_PERIOD = re.compile(r"^([1-4])Ç(\d{2})$")


def quarter_start(year: int, quarter: int) -> dt.date:
    return dt.date(year, 3 * quarter - 2, 1)


def period_of(text: str) -> dt.date | None:
    label = str(text).strip()
    found = TT_PERIOD.match(label)
    if found:
        return quarter_start(int(found.group(1)), int(found.group(2)))
    found = TURKCELL_PERIOD.match(label)
    if found:
        return quarter_start(2000 + int(found.group(2)), int(found.group(1)))
    return None


def read_sheet(
    path: Path, sheet_name: str, rows: dict, label_column: int, header_row: int
):
    """(indicator, period, value) for every quarter column the sheet fills in."""
    sheet = openpyxl.load_workbook(path, data_only=True)[sheet_name]
    periods = {}
    for column in range(1, sheet.max_column + 1):
        cell = sheet.cell(header_row, column).value
        if cell is None:
            continue
        period = period_of(cell)
        if period:
            periods[column] = period
    if not periods:
        raise ValueError(f"{path.name}/{sheet_name}: çeyrek başlığı bulunamadı")

    out = []
    for row in range(header_row + 1, sheet.max_row + 1):
        label = sheet.cell(row, label_column).value
        if not isinstance(label, str):
            continue
        cleaned = label.strip()
        match = next((v for k, v in rows.items() if cleaned.startswith(k)), None)
        if match is None:
            continue
        indicator, multiplier = match
        for column, period in periods.items():
            value = sheet.cell(row, column).value
            if not isinstance(value, (int, float)):
                continue
            out.append((indicator, period, float(value) * multiplier))
    return out


class TelecomOperators:
    source_id = "operator_ir"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        readings = [
            (
                "turk_telekom",
                read_sheet(raw / "tt_ozet_2c26.xlsx", "Abone Verileri", TT_ROWS, 2, 2),
            ),
            (
                "turkcell",
                read_sheet(
                    raw / "2C26-FO-Veri.xlsx",
                    "Operasyonel Veriler",
                    TURKCELL_ROWS,
                    2,
                    4,
                ),
            ),
        ]
        records = []
        for operator, rows in readings:
            for indicator, period, value in rows:
                if indicator != self.indicator_id:
                    continue
                records.append(
                    {
                        "indicator_id": indicator,
                        "area_id": "TR",
                        "area_level": "country",
                        "period_start": period,
                        "frequency": "quarterly",
                        "dims": format_dims({"operator": operator}),
                        "value": value,
                        "unit": "person",
                        "quality_flag": "measured",
                        "vintage": VINTAGE,
                        "source_id": self.source_id,
                        "retrieved_at": RETRIEVED,
                    }
                )
        if not records:
            raise ValueError(f"{self.indicator_id}: satır yok")
        return pl.DataFrame(records)


INDICATORS = (
    "telecom_mobile_subscribers",
    "telecom_postpaid_subscribers",
    "telecom_prepaid_subscribers",
    "telecom_fibre_subscribers",
    "telecom_broadband_subscribers",
    "telecom_tv_subscribers",
)

TELECOM_ADAPTERS = {
    name: type(
        "Telecom" + name.title().replace("_", ""),
        (TelecomOperators,),
        {"indicator_id": name},
    )
    for name in INDICATORS
}
