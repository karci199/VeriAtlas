"""Reading a district out of free text, and refusing to when the text does not say.

The resolver reads PTT's neighbourhood export, which lives outside the repository, so
every test here skips when it is not on disk rather than failing on a clean checkout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veriatlas.addresses import (
    POSTAL_CODES,
    _before,
    district_from_address,
)
from veriatlas.labels import district_id

pytestmark = pytest.mark.skipif(
    not sorted(POSTAL_CODES.glob("postakodu_*.csv")),
    reason="PTT posta kodu dökümü bu makinede yok",
)


def test_district_name_in_the_tail_wins():
    """`… Mamak / Ankara` needs no neighbourhood lookup at all."""
    found = district_from_address(
        "ANKARA",
        "Saimekadın Mahallesi Tıp Fakültesi Caddesi No: 135 / A Mamak / ANKARA",
    )
    assert found == district_id("Ankara", "Mamak")


def test_semt_resolves_through_its_neighbourhood():
    """Batıkent is a semt and no register has it; `Batıkent Mah.` puts it in Yenimahalle.

    This is the case the module exists for — an address that names a quarter people use
    and no administrative layer records.
    """
    found = district_from_address(
        "ANKARA", "Kentkoop Mh. Basıniş 19 Sitesi 14/A Batıkent / Ankara"
    )
    assert found == district_id("Ankara", "Yenimahalle")


def test_multi_word_neighbourhood_is_not_cut_to_its_last_word():
    """`Gülabi Bey Mah.` must be tried whole before `Bey`.

    An earlier version captured the shortest run before the marker and searched for
    `Bey`, which matches nothing — the failure was silent and looked like missing data.
    """
    assert _before("Gülabi Bey")[0] == "Gülabi Bey"
    assert _before("No: 250 / 29 Ulukavak") == ["Ulukavak"]


def test_shared_neighbourhood_name_resolves_to_nothing():
    """`Cumhuriyet Mah.` exists in four Aksaray districts; none of them may claim it."""
    assert (
        district_from_address("AKSARAY", "Cumhuriyet Mahallesi 129.Cadde No:31/ 1")
        is None
    )


def test_nothing_is_matched_outside_the_named_province():
    """Bismil is a Diyarbakır district; an address filed under Gaziantep stays unread."""
    assert district_from_address("Diyarbakır", "Bismil / Diyarbakır") is not None
    assert district_from_address("Gaziantep", "Bismil / Gaziantep") is None


def test_unknown_province_and_empty_address_are_refused():
    assert district_from_address("Atlantis", "Bir Mah. / Atlantis") is None
    assert district_from_address("Ankara", "") is None
    assert district_from_address(None, None) is None
