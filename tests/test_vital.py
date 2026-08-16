"""The transposed MEDAS export, and the two ways it can be read wrong in silence.

Both failure modes here produce a number, not an error, which is why they are tested:
a breakdown label that only appears on the first row of its block, and a month column
that has to be summed into its year rather than counted as a year of its own.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from veriatlas.adapters.tuik_vital import read_export
from veriatlas.derived import marriage_age_total, natural_increase

#: Two provinces across the header, two sexes down the rows, two months in each block,
#: two years in each month — small enough to add up by hand, shaped exactly like MEDAS's.
#: The sex is written once per block and left blank underneath, which is the trap.
DEATHS = """|||Sütunlar|
Satırlar|||Adana-1|Adıyaman-2|
||||
İkametgah Yerine Göre Ölüm Sayısı|Ölenin cinsiyeti:Erkek ve ay :01. (Ocak)|2009|100.0|10.0|
||2010|200.0|20.0|
|Ölenin cinsiyeti:Erkek ve ay :02. (Şubat)|2009|1.0|2.0|
||2010|3.0|4.0|
|Ölenin cinsiyeti:Kadın ve ay :01. (Ocak)|2009|50.0|5.0|
||2010|60.0|6.0|
|Ölenin cinsiyeti:Kadın ve ay :02. (Şubat)|2009|7.0|8.0|
||2010|9.0|1.0|
"""


@pytest.fixture
def deaths(tmp_path):
    path = tmp_path / "nufus-olum-province.csv"
    path.write_text(DEATHS, encoding="utf-8")
    return path


def test_a_breakdown_written_once_carries_down_its_block(deaths):
    """The blank label under a sex is that sex, not an unreadable row.

    Read literally it cost sixteen of seventeen years: every continuation row failed the
    sex match and was dropped, and deaths loaded as a single period without complaining.
    """
    rows = read_export(deaths, ("deaths", "deaths", ("sex",), {}), {})
    years = {(row["year"], row["dims"]) for row in rows}
    assert years == {
        (2009, "sex=male"),
        (2010, "sex=male"),
        (2009, "sex=female"),
        (2010, "sex=female"),
    }


def test_months_are_summed_into_the_year(deaths):
    """Two month rows of one province-year are one row worth their total."""
    rows = read_export(deaths, ("deaths", "deaths", ("sex",), {}), {})
    adana = {
        (row["year"], row["dims"]): row["value"]
        for row in rows
        if row["area_id"] == "TR-01"
    }
    assert adana[(2009, "sex=male")] == 101.0
    assert adana[(2010, "sex=female")] == 69.0
    assert len(rows) == 8, "iki il × iki yıl × iki cinsiyet"


def test_dropping_the_dim_sums_every_row_of_the_year(deaths):
    """Births are read this way: no breakdown kept, the whole block summed."""
    rows = read_export(deaths, ("births", "births", None, {}), {})
    adana = {row["year"]: row["value"] for row in rows if row["area_id"] == "TR-01"}
    assert adana == {2009: 158.0, 2010: 272.0}


def test_natural_increase_needs_both_sides():
    """A year with births and no deaths is not a year of natural increase equal to its
    births. Half an answer here would be a confident wrong number on the map."""
    frame = pl.DataFrame(
        {
            "indicator_id": ["births", "births", "deaths"],
            "area_id": ["TR-01", "TR-01", "TR-01"],
            "area_level": ["province"] * 3,
            "period_start": [
                dt.date(2024, 1, 1),
                dt.date(2025, 1, 1),
                dt.date(2024, 1, 1),
            ],
            "frequency": ["annual"] * 3,
            "dims": ["", "", "sex=male"],
            "value": [100.0, 120.0, 40.0],
            "unit": ["birth", "birth", "death"],
            "quality_flag": ["measured"] * 3,
            "vintage": ["2026-08"] * 3,
            "source_id": ["tuik_medas"] * 3,
            "retrieved_at": [dt.date(2026, 8, 14)] * 3,
        }
    )

    result = natural_increase(frame)
    assert len(result) == 1, "2025'in ölümü yok, satırı da olmamalı"
    assert result["value"][0] == 60.0


def marriage_ages(rows):
    """A frame of `mean_marriage_age` rows: (year, sex, value)."""
    return pl.DataFrame(
        {
            "indicator_id": ["mean_marriage_age"] * len(rows),
            "area_id": ["TR-01"] * len(rows),
            "area_level": ["province"] * len(rows),
            "period_start": [dt.date(year, 1, 1) for year, _, _ in rows],
            "frequency": ["annual"] * len(rows),
            "dims": ["sex=" + sex for _, sex, _ in rows],
            "value": [value for _, _, value in rows],
            "unit": ["year_of_age"] * len(rows),
            "quality_flag": ["measured"] * len(rows),
            "vintage": ["2026-08"] * len(rows),
            "source_id": ["tuik_medas"] * len(rows),
            "retrieved_at": [dt.date(2026, 8, 14)] * len(rows),
        }
    )


def test_marriage_age_total_is_the_midpoint():
    """Exact here, because every marriage has one groom and one bride — the two averages
    carry equal weight by construction, which is not true of the median age."""
    result = marriage_age_total(
        marriage_ages([(2024, "male", 31.2), (2024, "female", 28.4)])
    )
    assert len(result) == 1
    assert result["value"][0] == pytest.approx(29.8)
    assert result["dims"][0] == "sex=total"
    assert result["quality_flag"][0] == "estimated", "bizim hesabımız, rozeti taşımalı"


def test_marriage_age_total_needs_both_sexes():
    """One sex averaged with itself is that sex's figure wearing the label "Toplam"."""
    assert marriage_age_total(marriage_ages([(2024, "male", 31.2)])).is_empty()
