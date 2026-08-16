"""The district export's one trap: a code that looks like a plate number and is not.

`Adana-1` at province level and `Adana(Aladağ)-1757` at district level are the same shape
of label, and the province rule reads the second as the province TR-17. Nothing errors —
seventeen districts' births land on seventeen wrong provinces and the map still draws. So
the resolution is tested, and so is the other silent one: a renamed district keeps its
code and gets a second registry row, and picking without the year puts the early years on
an id the population series does not use.
"""

from __future__ import annotations

from veriatlas.adapters.tuik_median_age import area_of
from veriatlas.adapters.tuik_vital_district import (
    area_at,
    districts_by_code,
    read_export,
)

BIRTHS = """|||Sütunlar|
Satırlar|||Adana(Aladağ)-1757|Ankara(Kazan)-1815|
||||
İlçelere Göre Doğum Sayısı|Ölçüm bazında|2015|126.0|913.0|
"""

DEATHS = """|||Sütunlar|
Satırlar|||Adana(Aladağ)-1757|Ankara(Kazan)-1815|
||||
İlçelere Göre Ölüm Sayısı (İkametgah Yeri)|Ölenin cinsiyeti:Erkek|2015|77.0|100.0|
|Ölenin cinsiyeti:Kadın|2015|65.0|90.0|
"""


def written(tmp_path, name: str, body: str):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_district_code_is_not_a_plate_number():
    """The province rule answers for a district code — with a province that never was.

    `TR-1757` is not a province id and nothing downstream would recognise it, but the
    resolution itself does not complain: it is the caller's job to use the right rule,
    and this is the rule that has to be used here.
    """
    assert area_of("1757", {})[1] == "province"

    codes = districts_by_code()
    assert area_at(codes["1757"], 2015) == "TR-01-001"


def test_births_land_on_districts(tmp_path):
    path = written(tmp_path, "nufus-dogum-ilce-district-2015.csv", BIRTHS)
    rows = read_export(path, ("births_district", "births", None), districts_by_code())

    assert {row["area_level"] for row in rows} == {"district"}
    assert {row["dims"] for row in rows} == {""}
    by_area = {row["area_id"]: row["value"] for row in rows}
    assert by_area["TR-01-001"] == 126.0


def test_the_year_picks_the_identity(tmp_path):
    """Kazan became Kahramankazan in 2017: one code, two ids, and the year decides."""
    codes = districts_by_code()
    assert area_at(codes["1815"], 2015) == "TR-06-x1815"
    assert area_at(codes["1815"], 2025) == "TR-06-015"

    old = read_export(
        written(tmp_path, "nufus-dogum-ilce-district-2015.csv", BIRTHS),
        ("births_district", "births", None),
        codes,
    )
    assert {row["area_id"] for row in old} == {"TR-01-001", "TR-06-x1815"}


def test_deaths_keep_the_sex_they_arrived_with(tmp_path):
    path = written(tmp_path, "nufus-olum-ilce-district-2015.csv", DEATHS)
    rows = read_export(path, ("deaths_district", "deaths", "sex"), districts_by_code())

    kazan = {
        row["dims"]: row["value"] for row in rows if row["area_id"] == "TR-06-x1815"
    }
    assert kazan == {"sex=male": 100.0, "sex=female": 90.0}


def test_an_unknown_code_stops_the_load(tmp_path):
    """A district with no registry row must not be dropped: its births go with it."""
    body = BIRTHS.replace("Ankara(Kazan)-1815", "Bilinmeyen(Yok)-9999")
    path = written(tmp_path, "nufus-dogum-ilce-district-2015.csv", body)
    try:
        read_export(path, ("births_district", "births", None), districts_by_code())
    except KeyError as error:
        assert "9999" in str(error)
    else:
        raise AssertionError("tanınmayan ilçe sessizce düştü")
