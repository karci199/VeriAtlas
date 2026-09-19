"""AVM, telekom ve perakende: üçünün de sessizce bozulabileceği yerler."""

from __future__ import annotations

import polars as pl
import pytest

from veriatlas.adapters import ADAPTERS
from veriatlas.adapters.ayd_malls import SOURCE as AYD_SOURCE
from veriatlas.adapters.telecom_operators import FOLDER as TELECOM_FOLDER
from veriatlas.adapters.tuik_retail import FILES
from veriatlas.adapters.tuik_retail import FOLDER as RETAIL_FOLDER


def run(name: str) -> pl.DataFrame:
    adapter = ADAPTERS[name]()
    return adapter.parse(adapter.fetch())


@pytest.mark.skipif(not AYD_SOURCE.exists(), reason="AYD dökümü yok")
def test_mall_slices_are_not_areas():
    """Anadolu is the country minus İstanbul, not a place; all three stay at TR."""
    frame = run("mall_turnover_per_sqm")
    assert set(frame["area_id"]) == {"TR"}
    slices = {row.split("=", 1)[1] for row in frame["dims"]}
    assert slices == {"tr", "istanbul", "anadolu"}


@pytest.mark.skipif(not AYD_SOURCE.exists(), reason="AYD dökümü yok")
def test_istanbul_is_dearer_than_anadolu():
    """A sanity check on the slices not being swapped: İstanbul's rent-paying metre earns
    more than Anadolu's in every month the source has published."""
    frame = run("mall_turnover_per_sqm").with_columns(
        pl.col("dims").str.split("=").list.last().alias("dilim")
    )
    wide = frame.pivot(on="dilim", index="period_start", values="value").drop_nulls()
    assert (wide["istanbul"] > wide["anadolu"]).all()


@pytest.mark.skipif(
    not (TELECOM_FOLDER / "tt_ozet_2c26.xlsx").exists(), reason="telekom dosyası yok"
)
def test_operator_counts_are_people_not_millions():
    """The unit lives in the row label: `(mn)` for Türk Telekom, `(bin)` for Turkcell's
    fibre. Missing a multiplier leaves a number a thousand or a million times too small,
    and the series still looks like a tidy curve."""
    frame = run("telecom_mobile_subscribers")
    assert frame["value"].min() > 5e6
    assert frame["value"].max() < 60e6


@pytest.mark.skipif(
    not (TELECOM_FOLDER / "2C26-FO-Veri.xlsx").exists(), reason="telekom dosyası yok"
)
def test_both_operators_arrive():
    """Two spellings of a quarter — `2014 1Ç` and `1Ç22`. One regex would silently keep
    a single company."""
    frame = run("telecom_mobile_subscribers").with_columns(
        pl.col("dims").str.split("=").list.last().alias("operator")
    )
    counts = dict(frame.group_by("operator").len().iter_rows())
    assert set(counts) == {"turkcell", "turk_telekom"}
    assert min(counts.values()) > 10


@pytest.mark.skipif(
    not (RETAIL_FOLDER / FILES["retail_volume_index"]).exists(),
    reason="TÜİK tablosu yok",
)
def test_retail_year_carries_down_the_column():
    """The year is written once and the month on every row; a reader that expects both on
    the same row keeps twelve months of 2010 and nothing else."""
    frame = run("retail_volume_index")
    years = frame.select(pl.col("period_start").dt.year().unique()).to_series().sort()
    assert years.min() == 2010
    assert years.max() >= 2023
    assert len(years) > 10


@pytest.mark.skipif(
    not (RETAIL_FOLDER / FILES["retail_volume_index"]).exists(),
    reason="TÜİK tablosu yok",
)
def test_base_year_averages_one_hundred():
    """2015 = 100 is the one thing the source guarantees; if a change column were read as
    an index the average would be nowhere near it."""
    frame = run("retail_volume_index").filter(
        (pl.col("dims") == "adjustment=none;retail_sector=total")
        & (pl.col("period_start").dt.year() == 2015)
    )
    assert frame.height == 12
    assert abs(frame["value"].mean() - 100) < 1.0


@pytest.mark.skipif(
    not (RETAIL_FOLDER / FILES["retail_turnover_index"]).exists(),
    reason="TÜİK tablosu yok",
)
def test_turnover_outruns_volume_under_inflation():
    """Turnover carries the price rise, volume does not: by 2024 the two cannot agree."""
    key = "adjustment=none;retail_sector=total"
    volume = (
        run("retail_volume_index").filter(pl.col("dims") == key).sort("period_start")
    )
    turnover = (
        run("retail_turnover_index").filter(pl.col("dims") == key).sort("period_start")
    )
    # The last period the file carries, not a date written here: the series stops when
    # TÜİK rebases, and a hard-coded month turns that into a test failure about nothing.
    last = min(volume["period_start"][-1], turnover["period_start"][-1])
    v = volume.filter(pl.col("period_start") == last)["value"][0]
    t = turnover.filter(pl.col("period_start") == last)["value"][0]
    assert last.year >= 2023
    assert t > v * 2
