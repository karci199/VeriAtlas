"""BKM's sectoral tables: the two ways a column can lie about what it holds."""

from __future__ import annotations

import pytest

from veriatlas.adapters.bkm_sector import BKM_ADAPTERS, SECTORS, dump


def values_of(frame, key: str) -> set[str]:
    """`format_dims` sorts the pairs, so a dimension is read by name, never by position."""
    out = set()
    for dims in frame["dims"]:
        pairs = dict(pair.split("=", 1) for pair in dims.split(";"))
        out.add(pairs[key])
    return out


@pytest.fixture(scope="module")
def frames():
    return {name: cls().parse(cls().fetch()) for name, cls in BKM_ADAPTERS.items()}


def test_domestic_adapters_do_not_read_the_e_commerce_dump():
    """`sektorel_*.csv` also matches `sektorel_internet_*.csv`, and the internet file
    sorts last. The glob that ignored this handed the domestic adapter twelve columns."""
    assert "internet" not in dump("sektorel").name
    assert "internet" in dump("sektorel_internet").name


def test_total_row_is_not_stored_as_a_sector(frames):
    """`TOPLAM` sits in the published table beside the 26 groups. Stored, it would make
    every sum of the sector dimension exactly twice the truth."""
    for frame in frames.values():
        sectors = values_of(frame, "merchant_sector")
        assert sectors == set(SECTORS.values())
        assert "total" not in sectors and "TOPLAM" not in sectors


def test_e_commerce_slices_do_not_overlap(frames):
    """BKM prints the e-commerce table as two blocks that share a column: `Yurtiçi` and
    `Yerli Kart` are the same number. Keeping both would double-count domestic use."""
    frame = frames["ecommerce_spending_by_sector"]
    slices = values_of(frame, "card_usage")
    assert slices == {
        "domestic_card_abroad",
        "domestic_card_at_home",
        "foreign_card_at_home",
    }


def test_amounts_are_lira_not_million_lira(frames):
    """The source publishes million TL. A month of card spending in Türkiye is measured
    in trillions of lira; if the multiplication were dropped it would read as billions."""
    spending = frames["card_spending_by_sector"]
    newest = spending.filter(spending["period_start"] == spending["period_start"].max())
    assert newest["value"].sum() > 1e12
