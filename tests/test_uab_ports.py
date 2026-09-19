"""Port cargo: the cumulative file, the total row, and the four spellings of a port."""

from __future__ import annotations

import polars as pl
import pytest

from veriatlas.adapters.uab_ports import FOLDER, PortCargo, december, skeleton

pytestmark = pytest.mark.skipif(not FOLDER.exists(), reason="UAB dökümü yok")


@pytest.fixture(scope="module")
def frame():
    adapter = PortCargo()
    return adapter.parse(adapter.fetch())


def test_a_year_is_not_the_sum_of_its_months(frame):
    """The monthly files are year-to-date, so only December may be read.

    Türkiye handles roughly half a billion tonnes a year. Summing the twelve cumulative
    files gives about 3,5 billion — a number that still ranks the provinces correctly and
    is wrong by six and a half times.
    """
    total = frame.filter(pl.col("dims") == "cargo_direction=total;trade_type=total")
    for (year,), rows in total.group_by(pl.col("period_start").dt.year()):
        tonnes = rows["value"].sum()
        assert 4e8 < tonnes < 7e8, f"{year}: {tonnes / 1e6:.0f} mn ton"


def test_the_sheets_own_total_row_is_not_a_province(frame):
    """`Toplam / Total` sits among the ports; counted as one, it doubles the country."""
    assert frame["area_id"].str.starts_with("TR-").all()
    assert frame.filter(pl.col("area_level") != "province").height == 0


def test_capitalised_and_title_case_names_fold_together():
    """2020 writes ports in Turkish capitals, later years in title case."""
    assert skeleton("İSKENDERUN") == skeleton("İskenderun")
    assert skeleton("KARADENİZ EREĞLİSİ") == skeleton("Karadeniz Ereğli")


def test_a_year_without_december_is_left_out():
    """2020's twelfth file is missing at source; the year must not load short.

    Its November file reports 497 mn tonnes, which would pass any range check and read as
    a bad year rather than a missing month.
    """
    assert december(2020) is None


def test_loading_and_unloading_add_to_the_total(frame):
    """The three blocks are the source's own; if the columns slid, they stop agreeing."""
    wide = (
        frame.filter(pl.col("dims").str.contains("trade_type=total"))
        .with_columns(pl.col("dims").str.extract(r"cargo_direction=(\w+)").alias("yon"))
        .pivot(on="yon", index=["area_id", "period_start"], values="value")
    )
    drift = ((wide["loading"] + wide["unloading"]) / wide["total"] - 1).abs().max()
    assert drift < 0.001, drift
