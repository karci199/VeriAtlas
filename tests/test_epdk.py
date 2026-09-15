"""EPDK adapter: the silent paths — a total row joining the last province, parts not adding up."""

import pytest

from veriatlas.adapters import epdk
from veriatlas.adapters.kgm import provinces

KINDS = [
    "Aydınlatma",
    "Kamu ve Özel Hizmetler Sektörü ile Diğer",
    "Mesken",
    "Sanayi",
    "Tarımsal Faaliyetler",
]


def electricity_rows(grand_2025: float) -> list[tuple]:
    rows = [(None,) * 7, (None,) * 7]
    for name in provinces():
        for j, kind in enumerate(KINDS):
            rows.append((name if j == 0 else None, kind, 1.0, 0, 2.0, 0, 0))
        rows.append((None, "İl Toplam", 5.0, 0, 10.0, 0, 0))
    # The national total row has an empty name cell, right after the last province.
    rows.append(("", "Genel Toplam", 405.0, 1, grand_2025, 1, 0))
    return rows


def test_grand_total_row_is_not_read_as_last_province(monkeypatch):
    monkeypatch.setattr(epdk, "sheet", lambda path, name: electricity_rows(810.0))
    out = epdk.electricity("Tablo 3")
    assert max(o["value"] for o in out) == 2.0
    assert len(out) == 81 * 5 * 2


def test_national_total_not_adding_up_stops_the_load(monkeypatch):
    monkeypatch.setattr(epdk, "sheet", lambda path, name: electricity_rows(900.0))
    with pytest.raises(epdk.TotalMismatch):
        epdk.electricity("Tablo 3")


def test_istanbul_two_sides_are_added_not_overwritten():
    from veriatlas.adapters.epdk_history import wide_table
    from veriatlas.adapters.kgm import province_id

    kinds = {"mesken": "residential"}
    grid = [["İller", "Mesken", "Genel Toplam"]]
    for name in provinces():
        if province_id(name) == "TR-34":
            grid += [
                ["İSTANBUL (ANADOLU)", "10", "10"],
                ["İSTANBUL (AVRUPA)", "20", "20"],
            ]
        else:
            grid.append([name.upper(), "1", "1"])
    grid.append(["Genel Toplam", "110", "110"])
    out = wide_table(grid, kinds, "deneme")
    assert out["TR-34"]["residential"] == 30.0
