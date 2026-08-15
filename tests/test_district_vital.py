"""The district births and deaths export, and the two ways it goes wrong quietly.

Neither failure raises anything. The label written once per block turns sixteen years
into one; the code-to-area join, done without the year, sends a renamed district's whole
series to whichever of its two registry rows happened to be read last.
"""

from __future__ import annotations

import pytest

from veriatlas.adapters.tuik_district_vital import area_of, read_export, validity

#: Two districts across the header, two sexes down the rows, two years each — shaped
#: exactly like MEDAS's file, small enough to add up by hand. The sex is written on the
#: first row of its block and left blank underneath, which is the trap.
EXPORT = """|||Sütunlar|
Satırlar|||Adana(Aladağ)-1757|Adana(Ceyhan)-1219|
||||
İlçelere Göre Ölüm Sayısı (İkametgah Yeri)|Ölenin cinsiyeti:Erkek|2009|49.0|494.0|
||2010|72.0|478.0|
|Ölenin cinsiyeti:Kadın|2009|30.0|400.0|
||2010|40.0|410.0|
"""


@pytest.fixture
def export(tmp_path):
    path = tmp_path / "ilce-olum.csv"
    path.write_text(EXPORT, encoding="utf-8")
    return path


def test_a_sex_written_once_carries_down_its_block(export):
    """The blank label under a sex is that sex, not a row that cannot be placed."""
    rows = read_export(export, "sex")
    assert {(row["year"], row["dims"]) for row in rows} == {
        (2009, "sex=male"),
        (2010, "sex=male"),
        (2009, "sex=female"),
        (2010, "sex=female"),
    }
    aladag = {
        (row["year"], row["dims"]): row["value"]
        for row in rows
        if row["medas_code"] == "1757"
    }
    assert aladag[(2009, "sex=male")] == 49.0
    assert aladag[(2010, "sex=female")] == 40.0


def test_dropping_the_dim_sums_the_sexes(export):
    """How births are read: the split exists in the file and is added up, because the
    province series has no sex breakdown to line up against."""
    rows = read_export(export, None)
    aladag = {row["year"]: row["value"] for row in rows if row["medas_code"] == "1757"}
    assert aladag == {2009: 79.0, 2010: 112.0}


#: The two renames inside the span, as the registry holds them: one code, two areas,
#: validity ranges that do not overlap.
RENAMED = [
    {
        "area_id": "TR-06-015",
        "medas_code": 1815,
        "valid_from": 2017,
        "valid_to": None,
    },
    {
        "area_id": "TR-06-x1815",
        "medas_code": 1815,
        "valid_from": None,
        "valid_to": 2016,
    },
    {"area_id": "TR-01-001", "medas_code": 1757, "valid_from": None, "valid_to": None},
]


def test_a_renamed_district_is_resolved_by_year():
    """Kazan and Kahramankazan share MEDAS's code and are two areas in the registry.

    Matched on the code alone, one of them takes the whole seventeen years and the other
    draws as an empty district — a hole in the map that looks exactly like "no data".
    """
    by_code = validity(RENAMED)
    assert area_of(by_code, "1815", 2016) == "TR-06-x1815"
    assert area_of(by_code, "1815", 2017) == "TR-06-015"


def test_an_unclaimed_year_is_not_guessed():
    """Two rows and neither covering the year is unresolved, not "probably the newer one".
    The caller stops the load on a None; a guess would publish a number under the wrong
    district and never say so."""
    by_code = validity(
        [
            {"area_id": "A", "medas_code": 9, "valid_from": 2020, "valid_to": 2021},
            {"area_id": "B", "medas_code": 9, "valid_from": 2023, "valid_to": None},
        ]
    )
    assert area_of(by_code, "9", 2022) is None


def test_a_single_row_ignores_the_year():
    """Almost every district is one row with no validity at all, and it answers for every
    year the file carries."""
    assert area_of(validity(RENAMED), "1757", 2009) == "TR-01-001"


def test_an_unknown_code_is_unresolved():
    assert area_of(validity(RENAMED), "4242", 2020) is None
