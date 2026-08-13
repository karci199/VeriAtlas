"""Rolling values up a level of geography.

Sums add up; ratios do not. A fertility rate is a ratio, so the plain mean of the
provinces in a region is not the rate of that region — a province of 90.000 people would
count as much as İstanbul. Weighting by population fixes the worst of that.

It stays an approximation: the correct weight for a fertility rate is women of
childbearing age, not everybody. Everything produced here is therefore marked
`estimated`, which is what puts the yellow badge on the chart and tells the reader this
number was computed rather than published.
"""

from __future__ import annotations

import polars as pl

from .areas import load_areas, load_weights


def to_regions(provinces: pl.DataFrame) -> pl.DataFrame:
    """Population-weighted mean of province values, grouped by their parent region.

    `provinces` must carry `area_id`, `year`, `value`, `unit`, `vintage`, `source_id`.
    Provinces without a weight are dropped rather than silently counted as zero.
    """
    registry = load_areas()
    parent_of = registry.filter(pl.col("area_level") == "province").select(
        "area_id", pl.col("parent_id").alias("region_id")
    )
    region_names = registry.filter(pl.col("area_level") == "region").select(
        pl.col("area_id").alias("region_id"), pl.col("name_tr").alias("area")
    )

    return (
        provinces.join(parent_of, on="area_id", how="inner")
        .join(load_weights().select("area_id", "population"), on="area_id", how="inner")
        .group_by("region_id", "year")
        .agg(
            (pl.col("value") * pl.col("population")).sum().alias("weighted"),
            pl.col("population").sum().alias("total"),
            pl.col("unit").first(),
            pl.col("vintage").first(),
            pl.col("source_id").first(),
        )
        .join(region_names, on="region_id", how="left")
        .select(
            pl.col("region_id").alias("area_id"),
            "area",
            pl.lit("region").alias("level"),
            "year",
            (pl.col("weighted") / pl.col("total")).alias("value"),
            "unit",
            pl.lit("estimated").alias("quality_flag"),
            "vintage",
            "source_id",
        )
    )
