"""Old-lira prices: divided once, and a series already in new lira stops the load."""

import polars as pl
import pytest

from veriatlas.adapters.tuik_topics import old_lira_to_new


def _frame(values):
    return pl.DataFrame(
        {
            "area_id": ["TR"] * len(values),
            "dims": ["fish_species=701"] * len(values),
            "year": list(values),
            "value": list(values.values()),
        }
    )


def test_old_lira_divided_before_2005():
    out = old_lira_to_new(_frame({2004: 7_500_000.0, 2005: 9.0}), "sea_fish_price")
    assert out.sort("year")["value"].to_list() == [7.5, 9.0]


def test_series_already_in_new_lira_is_refused():
    # Divided again it would read 0.0000075 TL/kg in 2004.
    with pytest.raises(ValueError):
        old_lira_to_new(_frame({2004: 7.5, 2005: 9.0}), "sea_fish_price")
