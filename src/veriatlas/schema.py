"""Canonical fact table: one row per observation.

Every value we ingest, from any source, lands in this one shape. Variety goes into
rows, not columns — a new geographic level or a new indicator is a new *value*, never
a new column.

A row is identified by KEY_COLUMNS. Loading the same key twice is a collision and must
fail, so that re-running an import cannot silently double a number.

Turkish labels are not stored here. This table holds identifiers — `unit` included —
and the indicator dictionary maps them to `label_tr` / `label_en` (decision K1).
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

# region Vocabularies

#: How long the period starting at ``period_start`` lasts.
FREQUENCIES = ("daily", "weekly", "monthly", "quarterly", "annual")

#: Where the number comes from. Drives the badge shown on the chart: a reader must be
#: able to tell a measurement from a model output without leaving the screen.
QUALITY_FLAGS = (
    "measured",  # published by the source as-is
    "estimated",  # we derived it (e.g. the IPF split of urban/rural after 2013)
    "interpolated",  # filled between two published points
)

#: Geographic granularity. ``area_id`` carries the code, this says what kind of code
#: it is. Adding a level (electoral district, basin) means adding a value here.
AREA_LEVELS = ("country", "region", "province", "district", "neighbourhood")

# endregion

# region Key

#: Columns that make a row unique. ``frequency`` belongs here because an annual 2009
#: and a Q1 2009 share the same ``period_start``. ``vintage`` belongs here because we
#: keep revisions side by side rather than overwriting them (decision K6).
KEY_COLUMNS = (
    "indicator_id",
    "area_id",
    "period_start",
    "frequency",
    "dims",
    "vintage",
)

# endregion

# region Dimensions

DIMS_NONE = ""

_PAIR_SEP = ";"
_KV_SEP = "="


def format_dims(dims: dict[str, str] | None) -> str:
    """Render extra breakdowns as one canonical string.

    ``{"place": "rural", "age": "0-14"}`` becomes ``"age=0-14;place=rural"``.

    Keys are sorted so that the same breakdown always produces the same string — the
    uniqueness check depends on that. Indicators without breakdowns use ``DIMS_NONE``.

    Which keys an indicator may use is declared in the indicator dictionary; an
    undeclared key must fail at load time, so "flexible" does not become "anything
    goes".
    """
    if not dims:
        return DIMS_NONE

    for key, value in dims.items():
        if _PAIR_SEP in key or _KV_SEP in key:
            raise ValueError("dimension key must not contain ';' or '=': " + key)
        if _PAIR_SEP in value or _KV_SEP in value:
            raise ValueError("dimension value must not contain ';' or '=': " + value)

    return _PAIR_SEP.join(k + _KV_SEP + dims[k] for k in sorted(dims))


def parse_dims(dims: str) -> dict[str, str]:
    """Inverse of :func:`format_dims`."""
    if not dims:
        return {}

    out: dict[str, str] = {}
    for pair in dims.split(_PAIR_SEP):
        key, sep, value = pair.partition(_KV_SEP)
        if not sep:
            raise ValueError("malformed dims segment, expected key=value: " + pair)
        out[key] = value
    return out


# endregion

# region Schema

_ID = r"^[a-z0-9][a-z0-9_]*$"

#: ``2026-03`` or ``2026-03-17`` — the source's own release, not our download date.
_VINTAGE = r"^\d{4}-\d{2}(-\d{2})?$"

FACT_SCHEMA = pa.DataFrameSchema(
    {
        "indicator_id": pa.Column(pl.String, pa.Check.str_matches(_ID)),
        "area_id": pa.Column(pl.String, pa.Check.str_length(min_value=1)),
        "area_level": pa.Column(pl.String, pa.Check.isin(AREA_LEVELS)),
        "period_start": pa.Column(pl.Date),
        "frequency": pa.Column(pl.String, pa.Check.isin(FREQUENCIES)),
        "dims": pa.Column(pl.String, nullable=False),
        "value": pa.Column(pl.Float64),
        "unit": pa.Column(pl.String, pa.Check.str_matches(_ID)),
        "quality_flag": pa.Column(pl.String, pa.Check.isin(QUALITY_FLAGS)),
        "vintage": pa.Column(pl.String, pa.Check.str_matches(_VINTAGE)),
        "source_id": pa.Column(pl.String, pa.Check.str_matches(_ID)),
        "retrieved_at": pa.Column(pl.Date),
    },
    unique=list(KEY_COLUMNS),
    strict=True,
    coerce=True,
    name="fact",
)

#: Column order used when writing parquet, so files stay diffable and predictable.
FACT_COLUMNS = tuple(FACT_SCHEMA.columns)

# endregion


def validate(frame: pl.DataFrame) -> pl.DataFrame:
    """Check a frame against the fact schema and return it in canonical column order.

    Raises ``pandera.errors.SchemaError`` on the first violation, including a duplicate
    key — which is what stops a re-import from doubling a number.
    """
    validated = FACT_SCHEMA.validate(frame)
    return validated.select(FACT_COLUMNS)
