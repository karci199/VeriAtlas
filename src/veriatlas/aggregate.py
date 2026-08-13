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

from .areas import load_areas, load_parents, load_weights


def to_level(provinces: pl.DataFrame, target_level: str) -> pl.DataFrame:
    """Population-weighted mean of province values, grouped into `target_level`.

    Works for any level a province is a member of: `region` (geographic), `nuts2` (İBBS
    alt bölge) or `nuts1` (İBBS bölge). For `nuts1` the provinces are rolled up directly
    rather than through `nuts2` — averaging averages would reweight the result.

    `provinces` must carry `area_id`, `year`, `value`, `unit`, `vintage`, `source_id`.
    Provinces without a weight are dropped rather than silently counted as zero.
    """
    registry = load_areas()
    targets = registry.filter(pl.col("area_level") == target_level)
    parents = load_parents()

    # Walk up the membership until a parent sits at the target level, so nuts1 can be
    # reached from a province even though its immediate parent is a nuts2.
    reach = parents.select("area_id", pl.col("parent_id").alias("region_id"))
    for _ in range(3):
        resolved = reach.join(
            targets.select(pl.col("area_id").alias("region_id")),
            on="region_id",
            how="semi",
        )
        pending = reach.join(resolved, on=["area_id", "region_id"], how="anti")
        if pending.height == 0:
            break
        reach = pl.concat(
            [
                resolved,
                pending.join(
                    parents.select(
                        pl.col("area_id").alias("region_id"),
                        pl.col("parent_id").alias("next_id"),
                    ),
                    on="region_id",
                    how="inner",
                ).select("area_id", pl.col("next_id").alias("region_id")),
            ]
        )

    parent_of = reach.join(
        targets.select(pl.col("area_id").alias("region_id")), on="region_id", how="semi"
    ).unique()
    region_names = targets.select(
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
            pl.lit(target_level).alias("level"),
            "year",
            (pl.col("weighted") / pl.col("total")).alias("value"),
            "unit",
            pl.lit("estimated").alias("quality_flag"),
            "vintage",
            "source_id",
        )
    )
