"""Silent-failure paths in the election dataset builder.

The three checked here all produce plausible-looking output when they break:
a constituency-total row counted as a district doubles the province, a province
centre filed under its raw caption splits one place into several, and YTP put in
the wrong bloc quietly moves a whole election's left/right balance.
"""

import importlib.util
import pathlib
import sys

SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "build_election_series.py"
)
spec = importlib.util.spec_from_file_location("build_election_series", SCRIPT)
build = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = build
spec.loader.exec_module(build)


def test_ytp_is_two_different_parties():
    assert build.bloc_of("YTP", "1961") == "right"
    assert build.bloc_of("YTP", "2002") == "left"


def test_kurdish_parties_count_on_the_left():
    for party in build.KURDISH:
        assert build.bloc_of(party, "2018") == "left"


def test_no_party_is_in_both_blocs():
    assert not build.LEFT & build.RIGHT


def test_aggregate_rows_are_not_districts():
    for caption in (
        "Bursa Seçim çevresi toplamı (1 nolu)",
        "İl/İlçe merkezi",
        "Türkiye toplamı",
        "Belde ve köyler",
        "Bucağı",
    ):
        assert build.NOT_A_DISTRICT.search(build.lower_tr(caption)), caption


def test_real_districts_survive_the_filter():
    for name in ("İznik", "Merkez", "Şereflikoçhisar", "Çayırova"):
        assert not build.NOT_A_DISTRICT.search(build.lower_tr(name)), name


def test_slug_folds_turkish_letters():
    assert build.slugify("İznik") == "iznik"
    assert build.slugify("Şereflikoçhisar") == "sereflikochisar"
    assert build.slugify("Afyon Merkez") == "afyon-merkez"


def test_series_entry_keeps_parties_apart_from_totals():
    entry = build.series_entry(
        {
            build.REGISTERED: 100,
            build.VOTED: 90,
            build.VALID: 88,
            build.BALLOT_BOXES: 3,
            "CHP": 40,
            "AK PARTİ": 48,
            "CUMHUR İTTİFAKI": 48,  # alliance subtotal, would double-count
            "MHP": 0,  # not on the ballot here
        }
    )
    assert entry["e"] == 100 and entry["v"] == 90 and entry["g"] == 88
    assert entry["p"] == {"CHP": 40, "AK PARTİ": 48}
