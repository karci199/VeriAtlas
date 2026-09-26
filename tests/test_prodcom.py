"""PRODCOM hierarchy check: the paths that would pass or fail silently."""

import pytest

from veriatlas.adapters.prodcom import check_hierarchy, unit_id


def test_child_confidential_every_year_makes_the_set_incomplete():
    # 07.29.03.00 in 2023: one child published, two confidential ("c") in every year
    # shown. Built from rows with values only, the one child looked like the full set.
    table = {("07.29.03.00", 2023): 3630.0, ("07.29.03.00.01", 2023): 1564.0}
    listed = {"07.29.03.00", "07.29.03.00.01", "07.29.03.00.02", "07.29.03.00.03"}
    check_hierarchy("industrial_product_output", table, listed)


def test_complete_children_that_do_not_add_up_stop_the_load():
    table = {
        ("10.11.11", 2020): 100.0,
        ("10.11.11.10", 2020): 60.0,
        ("10.11.11.20", 2020): 30.0,
    }
    listed = {code for code, _ in table}
    with pytest.raises(ValueError):
        check_hierarchy("industrial_product_output", table, listed)


def test_enterprise_counts_are_not_additive():
    # A firm making both children is counted twice below, once above.
    table = {
        ("13.92.14", 2012): 121.0,
        ("13.92.14.10", 2012): 70.0,
        ("13.92.14.20", 2012): 54.0,
    }
    listed = {code for code, _ in table}
    check_hierarchy("industrial_product_enterprises", table, listed)
    table[("13.92.14", 2012)] = 60.0  # below the largest child: impossible
    with pytest.raises(ValueError):
        check_hierarchy("industrial_product_enterprises", table, listed)


def test_unit_id():
    assert unit_id("Number of items") == "number_of_items"
    assert unit_id("Turkish Lira") == "turkish_lira"
