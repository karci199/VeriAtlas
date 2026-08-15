"""First adapter: total fertility rate, 81 provinces, from the verified MEDAS pull.

The source here is a file someone downloaded by hand, not a service — which makes it a
good first adapter precisely because it is the awkward case. If the contract can hold a
file on disk and a REST API without bending, it is probably the right shape.

`fetch` copies the file into `raw/` rather than reading it in place: the point of the
raw copy is that it stays put even when the original is moved, edited or overwritten.
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
    r"C:\Users\katan\OneDrive\Desktop\demografi\cikti"
    r"\TUIK_toplam_dogurganlik_hizi_81il_2009-2025.csv"
)


class TuikTfr:
    """Wide CSV, one column per year, semicolon separated."""

    source_id = "tuik_medas"
    indicator_id = "tfr"

    # The file records no release date, only when we pulled it. Approximating the
    # vintage with the retrieval month is a known gap: once the MEDAS adapter reads a
    # report header, the real release date replaces this.
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 13)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "tuik_medas" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        wide = pl.read_csv(raw, separator=";")
        years = [column for column in wide.columns if column != "il"]
        area_of = resolve(wide["il"].to_list())

        return (
            wide.unpivot(index="il", on=years, variable_name="year", value_name="value")
            .with_columns(
                pl.col("il").replace_strict(area_of).alias("area_id"),
                pl.lit("province").alias("area_level"),
                pl.date(pl.col("year").cast(pl.Int32), 1, 1).alias("period_start"),
                pl.lit(indicator.frequency).alias("frequency"),
                pl.lit(DIMS_NONE).alias("dims"),
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit(indicator.unit.unit_id).alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit(self.vintage).alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(self.retrieved_at).alias("retrieved_at"),
            )
            .drop("il", "year")
        )
