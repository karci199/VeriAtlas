"""PTT postal codes: the ways a half-finished snapshot looks finished.

The fetch is 973 requests against an endpoint that rate-limits, so the failure that
matters is not a wrong number — it is a file that stops early and still parses.
"""

from __future__ import annotations

import polars as pl
import pytest

from veriatlas.adapters.ptt_postal import (
    EXPECTED_DISTRICTS,
    PostalCodes,
    codes_by_district,
)


@pytest.fixture(scope="module")
def frame():
    adapter = PostalCodes()
    return adapter.parse(adapter.fetch())


def test_every_district_is_there():
    _, districts = codes_by_district()
    assert len(districts) == EXPECTED_DISTRICTS


def test_semt_distribution_matches_the_2022_reading():
    """`docs/semt.md` counted these on the 2022 file; the 2026 snapshot repeats them.

    If PTT ever renumbers, this is the test that says so — and the semt layer's whole
    argument ("semt is the name of a postal code") would need re-checking.
    """
    _, districts = codes_by_district()
    counts = pl.Series(list(districts.values())).value_counts()
    single = counts.filter(pl.col("") == 1)["count"].item()
    assert single == 325
    assert max(districts.values()) == 21


def test_province_is_the_sum_of_its_districts(frame):
    """A postal code's first two digits are the plate number, so no code crosses a
    provincial boundary and the sums have to agree exactly."""
    districts = frame.filter(area_level="district")
    provinces = frame.filter(area_level="province")
    rolled = (
        districts.with_columns(area_id=districts["area_id"].str.slice(0, 5))
        .group_by("area_id")
        .agg(total=pl.col("value").sum())
        .sort("area_id")
    )
    got = provinces.select("area_id", total="value").sort("area_id")
    assert got.equals(rolled)


def test_no_district_is_left_without_a_code(frame):
    """A district with no postal code would mean the join lost it, not that the post
    office skips it: every inhabited place in Türkiye has a code."""
    districts = frame.filter(area_level="district")
    assert districts["value"].min() >= 1
