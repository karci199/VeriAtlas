"""Prison rows: the ways the loader could go quietly wrong."""

import pytest

from veriatlas.adapters import tuik_prison as prison


def _write(folder, name, columns, rows):
    """A MEDAS export: header lines, then `<title>|<breakdown>|<year>|<values...>`."""
    lines = [
        "|||Sütunlar|" + "|".join([""] * (len(columns) - 1)),
        "Satırlar|||" + "|".join(columns),
    ]
    lines += ["|" * (len(columns) + 2)] * 2
    lines += rows
    (folder / name).write_text("\n".join(lines), encoding="utf-8-sig")


def _folder(tmp_path, province_values, label="Cinsiyet:Erkek"):
    _write(
        tmp_path,
        "nufus-ceza-giren-02-k01-province.csv",
        ["Adana-1", "Ankara-6", "Yabancı Ülke-98"],
        [f"Title|{label}|2010|{province_values}"],
    )
    _write(
        tmp_path,
        "nufus-ceza-giren-02-k01-country.csv",
        ["Türkiye-TR"],
        [f"Title|{label}|2010|100"],
    )
    return tmp_path


def test_provinces_short_of_turkiye_load_and_turkiye_stays_whole(tmp_path):
    # 40 + 50 + 5 abroad = 95 of 100: five convicts with no province of residence
    frame = prison.read_indicator(
        "prison_admissions_by_residence", _folder(tmp_path, "40|50|5")
    )
    by_area = dict(zip(frame["area_id"], frame["value"]))
    assert by_area == {"TR-01": 40.0, "TR-06": 50.0, "TR": 100.0}
    # the people abroad are counted in the check, not stored under a province
    assert "TR-98" not in by_area


def test_provinces_above_turkiye_stop_the_load(tmp_path):
    # 60 + 50 = 110 > 100: a part file read twice, or a column under two provinces
    with pytest.raises(ValueError, match="asiyor"):
        prison.read_indicator(
            "prison_admissions_by_residence", _folder(tmp_path, "60|50|0")
        )


def test_an_unknown_label_stops_the_load(tmp_path):
    with pytest.raises(KeyError):
        prison.read_indicator(
            "prison_admissions_by_residence",
            _folder(tmp_path, "40|50|5", label="Cinsiyet:Bilinmiyor"),
        )


def test_a_cell_given_by_two_part_files_stops_the_load(tmp_path):
    folder = _folder(tmp_path, "40|50|5")
    _write(
        folder,
        "nufus-ceza-giren-02-k01-province-2.csv",
        ["Adana-1"],
        ["Title|Cinsiyet:Erkek|2010|40"],
    )
    with pytest.raises(ValueError, match="iki kez"):
        prison.read_indicator("prison_admissions_by_residence", folder)


def test_an_unknown_column_stops_the_load(tmp_path):
    _write(
        tmp_path,
        "nufus-ceza-giren-02-k01-province.csv",
        ["Bilinmeyen Yer-ZZ9"],
        ["Title|Cinsiyet:Erkek|2010|1"],
    )
    with pytest.raises(KeyError):
        prison.read_indicator("prison_admissions_by_residence", tmp_path)
