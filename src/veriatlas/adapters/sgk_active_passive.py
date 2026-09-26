"""SGK active-to-passive ratio (insured per pensioner), Türkiye, 2004-2018.

The yearbooks 2012-2018 print "Tablo 1.5 - Sosyal Güvenlik Kurumu Aktif Pasif Oranı" with a
row per year and four columns: all schemes, 4/a, 4/b, 4/c. The table stopped with the 2018
yearbook. Each year is taken from the latest yearbook that prints it; an earlier yearbook
printing a different figure for the same year (a revision) is reported by `revisions()`.

Cells come from `raw/sgk/national_cells.parquet` (`scripts/extract_sgk_national.py`); the
extractor could not read this table's header, so the columns are taken by position, and a
row with other than four numbers is refused.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from .sgk_national import CELLS

SCHEMES = ("total", "4a", "4b", "4c")


def printed() -> pl.DataFrame:
    """(yearbook, year, scheme, value) for every printed cell."""
    cells = (
        pl.scan_parquet(CELLS)
        .filter(pl.col("title").str.contains("Aktif Pasif Oranı"))
        .collect()
        .sort("year", "block", "row", "col")
    )
    records = []
    for (book, code), row in cells.group_by("year", "code", maintain_order=True):
        values = row["value"].to_list()
        if not str(code).isdigit():
            continue
        if len(values) != len(SCHEMES):
            raise ValueError(f"aktif/pasif {book} {code}: {len(values)} sütun")
        records += [
            {"book": book, "year": int(code), "scheme": s, "value": v}
            for s, v in zip(SCHEMES, values, strict=True)
        ]
    return pl.DataFrame(records)


def revisions() -> pl.DataFrame:
    """Years whose figure differs between yearbooks by more than 1 %."""
    frame = printed()
    return (
        frame.group_by("year", "scheme")
        .agg(pl.col("value").min().alias("low"), pl.col("value").max().alias("high"))
        .filter((pl.col("high") - pl.col("low")) > pl.col("high") * 0.01)
    )


class SgkActivePassive:
    source_id = "sgk"
    indicator_id = "sgk_active_passive_ratio"

    def fetch(self) -> Path:
        return CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        latest = printed().sort("book").group_by("year", "scheme").last()
        return latest.select(
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            ("scheme=" + pl.col("scheme")).alias("dims"),
            pl.col("value").cast(pl.Float64),
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("index").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 14)).alias("retrieved_at"),
        )


SGK_ACTIVE_PASSIVE_ADAPTERS = {"sgk_active_passive_ratio": SgkActivePassive}
