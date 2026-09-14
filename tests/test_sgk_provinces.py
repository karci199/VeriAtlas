"""Silent failure paths in the SGK yearbook adapter."""

import pytest

from veriatlas.adapters import sgk_provinces as s


def test_unknown_title_stops():
    with pytest.raises(KeyError):
        s.topic_of("Tablo 9.9- Hiç görülmemiş bir tablo")


def test_event_group_label_does_not_decide():
    # "iş kazası veya meslek hastalığı" names both; the inner segment decides.
    text = "gecmis yillarda is kazasi veya meslek hastaligi > is kazasi > erkek"
    assert s._event(text) == "accident"


def test_same_year_pension_title_is_new_awards():
    assert (
        s.topic_of("TABLO 69- 2009 YILI İÇİNDE AYLIK VE GELİR ALANLARIN")
        == "new_pensions"
    )


def _row(dims, value, where="x"):
    return {
        "indicator_id": "sgk_work_accident_cases",
        "area_id": "TR-01",
        "year": 2020,
        "dims": dims,
        "value": value,
        "where": where,
    }


def test_total_is_checked_and_dropped():
    rows = [
        _row({"scheme": "4a", "event": "accident", "sex": "female"}, 10),
        _row({"scheme": "4a", "event": "accident", "sex": "male"}, 30),
        _row({"scheme": "4a", "event": "accident", "sex": "total"}, 45),
    ]
    report: dict = {}
    out = s._partition(rows, report)
    assert sorted(r["dims"]["sex"] for r in out) == ["female", "male"]
    assert report["subtotals"]["sgk_work_accident_cases:sex"] == [1, 1]


def test_total_without_parts_is_kept_without_key():
    rows = [_row({"scheme": "4a", "event": "accident", "sex": "total"}, 41)]
    out = s._partition(rows, {})
    assert out[0]["dims"] == {"scheme": "4a", "event": "accident"}
