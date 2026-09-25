"""SKRS registers and MEDAS school counts: the silent paths."""

import pytest

from veriatlas.adapters.meb_counts import checked
from veriatlas.adapters.skrs_facilities import district_index, kind_of, place, upper_tr
from veriatlas.adapters.skrs_schools import level_of, ownership_of


def test_turkish_upper_case_matches_registry_spelling():
    assert upper_tr("İznik") == upper_tr("İZNİK")
    assert upper_tr("Kâhta") == "KAHTA"
    assert upper_tr("Gazi Osmanpaşa") == upper_tr("GAZİOSMANPAŞA")


def test_unknown_district_is_refused_and_merkez_is_placed():
    provinces, index = district_index()
    assert place("TR-16", "İNEGÖL", provinces, index) == place(
        "TR-16", "İnegöl", provinces, index
    )
    assert place("TR-14", "MERKEZ", provinces, index) is not None  # Bolu's centre
    assert (
        place("TR-06", "MERKEZ", provinces, index) is None
    )  # metropolitan: no district
    with pytest.raises(KeyError):
        place("TR-16", "YOKBÖYLE", provinces, index)


def test_new_hospital_type_is_refused_not_dropped():
    with pytest.raises(ValueError):
        kind_of({"Kurum Türü": "YENİ TİP HASTANESİ", "Kurum Tipi": ""})
    assert kind_of({"Kurum Türü": "EĞİTİM HASTANESİ", "Kurum Tipi": ""}) is None


def test_university_dental_centre_is_not_a_hospital():
    row = {
        "Kurum Türü": "Vakıf Üniversitesi SUAM",
        "Kurum Tipi": "Ağız ve Diş Sağlığı Uygulama Merkezi",
    }
    assert kind_of(row) == "oral_health_centre"


def test_special_education_is_not_private():
    assert ownership_of("Özel Eğitim Uygulama Merkezi (I. Kademe)") == "public"
    assert ownership_of("Özel Özel Eğitim Anaokulu") == "private"
    assert level_of("Özel Eğitim Uygulama Merkezi (I. Kademe)") == "special_education"
    assert level_of("Anadolu İmam Hatip Lisesi") == "upper_secondary_vocational"
    assert level_of("İmam Hatip Ortaokulu") == "lower_secondary"
    with pytest.raises(ValueError):
        level_of("Bilinmeyen Kurum")


def _row(level, value, area="TR-01", level_kind="province"):
    return {
        "area_id": area,
        "area_level": level_kind,
        "sex": None,
        "level": level,
        "year": 2020,
        "value": value,
    }


def test_upper_secondary_total_must_equal_its_parts():
    rows = [
        _row("Genel Ortaöğretim", 10),
        _row("Mesleki Ve Teknik Ortaöğretim", 5),
        _row("Ortaöğretim", 16),
    ]
    with pytest.raises(ValueError):
        checked(rows, [], "test")


def test_unknown_school_level_is_refused():
    with pytest.raises(ValueError):
        checked([_row("Yeni Kademe", 1)], [], "test")
