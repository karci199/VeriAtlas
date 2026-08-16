"""The median age of everyone, and the ways of getting it quietly wrong.

None of these show up on the chart. A median computed off a short denominator lands two
years low and looks entirely plausible; a median taken of the two published medians is a
number nobody can tell apart from the real one by eye. So they are pinned here.
"""

import datetime as dt

import polars as pl
import pytest

from veriatlas.derived import age_specific_death_rate, median_age_total

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


# region Age-specific death rate
#
# The failure here is a rate that comes out plausible. Both sides are counts, both are
# published, and any mistake in lining their age bands up produces a number in the right
# order of magnitude — so none of these would be caught by looking at the chart.


def deaths_by_age(age, sex, value, area_id="TR-16"):
    row = population(age, sex, value, area_id)
    return {**row, "indicator_id": "deaths_by_age", "unit": "death"}


def rates(rows, indicator_id="death_rate_by_age"):
    return {
        row["dims"]: row["value"]
        for row in age_specific_death_rate(frame(rows)).to_dicts()
        if row["indicator_id"] == indicator_id
    }


def test_single_years_fold_into_the_death_bands():
    """The population's single years are summed to the band the deaths came in.

    Ten deaths at 5-9 over a hundred people aged 5, 6, 7, 8 and 9 is 100‰. Fold the
    denominator wrong — one single year instead of five — and it is 500‰, which is a
    catastrophe rather than an implausibility, but the same arithmetic off by one band
    at 65-69 lands somewhere a reader would believe.
    """
    rows = [population(str(age), "male", 20) for age in range(5, 10)]
    rows.append(deaths_by_age("5-9", "male", 10))
    assert rates(rows) == {"age=5-9;sex=male": 100.0}


def test_infancy_is_its_own_band():
    """`0` and `1-4` are separate in the death file, so they are separate here.

    Folded together the infant rate — the highest under fifty — would be diluted across
    five years of childhood and drop by about four fifths.
    """
    rows = [population("0", "female", 100), population("1", "female", 100)]
    rows += [deaths_by_age("0", "female", 5), deaths_by_age("1-4", "female", 1)]
    assert rates(rows) == {"age=0;sex=female": 50.0, "age=1-4;sex=female": 10.0}


def test_the_unknown_band_has_no_rate():
    """It has no population to be a rate of, so it produces no row rather than a rate
    over somebody else's denominator."""
    rows = [population("0", "male", 100), deaths_by_age("unknown", "male", 7)]
    assert rates(rows) == {}


def test_a_band_with_no_population_produces_no_row():
    """An inner join. A rate over an assumed base is the shape of a number that cannot be
    checked and does not say so."""
    rows = [population("0", "male", 100), deaths_by_age("70-74", "male", 7)]
    assert rates(rows) == {}


def test_the_sexes_are_not_pooled():
    """Male deaths over the male population. Crossed, the two rates would swap and stay
    the same on the total — which is exactly the error nothing downstream can see."""
    rows = [
        population("0", "male", 100),
        population("0", "female", 200),
        deaths_by_age("0", "male", 10),
        deaths_by_age("0", "female", 10),
    ]
    assert rates(rows) == {"age=0;sex=male": 100.0, "age=0;sex=female": 50.0}


def test_the_rate_says_it_is_derived():
    """Both indicators the derivation writes: the published bands and the broad groups."""
    rows = [population("0", "male", 100), deaths_by_age("0", "male", 10)]
    result = age_specific_death_rate(frame(rows))
    assert set(result["quality_flag"]) == {"estimated"}
    assert set(result["unit"]) == {"per_mille"}
    assert set(result["indicator_id"]) == {"death_rate_by_age", "death_rate_broad"}


def test_the_broad_group_is_weighted_not_averaged():
    """Counts summed first, divided once.

    A thousand people at 65-69 with one death and ten at 75+ with five: 1‰ and 500‰. The
    65+ rate is 6/1010 ≈ 5,94‰ — the average of the two is 250‰ and their sum is 501‰,
    and both of those are numbers a reader would take at face value.
    """
    rows = [population(str(age), "male", 200) for age in range(65, 70)]
    rows += [population("75+", "male", 10)]
    rows += [deaths_by_age("65-69", "male", 1), deaths_by_age("75+", "male", 5)]

    broad = rates(rows, "death_rate_broad")
    assert broad["age=65+;sex=male"] == pytest.approx(6 / 1010 * 1000)


def test_the_broad_groups_partition_the_bands():
    """Every band lands in exactly one group, so the three groups hold every death that
    has an age. A band left out would quietly shrink one group's numerator."""
    rows = [population(str(age), "female", 10) for age in range(75)]
    rows += [population("75+", "female", 10)]
    rows += [
        deaths_by_age(band, "female", 1)
        for band in (
            "0",
            "1-4",
            "5-9",
            "10-14",
            "15-19",
            "20-24",
            "25-29",
            "30-34",
            "35-39",
            "40-44",
            "45-49",
            "50-54",
            "55-59",
            "60-64",
            "65-69",
            "70-74",
            "75+",
        )
    ]
    broad = rates(rows, "death_rate_broad")
    assert set(broad) == {
        "age=0-14;sex=female",
        "age=15-64;sex=female",
        "age=65+;sex=female",
    }
    # Four bands of the seventeen are children (fifteen single years of population),
    # three are old (ten single years plus the closing band), ten are in between.
    assert broad["age=0-14;sex=female"] == pytest.approx(4 / 150 * 1000)
    assert broad["age=65+;sex=female"] == pytest.approx(3 / 110 * 1000)


# endregion
