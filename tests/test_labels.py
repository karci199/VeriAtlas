"""The ways a name match can go wrong without anyone noticing.

Not a tour of the happy path: each test below is a way a loosened comparison would file
one place under another and still look like it worked.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from veriatlas.labels import district_id, fold, province_id


def test_folding_loses_case_and_accents_but_nothing_else():
    """Case and accents go; the letters themselves stay.

    The upper-case dotless form is what store finders write, so `IĞDIR` has to reach the
    same key as `Iğdır`. The guard is the second pair: folding must not shorten a name
    into another real one, which is how a loosened matcher starts moving places around.
    """
    assert fold("IĞDIR") == fold("Iğdır") == "igdir"
    assert fold("Muş") != fold("Muşkara")
    assert fold("Kars") != fold("Kırşehir")


def test_renamed_provinces_resolve_to_one_place():
    """Three spellings of Kahramanmaraş must be one id, not three areas."""
    assert province_id("K.Maraş") == province_id("Kahramanmaraş")
    assert province_id("AFYON") == province_id("Afyonkarahisar")
    assert province_id("İçel") == province_id("Mersin")


def test_unknown_province_is_refused_not_guessed():
    """A name we do not know returns None rather than the nearest province."""
    assert province_id("Muş") is not None
    assert province_id("Muşkara") is None
    assert province_id("") is None
    assert province_id(None) is None


def test_centre_resolves_where_the_centre_survived():
    """`Merkez` in a province whose central district kept the province's name."""
    assert district_id("Amasya", "Merkez") == district_id("Amasya", "Amasya")
    assert district_id("Bolu", "Merkez") == district_id("Bolu", "Bolu")
    assert district_id("UŞAK", "UŞAK MERKEZ") == district_id("Uşak", "Uşak")


def test_centre_is_refused_where_the_centre_was_split():
    """Kahramanmaraş's Merkez became two districts in 2013; neither may claim the name.

    This is the test that matters. Picking Dulkadiroğlu or Oniki Şubat would produce a
    plausible number for a place the source never named.
    """
    assert district_id("Kahramanmaraş", "Merkez") is None
    assert district_id("Hatay", "Merkez") is None


def test_abolished_district_never_matches_itself():
    """The registry still holds `Eyüp` with a 2017 end date; today's stores are not filed
    there. The old name resolves onto the current district instead."""
    assert district_id("İstanbul", "Eyüp") == district_id("İstanbul", "Eyüpsultan")
    assert district_id("Ankara", "Kazan") == district_id("Ankara", "Kahramankazan")


def test_district_in_the_wrong_province_is_refused():
    """Seç Market files a Bismil store under Gaziantep; Bismil is in Diyarbakır.

    A matcher that searched all 973 districts would 'find' it and move a store across
    the country. Matching is scoped to the named province, so this stays unresolved.
    """
    assert district_id("Diyarbakır", "Bismil") is not None
    assert district_id("Gaziantep", "Bismil") is None
    assert district_id("Şanlıurfa", "Kızıltepe") is None


def test_junk_in_the_district_field_is_refused():
    """Postal codes and neighbourhood names appear where a district should be."""
    assert district_id("Elazığ", "23000") is None
    assert district_id("Bayburt", "CUMHURİYET MAH") is None


def test_spacing_only_matches_after_an_exact_try():
    """`ONİKİŞUBAT` is the registry's `Oniki Şubat`; collapsing spaces must not invent
    a match where the tightened forms differ."""
    assert district_id("Kahramanmaraş", "ONİKİŞUBAT") is not None
    assert district_id("Kahramanmaraş", "Oniki Şubat") == district_id(
        "Kahramanmaraş", "ONİKİŞUBAT"
    )
