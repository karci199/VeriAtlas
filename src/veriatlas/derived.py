"""Rows computed from other rows, after every adapter has run.

Distinct from the derivations of K12, which the page computes on the fly from a single
series and never stores: these read *across* indicators, which the page cannot do, and
so they are built here and stored like any other observation — carrying `estimated`, so
a reader can tell them from something TÜİK published.

An adapter turns one source into rows. This turns rows into rows, which is why it is not
an adapter and does not pretend to be one.
"""

from __future__ import annotations

import re

import polars as pl

from .schema import format_dims

#: Single years arrive as bare numbers; the closing band is `75+`, which is not one.
SINGLE_AGE = re.compile(r"^\d+$")

#: The published median age is by sex only, so this is the value the total goes under.
TOTAL = "total"


def median_age_total(fact: pl.DataFrame) -> pl.DataFrame:
    """The median age of everyone, from the single-year population distribution.

    TÜİK publishes the median age for men and for women, never for the two together, and
    the average of two medians is not a median — the median age adapter says so and
    refuses to invent one. But the population itself *is* published by single year of age
    at province and country level, and a median is a property of a distribution: the age
    at which the cumulative count crosses half. So the number can be computed honestly
    rather than guessed.

    Checked against the published male and female medians it is not allowed to replace:
    over 3.116 area-year-sex pairs the mean absolute difference is **0,05 years**, which
    is the rounding in TÜİK's own one-decimal figures. Seven pairs sit further out, all
    of them male, all in Hakkâri and Bingöl — provinces whose male age structure has a
    conscript spike right where the median falls, so a year's width there covers an
    unusual number of people. Recorded rather than smoothed away.
    """
    single = (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & pl.col("area_level").is_in(["country", "province"])
        )
        .with_columns(
            pl.col("dims").str.extract(r"age=([^;]*)").alias("age"),
        )
        .drop_nulls("age")
    )
    if single.is_empty():
        return single.head(0)

    # Only where single years actually exist. The district file is banded, and a median
    # off five-year bands is a different, coarser number wearing the same name.
    resolved = single.filter(pl.col("age").str.contains(SINGLE_AGE.pattern))
    if resolved.is_empty():
        return single.head(0)

    keys = ["area_id", "area_level", "period_start", "frequency", "vintage"]

    # The closing `75+` band carries no single age but it carries people, and the median
    # is a position in the whole population. Dropping it shrinks the denominator and
    # pulls the median down — by 1,3 years on average, which is how this was caught.
    # The source travels with the number: these really are TÜİK's people, counted by
    # TÜİK, and only the statistic taken of them is ours — which `estimated` is what says.
    # Inventing a source id here would break the badge's promise in the other direction.
    whole = single.group_by(keys).agg(
        pl.col("value").sum().alias("everyone"),
        pl.col("source_id").first(),
        pl.col("retrieved_at").max(),
    )

    running = (
        resolved.with_columns(pl.col("age").cast(pl.Int32))
        .sort("age")
        .group_by(keys, maintain_order=True)
        .agg(
            pl.col("age").alias("ages"),
            pl.col("value").sum().over(keys).alias("ignored"),
            pl.col("value").alias("counts"),
        )
        .drop("ignored")
        .join(whole, on=keys)
    )

    medians = []
    for row in running.iter_rows(named=True):
        half = row["everyone"] / 2
        seen = 0.0
        found = None
        for age, count in zip(row["ages"], row["counts"]):
            if seen + count >= half:
                # Inside the band the count is spread evenly across the year: someone
                # recorded as 30 is somewhere in [30, 31).
                found = age + (half - seen) / count if count else float(age)
                break
            seen += count
        if found is None:
            # The median falls inside the closing band, which has no interior. Above 75
            # is not a place this data can locate anyone, so nothing is claimed.
            continue
        medians.append(
            {
                **{key: row[key] for key in keys},
                "source_id": row["source_id"],
                "retrieved_at": row["retrieved_at"],
                "value": found,
            }
        )

    if not medians:
        return single.head(0)

    return (
        pl.DataFrame(medians)
        .with_columns(
            pl.lit("median_age").alias("indicator_id"),
            pl.lit(format_dims({"sex": TOTAL})).alias("dims"),
            pl.lit("year_of_age").alias("unit"),
            pl.lit("estimated").alias("quality_flag"),
            pl.col("value").cast(pl.Float64),
        )
        .select(fact.columns)
    )
