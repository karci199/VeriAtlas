"""TESK: the ways the registry tables break without looking broken.

The hazard here is a province that quietly disappears. pdfplumber's table finder drops one
row per file (Karabük from 2025, Kırklareli from the snapshot) although both are in the
text layer, and a short table looks exactly like a complete one downstream.
"""

from __future__ import annotations

import pytest

from veriatlas.adapters.kgm import province_id, provinces
from veriatlas.adapters.tesk import FLOW, STOCK, YEARS, count, flow, stock


def test_every_province_in_every_year():
    expected = set(provinces().values())
    for year in YEARS:
        assert set(flow(year)) == expected, year


def test_snapshot_holds_all_81():
    assert set(stock()) == set(provinces().values())


def test_karabuk_and_kirklareli_are_read():
    """The two rows pdfplumber's table finder loses."""
    assert flow(2025)["TR-78"]["registrations"] == 1284
    assert stock()["TR-39"]["tradesmen"] == 14803


def test_stock_keeps_counts_not_population():
    """The row carries a population column we drop; it must not land in another field."""
    match = STOCK.search("ADANA 59266 62953 2283609 2.60% 77")
    assert match is not None
    assert [match.group(i) for i in (2, 3, 5)] == ["59266", "62953", "77"]
    adana = stock()["TR-01"]
    assert adana["tradesmen"] > adana["chambers"]
    assert adana["chambers"] < 200  # chambers per province, not the province population


def test_chambers_are_chambers():
    """A province with more `chambers` than tradesmen means a column slipped."""
    for area, row in stock().items():
        assert row["chambers"] < row["tradesmen"] / 10, area
    assert 2000 < sum(r["chambers"] for r in stock().values()) < 5000


def test_short_row_does_not_shift_columns():
    """`BİNGÖL 468 4 478` has three numbers for four columns; it must not match at all."""
    assert FLOW.search("BİNGÖL 468 4 478") is None
    assert FLOW.search("HAKKARİ 9") is None


def test_thousand_separator():
    match = FLOW.search("ADANA 5.257 440 2925 190")
    assert match is not None
    assert count(match.group(2)) == 5257


def test_unknown_province_is_refused():
    with pytest.raises(KeyError):
        province_id("KUZEY ADANA")
