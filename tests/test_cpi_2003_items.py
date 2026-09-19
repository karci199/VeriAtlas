"""The closed 2003=100 CPI basket: the two years the current basket does not reach.

`cpi_2025_items` starts in 2005-01 because that is where CBRT links its 2025=100 series.
This archive group is the only place 2003 and 2004 exist, so the tests guard the two ways
it could go wrong without anyone noticing: the old series quietly losing its early months,
and its items being read against the wrong basket's dictionary.
"""

from __future__ import annotations

import datetime as dt

import pytest

from veriatlas.adapters.evds_series import DOWNLOADS, index_tree
from veriatlas.indicators import load

GROUP = DOWNLOADS / "bie_tukfiy4.json"

pytestmark = pytest.mark.skipif(
    not GROUP.exists(), reason="EVDS arşiv grubu indirilmemiş"
)


@pytest.fixture(scope="module")
def records():
    return index_tree("cpi_2003_items")


def test_reaches_january_2003(records):
    """The whole point of keeping the closed basket."""
    periods = {r["period_start"] for r in records}
    assert min(periods) == dt.date(2003, 1, 1)


def test_general_index_averages_one_hundred_in_its_base_year(records):
    """A rebased series would come through looking fine but sitting on another scale.

    The base year is the one thing the source guarantees: the general index averages 100
    across 2003. If EVDS ever republishes this group on a different base, this fails
    rather than mixing two scales into one indicator.
    """
    general = [
        r["value"]
        for r in records
        if r["dims"] == "cpi_2003_item=fg_j0" and r["period_start"].year == 2003
    ]
    assert len(general) == 12
    assert abs(sum(general) / 12 - 100) < 0.5


def test_items_are_not_the_2025_basket(records):
    """Two baskets, two dictionaries; the codes must not be shared.

    `index_tree` raises on an item missing from the dictionary, but an item present in
    both dictionaries under the same id would pass silently and land 2003 values next to
    2025 ones.
    """
    dictionary = load().dimensions
    old = set(dictionary["cpi_2003_item"].values_tr)
    new = set(dictionary["cpi_2025_item"].values_tr)
    assert not old & new
    assert {r["dims"].split("=", 1)[1] for r in records} <= old
