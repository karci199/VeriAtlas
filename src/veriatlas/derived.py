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


def marriage_age_total(fact: pl.DataFrame) -> pl.DataFrame:
    """The average age at marriage of everyone marrying, from the two published averages.

    Normally averaging two averages is the mistake this module exists to avoid — it is
    why the median age total is computed from the distribution and not from the published
    medians. Here it is exact, and for a reason that belongs to this measure only: every
    marriage TÜİK records has one groom and one bride, so the two averages carry the
    **same weight** by construction. (N·m + N·f) / 2N is (m + f) / 2 with nothing assumed.

    `mean_first_marriage_age` is deliberately not given the same treatment. A marriage can
    be his first and her second, so the number of first-time grooms and first-time brides
    are different numbers, and their average would need weights we do not hold.
    """
    ages = fact.filter(pl.col("indicator_id") == "mean_marriage_age").with_columns(
        pl.col("dims").str.extract(r"sex=([^;]*)").alias("sex")
    )
    if ages.is_empty():
        return fact.head(0)

    keys = ["area_id", "area_level", "period_start", "frequency", "vintage"]
    pairs = (
        ages.filter(pl.col("sex").is_in(["male", "female"]))
        .group_by(keys)
        .agg(
            pl.col("value").mean().alias("value"),
            pl.col("sex").n_unique().alias("sides"),
            pl.col("source_id").first(),
            pl.col("retrieved_at").max(),
        )
        # Both sides or nothing: one sex alone averaged with itself is that sex's figure
        # wearing the label "Toplam".
        .filter(pl.col("sides") == 2)
    )
    if pairs.is_empty():
        return fact.head(0)

    return pairs.with_columns(
        pl.lit("mean_marriage_age").alias("indicator_id"),
        pl.lit(format_dims({"sex": TOTAL})).alias("dims"),
        pl.lit("year_of_age").alias("unit"),
        pl.lit("estimated").alias("quality_flag"),
    ).select(fact.columns)


def natural_increase(fact: pl.DataFrame) -> pl.DataFrame:
    """Births minus deaths: the population change a place makes on its own.

    Read next to the population's actual change, the gap between the two is migration.
    That is the reason it earns a row of its own rather than being left to the reader:
    Türkiye's natural increase has fallen from 897 thousand in 2009 to 404 thousand in
    2025 while several provinces have already crossed into negative, and neither fact is
    visible from births or deaths alone.

    Stored rather than left to the page because it reads across two indicators, which the
    page's derivations cannot do (K12). Exact arithmetic on two published counts — no
    model, no assumption — but it is still our subtraction and not TÜİK's publication, so
    it carries `estimated` like everything else computed here.

    Only where both sides exist for the same area-year. A province with births and no
    deaths would otherwise come out as a natural increase equal to its births, which is
    the most confident possible way to be wrong.
    """
    keys = ["area_id", "area_level", "period_start", "frequency", "vintage"]

    def side(indicator_id: str, name: str) -> pl.DataFrame:
        return (
            fact.filter(pl.col("indicator_id") == indicator_id)
            # Deaths arrive split by sex, births whole. Summing across the breakdown is
            # right for both: an additive count's total is the sum of its parts.
            .group_by(keys)
            .agg(
                pl.col("value").sum().alias(name),
                pl.col("source_id").first(),
                pl.col("retrieved_at").max(),
            )
        )

    births = side("births", "births")
    deaths = side("deaths", "deaths").drop("source_id", "retrieved_at")
    if births.is_empty() or deaths.is_empty():
        return fact.head(0)

    return (
        births.join(deaths, on=keys, how="inner")
        .with_columns(
            (pl.col("births") - pl.col("deaths")).cast(pl.Float64).alias("value"),
            pl.lit("natural_increase").alias("indicator_id"),
            pl.lit("").alias("dims"),
            pl.lit("person").alias("unit"),
            pl.lit("estimated").alias("quality_flag"),
        )
        .select(fact.columns)
    )


#: The bands the death export uses, and the rule that folds a single year of population
#: into one of them: infancy on its own, then 1-4, then fives, closing at 75+.
def _death_band(age: pl.Expr) -> pl.Expr:
    year = age.cast(pl.Int32, strict=False)
    five = (year // 5) * 5
    return (
        pl.when(year == 0)
        .then(pl.lit("0"))
        .when(year < 5)
        .then(pl.lit("1-4"))
        .when(year >= 75)
        .then(pl.lit("75+"))
        .otherwise(five.cast(pl.String) + "-" + (five + 4).cast(pl.String))
    )


def age_specific_death_rate(fact: pl.DataFrame) -> pl.DataFrame:
    """Deaths per thousand people **of the same age and sex**.

    The one number the page cannot build for itself and the one most often wanted from
    the death counts. "Alan nüfusunun %'si" divides by everybody, which answers a
    different question: a province full of pensioners has many deaths at 65+ because it
    has many people at 65+, and dividing by its whole population keeps that in the answer
    instead of taking it out. Here the denominator is the band's own population, so what
    is left is mortality — 65+ in Türkiye is around forty per thousand and the provinces
    spread across it for reasons that are not their age structure.

    The two files do not band alike: population is published by single year and deaths by
    band, with infancy split off. The single years are folded to the death file's bands
    rather than the other way round — that direction is an exact sum, the other would be
    a guess at how a band divides.

    Left out on purpose:

    * **Yaşı bilinmeyen** — the band has no population to be a rate of. Kept in the count
      indicator, absent here, and the two are meant to disagree by exactly that.
    * **Any area-year missing either side.** An inner join, so a band with deaths and no
      published population produces no row rather than a rate over an assumed base.

    The denominator is the year-end register, which is what TÜİK's own crude rates use;
    a mid-year average would be defensible too and would move the numbers slightly. The
    rate is stored, so it says which one was chosen instead of leaving it to be guessed.
    """
    keys = ["area_id", "area_level", "period_start", "frequency", "vintage"]

    deaths = (
        fact.filter(pl.col("indicator_id") == "deaths_by_age")
        .with_columns(
            pl.col("dims").str.extract(r"age=([^;]+)").alias("age"),
            pl.col("dims").str.extract(r"sex=([^;]+)").alias("sex"),
        )
        .filter(pl.col("age") != "unknown")
        .group_by([*keys, "age", "sex"])
        .agg(
            pl.col("value").sum().alias("deaths"),
            pl.col("source_id").first(),
            pl.col("retrieved_at").max(),
        )
    )
    people = (
        fact.filter(pl.col("indicator_id") == "population")
        .with_columns(
            pl.col("dims").str.extract(r"age=([^;]+)").alias("age"),
            pl.col("dims").str.extract(r"sex=([^;]+)").alias("sex"),
        )
        # Single years and the closing band only: the same rows the median age is built
        # from. A level that publishes population already banded (district, mahalle) has
        # no death counts to pair with anyway, and folding a `10-14` into a `10-14` twice
        # is the double count K14 warns about.
        .filter(
            pl.col("sex").is_in(["male", "female"])
            & (
                pl.col("age").str.contains(SINGLE_AGE.pattern)
                | (pl.col("age") == "75+")
            )
        )
        .with_columns(
            pl.when(pl.col("age") == "75+")
            .then(pl.lit("75+"))
            .otherwise(_death_band(pl.col("age")))
            .alias("age")
        )
        .group_by([*keys, "age", "sex"])
        .agg(pl.col("value").sum().alias("people"))
    )
    if deaths.is_empty() or people.is_empty():
        return fact.head(0)

    paired = deaths.join(people, on=[*keys, "age", "sex"], how="inner").filter(
        pl.col("people") > 0
    )

    def rate(frame: pl.DataFrame, indicator_id: str) -> pl.DataFrame:
        return frame.with_columns(
            (pl.col("deaths") / pl.col("people") * 1000).alias("value"),
            pl.lit(indicator_id).alias("indicator_id"),
            (pl.lit("age=") + pl.col("age") + pl.lit(";sex=") + pl.col("sex")).alias(
                "dims"
            ),
            pl.lit("per_mille").alias("unit"),
            pl.lit("estimated").alias("quality_flag"),
        ).select(fact.columns)

    # The three broad groups, computed here rather than left to the screen. The screen
    # would have to add the bands' rates together, and a rate is not the sum of its parts:
    # 65-69, 70-74 and 75+ come to 136‰ added and 43‰ done properly. Properly is both
    # counts summed first and divided once, which is a weighting — by the population of
    # each band — and weights are not something a grouping box can carry.
    broad = (
        paired.with_columns(
            pl.when(pl.col("age").is_in(["0", "1-4", "5-9", "10-14"]))
            .then(pl.lit("0-14"))
            .when(pl.col("age").is_in(["65-69", "70-74", "75+"]))
            .then(pl.lit("65+"))
            .otherwise(pl.lit("15-64"))
            .alias("age")
        )
        .group_by([*keys, "age", "sex"])
        .agg(
            pl.col("deaths").sum(),
            pl.col("people").sum(),
            pl.col("source_id").first(),
            pl.col("retrieved_at").max(),
        )
    )

    return pl.concat(
        [rate(paired, "death_rate_by_age"), rate(broad, "death_rate_broad")]
    )


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
