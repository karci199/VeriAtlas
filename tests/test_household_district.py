"""District household files: the two ways they could corrupt the load without a word.

A district label read with the province rule becomes a province (`-1757` → TR-17), and a
district code the registry does not know would be dropped with its households. And a
district series that does not add up to its province — a district missing from a year, a
code resolved into the wrong province — looks like a finished map. Both have to stop.
"""

from __future__ import annotations

import polars as pl
import pytest

from veriatlas.adapters.tuik_simple import MEASURES, check_districts_add_up, read_export
from veriatlas.adapters.tuik_vital_district import districts_by_code

COUNT = """||Sütunlar|
Satırlar||Toplam Hanehalkı Sayısı|
||Ölçüm bazında|
|||
2015|Adana(Aladağ)-1757|4279.0|
|Adana(Yok)-999999|10.0|
"""


def written(tmp_path, body: str):
    path = tmp_path / "nufus-hane-sayisi-ilce-district.csv"
    path.write_text(body, encoding="utf-8")
    return path


def test_district_rows_resolve_by_district_code(tmp_path):
    body = COUNT.replace("|Adana(Yok)-999999|10.0|\n", "")
    rows = read_export(
        written(tmp_path, body), MEASURES["hane-sayisi"], {}, districts_by_code()
    )
    assert rows == [
        {
            "area_id": "TR-01-001",
            "area_level": "district",
            "year": 2015,
            "dims": "",
            "value": 4279.0,
        }
    ]


def test_unknown_district_with_a_value_stops(tmp_path):
    with pytest.raises(KeyError, match="karsiligi olmayan ilce"):
        read_export(
            written(tmp_path, COUNT), MEASURES["hane-sayisi"], {}, districts_by_code()
        )


def frame(rows):
    return pl.DataFrame(
        rows, schema=["area_id", "area_level", "year", "dims", "value"], orient="row"
    )


def test_districts_short_of_province_stop():
    rows = [
        ("TR-01", "province", 2015, "", 100.0),
        ("TR-01-001", "district", 2015, "", 60.0),
        ("TR-01-002", "district", 2015, "", 30.0),
    ]
    with pytest.raises(ValueError, match="tutmuyor"):
        check_districts_add_up(frame(rows), "household_count", additive=True)

    rows[-1] = ("TR-01-002", "district", 2015, "", 40.0)
    check_districts_add_up(frame(rows), "household_count", additive=True)


def test_mean_checks_coverage_not_sum():
    rows = [
        ("TR-01", "province", 2015, "", 3.2),
        ("TR-02", "province", 2015, "", 3.9),
        ("TR-01-001", "district", 2015, "", 3.1),
    ]
    with pytest.raises(KeyError, match="ilce satiri olmayan"):
        check_districts_add_up(frame(rows), "household_size", additive=False)


BIRTHPLACE = """||Sütunlar||||
Satırlar||İkamet Edilen Ilçelere Göre Doğum Yerleri||||
||Doğum Yeri:Adana|Doğum Yeri:Adıyaman|Doğum Yeri:Yurtdışı|
||||
2025|Adana(Aladağ)-1757|14518.0|-9.98E8|12.0|
"""


def test_suppressed_birthplace_cell_is_withheld_not_a_number(tmp_path):
    """MEDAS writes a withheld cell as -9.98E8; read as a count it takes a billion
    people off the district."""
    from veriatlas.adapters.tuik_origin_district import (
        MEASURES as ORIGIN,
    )
    from veriatlas.adapters.tuik_origin_district import (
        provinces_by_name,
        read_square,
    )

    path = tmp_path / "nufus-dogumyeri-ilce-adana-2025-2025.csv"
    path.write_text(BIRTHPLACE, encoding="utf-8")
    rows, withheld = read_square(
        path, ORIGIN["dogumyeri"], provinces_by_name(), districts_by_code()
    )
    assert withheld == 1
    assert {row["dims"]: row["value"] for row in rows} == {
        "birth_province=TR-01": 14518.0,
        "birth_province=abroad": 12.0,
    }


def test_spouse_ages_read_from_one_label_are_not_swapped():
    """Both spouses share a label; a reader that took the first band for both would put
    every marriage on the diagonal and still sum to the right total."""
    from veriatlas.adapters.tuik_vital import READERS

    label = "Kadının yaş grubu:20-24 ve Erkeğin yaş grubu:Bilinmeyen"
    assert READERS["bride_age"](label) == "20-24"
    assert READERS["groom_age"](label) == "unknown"
