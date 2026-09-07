"""Transcription guards for the hand-read BTK per-operator ARPU series.

Nothing here can be re-parsed mechanically: the numbers are chart labels in
images. What the source does give is redundancy — the reports' windows overlap,
so most quarters are printed twice. OVERLAP holds the second reading, taken from
the other report, for every overlap that was actually checked against a rendered
page. A mistyped digit in the dataset breaks the match.
"""

import importlib.util
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "btk_arpu_dataset",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "btk_arpu_dataset.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

ROWS = mod.build()
BY_KEY = {(r["tip"], r["donem"], r["isletmeci"]): r for r in ROWS}
PERIODS = [f"{y}-{q}" for y in range(2011, 2026) for q in range(1, 5)] + ["2026-1"]

# (tip, donem) -> (turkcell, vodafone, ttmobil) as printed by the *other* report
# covering that quarter. Read back off the rendered pages named in the comment.
OVERLAP = {
    # 2012 report, read against the 2013 report's window
    ("on_odemeli", "2012-1"): (10.13, 11.50, 10.92),
    ("on_odemeli", "2012-2"): (11.31, 12.70, 12.10),
    ("on_odemeli", "2012-3"): (12.56, 13.96, 13.03),
    ("on_odemeli", "2012-4"): (12.10, 13.47, 13.56),
    ("faturali", "2012-4"): (38.10, 37.43, 32.67),
    # 2019 report, read against the 2020 report's window
    ("on_odemeli", "2018-1"): (14.9, 16.4, 18.5),
    ("on_odemeli", "2018-3"): (18.4, 18.8, 20.0),
    ("on_odemeli", "2019-4"): (18.5, 19.4, 18.9),
    ("faturali", "2018-1"): (44.0, 40.9, 35.7),
    ("faturali", "2019-3"): (58.4, 46.8, 42.7),
    ("faturali", "2019-4"): (57.8, 46.3, 42.7),
    # 2022 report, read against the 2023 report's window
    ("on_odemeli", "2022-4"): (43.9, 41.3, 46.9),
    ("faturali", "2022-4"): (96.9, 77.7, 72.0),
    # 2023 report, read against the 2024 report's window
    ("on_odemeli", "2023-4"): (87.6, 80.7, 93.6),
    ("faturali", "2023-4"): (169.0, 141.9, 128.2),
}


@pytest.mark.parametrize("key", sorted(OVERLAP), ids=lambda k: f"{k[0]}-{k[1]}")
def test_overlapping_reports_agree(key):
    tip, donem = key
    for op, other in zip(mod.OPERATORS, OVERLAP[key]):
        stored = BY_KEY[(tip, donem, op)]["tl"]
        revision = mod.REVISIONS.get((tip, donem, op))
        if revision:
            assert (revision[0], revision[1]) == (other, stored)
        else:
            assert stored == pytest.approx(other)


def test_every_quarter_present_for_both_series_and_all_operators():
    for tip in ("on_odemeli", "faturali"):
        for donem in PERIODS:
            for op in mod.OPERATORS:
                assert (tip, donem, op) in BY_KEY


def test_no_duplicate_rows():
    keys = [(r["tip"], r["donem"], r["isletmeci"]) for r in ROWS]
    assert len(set(keys)) == len(keys)


@pytest.mark.parametrize("donem", PERIODS)
@pytest.mark.parametrize("op", mod.OPERATORS)
def test_postpaid_is_always_above_prepaid(op, donem):
    """A swapped pair of charts is the easiest mistake to make here."""
    assert BY_KEY[("faturali", donem, op)]["tl"] > BY_KEY[("on_odemeli", donem, op)]["tl"]


@pytest.mark.parametrize("row", ROWS, ids=lambda r: f"{r['tip']}-{r['donem']}-{r['isletmeci']}")
def test_currency_conversions_are_consistent(row):
    """Euro and dollar figures must be the lira figure over that quarter's rate."""
    fx = mod.macro()[row["donem"]]
    assert row["eur"] == pytest.approx(row["tl"] / float(fx["eur_try"]), abs=0.01)
    assert row["usd"] == pytest.approx(row["tl"] / float(fx["usd_try"]), abs=0.01)


def test_real_lira_is_missing_only_where_the_deflator_is():
    """Eurostat's Turkish HICP stops at 2025-12, so 2026-1 has no real lira."""
    missing = sorted({r["donem"] for r in ROWS if r["tl_reel"] is None})
    assert missing == ["2026-1"]


def test_base_quarter_real_equals_nominal():
    for r in ROWS:
        if r["donem"] != mod.BASE:
            continue
        assert r["tl_reel"] == pytest.approx(r["tl"], abs=0.01)
        assert r["eur_reel"] == pytest.approx(r["eur"], abs=0.01)
        assert r["usd_reel"] == pytest.approx(r["usd"], abs=0.01)
