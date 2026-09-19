"""Provincial GDP in liras: the header that hides half the table, and the totals."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from veriatlas.adapters.tuik_province_gdp import (
    SECTORS,
    ProvinceGdpChained,
    ProvinceGdpCurrent,
)

pytestmark = pytest.mark.skipif(
    not (ProvinceGdpCurrent().fetch()).exists(), reason="TÜİK portal tablosu yok"
)


@pytest.fixture(scope="module")
def current():
    adapter = ProvinceGdpCurrent()
    return adapter.parse(adapter.fetch())


@pytest.fixture(scope="module")
def chained():
    adapter = ProvinceGdpChained()
    return adapter.parse(adapter.fetch())


def test_every_sector_column_is_read(current, chained):
    """The heads carry their English translation on the same line, padded with spaces.

    Cutting only at the newline matched three columns of fourteen, and the result looked
    healthy: 81 provinces, 25 years, every value correct — just eleven sectors missing.
    """
    wanted = set(SECTORS.values())
    for frame in (current, chained):
        found = {row.split("=", 1)[1] for row in frame["dims"]}
        assert found == wanted, wanted - found


def test_provinces_add_up_to_the_country_row(current):
    """The source prints its own Türkiye total; ours must be the same number."""
    gdp = current.filter(pl.col("dims") == "gdp_sector=gdp")
    country = gdp.filter(pl.col("area_level") == "country").select(
        "period_start", "value"
    )
    summed = (
        gdp.filter(pl.col("area_level") == "province")
        .group_by("period_start")
        .agg(pl.col("value").sum().alias("summed"))
    )
    joined = country.join(summed, on="period_start")
    drift = (joined["summed"] / joined["value"] - 1).abs().max()
    assert drift < 0.001, drift


def test_manufacturing_sits_inside_industry(current):
    """C is a part of B-E, not a sibling: if it ever exceeds industry, the columns slid."""
    wide = (
        current.filter(pl.col("area_level") == "province")
        .with_columns(pl.col("dims").str.split("=").list.last().alias("sector"))
        .pivot(on="sector", index=["area_id", "period_start"], values="value")
    )
    assert (wide["c"] <= wide["b_e"] * 1.0001).all()


def test_scale_is_thousand_lira(current):
    """A unit read as lira or as million lira would still rank the provinces correctly."""
    istanbul_2024 = current.filter(
        (pl.col("area_id") == "TR-34")
        & (pl.col("period_start") == dt.date(2024, 1, 1))
        & (pl.col("dims") == "gdp_sector=gdp")
    )["value"][0]
    # 13 trillion lira, written in thousands.
    assert 1e10 < istanbul_2024 < 2e10
