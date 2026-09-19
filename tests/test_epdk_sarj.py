"""EPDK charging stations: the ways an exported-by-hand register goes wrong quietly.

The file is not fetched by a script — it is exported page by page from behind a
reCAPTCHA — so the failures that matter are a missing page, a page counted twice, and an
address the parser stops understanding.
"""

from __future__ import annotations

import polars as pl
import pytest

from veriatlas.adapters.epdk_sarj import ChargingStations, by_district, stations


@pytest.fixture(scope="module")
def frame():
    adapter = ChargingStations()
    return adapter.parse(adapter.fetch())


def test_pages_overlap_and_are_deduplicated():
    """The exported pages repeat stations; keying on the station number is what keeps the
    count honest. Raw rows across the files exceed the distinct stations."""
    raw = 0
    import xlrd

    from veriatlas.adapters.epdk_sarj import FOLDER, STATION_NO

    for path in sorted(FOLDER.glob("*.xls")):
        sheet = xlrd.open_workbook(path).sheet_by_index(0)
        raw += sum(
            1
            for row in range(sheet.nrows)
            if str(sheet.cell_value(row, STATION_NO)).strip().startswith("ŞRJ")
        )
    assert raw > len(stations()), "sayfalar çakışmıyor — bir sayfa eksik olabilir"


def test_almost_every_address_names_a_place():
    _, unplaced = by_district()
    assert unplaced / len(stations()) < 0.02


def test_province_total_is_the_sum_of_its_districts(frame):
    """A station whose district the registry does not recognise is kept at province level,
    so the province total is at least its districts' — never less."""
    districts = frame.filter(area_level="district")
    provinces = frame.filter(area_level="province")
    rolled = (
        districts.with_columns(area_id=districts["area_id"].str.slice(0, 5))
        .group_by("area_id")
        .agg(total=pl.col("value").sum())
    )
    merged = provinces.join(rolled, on="area_id", how="left").fill_null(0)
    assert (merged["value"] >= merged["total"]).all()


def test_all_81_provinces_are_present(frame):
    """Every province has at least one licensed charging station; a province missing
    altogether would mean a page of the export never arrived."""
    assert frame.filter(area_level="province").height == 81
