"""Births by province and the mother's legal marital status, 2012-2025.

Same file shape as `tuik_births_by_age` — year and province down, marital status
across — and the same five values `marital_status` already uses at population level
(never_married, married, widowed, divorced, unknown), so no new dictionary entries are
needed beyond the indicator itself.

"Legal" marital status: a religious marriage with no civil registration reads as never
married here, a reading gap documented for the same reason in the fertility notes —
this file does not resolve it either.
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
    r"C:\Users\katan\OneDrive\Desktop\demografi\İl ve annenin yasal medeni durumuna göre doğumlar.xls"
)

COUNTRY_LABEL = "Türkiye"

MARITAL_COLUMNS = {
    3: "never_married",
    4: "married",
    5: "widowed",
    6: "divorced",
    7: "unknown",
}


class TuikBirthsMarital:
    """Births by province and mother's legal marital status, 2012-2025."""

    source_id = "tuik_medas"
    indicator_id = "births_by_marital"

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
            for index, status in MARITAL_COLUMNS.items():
                value = as_float(row[index])
                if value is None:
                    continue
                records.append(
                    {
                        "area_name": province.strip(),
                        "year": year,
                        "marital": status,
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
            pl.col("marital")
            .map_elements(lambda v: format_dims({"marital": v}), return_dtype=pl.String)
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
