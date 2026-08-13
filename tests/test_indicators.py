"""The dictionary's job is to refuse things, so that is what these check.

An undeclared indicator or an undeclared breakdown key must fail at load time. Both
would otherwise pass silently and only show up as a chart with a missing or duplicated
series, long after the import that caused it.
"""

import pytest

from veriatlas.indicators import DICTIONARY_PATH, VIEWS, check_dims, get, load
from veriatlas.schema import QUALITY_FLAGS


def test_every_indicator_resolves_its_topic_and_unit():
    """load() cross-references the file; a dangling reference raises there, not here."""
    dictionary = load()
    assert dictionary.indicators, "dictionary is empty"
    for indicator in dictionary.indicators.values():
        assert indicator.topic.topic_id in dictionary.topics
        assert indicator.unit.unit_id in dictionary.units


def test_tfr_carries_its_label_and_unit():
    tfr = get("tfr")
    assert tfr.label_tr == "Toplam doğurganlık hızı"
    assert tfr.unit.unit_id == "children_per_woman"
    assert tfr.unit.label_tr == "çocuk/kadın"
    assert tfr.unit.decimals == 2
    assert tfr.frequency == "annual"


def test_undeclared_indicator_raises():
    with pytest.raises(KeyError, match="undeclared indicator"):
        get("nufus_yogunlugu")


def test_undeclared_dimension_is_refused():
    """A typo like `yas` must not become a second, parallel series."""
    with pytest.raises(KeyError, match="yas"):
        check_dims("tfr", {"yas"})


def test_declared_dimensions_pass():
    check_dims("tfr", set())


def test_every_declared_view_is_one_the_screen_can_draw():
    """A view name outside VIEWS would render as a tab that draws nothing."""
    for indicator in load().indicators.values():
        assert indicator.views, indicator.indicator_id + " offers no view"
        assert set(indicator.views) <= set(VIEWS), indicator.indicator_id


def test_unknown_view_name_is_refused(tmp_path, monkeypatch):
    body = DICTIONARY_PATH.read_text(encoding="utf-8").replace(
        'views = ["table", "map", "line", "bar"]',
        'views = ["table", "cizgi"]',
        1,
    )
    fake = tmp_path / "indicators.toml"
    fake.write_text(body, encoding="utf-8")

    monkeypatch.setattr("veriatlas.indicators.DICTIONARY_PATH", fake)
    load.cache_clear()
    try:
        with pytest.raises(KeyError, match="cizgi"):
            load()
    finally:
        load.cache_clear()


def test_pyramid_is_only_offered_where_the_breakdown_exists():
    """The pyramid needs age and sex; offering it without them draws an empty chart."""
    for indicator in load().indicators.values():
        if "pyramid" in indicator.views:
            assert {"age", "sex"} <= set(indicator.dims), indicator.indicator_id


def test_derivations_declare_a_known_unit_and_quality():
    """A derived number that claims `measured` when it is modelled would mislabel the
    badge the reader trusts."""
    for derived in load().derivations.values():
        assert derived.unit.unit_id in load().units
        assert derived.quality in QUALITY_FLAGS, derived.derivation_id


def test_tree_is_ordered_and_places_each_indicator_once():
    tree = load().tree()
    orders = [topic.order for topic, _ in tree]
    assert orders == sorted(orders)

    placed = [ind.indicator_id for _, items in tree for ind in items]
    assert sorted(placed) == sorted(load().indicators), (
        "an indicator fell out of the tree"
    )
    assert len(placed) == len(set(placed)), "an indicator appears twice"


def test_buildings_and_dwellings_are_separate_indicators():
    """The confusion the dictionary exists to prevent: 146.553 bina = 1,19 milyon daire."""
    buildings = get("building_permits_buildings")
    dwellings = get("building_permits_dwellings")
    assert buildings.unit.unit_id != dwellings.unit.unit_id
