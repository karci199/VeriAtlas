"""The contract's job is to stop a bad adapter, so that is what these check.

An adapter that writes the wrong unit, invents a dimension, or wanders into another
indicator would otherwise land in the fact table and only show up as a chart that looks
slightly off.
"""

import datetime as dt

import polars as pl
import pytest

from veriatlas.adapters import base
from veriatlas.adapters.base import Manifest, checksum, ingest, record
from veriatlas.schema import FACT_COLUMNS


@pytest.fixture(autouse=True)
def isolated_manifest(tmp_path, monkeypatch):
    """Ingest history is a record of real runs; tests must not write into it."""
    monkeypatch.setattr(base, "MANIFEST_PATH", tmp_path / "manifests.jsonl")


class FakeAdapter:
    """Minimal adapter over a file the test writes itself."""

    source_id = "tuik_medas"
    indicator_id = "tfr"

    def __init__(self, path, **overrides):
        self.path = path
        self.overrides = overrides

    def fetch(self):
        return self.path

    def parse(self, raw):
        row = {
            "indicator_id": "tfr",
            "area_id": "TR-16",
            "area_level": "province",
            "period_start": dt.date(2025, 1, 1),
            "frequency": "annual",
            "dims": "",
            "value": 1.32,
            "unit": "children_per_woman",
            "quality_flag": "measured",
            "vintage": "2026-08",
            "source_id": "tuik_medas",
            "retrieved_at": dt.date(2026, 8, 13),
        }
        return pl.DataFrame([row | self.overrides])


@pytest.fixture
def payload(tmp_path):
    path = tmp_path / "payload.csv"
    path.write_text("il;2025\nBursa;1.32\n", encoding="utf-8")
    return path


def test_ingest_returns_validated_rows_and_a_manifest(payload):
    frame, manifest = ingest(FakeAdapter(payload))
    assert tuple(frame.columns) == FACT_COLUMNS
    assert manifest.rows == 1
    assert manifest.areas == 1
    assert manifest.checksum == checksum(payload)


def test_unit_that_disagrees_with_the_dictionary_is_refused(payload):
    """The dictionary owns the unit; an adapter may not invent its own."""
    with pytest.raises(ValueError, match="unit"):
        ingest(FakeAdapter(payload, unit="person"))


def test_undeclared_dimension_is_refused(payload):
    """tfr declares no breakdowns, so a dims value must not slip through."""
    with pytest.raises(KeyError, match="age"):
        ingest(FakeAdapter(payload, dims="age=0-14"))


def test_rows_for_another_indicator_are_refused(payload):
    with pytest.raises(ValueError, match="another indicator"):
        ingest(FakeAdapter(payload, indicator_id="median_age"))


def test_checksum_follows_the_bytes(tmp_path):
    first = tmp_path / "a.csv"
    first.write_text("il;2025\nBursa;1.32\n", encoding="utf-8")
    before = checksum(first)

    first.write_text("il;2025\nBursa;1.33\n", encoding="utf-8")
    assert checksum(first) != before, "a revised payload must not look identical"


def test_manifest_history_is_append_only():
    from veriatlas.adapters.base import history

    before = len(history())
    record(
        Manifest(
            source_id="test",
            indicator_id="tfr",
            vintage="2026-08",
            retrieved_at="2026-08-13",
            raw_path="test.csv",
            checksum="0" * 16,
            rows=0,
            areas=0,
            periods=0,
            note="test kaydı",
        )
    )
    after = history()
    assert len(after) == before + 1
    assert after[-1]["note"] == "test kaydı"
    assert "ingested_at" in after[-1]


MIGRATION = """||Sütunlar|||||
Satırlar||Bölgelerin Aldığı Göç Bilgileri|||||
||Erkek ve 20-24|Erkek ve 65+|Kadın ve 20-24|Kadın ve 65+|
||||||
2024|Adana-1|100.0|5.0|90.0|7.0|
|Adıyaman-2|10.0|1.0|9.0|2.0|
"""


def test_migration_columns_carry_two_dims_at_once():
    """`Erkek ve 20-24` is one column and two breakdowns.

    MEDAS publishes migration only this way — there is no sex-only export and no age-only
    one — so a parser that reads a single dim out of the header can have neither.
    """
    import tempfile
    from pathlib import Path

    from veriatlas.adapters.tuik_simple import read_export

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "nufus-goc-aldigi-province.csv"
        path.write_text(MIGRATION, encoding="utf-8")
        rows = read_export(path, ("migration_in_by_age", "sex_age", None), {})

    adana = {row["dims"]: row["value"] for row in rows if row["area_id"] == "TR-01"}
    assert adana == {
        "age=20-24;sex=male": 100.0,
        "age=65+;sex=male": 5.0,
        "age=20-24;sex=female": 90.0,
        "age=65+;sex=female": 7.0,
    }
    assert len(rows) == 8, "iki il × dört kırılım"
