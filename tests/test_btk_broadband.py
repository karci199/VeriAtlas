"""Transcription guards for the hand-keyed BTK broadband table.

Every row is read off a PDF by eye, so a digit can go wrong without anything
looking odd. The reports print a total that is not used to build the row, which
gives an independent check on each row.
"""

import importlib.util
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "btk_broadband_dataset",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "btk_broadband_dataset.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

ROWS = mod.build()


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["donem"])
def test_components_match_reported_total(row):
    parts = ("xdsl", "kablo", "kablosuz_sabit", "diger", "mobil_bilgisayar", "mobil_cep")
    total = sum(row[k] or 0 for k in parts) + (row["fiber"] or 0)
    assert total == row["toplam"]


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["donem"])
def test_fiber_total_matches_its_split(row):
    if row["ftth"] is None:
        return
    assert row["ftth"] + row["fttb"] == row["fiber"]


def test_periods_are_unique_and_ordered():
    periods = [r["donem"] for r in ROWS]
    assert len(set(periods)) == len(periods)
    assert periods == sorted(periods)
