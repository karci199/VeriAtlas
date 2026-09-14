"""KGM adapter: the silent paths — grouped-thousands rows, bracketed and unknown names."""

import pytest

from veriatlas.adapters.kgm import province_id, resolve_district, split_grouped


def test_grouped_row_is_split_by_its_total():
    # 1967: 1 289 | 12 712 | 207 | 31 190 | 9 319 | 4 540 | 59 257
    row = "1 289 12 712 207 31 190 9 319 4 540 59 257"
    assert split_grouped(row, 7) == [1289, 12712, 207, 31190, 9319, 4540, 59257]


def test_grouped_row_that_does_not_add_up_is_refused():
    with pytest.raises(ValueError):
        split_grouped("1 289 12 712 207 31 190 9 319 4 540 59 258", 7)


def test_bracketed_centre_town_and_abbreviation():
    assert province_id("KOCAELİ (İZMİT)") == "TR-41"
    assert province_id("Ş.Urfa") == "TR-63"


def test_unknown_province_is_refused():
    with pytest.raises(KeyError):
        province_id("MARAŞ")


def test_merkez_is_district_or_province_centre():
    key = {("TR-05", "amasya"): ("TR-05-001", "district")}
    assert resolve_district(key, "AMASYA", "MERKEZ") == ("TR-05-001", "district")
    assert resolve_district(key, "ANKARA", "MERKEZ") == ("TR-06", "province")
    with pytest.raises(KeyError):
        resolve_district(key, "AMASYA", "YOKBÖYLE")
