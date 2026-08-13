"""Rolling a ratio up a level is the easiest place to be quietly wrong.

The plain mean looks right, produces plausible numbers, and is wrong — which is exactly
the kind of error nobody catches by reading the chart. These tests pin the weighting.
"""

import polars as pl

from veriatlas.aggregate import to_level
from veriatlas.areas import load_areas, load_parents, load_weights


def to_level_region(frame):
    return to_level(frame, "region")


def province_row(area_id, value, year=2025):
    return {
        "area_id": area_id,
        "area": area_id,
        "level": "province",
        "year": year,
        "value": value,
        "unit": "children_per_woman",
        "quality_flag": "measured",
        "vintage": "2026-08",
        "source_id": "tuik_medas",
    }


def two_provinces_of_one_region():
    """İstanbul (TR-34) and Bilecik (TR-11) are both Marmara, and wildly different sizes."""
    return pl.DataFrame([province_row("TR-34", 1.0), province_row("TR-11", 3.0)])


def test_weighted_mean_is_not_the_plain_mean():
    result = to_level_region(two_provinces_of_one_region())
    assert result.height == 1

    weights = dict(zip(load_weights()["area_id"], load_weights()["population"]))
    expected = (1.0 * weights["TR-34"] + 3.0 * weights["TR-11"]) / (
        weights["TR-34"] + weights["TR-11"]
    )

    value = result["value"][0]
    assert abs(value - expected) < 1e-9
    assert abs(value - 2.0) > 0.5, (
        "a plain mean would land on 2.0; the big province wins"
    )


def test_region_rows_are_flagged_estimated():
    """The number was computed, not published — the badge has to say so."""
    result = to_level_region(two_provinces_of_one_region())
    assert result["quality_flag"].to_list() == ["estimated"]
    assert result["level"].to_list() == ["region"]


def test_region_gets_its_turkish_name():
    result = to_level_region(two_provinces_of_one_region())
    assert result["area"][0] == "Marmara"


def test_province_without_a_weight_is_dropped_not_counted_as_zero():
    frame = pl.concat(
        [
            two_provinces_of_one_region(),
            pl.DataFrame([province_row("TR-99", 9.0)]),  # no such province, no weight
        ]
    )
    result = to_level_region(frame)
    assert result.height == 1, "an unknown area must not create a region of its own"


def test_every_province_has_a_parent_in_both_hierarchies_and_a_weight():
    """A gap here would silently shrink a region's population base."""
    registry = load_areas()
    provinces = set(registry.filter(pl.col("area_level") == "province")["area_id"])
    assert len(provinces) == 81
    assert provinces == set(load_weights()["area_id"])

    for hierarchy in ("geographic", "nuts"):
        members = load_parents(hierarchy)
        assert provinces <= set(members["area_id"]), hierarchy


def test_nuts_levels_have_the_official_counts():
    registry = load_areas()
    counts = dict(registry.group_by("area_level").len().iter_rows())
    assert counts["nuts1"] == 12, "İBBS-1: 12 bölge"
    assert counts["nuts2"] == 26, "İBBS-2: 26 alt bölge"
    assert counts["region"] == 7, "7 coğrafi bölge"


def test_nuts1_is_rolled_up_from_provinces_not_from_nuts2():
    """Averaging averages would reweight; TR4 must equal the weighted mean of its provinces."""
    weights = dict(zip(load_weights()["area_id"], load_weights()["population"]))
    rows = [
        province_row("TR-16", 1.0),
        province_row("TR-26", 3.0),
        province_row("TR-11", 5.0),
    ]
    frame = pl.DataFrame(rows)

    result = to_level(frame, "nuts1").filter(pl.col("area_id") == "TR4")
    expected = sum(r["value"] * weights[r["area_id"]] for r in rows) / sum(
        weights[r["area_id"]] for r in rows
    )
    assert abs(result["value"][0] - expected) < 1e-9
