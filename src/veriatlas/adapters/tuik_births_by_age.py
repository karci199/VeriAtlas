"""Births by province and age group of the mother, 2009-2025.

A hand-downloaded TÜİK export, wide: year and province down the rows (year filled only
when it changes, province given on every row), ten age bands and an "unknown" column
across. Fine-grained where `births` alone is a single count — this is what the total
fertility rate is made of, and the file says directly which age group is moving,
rather than leaving that to be inferred from the rate.

Bands are read as-is into the `age` dim: they are TÜİK's own edges (`<15`, `15-17`,
`18-19`, `20-24`, …, `50+`), not the five-year population bands, and the dictionary's
age dim already prints whatever band string it is given (docs on `dim.age`) — no
values table needed.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..areas import resolve
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .base import cached_copy

SOURCE_FILE = Path(
    r"C:\Users\katan\OneDrive\Desktop\demografi\İl ve Annenin Yaş Grubuna Göre Doğumlar.xls"
)

COUNTRY_LABEL = "Türkiye"

#: Column index (0-based) to age band. Column 13 is unlabelled in the source — the
#: header names it only in English ("Unknown") — so it is listed here rather than read
#: off the sheet.
AGE_COLUMNS = {
    3: "<15",
    4: "15-17",
    5: "18-19",
    6: "20-24",
    7: "25-29",
    8: "30-34",
    9: "35-39",
    10: "40-44",
    11: "45-49",
    12: "50+",
    13: "unknown",
}


class TuikBirthsByAge:
    """Births by province and mother's age group, 2009-2025."""

    source_id = "tuik_medas"
    indicator_id = "births_by_age"

    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 17)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "tuik_medas" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        sheet = pl.read_excel(raw, engine="calamine", has_header=False)

        def as_float(cell: object) -> float | None:
            if cell is None:
                return None
            text = str(cell).strip()
            if not text or text == "-":
                return None
            try:
                return float(text)
            except ValueError:
                return None

        records: list[dict] = []
        year = None
        for row_index in range(5, sheet.height):
            row = sheet.row(row_index)
            year_cell = row[0]
            if year_cell:
                text = str(year_cell).strip()
                digits = "".join(ch for ch in text[:4] if ch.isdigit())
                if len(digits) == 4:
                    year = int(digits)
            province = row[1]
            if not isinstance(province, str) or not province.strip() or year is None:
                continue
            for index, age in AGE_COLUMNS.items():
                value = as_float(row[index])
                if value is None:
                    continue
                records.append(
                    {
                        "area_name": province.strip(),
                        "year": year,
                        "age": age,
                        "value": value,
                    }
                )

        if not records:
            raise ValueError(self.indicator_id + ": dosyada satir yok")

        frame = pl.DataFrame(records)
        provinces = [
            name for name in frame["area_name"].unique() if name != COUNTRY_LABEL
        ]
        area_of = resolve(provinces) | {COUNTRY_LABEL: "TR"}

        return frame.with_columns(
            pl.col("area_name").replace_strict(area_of).alias("area_id"),
            pl.when(pl.col("area_name") == COUNTRY_LABEL)
            .then(pl.lit("country"))
            .otherwise(pl.lit("province"))
            .alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.col("age")
            .map_elements(lambda v: format_dims({"age": v}), return_dtype=pl.String)
            .alias("dims"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).select(
            "indicator_id",
            "area_id",
            "area_level",
            "period_start",
            "frequency",
            "dims",
            "value",
            "unit",
            "quality_flag",
            "vintage",
            "source_id",
            "retrieved_at",
        )
