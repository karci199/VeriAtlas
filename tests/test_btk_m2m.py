"""Guards for the M2M series.

The annual figures are exact text, so they can be checked against each other:
the summary table also prints the total and the "kisi" row, and those three are
supposed to reconcile through a formula that changed part-way through the series.
A mistyped digit in any of the three breaks the identity.
"""

import importlib.util
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "btk_m2m_dataset",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "btk_m2m_dataset.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

ANNUAL = mod.build_annual()
QUARTERLY = mod.build_quarterly()


@pytest.mark.parametrize("row", ANNUAL, ids=lambda r: str(r["yil"]))
def test_summary_table_rows_reconcile(row):
    if row["toplam"] is None:
        assert row["yil"] == 2011, "yalnizca 2011 ozet tablosunda yok"
        return
    expected = row["toplam"] - row["m2m"] - mod.MOBILE_COMPUTER.get(row["yil"], 0)
    assert expected == row["kisi"]


def test_years_are_complete_and_ordered():
    assert [r["yil"] for r in ANNUAL] == list(range(2011, 2026))


@pytest.mark.parametrize("row", ANNUAL, ids=lambda r: str(r["yil"]))
def test_m2m_grows_every_year(row):
    """M2M has never fallen; a drop would mean a mis-keyed row."""
    index = ANNUAL.index(row)
    if index == 0:
        return
    assert row["m2m"] > ANNUAL[index - 1]["m2m"]


def test_quarterly_matches_the_annual_figures_it_overlaps():
    """Year-end quarters must round to the annual number, in millions."""
    by_period = {r["donem"]: r["m2m_milyon"] for r in QUARTERLY}
    annual = {r["yil"]: r["m2m"] for r in ANNUAL}
    for year in (2024, 2025):
        assert by_period[f"{year}-4"] == pytest.approx(annual[year] / 1e6, abs=0.05)


def test_quarterly_is_ordered_and_monotonic():
    values = [r["m2m_milyon"] for r in QUARTERLY]
    assert values == sorted(values)
    periods = [r["donem"] for r in QUARTERLY]
    assert periods == sorted(periods)


def test_the_2026_break_is_recorded():
    """2026-1's headline total excludes M2M; the two bases must not be mixed."""
    m2m_2026q1 = {r["donem"]: r["m2m_milyon"] for r in QUARTERLY}["2026-1"]
    inclusive = mod.REAL_USERS_2026Q1 + m2m_2026q1 * 1e6
    # About 98,3 million on the old basis - below 2025's 99,7 million, so the
    # apparent fall in the headline number is not all definitional.
    assert 98.0e6 < inclusive < 98.6e6


@pytest.mark.parametrize("row", ANNUAL, ids=lambda r: str(r["yil"]))
def test_penetration_matches_its_own_inputs(row):
    if row["yaygin_m2m_haric"] is None:
        assert row["nufus"] is None or row["toplam"] is None
        return
    assert row["yaygin_m2m_haric"] == pytest.approx(
        100 * row["gercek_kullanici"] / row["nufus"], abs=0.05)


def test_published_alternative_rate_is_reproduced():
    """BTK prints 106,5% for 2019 and 114,5% for 2026-1 on the 0-9-excluded base.

    Reproducing both pins the subscriber figures and the population footnotes at
    once, and confirms BTK divides total-minus-M2M rather than the "kisi" row.
    """
    by_year = {r["yil"]: r for r in ANNUAL}
    assert by_year[2019]["yaygin_m2m_ve_0_9_haric"] == pytest.approx(106.5, abs=0.05)
    rate_2026 = 100 * mod.REAL_USERS_2026Q1 / mod.NUFUS_0_9_HARIC[2025]
    assert rate_2026 == pytest.approx(114.5, abs=0.05)
