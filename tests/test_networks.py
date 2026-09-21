"""Branch and ATM networks: the ways a record is miscounted without an error."""

from __future__ import annotations

import pytest

from veriatlas.adapters import networks as n


def run(brand, rows):
    n.points.cache_clear()
    return n.points(brand, lambda: iter(rows))


ANKARA = (39.908, 32.854)  # Kızılay, Çankaya


def test_broken_coordinate_is_unplaced_not_abroad():
    """Halkbank has ATMs at 65°N. Counting them as abroad hid them from the limit."""
    rows = [n.Point(f"k{i}", "atm", *ANKARA) for i in range(10)]
    rows.append(n.Point("bad", "atm", 65.46, 55.65))
    with pytest.raises(ValueError, match="ilçeye düşmedi"):
        n.MIN_UNPLACED_ALLOWANCE, saved = 0, n.MIN_UNPLACED_ALLOWANCE
        try:
            run("x", rows)
        finally:
            n.MIN_UNPLACED_ALLOWANCE = saved


def test_northern_cyprus_is_abroad():
    rows = [n.Point("a", "atm", *ANKARA), n.Point("b", "atm", 35.19, 33.36)]
    assert len(run("y", rows)) == 1
    assert n.REPORTS[("y", "atm")].abroad == 1


def test_swapped_coordinates_fail_province_agreement():
    """Akbank's locationX is the latitude; reading it as longitude must not load."""
    rows = [n.Point(f"k{i}", "branch", 36.99, 35.33, "TR-01") for i in range(40)]
    rows += [n.Point(f"m{i}", "branch", *ANKARA, "TR-01") for i in range(5)]
    with pytest.raises(ValueError, match="uyuşuyor"):
        run("z", rows)


def test_unmeasured_duplicates_stop_the_load():
    rows = [n.Point("same", "branch", *ANKARA)] * 3
    with pytest.raises(ValueError, match="yinelenen"):
        run("w", rows)


def test_province_names():
    assert n.province("İstanbul-Anadolu") == "TR-34"
    assert n.province("AFYON") == "TR-03"
    assert n.province(6) == "TR-06"
    assert isinstance(n.province("Atlantis"), n.Unknown)


def test_bddk_gate_catches_a_doubled_bank():
    ok = {
        "ziraat": 1733,
        "vakifbank": 965,
        "halkbank": 1103,
        "ziraatkatilim": 234,
        "vakifkatilim": 224,
        "emlakkatilim": 132,
        "kuveytturk": 460,
        "turkiyefinans": 217,
        "albaraka": 221,
    }
    n.check_bddk(ok)
    with pytest.raises(ValueError, match="state"):
        n.check_bddk(ok | {"ziraat": 3466})
