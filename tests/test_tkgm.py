"""TKGM MEGSİS: what a careless reading of the parcel table would get wrong.

The page prints three readings of the same parcels side by side. They look like parts of a
whole and are not: adding the title deed's parcels to the cadastre's counts most of the
country twice, and the approval columns cover a different universe again.
"""

from __future__ import annotations

import polars as pl

from veriatlas.adapters.tkgm import (
    ParcelApproval,
    ParcelCoordinates,
    Parcels,
    snapshot,
    table,
)


def rows(cls) -> pl.DataFrame:
    adapter = cls()
    return adapter.parse(adapter.fetch())


def test_every_province_once_per_breakdown():
    for cls in (Parcels, ParcelApproval, ParcelCoordinates):
        frame = rows(cls)
        assert frame["area_id"].n_unique() == 81, cls.indicator_id
        assert frame.select("area_id", "dims").is_duplicated().sum() == 0


def test_the_three_readings_are_not_parts_of_a_whole():
    """If they were, the deed plus the cadastre would be near the approved count."""
    register = rows(Parcels)
    deeds = register.filter(pl.col("dims") == "parcel_register=title_deed")[
        "value"
    ].sum()
    cadastre = register.filter(pl.col("dims") == "parcel_register=cadastre")[
        "value"
    ].sum()
    approved = (
        rows(ParcelApproval)
        .filter(pl.col("dims") == "parcel_approval=approved")["value"]
        .sum()
    )
    assert abs(deeds - cadastre) / cadastre < 0.05  # two counts of the same parcels
    assert deeds + cadastre > approved * 1.5


def test_snapshot_date_is_carried_not_guessed():
    taken, _ = table()
    assert snapshot().stem.endswith(taken.isoformat())
    assert rows(Parcels)["vintage"].unique().to_list() == [taken.strftime("%Y-%m")]
