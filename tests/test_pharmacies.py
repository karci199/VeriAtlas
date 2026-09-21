"""The pharmacy register: a count that fails silently when a name does not match."""

from __future__ import annotations

import csv

import polars as pl
import pytest

from veriatlas.adapters.pharmacies import Pharmacies, dump
from veriatlas.areas import resolve_district


@pytest.fixture(scope="module")
def frame():
    adapter = Pharmacies()
    return adapter.parse(adapter.fetch())


def test_every_licensed_pharmacy_reaches_a_district(frame):
    """Not 95%, all of them: an unplaced name shows up as a district with no pharmacy,
    which reads as a fact about the country rather than a parsing gap."""
    with dump().open(encoding="utf-8", newline="") as handle:
        published = sum(1 for _ in csv.DictReader(handle))
    districts = frame.filter(area_level="district")
    assert int(districts["value"].sum()) == published


def test_province_rows_are_the_sum_of_their_districts(frame):
    districts = frame.filter(area_level="district")
    provinces = frame.filter(area_level="province")
    assert len(provinces) == 81
    rolled = (
        districts.with_columns(area_id=districts["area_id"].str.slice(0, 5))
        .group_by("area_id")
        .agg(pl.col("value").sum())
        .sort("area_id")
    )
    got = provinces.select("area_id", "value").sort("area_id")
    assert got.equals(rolled)


def test_central_district_and_the_alias_table_still_apply():
    """The register writes `Merkez` and drops circumflexes, exactly like the two store
    finders. If that rule broke, a province's biggest district would vanish."""
    assert resolve_district("Bolu", "Merkez") == "TR-14-001"
    assert resolve_district("Adıyaman", "Kahta") == resolve_district(
        "Adıyaman", "Kâhta"
    )
    with pytest.raises(KeyError):
        resolve_district("Ankara", "Yenimahalleee")
