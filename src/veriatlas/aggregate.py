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


def members_of(target_level: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Which target area each province belongs to, plus the target areas' names.

    Works for any level a province is a member of: `country`, `region` (geographic),
    `nuts2` (İBBS alt bölge) or `nuts1` (İBBS bölge). For `nuts1` the provinces are
    reached directly rather than through `nuts2` — a roll-up of roll-ups would reweight
    a mean and, for a sum, would depend on the intermediate level existing at all.

    Returns `(parent_of, region_names)`, both keyed on `region_id`.
    """
    targets = load_areas().filter(pl.col("area_level") == target_level)
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

    provinces = (
        load_areas().filter(pl.col("area_level") == "province").select("area_id")
    )
    parent_of = (
        reach.join(
            targets.select(pl.col("area_id").alias("region_id")),
            on="region_id",
            how="semi",
        )
        # Provinces only. The membership table also holds nuts2-in-nuts1 and nuts1-in-TR,
        # and those rows reach the country too: left in, Türkiye claimed 126 members and
        # a complete sum of 81 provinces looked short of itself.
        .join(provinces, on="area_id", how="semi")
        .unique()
    )
    region_names = targets.select(
        pl.col("area_id").alias("region_id"), pl.col("name_tr").alias("area")
    )
    return parent_of, region_names


def to_level(provinces: pl.DataFrame, target_level: str) -> pl.DataFrame:
    """Population-weighted mean of province values, grouped into `target_level`.

    `provinces` must carry `area_id`, `year`, `value`, `unit`, `vintage`, `source_id`.
    Provinces without a weight are dropped rather than silently counted as zero.
    """
    parent_of, region_names = members_of(target_level)

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


def sum_to_level(
    provinces: pl.DataFrame, target_level: str, by: tuple[str, ...] = ()
) -> pl.DataFrame:
    """Exact sum of province counts into `target_level`, one row per breakdown value.

    For additive units only. A count of people adds up, so this is not an estimate the
    way `to_level` is: the rows keep the source's own `quality_flag` rather than being
    marked `estimated`.

    `by` names the breakdown columns to keep — summing across them instead would fold
    the breakdown away and count everybody once per value.

    A sum is a total only if every province is in it. A year missing forty provinces
    would still produce a number, and that number would be a country total that is
    wrong rather than absent, so the incomplete years are refused.
    """
    parent_of, region_names = members_of(target_level)
    members = parent_of.group_by("region_id").len().rename({"len": "expected"})

    rolled = (
        provinces.join(parent_of, on="area_id", how="inner")
        .group_by("region_id", "year", *by)
        .agg(
            pl.col("value").sum(),
            pl.col("area_id").n_unique().alias("found"),
            pl.col("quality_flag").first(),
            pl.col("vintage").first(),
            pl.col("source_id").first(),
        )
        .join(members, on="region_id", how="left")
    )

    short = rolled.filter(pl.col("found") < pl.col("expected"))
    if short.height:
        row = short.row(0, named=True)
        raise ValueError(
            "sum_to_level: eksik il, toplam gercek toplam degil — "
            + str(row["region_id"])
            + " "
            + str(row["year"])
            + ": "
            + str(row["found"])
            + "/"
            + str(row["expected"])
        )

    return rolled.join(region_names, on="region_id", how="left").select(
        pl.col("region_id").alias("area_id"),
        "area",
        pl.lit(target_level).alias("level"),
        "year",
        *by,
        "value",
        "quality_flag",
        "vintage",
        "source_id",
    )
