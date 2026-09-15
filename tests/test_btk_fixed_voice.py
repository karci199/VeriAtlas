"""Transcription guards for the hand-keyed BTK fixed-voice technology table.

The reports print a TOPLAM that is not used to build the row, so it is an
independent check on the six cells beside it. It does not always agree with them
— that is the source's own arithmetic, recorded quarter by quarter in
REPORTED_GAP. Pinning the gap rather than waiving it means a mistyped digit
still fails, because it would move the gap.
"""

import importlib.util
import itertools
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "btk_fixed_voice_dataset",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "btk_fixed_voice_dataset.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

ROWS = mod.build()
BY_PERIOD = {r["donem"]: r for r in ROWS}


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["donem"])
def test_components_reconcile_with_reported_total(row):
    if row["bilesen_toplami"] is None:
        assert row["not"], "eksik bilesen aciklamasiz birakilamaz"
        return
    gap = row["toplam"] - row["bilesen_toplami"]
    assert gap == mod.REPORTED_GAP.get(row["donem"], 0)


def test_recorded_gaps_all_belong_to_real_periods():
    assert set(mod.REPORTED_GAP) <= set(BY_PERIOD)


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["donem"])
def test_gap_stays_small_enough_to_be_a_reporting_slip(row):
    """A mistyped leading digit would blow past a fraction of a percent."""
    if row["bilesen_toplami"] is None:
        return
    gap = abs(row["toplam"] - row["bilesen_toplami"])
    assert gap / row["toplam"] < 0.005


def test_periods_are_unique_and_ordered():
    periods = [r["donem"] for r in ROWS]
    assert len(set(periods)) == len(periods)
    assert periods == sorted(periods)


def test_no_quarter_is_missing_from_the_run():
    """A dropped quarter would silently flatten every rate of change."""
    expected = [f"{y}-{q}" for y in range(2015, 2026) for q in range(1, 5)]
    expected = ["2014-4", *expected, "2026-1"]
    assert [r["donem"] for r in ROWS] == expected


def test_payphones_shrink_in_every_quarter_but_the_known_one():
    """Payphones fall monotonically; a rise elsewhere would mean a mis-keyed row.

    The single exception is 2020-1, where the count went from 55.113 to 55.779.
    Both figures were read back off the PDFs.
    """
    rises = [b["donem"] for a, b in itertools.pairwise(ROWS)
             if b["tt_ankesor"] >= a["tt_ankesor"]]
    assert rises == ["2020-1"]
