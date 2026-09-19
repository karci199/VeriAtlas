"""Average item prices: the redenomination, and the file that lies about its format."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from veriatlas.adapters.tuik_item_prices import (
    NEW_LIRA,
    AverageItemPrices,
    source_file,
    table,
)


@pytest.fixture(scope="module")
def frame():
    adapter = AverageItemPrices()
    return adapter.parse(adapter.fetch())


def test_old_lira_is_converted():
    """Rice is 2.545.872 in December 2004 and 2,55 in January 2005 in the source.

    Both must come out on the same scale, or every chart breaks at exactly that month.
    The check is a ratio rather than a value: the price itself may be revised, the jump
    may not reappear.
    """
    _, values = table()
    rice = {period: price for code, period, price in values if code == "0111101"}
    before = rice[dt.date(2004, 12, 1)]
    after = rice[NEW_LIRA]
    assert 0.5 < before / after < 2, f"para birimi çevrilmemiş: {before} -> {after}"


def test_no_item_jumps_across_the_redenomination():
    """The conversion is checked on every item, not just rice.

    An item whose December 2004 price is a million times its January 2005 price is one
    the conversion missed. The tolerance is wide (a factor of three) because a real price
    can move over a new year — a sharp threshold here would fail on cabbage.
    """
    _, values = table()
    before: dict[str, float] = {}
    after: dict[str, float] = {}
    for code, period, price in values:
        if period == dt.date(2004, 12, 1):
            before[code] = price
        elif period == NEW_LIRA:
            after[code] = price
    checked = 0
    for code, old_price in before.items():
        new_price = after.get(code)
        if not new_price:
            continue
        checked += 1
        assert 1 / 3 < old_price / new_price < 3, f"{code}: {old_price} -> {new_price}"
    assert checked > 100, "karşılaştırılacak madde bulunamadı"


def test_the_file_is_read_by_its_bytes_not_its_name():
    """The portal names both `.xls` and zipped `xlsx` files `.xls`; this one is a real
    BIFF file and `xlrd` proves it by opening it."""
    assert source_file().suffix == ".xls"
    with source_file().open("rb") as handle:
        assert handle.read(2) != b"PK", "bu dosya xlsx, okuyucu değiştirilmeli"


def test_series_is_monthly_and_country_level(frame):
    assert set(frame["area_id"].unique()) == {"TR"}
    assert set(frame["frequency"].unique()) == {"monthly"}
    months = frame.select(pl.col("period_start").dt.month().unique())
    assert months.height > 1
