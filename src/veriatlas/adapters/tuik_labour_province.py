r"""Labour force by province: the one cut of the survey MEDAS does not publish.

MEDAS carries the labour force survey down to İBBS-2 (26 regions) and no further. The
data portal publishes three tables that go a level lower — 81 provinces, 2022-2025 —
which is why they are here and not in a MEDAS fetcher:
`İl düzeyinde işsizlik oranı`, `İl düzeyinde istihdam oranı`,
`İl düzeyinde işgücüne katılma oranı` (`C:\veri-ham\tuik_portal\dosya\tablo`).

**The interval is loaded with the estimate.** This is a household survey, not a register:
the table prints a 95% confidence band next to every rate, and in the small provinces it
is wide — Hakkâri's 2025 unemployment is 13,8% with a band from 10,6 to 17,0. Dropping the
band would turn a ranking of survey estimates into a ranking of facts, so the bounds are
stored as their own `bound` values beside the point estimate.

Two traps in the file:

* The eastern provinces are coded `TRA11`, `TRB21`, `TRC33` — letters, not digits. A
  `TR\d+` pattern silently drops 28 rows, and they are exactly the provinces with the
  highest unemployment. The code is not used at all here: the province name in the next
  column is the key, as everywhere else in this repository.
* The header is three rows deep — year, `Oran`, then `Alt sınır` / `Üst sınır` — and the
  year sits above the rate with the two bounds two and three columns to its right.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl
import xlrd

from ..config import RAW
from ..schema import format_dims
from .kgm import province_id

FOLDER = RAW / "tuik_portal" / "dosya" / "tablo"

#: Where the rate's 95% band sits, relative to the rate's own column.
LOWER, UPPER = 2, 3

#: The year row, and the first data row under the three header rows.
YEAR_ROW, FIRST_ROW = 3, 6

#: `TR`, `TR100`, `TRA11` — the country row and the province rows, and nothing else.
CODE = re.compile(r"TR[0-9A-Z]*")

#: `13,8 (1)`: the footnote marks an estimate the source says to treat with caution. It
#: is kept as a number — the interval already carries how uncertain it is.
FOOTNOTE = re.compile(r"\(\d\)")


def value(cell: object) -> float | None:
    """A rate, or None for the blank cells the table leaves where it has no estimate."""
    text = FOOTNOTE.sub("", str(cell)).strip().replace(",", ".")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read(path: Path) -> list[dict]:
    """One table to records of (area, year, bound, rate)."""
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    years: dict[int, int] = {}
    for column in range(sheet.ncols):
        head = str(sheet.cell_value(YEAR_ROW, column)).strip()
        if re.fullmatch(r"\d{4}(\.0)?", head):
            years[int(float(head))] = column
    if not years:
        raise ValueError(f"{path.name}: yıl başlığı bulunamadı")

    records: list[dict] = []
    seen: set[str] = set()
    for row in range(FIRST_ROW, sheet.nrows):
        code = str(sheet.cell_value(row, 0)).strip()
        name = str(sheet.cell_value(row, 1)).strip()
        if not name or not CODE.fullmatch(code):
            continue
        area = "TR" if code == "TR" else province_id(name)
        level = "country" if code == "TR" else "province"
        if area in seen:
            raise ValueError(f"{path.name}: {name} iki kez")
        seen.add(area)
        for year, column in sorted(years.items()):
            for bound, offset in (
                ("point", 0),
                ("lower_95", LOWER),
                ("upper_95", UPPER),
            ):
                rate = value(sheet.cell_value(row, column + offset))
                if rate is None:
                    continue
                records.append(
                    {
                        "area_id": area,
                        "area_level": level,
                        "period_start": dt.date(year, 1, 1),
                        "dims": format_dims({"bound": bound}),
                        "value": rate,
                    }
                )
    provinces = {r["area_id"] for r in records if r["area_level"] == "province"}
    if len(provinces) != 81:
        raise ValueError(f"{path.name}: 81 il bekleniyordu, {len(provinces)} bulundu")
    return records


class ProvinceLabour:
    """One of the three rates, at province level, with its confidence band."""

    source_id = "tuik_portal"
    unit = "percent"
    retrieved_at = dt.date(2026, 9, 18)
    indicator_id: str
    stem: str

    def fetch(self) -> Path:
        files = sorted(FOLDER.glob(self.stem))
        if not files:
            raise FileNotFoundError(
                f"TÜİK portal tablosu yok: {self.stem} "
                "(scripts/fetch_tuik_portal_files.py)"
            )
        return files[0]

    def parse(self, raw: Path) -> pl.DataFrame:
        return pl.DataFrame(read(raw)).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit(self.unit).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        )


class UnemploymentRate(ProvinceLabour):
    indicator_id = "unemployment_rate"
    stem = "00503_*.xls"


class EmploymentRate(ProvinceLabour):
    indicator_id = "employment_rate"
    stem = "00502_*.xls"


class ParticipationRate(ProvinceLabour):
    indicator_id = "labour_force_participation_rate"
    stem = "00501_*.xls"


LABOUR_PROVINCE_ADAPTERS = {
    "unemployment_rate": UnemploymentRate,
    "employment_rate": EmploymentRate,
    "labour_force_participation_rate": ParticipationRate,
}
