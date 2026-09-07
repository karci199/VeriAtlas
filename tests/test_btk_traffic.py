"""Transcription guards for the hand-keyed BTK traffic series.

Two of the three series are read off rendered chart images rather than a text
layer, so there is no way to re-parse them mechanically. What each source does
give is a second number that the transcription does not feed into: the reports
print a total beside the parts, and the share figure sums to 100. Those are the
checks here.
"""

import importlib.util
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "btk_traffic_dataset",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "btk_traffic_dataset.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

ANNUAL = mod.build_annual()
TT = mod.build_tt()
MOBILE = mod.build_mobile()

# Turk Telekom's table is printed in whole million minutes, so the total can
# miss the sum of five rounded parts by a couple. 2024-2 is past that: its
# international row reads 9 where the quarters either side read 5, and dropping
# it to 5 makes the row reconcile exactly. Kept as printed, pinned here.
TT_TOLERANCE = 2
TT_KNOWN_GAP = {"2024-2": -4}


@pytest.mark.parametrize("row", TT, ids=lambda r: r["donem"])
def test_tt_parts_reconcile_with_reported_total(row):
    gap = round(row["toplam"] - row["bilesen_toplami"], 1)
    if row["donem"] in TT_KNOWN_GAP:
        assert gap == TT_KNOWN_GAP[row["donem"]]
    else:
        assert abs(gap) <= TT_TOLERANCE


@pytest.mark.parametrize("row", ANNUAL, ids=lambda r: str(r["yil"]))
def test_annual_split_adds_to_the_total(row):
    """Read off bar labels; the plotted total is the independent third number."""
    assert round(abs(row["mobil"] + row["sabit"] - row["toplam"]), 2) <= 0.1


@pytest.mark.parametrize("row", ANNUAL, ids=lambda r: str(r["yil"]))
def test_fixed_traffic_only_ever_falls(row):
    """Fixed call minutes declined every year except 2024, verified on the chart."""
    index = ANNUAL.index(row)
    if index == 0:
        return
    previous = ANNUAL[index - 1]["sabit"]
    assert row["sabit"] < previous or row["yil"] in (2024, 2025)


@pytest.mark.parametrize("row", MOBILE, ids=lambda r: r["donem"])
def test_operator_shares_sum_to_a_hundred(row):
    total = row["turkcell_pay"] + row["vodafone_pay"] + row["ttmobil_pay"]
    assert round(abs(total - 100), 2) <= 0.1


@pytest.mark.parametrize("row", MOBILE, ids=lambda r: r["donem"])
def test_derived_operator_volumes_add_back_to_the_total(row):
    parts = row["turkcell"] + row["vodafone"] + row["ttmobil"]
    assert round(abs(parts - row["toplam"]), 2) <= 0.1


def test_tt_quarters_are_complete_and_ordered():
    expected = ["2014-4"]
    expected += [f"{y}-{q}" for y in range(2015, 2026) for q in range(1, 5)]
    expected += ["2026-1"]
    assert [r["donem"] for r in TT] == expected


def test_annual_years_are_complete_and_ordered():
    assert [r["yil"] for r in ANNUAL] == list(range(2009, 2026))


def test_annual_overlap_between_the_two_charts_agrees():
    """2013-2019 appear on both the 2019 and 2026-Q1 charts; only one is stored.

    The stored rows switch source at 2013, so this pins which chart each year
    came from — a silent swap would change the provenance without changing a
    number, and that is worth catching.
    """
    sources = {r["yil"]: r["kaynak_rapor"] for r in ANNUAL}
    assert all(sources[y] == "2019" for y in range(2009, 2013))
    assert all(sources[y] == "2026-Q1" for y in range(2013, 2026))
