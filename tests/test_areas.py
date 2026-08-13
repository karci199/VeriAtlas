"""The area registry's failure mode is silence: a name that does not match.

Sources publish names, not codes, so an unmatched name is the most likely way for an
import to lose rows without anyone noticing. These tests pin the refusal to guess.
"""

import pytest

from veriatlas.areas import load_areas, resolve


def test_registry_holds_81_provinces_and_the_country():
    areas = load_areas()
    assert areas.filter(areas["area_level"] == "province").height == 81
    assert areas.filter(areas["area_level"] == "country").height == 1


def test_plate_codes_match_known_provinces():
    """The ids are ISO 3166-2:TR, so the number is the plate code."""
    mapping = resolve(["Adana", "İstanbul", "Mersin", "Kahramanmaraş", "Düzce"])
    assert mapping == {
        "Adana": "TR-01",
        "İstanbul": "TR-34",
        "Mersin": "TR-33",
        "Kahramanmaraş": "TR-46",
        "Düzce": "TR-81",
    }


def test_unknown_name_raises_instead_of_yielding_a_null_id():
    with pytest.raises(KeyError, match="Maraş"):
        resolve(["Adana", "Maraş"])


def test_surrounding_whitespace_is_tolerated():
    assert resolve([" Bursa "]) == {" Bursa ": "TR-16"}
