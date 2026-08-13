"""The adapter contract: how a source becomes rows in the fact table.

Every source is different — EVDS is a REST API with a key, MEDAS is a browser session,
this first one is a file on disk — so the contract stays deliberately small:

    fetch()   bring the raw bytes in and keep them, untouched
    parse()   turn those bytes into fact-table rows
    manifest  say what happened, in a line that outlives the run

The split matters because parsing is where we get things wrong. Keeping the raw payload
means a parsing bug can be fixed and replayed without going back to the source — which
may by then have revised, renamed or withdrawn the data.

The manifest is appended to `raw/manifests.jsonl`, one line per ingest. It records the
checksum of the raw bytes, so "did this file change since last time" is answerable
without a diff, and "which version of the data produced this chart" stays answerable
after the source has moved on.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import polars as pl

from ..config import RAW, ensure_dirs
from ..indicators import check_dims, get
from ..schema import parse_dims, validate

MANIFEST_PATH = RAW / "manifests.jsonl"


@dataclass(frozen=True)
class Manifest:
    """What one ingest run did. Append-only history, never rewritten."""

    source_id: str
    indicator_id: str
    vintage: str
    retrieved_at: str
    raw_path: str
    checksum: str
    rows: int
    areas: int
    periods: int
    note: str = ""


class Adapter(Protocol):
    """A source we can pull an indicator from."""

    source_id: str
    indicator_id: str

    def fetch(self) -> Path:
        """Put the raw payload under `raw/` and return its path. No parsing here."""
        ...

    def parse(self, raw: Path) -> pl.DataFrame:
        """Turn the raw payload into fact-table rows. No fetching here."""
        ...


def checksum(path: Path) -> str:
    """SHA-256 of the raw bytes, short form — enough to spot a changed payload."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:16]


def ingest(adapter: Adapter) -> tuple[pl.DataFrame, Manifest]:
    """Run one adapter end to end: fetch, parse, validate, record.

    Validation is not optional and not the adapter's job: every source goes through the
    same schema and the same dimension check, so a new adapter cannot quietly widen what
    the fact table accepts.
    """
    ensure_dirs()

    raw = adapter.fetch()
    frame = validate(adapter.parse(raw))

    declared = get(adapter.indicator_id)
    for dims in frame["dims"].unique():
        check_dims(adapter.indicator_id, set(parse_dims(dims)))

    if set(frame["indicator_id"]) != {adapter.indicator_id}:
        raise ValueError(
            adapter.source_id
            + " produced rows for another indicator than "
            + adapter.indicator_id
        )
    if set(frame["unit"]) != {declared.unit.unit_id}:
        raise ValueError(
            adapter.source_id
            + " unit does not match the dictionary: expected "
            + declared.unit.unit_id
        )

    manifest = Manifest(
        source_id=adapter.source_id,
        indicator_id=adapter.indicator_id,
        vintage=frame["vintage"][0],
        retrieved_at=str(frame["retrieved_at"][0]),
        raw_path=str(raw.relative_to(RAW) if raw.is_relative_to(RAW) else raw),
        checksum=checksum(raw),
        rows=frame.height,
        areas=frame["area_id"].n_unique(),
        periods=frame["period_start"].n_unique(),
    )
    record(manifest)
    return frame, manifest


def record(manifest: Manifest) -> None:
    """Append a manifest line. History, so it is never rewritten in place."""
    ensure_dirs()
    stamped = asdict(manifest) | {"ingested_at": dt.datetime.now(tz=dt.UTC).isoformat()}
    with MANIFEST_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(stamped, ensure_ascii=False) + "\n")


def history() -> list[dict]:
    """Every ingest so far, oldest first."""
    if not MANIFEST_PATH.exists():
        return []
    return [
        json.loads(line)
        for line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
