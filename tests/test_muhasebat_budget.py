"""The province budget tables fail quietly in two ways, so both are checked here.

A column the dictionary has no label for reaches the screen as a bare slug, and a province
name the register does not know used to end the table early: the reader stopped at the first
name it could not resolve, which turned 81 provinces into 62 without an error.
"""

import pytest

from veriatlas.adapters.kgm import province_id
from veriatlas.adapters.muhasebat import (
    EXPENDITURE_COLUMNS,
    NAME_ALIASES,
    REVENUE_COLUMNS,
)
from veriatlas.indicators import load


def test_every_budget_column_carries_a_label():
    dictionary = load()
    revenue = dictionary.dimensions["budget_revenue_item"].values_tr
    expenditure = dictionary.dimensions["budget_expenditure_item"].values_tr
    classification = dictionary.dimensions["budget_classification"].values_tr
    assert set(REVENUE_COLUMNS.values()) <= set(revenue)
    assert {line for line, _ in EXPENDITURE_COLUMNS.values()} <= set(expenditure)
    assert {kind for _, kind in EXPENDITURE_COLUMNS.values()} <= set(classification)


def test_the_abbreviated_province_name_resolves():
    assert province_id(NAME_ALIASES["urfa"]) == "TR-63"


def test_an_unknown_province_name_raises():
    with pytest.raises(KeyError):
        province_id("Urfa")
