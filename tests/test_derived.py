"""The median age of everyone, and the ways of getting it quietly wrong.

None of these show up on the chart. A median computed off a short denominator lands two
years low and looks entirely plausible; a median taken of the two published medians is a
number nobody can tell apart from the real one by eye. So they are pinned here.
"""

import datetime as dt

import polars as pl

from veriatlas.derived import median_age_total

COLUMNS = (
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


def population(age, sex, value, area_id="TR-16"):
    return {
        "indicator_id": "population",
        "area_id": area_id,
        "area_level": "province",
        "period_start": dt.date(2025, 1, 1),
        "frequency": "annual",
        "dims": "age=" + age + ";sex=" + sex,
        "value": float(value),
        "unit": "person",
        "quality_flag": "measured",
        "vintage": "2026-08",
        "source_id": "tuik_medas",
        "retrieved_at": dt.date(2026, 8, 14),
    }


def published_median(sex, value, area_id="TR-16"):
    row = population("", sex, value, area_id)
    return {
        **row,
        "indicator_id": "median_age",
        "dims": "sex=" + sex,
        "unit": "year_of_age",
    }


def frame(rows):
    return pl.DataFrame(rows).select(COLUMNS)


def only_value(result):
    assert len(result) == 1
    return result["value"][0]


def test_median_is_the_middle_of_the_distribution():
    # Ten people at each age 0..9: the middle of a hundred falls at the top of age 4.
    rows = [population(str(age), "male", 10) for age in range(10)]
    rows.append(published_median("male", 4.5))
    assert only_value(median_age_total(frame(rows))) == 5.0


def test_closing_band_counts_towards_the_half():
    """The 75+ band has no single age but it has people.

    Left out of the denominator the half falls earlier in the distribution and the median
    comes back too young — by 1,3 years across the real data, which is enough to move a
    province several places and not nearly enough to look wrong.
    """
    rows = [population(str(age), "male", 10) for age in range(10)]
    rows.append(published_median("male", 4.5))

    without = only_value(median_age_total(frame(rows)))

    # A hundred more people above the listed ages: two hundred in all, so the half falls
    # at the very top of age 9 rather than at the top of age 4.
    rows.append(population("75+", "male", 100))

    assert without == 5.0
    assert only_value(median_age_total(frame(rows))) == 10.0


def test_both_sexes_are_one_distribution():
    """Not the average of the two medians.

    Men aged 0-9 and women aged 20-29, in equal numbers: the average of the two medians
    is 15, an age at which this population contains nobody. The median of the pooled
    distribution is the boundary between the groups.
    """
    rows = [population(str(age), "male", 10) for age in range(10)]
    rows += [population(str(age), "female", 10) for age in range(20, 30)]
    rows.append(published_median("male", 4.5))
    rows.append(published_median("female", 24.5))

    assert only_value(median_age_total(frame(rows))) == 10.0


def test_derived_rows_say_they_are_derived():
    rows = [population(str(age), "male", 10) for age in range(10)]
    rows.append(published_median("male", 4.5))
    result = median_age_total(frame(rows))

    assert result["quality_flag"].to_list() == ["estimated"]
    assert result["dims"].to_list() == ["sex=total"]
    assert result["indicator_id"].to_list() == ["median_age"]


def test_banded_ages_produce_nothing():
    """A median off five-year bands is a coarser number wearing the same name.

    The bands are at province level here on purpose: the level filter would reject a
    district row before the age ever mattered, and then this would pass without testing
    anything.
    """
    rows = [
        population("0-4", "male", 10),
        population("5-9", "male", 10),
        published_median("male", 4.5),
    ]
    assert median_age_total(frame(rows)).is_empty()
