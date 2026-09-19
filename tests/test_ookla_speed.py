"""Measured internet speed: the ways a tile average can quietly become the wrong number."""

from __future__ import annotations

import polars as pl
import pytest

from veriatlas.adapters.ookla_speed import SOURCE, OoklaSpeed

pytestmark = pytest.mark.skipif(not SOURCE.exists(), reason="Ookla karo dökümü yok")


@pytest.fixture(scope="module")
def table():
    return pl.read_csv(SOURCE)


def test_province_lies_between_its_districts(table):
    """A province is summed from tiles, so it cannot fall outside its districts' range.

    If it does, the two levels were built from different sets of tiles — the kind of
    mistake that leaves both numbers looking plausible on their own.
    """
    districts = table.filter(pl.col("area_level") == "district").with_columns(
        pl.col("area_id").str.slice(0, 5).alias("province")
    )
    bounds = districts.group_by(["period", "province"]).agg(
        pl.col("download").min().alias("low"), pl.col("download").max().alias("high")
    )
    provinces = table.filter(pl.col("area_level") == "province").rename(
        {"area_id": "province"}
    )
    joined = provinces.join(bounds, on=["period", "province"], how="inner")
    outside = joined.filter(
        (pl.col("download") < pl.col("low") - 0.01)
        | (pl.col("download") > pl.col("high") + 0.01)
    )
    assert outside.height == 0, outside.head().to_dicts()


def test_speeds_are_in_a_physical_range(table):
    """Kbit/s left unconverted would read as 70.000 Mbit/s and still sort correctly."""
    assert table["download"].max() < 1000
    assert table["download"].min() > 0
    assert table["latency"].max() < 5000


def test_every_area_is_a_turkish_area_id(table):
    """The source file is global; a tile in Tbilisi must not arrive as a district."""
    assert table["area_id"].str.starts_with("TR-").all()


def test_parse_keeps_every_built_row(table):
    adapter = OoklaSpeed()
    adapter.indicator_id = "mobile_download_speed"
    assert adapter.parse(SOURCE).height == table.height
