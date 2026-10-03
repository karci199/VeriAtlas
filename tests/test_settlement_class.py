"""Silent-corruption paths of the hand-made settlement class adapter."""

import json

import pytest

from veriatlas.adapters import settlement_class as sc
from veriatlas.areas import load_neighbourhoods


def _write(tmp_path, decisions):
    path = tmp_path / "kullanici_karar.json"
    path.write_text(json.dumps(decisions, ensure_ascii=False), "utf-8")
    return path


def _ids(n):
    return load_neighbourhoods()["area_id"].to_list()[:n]


def test_unknown_class_is_an_error(tmp_path):
    a = _ids(1)[0]
    with pytest.raises(ValueError, match="bilinmeyen sinif"):
        sc.SettlementClass().parse(_write(tmp_path, {a: {"s": "Kasaba", "n": "x"}}))


def test_unregistered_id_is_an_error_but_osb_rows_are_skipped(tmp_path):
    a = _ids(1)[0]
    ok = {a: {"s": "Köy", "n": "elle"}, "TR-99-999-1": {"s": "Köy", "n": "OSB satırı"}}
    frame = sc.SettlementClass().parse(_write(tmp_path, ok))
    assert frame["area_id"].to_list() == [a]
    with pytest.raises(ValueError, match="kayitta olmayan"):
        sc.SettlementClass().parse(
            _write(tmp_path, {a: {"s": "Köy", "n": "elle"}, "TR-99-999-2": {"s": "Köy", "n": "yazım hatası"}})
        )
