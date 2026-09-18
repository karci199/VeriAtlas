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
    district_table,
    snapshot,
    table,
)


def rows(cls) -> pl.DataFrame:
    adapter = cls()
    return adapter.parse(adapter.fetch())


def test_every_area_once_per_breakdown():
    """Several cadastral units can share a settlement; they are summed, not repeated."""
    for cls in (Parcels, ParcelApproval, ParcelCoordinates):
        frame = rows(cls)
        provinces = frame.filter(pl.col("area_level") == "province")
        districts = frame.filter(pl.col("area_level") == "district")
        assert provinces["area_id"].n_unique() == 81, cls.indicator_id
        assert districts["area_id"].n_unique() == 973, cls.indicator_id
        assert frame.select("area_id", "dims").is_duplicated().sum() == 0


def test_districts_add_up_to_their_province():
    """The page's own arithmetic: a drill-down that came back for the wrong parent
    would otherwise look like perfectly good data."""
    frame = rows(Parcels).filter(pl.col("dims") == "parcel_register=cadastre")
    provinces = frame.filter(pl.col("area_level") == "province")
    districts = (
        frame.filter(pl.col("area_level") == "district")
        .with_columns(pl.col("area_id").str.slice(0, 5).alias("province"))
        .group_by("province")
        .agg(pl.col("value").sum())
    )
    joined = provinces.join(districts, left_on="area_id", right_on="province")
    assert joined.height == 81
    assert (joined["value"] - joined["value_right"]).abs().max() == 0


def test_settlements_never_exceed_their_district():
    """Matched units are a subset of the district's units, never a superset."""
    frame = rows(Parcels).filter(pl.col("dims") == "parcel_register=cadastre")
    districts = dict(
        zip(
            frame.filter(pl.col("area_level") == "district")["area_id"],
            frame.filter(pl.col("area_level") == "district")["value"],
            strict=True,
        )
    )
    settlements = (
        frame.filter(pl.col("area_level").is_in(["neighbourhood", "village"]))
        .with_columns(pl.col("area_id").str.slice(0, 9).alias("district"))
        .group_by("district")
        .agg(pl.col("value").sum())
    )
    for district, value in zip(
        settlements["district"], settlements["value"], strict=True
    ):
        assert value <= districts[district] + 1, district


def test_the_three_readings_are_not_parts_of_a_whole():
    """If they were, the deed plus the cadastre would be near the approved count."""
    register = rows(Parcels).filter(pl.col("area_level") == "province")
    deeds = register.filter(pl.col("dims") == "parcel_register=title_deed")[
        "value"
    ].sum()
    cadastre = register.filter(pl.col("dims") == "parcel_register=cadastre")[
        "value"
    ].sum()
    approved = (
        rows(ParcelApproval)
        .filter(pl.col("area_level") == "province")
        .filter(pl.col("dims") == "parcel_approval=approved")["value"]
        .sum()
    )
    assert abs(deeds - cadastre) / cadastre < 0.05  # two counts of the same parcels
    assert deeds + cadastre > approved * 1.5


def test_snapshot_date_is_carried_not_guessed():
    taken, _ = table()
    assert snapshot().stem.endswith(taken.isoformat())
    drilled, _ = district_table()
    assert rows(Parcels)["vintage"].unique().to_list() == [drilled.strftime("%Y-%m")]


def test_province_rows_come_from_the_same_snapshot_as_the_rest():
    """Not from the province table: it is four days older and a few thousand parcels
    short, which would make the levels disagree with each other."""
    published = table()[1]["TR-34"]["kadastro_parsel"]
    rebuilt = (
        rows(Parcels)
        .filter(pl.col("area_id") == "TR-34")
        .filter(pl.col("dims") == "parcel_register=cadastre")["value"]
        .item()
    )
    assert rebuilt != published
    assert abs(rebuilt - published) < published * 0.01
