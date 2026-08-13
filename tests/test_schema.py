"""The parts of the fact schema that fail silently if they break.

Only the guarantees you cannot see by reading a frame are tested here: that a repeated
key is rejected, that a revision is not mistaken for a repeat, and that two frequencies
starting on the same day stay apart.
"""

import datetime as dt

import polars as pl
import pytest
from pandera.errors import SchemaError

from veriatlas.schema import FACT_COLUMNS, format_dims, parse_dims, validate


def row(area="TR-16", year=2009, value=1.78, **overrides):
    base = {
        "indicator_id": "tfr",
        "area_id": area,
        "area_level": "province",
        "period_start": dt.date(year, 1, 1),
        "frequency": "annual",
        "dims": "",
        "value": value,
        "unit": "children_per_woman",
        "quality_flag": "measured",
        "vintage": "2026-03",
        "source_id": "tuik_medas",
        "retrieved_at": dt.date(2026, 8, 13),
    }
    base.update(overrides)
    return base


def test_valid_frame_comes_back_in_canonical_order():
    frame = pl.DataFrame([row(), row(year=2025, value=1.32), row(area="TR-35")])
    out = validate(frame)
    assert out.height == 3
    assert tuple(out.columns) == FACT_COLUMNS


def test_repeated_key_is_rejected():
    """Re-running an import must not silently double a number."""
    frame = pl.DataFrame([row(), row(value=1.79)])
    with pytest.raises(SchemaError):
        validate(frame)


def test_two_vintages_of_the_same_observation_coexist():
    """A revision is a second row, not a collision — that is why vintage is in the key."""
    frame = pl.DataFrame([row(), row(value=1.79, vintage="2025-11")])
    assert validate(frame).height == 2


def test_same_day_different_frequency_does_not_collide():
    """Annual 2009 and Q1 2009 both start on 2009-01-01."""
    frame = pl.DataFrame([row(), row(frequency="quarterly")])
    assert validate(frame).height == 2


def test_unknown_quality_flag_is_rejected():
    frame = pl.DataFrame([row(quality_flag="olcum")])
    with pytest.raises(SchemaError):
        validate(frame)


def test_unknown_area_level_is_rejected():
    frame = pl.DataFrame([row(area_level="il")])
    with pytest.raises(SchemaError):
        validate(frame)


def test_dims_are_canonical_regardless_of_insertion_order():
    """The uniqueness check compares strings, so the same breakdown must render once."""
    assert format_dims({"place": "rural", "age": "0-14"}) == "age=0-14;place=rural"
    assert format_dims({"age": "0-14", "place": "rural"}) == "age=0-14;place=rural"
    assert format_dims(None) == ""


def test_dims_round_trip():
    dims = {"age": "0-14", "place": "rural"}
    assert parse_dims(format_dims(dims)) == dims
    assert parse_dims("") == {}


def test_separator_inside_a_dimension_is_refused():
    with pytest.raises(ValueError):
        format_dims({"age": "0-14;15-64"})
