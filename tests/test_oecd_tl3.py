"""OECD TL3: the ways these files break without looking broken.

Every dataflow carries the same measure twice, once as a count and once as a rate, and the
patent file carries each year twice, by application and by priority date. Dropping either
filter doubles a province-year without raising anything.
"""

from __future__ import annotations

import polars as pl

from veriatlas.adapters.oecd_tl3 import (
    HomicideRate,
    HospitalDischarges,
    PatentApplications,
    VehicleThefts,
)


def rows(cls) -> pl.DataFrame:
    adapter = cls()
    return adapter.parse(adapter.fetch())


def test_one_value_per_province_year():
    """The count/rate pair and the two patent date types must each leave one row."""
    for cls in (HospitalDischarges, HomicideRate, VehicleThefts, PatentApplications):
        frame = rows(cls)
        keys = frame.select("area_id", "period_start", "dims")
        assert keys.is_duplicated().sum() == 0, cls.indicator_id
        assert frame["area_id"].n_unique() == 81, cls.indicator_id


def test_patents_are_application_year_and_fractional():
    frame = rows(PatentApplications)
    assert frame["period_start"].dt.year().max() == 2024  # priority stops at 2023
    total = frame.filter(pl.col("dims") == "patent_technology=total")
    assert (total["value"] % 1 != 0).any()  # inventors split between provinces


def test_technology_total_is_not_the_sum_of_the_fields():
    """The seven fields overlap; adding them up would overcount."""
    frame = rows(PatentApplications).filter(pl.col("period_start").dt.year() == 2024)
    total = frame.filter(pl.col("dims") == "patent_technology=total")["value"].sum()
    fields = frame.filter(pl.col("dims") != "patent_technology=total")["value"].sum()
    assert total > 0 and fields > 0 and abs(total - fields) > 1


def test_homicide_is_a_rate_not_a_count():
    """Istanbul has the most homicides and nowhere near the highest rate."""
    frame = rows(HomicideRate).filter(pl.col("period_start").dt.year() == 2024)
    istanbul = frame.filter(pl.col("area_id") == "TR-34")["value"].item()
    assert istanbul < frame["value"].max()
    assert frame["value"].max() < 50  # a count would run into the hundreds
