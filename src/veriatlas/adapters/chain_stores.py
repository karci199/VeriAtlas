r"""Burger King and McDonald's restaurants, counted by district.

Neither chain publishes a table. Both were read off their own store finders
(`scripts/fetch_burgerking.py`, `scripts/fetch_mcdonalds.py`, raw CSVs in
`C:\veri-ham\burgerking` and `C:\veri-ham\mcdonalds`) and both hand out a coordinate per
restaurant, so the district is not taken from the address text — it is the district whose
boundary the point falls in (`public/geo/districts/*.geojson`, the same polygons the atlas
draws).

Why the point and not the address: Burger King's URL carries a province and district slug,
but it is the chain's own marketing geography — `istanbul/atasehir` for a branch that sits
in Ümraniye, and slugs that fold `ç/ş/ı` away so `Çukurova` and `Cukurova` collide.
McDonald's response has `city` and `town` fields and leaves both empty in every one of the
335 rows. The coordinate is the only thing both sources agree on.

A restaurant whose point falls outside every district polygon is dropped, not guessed at —
12 of 847 Burger Kings and 1 of 335 McDonald's, all of them on the coastline where the
boundary runs inland of the shore (marinas, beach clubs, a ferry terminal). The parser
raises if more than 3% goes missing, so a boundary file that stops matching cannot quietly
shrink the count.

This is a snapshot of the day it was taken (2026-09-18), not a series: the store finders
show what is open now and neither keeps a history. It is stored under that year and will
be replaced, not appended to.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from functools import cache
from pathlib import Path

import polars as pl

from ..config import PUBLIC, RAW
from .base import cached_copy

#: The copies `ingest` checksums; the brand dumps themselves live one folder up each.
FOLDER = RAW / "zincir"
SOURCE = "chain_store_finders"
RETRIEVED = dt.date(2026, 9, 18)
#: The snapshot's own date, and the year its rows are filed under.
SNAPSHOT = dt.date(2026, 9, 18)
VINTAGE = "2026-09"

#: Brand -> its raw CSV. Both files carry `lat` and `lng` columns and nothing else we need.
BRANDS = {
    "burger_king": RAW / "burgerking" / "restaurants.csv",
    "mcdonalds": RAW / "mcdonalds" / "restaurants.csv",
}

#: The share of a brand's restaurants allowed to fall outside every polygon. Measured at
#: 1.4% (Burger King) and 0.3% (McDonald's) on the 2026-09-18 snapshot.
MAX_UNPLACED = 0.03

Ring = list[list[float]]


@cache
def _districts() -> list[tuple[str, list[Ring], tuple[float, float, float, float]]]:
    """(area_id, rings, bounding box) for every district the atlas has a boundary for."""
    out = []
    for path in sorted((PUBLIC / "geo" / "districts").glob("TR-*.geojson")):
        for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
            geometry = feature["geometry"]
            polygons = (
                [geometry["coordinates"]]
                if geometry["type"] == "Polygon"
                else geometry["coordinates"]
            )
            # Outer rings only: a hole in a district is another district's territory, and
            # a restaurant there belongs to that one, which its own polygon will claim.
            rings = [polygon[0] for polygon in polygons]
            xs = [point[0] for ring in rings for point in ring]
            ys = [point[1] for ring in rings for point in ring]
            out.append(
                (
                    feature["properties"]["area_id"],
                    rings,
                    (min(xs), min(ys), max(xs), max(ys)),
                )
            )
    if not out:
        raise FileNotFoundError(f"İlçe sınırları yok: {PUBLIC / 'geo' / 'districts'}")
    return out


def _in_ring(x: float, y: float, ring: Ring) -> bool:
    """Ray casting. Points on the boundary itself are undefined, and we do not care:
    no restaurant sits on a district line to seven decimal places."""
    inside = False
    for index in range(len(ring)):
        x1, y1 = ring[index][0], ring[index][1]
        x2, y2 = ring[(index + 1) % len(ring)][0], ring[(index + 1) % len(ring)][1]
        # The crossing test comes first and stays first: it is also what keeps the
        # division below from dividing by zero on a horizontal edge.
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def locate(lng: float, lat: float) -> str | None:
    """The district holding this point, or None when it falls outside all of them."""
    for area_id, rings, (x0, y0, x1, y1) in _districts():
        # The bounding box first: it rejects 80 of the 81 provinces without walking a
        # ring, which is what makes a full pass over 1.182 restaurants take a second.
        if (x0 <= lng <= x1 and y0 <= lat <= y1) and any(
            _in_ring(lng, lat, ring) for ring in rings
        ):
            return area_id
    return None


@cache
def counts(brand: str) -> dict[str, int]:
    """District id -> the brand's restaurant count there."""
    # The copy, not the original: it is what the manifest's checksum describes, and it is
    # still there when the brand folder is not.
    path = cached_copy(BRANDS[brand], FOLDER / f"{brand}.csv")
    placed: dict[str, int] = {}
    total = unplaced = 0
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            total += 1
            try:
                lng, lat = float(row["lng"]), float(row["lat"])
            except ValueError:  # the source left the coordinate blank
                unplaced += 1
                continue
            area = locate(lng, lat)
            if area is None:
                unplaced += 1
                continue
            placed[area] = placed.get(area, 0) + 1
    if not total:
        raise ValueError(f"{brand}: döküm boş ({path})")
    if unplaced / total > MAX_UNPLACED:
        raise ValueError(
            f"{brand}: {unplaced}/{total} şube hiçbir ilçeye düşmedi "
            f"(sınır %{MAX_UNPLACED:.0%})"
        )
    return placed


class ChainRestaurants:
    """Restaurants of both brands, as one indicator broken down by brand."""

    indicator_id = "chain_restaurants"
    source_id = SOURCE

    def fetch(self) -> Path:
        """Both brands' dumps, gathered into one folder.

        `ingest` checksums whatever this returns, and it walks a directory to do it, so
        returning `RAW` would hash the entire raw store — hundreds of gigabytes for two
        files of a few hundred kilobytes. The copies are what the manifest describes.
        """
        for brand, path in BRANDS.items():
            cached_copy(path, FOLDER / f"{brand}.csv")
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        areas: list[str] = []
        levels: list[str] = []
        brands: list[str] = []
        values: list[float] = []
        for brand in BRANDS:
            districts = counts(brand)
            # The province total is written out rather than left to the roll-up: it is an
            # exact sum of a count, not the weighted estimate `aggregate` would mark it as.
            provinces: dict[str, int] = {}
            for area, count in districts.items():
                provinces[area[:5]] = provinces.get(area[:5], 0) + count
            for level, rows in (("district", districts), ("province", provinces)):
                for area, count in sorted(rows.items()):
                    areas.append(area)
                    levels.append(level)
                    brands.append(f"restaurant_brand={brand}")
                    values.append(float(count))
        return pl.DataFrame(
            {
                "indicator_id": self.indicator_id,
                "area_id": areas,
                "area_level": levels,
                "period_start": dt.date(SNAPSHOT.year, 1, 1),
                "frequency": "annual",
                "dims": brands,
                "value": values,
                "unit": "item",
                "quality_flag": "measured",
                "vintage": VINTAGE,
                "source_id": self.source_id,
                "retrieved_at": RETRIEVED,
            }
        )


CHAIN_STORE_ADAPTERS = {"chain_restaurants": ChainRestaurants}
