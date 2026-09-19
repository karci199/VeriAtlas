"""Chain restaurants: the ways a coordinate-to-district join fails quietly.

Nothing downstream can tell a district that has no Burger King from one whose restaurants
fell outside the boundary file, so the checks here are about placement, not totals.
"""

from __future__ import annotations

import csv

import polars as pl
import pytest

from veriatlas.adapters.chain_stores import (
    BRANDS,
    TURKEY,
    ChainRestaurants,
    ChainStores,
    counts,
    dump,
    locate,
)


@pytest.fixture(scope="module")
def frame():
    adapter = ChainRestaurants()
    return adapter.parse(adapter.fetch())


def test_known_points_land_in_their_district():
    """Coordinates checked by hand against the address the source prints."""
    assert locate(32.8541, 39.9080) == "TR-06-007"  # Kızılay, Ankara Çankaya
    assert locate(28.9784, 41.0082) == "TR-34-020"  # Sultanahmet, İstanbul Fatih
    assert locate(35.0, 35.0) is None  # Mediterranean, off the Syrian coast


def test_every_brand_places_almost_all_of_its_restaurants():
    """A boundary file that stops matching would shrink the count without erroring."""
    for brand in BRANDS:
        placed = sum(counts(brand).values())
        with dump(brand).open(encoding="utf-8") as handle:
            total = sum(1 for _ in handle) - 1
        assert placed / total > 0.95, f"{brand}: {placed}/{total}"


def test_one_row_per_area_and_brand(frame):
    keys = frame.select("area_id", "dims")
    assert len(keys) == len(keys.unique()), "aynı ilçe-marka iki satır"


def test_province_rows_equal_their_districts(frame):
    """The province is a sum of districts, not a second reading of the same source."""
    districts = frame.filter(area_level="district")
    provinces = frame.filter(area_level="province")
    rolled = (
        districts.with_columns(area_id=districts["area_id"].str.slice(0, 5))
        .group_by("area_id", "dims")
        .agg(total=pl.col("value").sum())
        .sort("area_id", "dims")
    )
    got = provinces.select("area_id", "dims", total="value").sort("area_id", "dims")
    assert got.equals(rolled)


def test_brands_are_not_added_together(frame):
    """Every brand is a separate row; a caller summing them is doing that
    deliberately, the indicator never pre-sums them into a 'total' row."""
    brands = set(frame["dims"].unique())
    assert brands == {f"restaurant_brand={brand}" for brand in BRANDS}


def test_retail_is_a_separate_indicator():
    """A cosmetics shop and a burger branch are not the same count, and the two
    indicators must not leak into one another's rows."""
    stores = ChainStores()
    frame = stores.parse(stores.fetch())
    assert set(frame["indicator_id"].unique()) == {"chain_stores"}
    assert all(d.startswith("store_brand=") for d in frame["dims"].unique())


def test_stores_abroad_leave_the_count_without_tripping_the_threshold():
    """Madame Coco lists Moscow, Almaty and Beirut in the same file as Adana.

    Those rows are foreign, not misplaced, so they must not eat into the 3% that guards
    the boundary file — before the two were separated the brand failed the load outright.
    The rows are counted with the csv reader, not by lines: an address field carries a
    newline often enough that `wc -l` overstates the file by fifteen stores.
    """
    x0, y0, x1, y1 = TURKEY
    inside = 0
    with dump("madame_coco").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                lng, lat = float(row["lng"]), float(row["lat"])
            except ValueError:
                continue
            inside += x0 <= lng <= x1 and y0 <= lat <= y1
    placed = sum(counts("madame_coco").values())
    assert inside < 719, "yurt dışı mağazalar ayıklanmadı"
    assert placed / inside > 0.97, f"yurt içi kayıp fazla: {placed}/{inside}"
