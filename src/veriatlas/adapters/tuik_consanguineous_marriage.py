"""Consanguineous marriage rate, province and country, 2010-2025.

A TÜİK veri portalı export ("İllere Göre Evlenme Sayısı ile Akraba Evliliği Sayısı ve
Oranı"), a rate rather than a count: the source publishes the percentage directly,
column-per-year, province rows carrying a trailing-space label (`Türkiye  `) that has
to be stripped before it matches the registry.

No dims, no roll-up: the number in the file already is the province's own rate, not
something built from a count this fact table would need to add up.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..areas import resolve
from ..config import RAW
from ..indicators import get
from ..schema import DIMS_NONE
from .base import cached_copy

SOURCE_FILE = Path(
    r"C:\Users\katan\OneDrive\Desktop\demografi"
    r"\İllere Göre Evlenme Sayısı ile Akraba Evliliği Sayısı ve Oranı"
    r" (TR,DF_EVLENME_AKRABA_EVLILIK,1.0).xlsx"
)

SHEET = "NG_AEO"
COUNTRY_LABEL = "Türkiye"


class TuikConsanguineousMarriage:
    """Share of marriages between relatives, province and country, 2010-2025."""

    source_id = "tuik_medas"
    indicator_id = "consanguineous_marriage"

    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 17)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "tuik_medas" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        sheet = pl.read_excel(
            raw, sheet_name=SHEET, engine="calamine", has_header=False
        )

        # The header ("Zaman") row is found rather than counted to: openpyxl and
        # calamine disagree on whether the file's blank second line survives, which
        # shifts every fixed row index by one depending on which reader is used.
        year_row_index = next(
            i
            for i in range(sheet.height)
            if str(sheet.row(i)[0] or "").strip() == "Zaman"
        )
        year_row = sheet.row(year_row_index)

        # Each year spans three columns: the value, an observation status and a
        # confidentiality status. Only the value column is kept — found by position,
        # since the two status columns carry no header of their own to read.
        year_columns: dict[int, int] = {}
        for index in range(1, sheet.width, 3):
            cell = year_row[index]
            if cell is None:
                continue
            digits = "".join(ch for ch in str(cell).strip() if ch.isdigit())
            if len(digits) == 4:
                year_columns[int(digits)] = index

        records: list[dict] = []
        for row_index in range(year_row_index + 2, sheet.height):
            row = sheet.row(row_index)
            name = row[0]
            if not isinstance(name, str) or not name.strip():
                continue
            area_name = name.strip()
            for year, index in year_columns.items():
                cell = row[index]
                if cell is None:
                    continue
                try:
                    value = float(cell)
                except (TypeError, ValueError):
                    continue
                records.append({"area_name": area_name, "year": year, "value": value})

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
            pl.lit(DIMS_NONE).alias("dims"),
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
