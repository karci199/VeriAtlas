"""Registered road motor vehicles by province and type, one snapshot.

A hand-downloaded TÜİK export (July 2026), printed as two side-by-side province blocks
(columns 0-10 and 13-23) so it fits a page — the same block layout repeated once. No
"Adana-1"-style code in the label here, only the plain Turkish name, so provinces are
matched with `areas.resolve` rather than the code-based `area_of` the MEDAS exports use.

Two names arrive mis-encoded (a Turkish-locale case-folding bug upstream of us, not
something `resolve` can guess): "Balikesi̇r" for Balıkesir and "Elaziğ" for Elazığ.
Fixed by an explicit override rather than a normalization rule, because a rule general
enough to catch these two would also silently rewrite names that were already correct.

Nine columns per block: total, its share of the country total, and eight vehicle types.
The share is a computed percentage of a total we already store — not loaded, K12. The
eight types are additive and their sum reproduces the published total (checked, not
assumed) so they are kept as one indicator with a `vehicle_type` dim rather than eight
indicators that would need to be added back up on the screen.
"""

from __future__ import annotations

import datetime as dt
import unicodedata
from pathlib import Path

import polars as pl

from ..areas import resolve
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .base import cached_copy

SOURCE_FILE = Path(
    r"C:\Users\katan\OneDrive\Desktop\demografi\Ulaşım"
    r"\İllere göre motorlu kara taşıtları sayısı.xls"
)

COUNTRY_LABEL = "Toplam-Total"
YEAR = 2026  # "Temmuz 2026" in the file title; no finer date is published.

#: Column position within each block (0 = the province label) to the vehicle-type id.
#: Read by position, not by header name — the header row carries a merged "Özel amaçlı"
#: cell that comes back as "Special" in one language and split across two rows in the
#: other, so no single header cell reliably names every column.
VEHICLE_COLUMNS = {
    3: "car",
    4: "minibus",
    5: "bus",
    6: "light_truck",
    7: "truck",
    8: "motorcycle",
    9: "special_purpose",
    10: "tractor",
}

#: Names the file writes with a stray combining dot above ("i̇") on top of an already
#: correct letter — stripping the combining mark alone fixes most of these (İzmi̇r ->
#: İzmir). These two need the letter itself corrected, so they are listed by hand.
NAME_OVERRIDES = {
    "Balikesi̇r": "Balıkesir",
    "Elaziğ": "Elazığ",
}


def _clean_name(name: str) -> str:
    fixed = unicodedata.normalize("NFC", name).replace("i̇", "i")
    return NAME_OVERRIDES.get(name, fixed)


class TuikVehicles:
    """Registered vehicles by province and type, one snapshot (July 2026)."""

    source_id = "tuik_medas"
    indicator_id = "vehicles"

    vintage = "2026-07"
    retrieved_at = dt.date(2026, 8, 17)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "tuik_medas" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        sheet = pl.read_excel(raw, engine="calamine", has_header=False)

        def as_float(cell: object) -> float | None:
            if cell is None:
                return None
            try:
                return float(cell)
            except (TypeError, ValueError):
                return None

        records: list[dict] = []
        for row_index in range(6, sheet.height):
            row = sheet.row(row_index)
            for start in (0, 13):
                label = row[start]
                total = as_float(row[start + 1])
                # Footnotes land in column 0 on trailing rows; a real row always has a
                # numeric total next to its label. Columns come back as strings (the
                # title rows above force the whole column to String), so the total is
                # tested by whether it parses, not by its Python type.
                if not isinstance(label, str) or total is None:
                    continue
                for offset, vehicle_type in VEHICLE_COLUMNS.items():
                    value = as_float(row[start + offset])
                    if value is None:
                        continue
                    records.append(
                        {
                            "area_name": label,
                            "vehicle_type": vehicle_type,
                            "value": value,
                        }
                    )

        frame = pl.DataFrame(records)

        cleaned = {name: _clean_name(name) for name in frame["area_name"].unique()}
        provinces = [
            cleaned[name] for name in cleaned if cleaned[name] != COUNTRY_LABEL
        ]
        area_of = resolve(provinces) | {COUNTRY_LABEL: "TR"}

        return (
            frame.with_columns(
                pl.col("area_name").replace_strict(cleaned).alias("area_name_clean"),
            )
            .with_columns(
                pl.col("area_name_clean").replace_strict(area_of).alias("area_id"),
                pl.when(pl.col("area_name_clean") == COUNTRY_LABEL)
                .then(pl.lit("country"))
                .otherwise(pl.lit("province"))
                .alias("area_level"),
                pl.date(pl.lit(YEAR), 7, 1).alias("period_start"),
                pl.lit(indicator.frequency).alias("frequency"),
                pl.col("vehicle_type")
                .map_elements(
                    lambda v: format_dims({"vehicle_type": v}), return_dtype=pl.String
                )
                .alias("dims"),
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit(indicator.unit.unit_id).alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit(self.vintage).alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(self.retrieved_at).alias("retrieved_at"),
            )
            .select(
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
        )
