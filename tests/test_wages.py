"""Silent-corruption paths of the HMB pay-parameter tables."""

import datetime as dt

import pytest

from veriatlas.adapters.wages import _cell_date, _in_force

D = dt.date


def test_same_date_twice_is_refused():
    with pytest.raises(ValueError, match="tarih sırası"):
        _in_force([(D(2020, 1, 1), 1.0), (D(2020, 1, 1), 2.0)], "test")


def test_january_2012_revision_takes_the_later_row():
    series = _in_force([(D(2012, 1, 1), 1.0), (D(2012, 1, 1), 2.0)], "test")
    assert series[D(2012, 1, 1)] == 2.0


def test_unconverted_old_lira_breaks_at_2005():
    # A pre-2005 value left in old lira is a millionfold drop at the redenomination.
    with pytest.raises(ValueError, match="YTL"):
        _in_force([(D(2004, 7, 1), 38_610.0), (D(2005, 1, 1), 0.0401)], "test")


def test_unknown_month_name_is_refused():
    with pytest.raises(ValueError, match="okunamadı"):
        _cell_date("1 Ocuk 1990", 0)
