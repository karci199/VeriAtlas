"""Crop balance sheets: cell markers and the identity check."""

import pytest

from veriatlas.adapters.crop_balance import check, number


def test_markers():
    # "-" is a published zero; "..." and "." are unknown, never zero.
    assert number("-") == 0.0
    assert number("...") is None
    assert number(".") is None
    assert number("1884275.7") == 1884275.7


def _row(**cols):
    cells = [None] * 21
    for col, value in cols.items():
        cells[int(col[1:])] = value
    return cells


def test_identity_that_does_not_hold_stops_the_load():
    # tomato 2024/25 with exports misread by one column
    good = _row(
        c2=14617000,
        c4=511595,
        c5=14139516,
        c6=14105405,
        c7=34111,
        c9=12561838,
        c16=1577678,
    )
    check("tomato", 2024, good)
    bad = list(good)
    bad[16] = 683220
    with pytest.raises(ValueError):
        check("tomato", 2024, bad)
