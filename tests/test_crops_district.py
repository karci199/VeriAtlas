"""District crop rows: districts must add up to their province."""

import polars as pl
import pytest

from veriatlas.adapters.tuik_crops import check_districts


def _frame(district_values, province_value):
    rows = [
        {
            "area_id": f"TR-16-{i:03d}",
            "area_level": "district",
            "year": 2024,
            "dims": "crop=01.26.11.00.00",
            "value": v,
        }
        for i, v in enumerate(district_values, start=1)
    ]
    rows.append(
        {
            "area_id": "TR-16",
            "area_level": "province",
            "year": 2024,
            "dims": "crop=01.26.11.00.00",
            "value": province_value,
        }
    )
    return pl.DataFrame(rows)


def test_districts_adding_up_pass():
    check_districts(_frame([70719, 61666, 54614], 187000 - 1), "fruit_production")


def test_a_district_column_lost_stops_the_load():
    with pytest.raises(ValueError):
        check_districts(_frame([70719, 61666], 187000), "fruit_production")


def test_yields_are_not_summed():
    check_districts(_frame([13, 9, 12], 11), "fruit_yield_per_tree")
