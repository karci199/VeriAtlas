"""Province labour force: the ways this table goes quietly wrong.

It is a survey read as if it were a register, and a header three rows deep read as if it
were one. Both cost whole provinces.
"""

from __future__ import annotations

import polars as pl

from veriatlas.adapters.tuik_labour_province import (
    ParticipationRate,
    UnemploymentRate,
    value,
)


def rows(cls) -> pl.DataFrame:
    adapter = cls()
    return adapter.parse(adapter.fetch())


def test_the_lettered_provinces_are_not_dropped():
    r"""`TRA11`, `TRB21`, `TRC33`: a `TR\d+` pattern loses the east, which is exactly
    where unemployment is highest."""
    frame = rows(UnemploymentRate).filter(pl.col("area_level") == "province")
    assert frame["area_id"].n_unique() == 81
    for province in ("TR-30", "TR-65", "TR-25"):  # Hakkâri, Van, Erzurum
        assert province in frame["area_id"].to_list()


def test_the_interval_comes_with_the_estimate():
    """A point estimate on its own would rank survey noise as if it were fact."""
    frame = rows(UnemploymentRate).filter(
        (pl.col("area_id") == "TR-30") & (pl.col("period_start").dt.year() == 2025)
    )
    bounds = dict(zip(frame["dims"], frame["value"], strict=True))
    assert bounds["bound=lower_95"] < bounds["bound=point"] < bounds["bound=upper_95"]
    assert bounds["bound=upper_95"] - bounds["bound=lower_95"] > 5  # small province


def test_every_province_has_every_year():
    frame = rows(ParticipationRate).filter(pl.col("area_level") == "province")
    assert frame["period_start"].n_unique() == 4
    assert frame.height == 81 * 4 * 3


def test_a_footnote_marker_does_not_turn_a_rate_into_nothing():
    assert value("13,8 (1)") == 13.8
    assert value("") is None
    assert value("-") is None
