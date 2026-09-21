"""Endeksa adapter: the silent-failure paths.

A neighbourhood whose name does not match the registry must be refused, not dropped; a
placeholder (household count 0) must produce no demographic rows; a null vote count must
be skipped rather than become a zero.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from veriatlas.adapters import endeksa


def _county(name: str, did: int, placeholder: bool) -> dict:
    demo = {
        "DistrictName": name,
        "DistrictId": did,
        "HouseholdCount": 0 if placeholder else 10,
        "PopulationTotal": 30,
        "PopulationMale": 14,
        "PopulationFemale": 16,
        "Area": 1.5,
    }
    for key in endeksa.AGE_BANDS:
        for sfx in ("Total", "Male", "Female"):
            demo[f"Age_{key}_{sfx}"] = 0 if placeholder else 1
    return demo


def _write(folder: Path, quarters: list[tuple[str, int, bool]]) -> None:
    folder.mkdir(parents=True)
    subs = [{"DistrictId": d, "RegionName": n} for n, d, _ in quarters]
    county = {"Demography": _county("X", 0, False), "SubRegionals": subs}
    (folder / "county.json").write_text(json.dumps(county), "utf-8")
    for name, did, ph in quarters:
        (folder / f"{did}-x.json").write_text(
            json.dumps({"Demography": _county(name, did, ph)}), "utf-8"
        )
    election = {
        "county": [],
        "quarters": {
            str(d): [
                {
                    "Code": "2011genelsecim",
                    "SandikSayisi": 1,
                    "KayitliSecmen": 10,
                    "KullanilanOy": 8,
                    "GecerliOy": 8,
                    "GecersizOy": 0,
                    "Secenekler": [
                        {"Secenek": "AK Parti", "OySayisi": 5},
                        {"Secenek": "Bağımsız 7", "OySayisi": None},
                    ],
                }
            ]
            for _, d, _ in quarters
        },
    }
    (folder / "election.json").write_text(json.dumps(election), "utf-8")
    (folder / "fellowcountryman.json").write_text(
        json.dumps({"county": None, "quarters": {}}), "utf-8"
    )


KNOWN = {("TR-99-001", "beyler"): "TR-99-001-1", ("TR-99-001", "selçuk"): "TR-99-001-2"}


def test_unknown_name_is_refused(tmp_path: Path) -> None:
    _write(tmp_path / "TR-99-001", [("Beyler", 1, False), ("Yokköy", 3, False)])
    with pytest.raises(KeyError, match="Yokköy"):
        endeksa.read_district(tmp_path / "TR-99-001", KNOWN)


def test_placeholder_yields_no_demography_but_keeps_votes(
    tmp_path: Path, monkeypatch
) -> None:
    _write(tmp_path / "TR-99-001", [("Beyler", 1, False), ("Selçuk", 2, True)])
    district = endeksa.read_district(tmp_path / "TR-99-001", KNOWN)
    monkeypatch.setattr(endeksa, "read_all", lambda: (district,))

    pop = endeksa.ENDEKSA_ADAPTERS["endeksa_population"]().parse(tmp_path)
    assert set(pop["area_id"]) == {"TR-99-001-1"}

    votes = endeksa.ENDEKSA_ADAPTERS["endeksa_votes"]().parse(tmp_path)
    assert set(votes["area_id"]) == {"TR-99-001-1", "TR-99-001-2"}
    # the null-count independent is absent, not zero
    assert votes["value"].min() == 5.0
    assert votes.height == 2
