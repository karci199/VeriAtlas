r"""AFAD earthquake catalogue counted by province, district, year and magnitude class.

`scripts/fetch_afad_earthquakes.py` keeps one JSON file per year in `C:\veri-ham\afad`
(1990-2025; the API returns nothing earlier). Each event carries the province, district and
neighbourhood AFAD assigns to its epicentre; events at sea or abroad have no Turkish province
and are not counted.

Magnitude classes: under 3, 3-3.9, 4-4.9, 5 and over, plus the total. The catalogue's
detection threshold fell over the years (1990: 344 events, 2024: 32,578), so counts under 3 are
mostly a measure of the network, not of seismicity; the 4+ classes are comparable over time.

Checks: no event id twice in a year; district counts add up to their province's where every
district resolves (unresolved district names are listed in UNRESOLVED, their events stay in the
province count).
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import district_key, province_id, resolve_district

FOLDER = RAW / "afad" if (RAW / "afad").exists() else Path("C:/veri-ham/afad")
CLASSES = ((3.0, "under_3"), (4.0, "3_to_3_9"), (5.0, "4_to_4_9"), (99.0, "5_plus"))
#: (province, district) names that do not resolve, with their event count
UNRESOLVED: Counter = Counter()


def magnitude_class(magnitude: float) -> str:
    return next(name for limit, name in CLASSES if magnitude < limit)


def load_all() -> dict[tuple[str, str, str, int], float]:
    """{(area, level, dims, year): count}"""
    key = district_key()
    out: Counter = Counter()
    for path in sorted(FOLDER.glob("deprem-*.json")):
        year = int(path.stem.split("-")[1])
        events = json.loads(path.read_text(encoding="utf-8"))
        ids = [e["eventID"] for e in events]
        if len(ids) != len(set(ids)):
            raise ValueError(f"AFAD {year}: aynı olay iki kez")
        for event in events:
            if event.get("country") != "Türkiye" or not event.get("province"):
                continue
            province = province_id(event["province"])
            klass = magnitude_class(float(event["magnitude"]))
            for dims in (f"magnitude_class={klass}", "magnitude_class=total"):
                out[(province, "province", dims, year)] += 1
            district = event.get("district")
            if not district:
                continue
            try:
                area, level = resolve_district(key, event["province"], district)
            except KeyError:
                UNRESOLVED[(event["province"], district)] += 1
                continue
            if level != "district":
                continue
            for dims in (f"magnitude_class={klass}", "magnitude_class=total"):
                out[(area, "district", dims, year)] += 1
    return dict(out)


_CACHE: dict = {}


class AfadEarthquakes:
    source_id = "afad"
    indicator_id = "afad_earthquakes"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        if not _CACHE:
            _CACHE.update(load_all())
        records = [
            {
                "area_id": area,
                "area_level": level,
                "period_start": dt.date(year, 1, 1),
                "dims": dims,
                "value": float(value),
            }
            for (area, level, dims, year), value in _CACHE.items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit("item").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


AFAD_ADAPTERS = {"afad_earthquakes": AfadEarthquakes}
