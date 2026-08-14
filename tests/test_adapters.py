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
