"""TÜİK baby names: the ways this table misleads without looking broken.

Two traps. The portal's province list misspells Siirt, so a name-matched province would go
missing; and the rows are a top-30 cut, so anything that sums them — provinces into a
country, names into a year's births — is wrong while looking perfectly reasonable.
"""

from __future__ import annotations

import polars as pl

from veriatlas.adapters.tuik_names import (
    BabyNames,
    CommonNames,
    CommonSurnames,
    rows,
)


def frame(cls=BabyNames) -> pl.DataFrame:
    adapter = cls()
    return adapter.parse(adapter.fetch())


def test_every_province_and_the_country():
    data = rows("bebek", "Isim", "given_name", "DogumYil")
    provinces = data.filter(pl.col("area_level") == "province")
    assert provinces["area_id"].n_unique() == 81
    assert set(data.filter(pl.col("area_level") == "country")["area_id"]) == {"TR"}
    assert "TR-56" in set(provinces["area_id"])  # Siirt, spelt SİİRT by the portal


def test_one_row_per_area_year_name_sex():
    keys = frame().select("area_id", "period_start", "dims")
    assert keys.is_duplicated().sum() == 0


def test_short_lists_are_the_threshold_not_a_lost_request():
    """Fewer than 30 names is legitimate only where the third baby cuts the list off.

    TÜİK does not publish a name given to fewer than three babies, so Tunceli, Bayburt and
    Ardahan run out of names before 30. Anywhere else a short list means a request came
    back truncated and was saved anyway.
    """
    data = frame().with_columns(pl.col("dims").str.extract(";sex=(.+)$").alias("sex"))
    groups = data.group_by("area_id", "period_start", "sex").agg(
        pl.len().alias("names"), pl.col("value").min().alias("smallest")
    )
    assert data["value"].min() == 3
    short = groups.filter(pl.col("names") < 30)
    assert (short["smallest"] == 3).all()


def test_country_is_not_the_sum_of_provinces():
    """The top-30 cut: Türkiye is fetched, never added up."""
    data = frame().filter(pl.col("period_start").dt.year() == 2024)
    country = data.filter(pl.col("area_level") == "country")["value"].sum()
    provinces = data.filter(pl.col("area_level") == "province")["value"].sum()
    assert country < provinces


def test_the_three_tables_stay_apart():
    """One endpoint, three datasets: a folder mix-up would show up as the wrong dims."""
    assert frame(CommonNames)["dims"].str.contains("sex=").all()
    surnames = frame(CommonSurnames)
    assert not surnames["dims"].str.contains("sex=").any()
    assert surnames["dims"].str.starts_with("surname=").all()


def test_the_living_outnumber_the_newborns():
    """The stock table counts everyone alive, the birth table one year's babies."""
    year = 2024
    born = (
        frame()
        .filter(
            (pl.col("area_id") == "TR") & (pl.col("period_start").dt.year() == year)
        )["value"]
        .max()
    )
    alive = (
        frame(CommonNames)
        .filter(
            (pl.col("area_id") == "TR") & (pl.col("period_start").dt.year() == year)
        )["value"]
        .max()
    )
    assert alive > born * 20
