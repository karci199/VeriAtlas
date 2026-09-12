"""Marital status at district level shares `tuik_vital_district`'s one trap: a renamed
district keeps its MEDAS code, and only the row's own year picks which registry area it
means. Untested, a code resolved without the year would put the early years of a renamed
district on an id the population series does not use — silent, because the district still
draws, just under the wrong name for those years.
"""

from __future__ import annotations

from veriatlas.adapters.tuik_marital import read_export_district
from veriatlas.adapters.tuik_vital_district import area_at, districts_by_code

HEADER = "||Erkek ve 15-19 ve Evli|Erkek ve 15-19 ve Hiç Evlenmedi|"
BODY = f"""||Sütunlar|
Satırlar|Medeni Duruma Göre Nüfus Bilgileri (15 Yaş üstü)|
{HEADER}
2015|Adana(Aladağ)-1757|12.0|340.0|
|Ankara(Kazan)-1815|8.0|210.0|
"""


def written(tmp_path, name: str, body: str):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_rows_land_on_districts(tmp_path):
    path = written(tmp_path, "nufus-medeni-ilce-adana-2015-2015.csv", BODY)
    rows = read_export_district(path, districts_by_code())

    assert {row["area_level"] for row in rows} == {"district"}
    by_area = {(row["area_id"], row["marital"]): row["value"] for row in rows}
    assert by_area[("TR-01-001", "married")] == 12.0
    assert by_area[("TR-01-001", "never_married")] == 340.0


def test_the_year_picks_the_identity(tmp_path):
    """Kazan became Kahramankazan in 2017 — same trap as the vital-district adapter."""
    codes = districts_by_code()
    assert area_at(codes["1815"], 2015) == "TR-06-x1815"
    assert area_at(codes["1815"], 2025) == "TR-06-015"

    path = written(tmp_path, "nufus-medeni-ilce-ankara-2015-2015.csv", BODY)
    rows = read_export_district(path, codes)
    assert {row["area_id"] for row in rows} == {"TR-01-001", "TR-06-x1815"}


def test_an_unknown_code_stops_the_load(tmp_path):
    """A district with no registry row must not be dropped: its people go with it."""
    body = BODY.replace("Ankara(Kazan)-1815", "Bilinmeyen(Yok)-9999")
    path = written(tmp_path, "nufus-medeni-ilce-x-2015-2015.csv", body)
    try:
        read_export_district(path, districts_by_code())
    except KeyError as error:
        assert "9999" in str(error)
    else:
        raise AssertionError("tanınmayan ilçe sessizce düştü")
