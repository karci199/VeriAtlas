"""Chain restaurants: the ways a coordinate-to-district join fails quietly.

Nothing downstream can tell a district that has no Burger King from one whose restaurants
fell outside the boundary file, so the checks here are about placement, not totals.
"""

from __future__ import annotations

import csv

import polars as pl
import pytest

from veriatlas.adapters import chain_stores
from veriatlas.adapters.chain_stores import (
    BRANDS,
    TURKEY,
    ChainRestaurants,
    ChainStores,
    counts,
    dump,
    label_counts,
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


def domestic(brand: str) -> int:
    """Rows whose coordinate is inside Türkiye — the only fair denominator.

    Several brands list branches abroad in the same file: EspressoLab has 102 (Casablanca,
    Cairo, Amman, Bavaria, Dubai) of 421, Madame Coco 59 of 719. Counting those as
    "unplaced" would make a perfectly healthy parse look broken.
    """
    x0, y0, x1, y1 = TURKEY
    inside = 0
    with dump(brand).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                lng, lat = float(row["lng"]), float(row["lat"])
            except ValueError:
                inside += 1  # no coordinate at all still counts against the parse
                continue
            inside += x0 <= lng <= x1 and y0 <= lat <= y1
    return inside


def test_every_brand_places_almost_all_of_its_domestic_branches():
    """A boundary file that stops matching would shrink the count without erroring."""
    for brand in BRANDS:
        placed = sum(counts(brand).values())
        inside = domestic(brand)
        assert placed / inside > 0.95, f"{brand}: {placed}/{inside}"


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


def test_label_counts_lose_nothing():
    """BİM and Migros publish a total; every store in it has to reach a district.

    A coordinate that falls outside a boundary is a visible failure — the parse counts it
    and trips a threshold. A *name* that fails to match is invisible: the district simply
    shows no BİM, which reads as a fact about the country rather than a gap in the
    parsing. So the bar here is not 95%, it is all of them.
    """
    for brand, expected in (("bim", 13057), ("migros", 3442)):
        assert sum(label_counts(brand).values()) == expected


def test_unknown_district_name_raises_rather_than_dropping_the_row(
    tmp_path, monkeypatch
):
    """The whole point of the alias tables: a name nobody recognised must stop the load."""
    bad = tmp_path / "district_counts.csv"
    bad.write_text(
        "il,ilce,magaza_sayisi\nAnkara,Çankaya,3\nAnkara,Yenimahalleee,4\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(chain_stores.COUNT_BRANDS, "sahte", str(bad))
    monkeypatch.setattr(chain_stores, "dump", lambda brand: bad)
    monkeypatch.setattr(chain_stores, "cached_copy", lambda source, target: source)
    with pytest.raises(KeyError, match="Yenimahalleee"):
        chain_stores.label_counts.__wrapped__("sahte")


def test_central_district_is_the_province_name():
    """Both sources write `Merkez`; the registry writes `Bolu`. If that rule broke, the
    province's biggest district would go missing and nothing else would complain."""
    counts_by_area = label_counts("bim")
    assert counts_by_area["TR-14-001"] == 36, "Bolu Merkez yerine oturmadı"
