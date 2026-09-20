r"""Chain branches, counted by district: two burger chains and three çiğ köfte chains.

None of them publishes a table. Each was read off its own store finder
(`scripts/fetch_burgerking.py`, `scripts/fetch_mcdonalds.py`, `scripts/fetch_cigkofte.py`)
and every one of them hands out a coordinate per branch, so the district is not taken from
the address text — it is the district whose boundary the point falls in
(`public/geo/districts/*.geojson`, the same polygons the atlas draws).

Why the point and not the address:

* Burger King's URL carries a province and district slug, but it is the chain's own
  marketing geography — `istanbul/atasehir` for a branch that sits in Ümraniye, and slugs
  that fold `ç/ş/ı` away so `Çukurova` and `Cukurova` collide.
* McDonald's response has `city` and `town` fields and leaves both empty in all 335 rows.
* Ziyafet's dealer list is a Google My Maps export with no province field at all.
* Komagene writes the same province two ways one row apart — `"ADANA"` and `"Adana"`.

The coordinate is the only thing all five sources agree on.

A branch whose point falls outside every district polygon is dropped, not guessed at.
There are two reasons a point lands outside, and both are correct to drop:

* the coastline, where the boundary runs inland of the shore — marinas, beach clubs, a
  ferry terminal (12 of 847 Burger Kings, 1 of 335 McDonald's, 9 of 3.814 Komagenes);
* branches abroad, which the source files mix in without saying so in a separate field —
  Oses labels 33 of its 1.670 rows `Yurtdışı`, and their coordinates are in Europe.

Oses therefore loses 2,5% of its rows, close to the 3% the parser tolerates before it
raises. That threshold is there so a boundary file that stops matching cannot quietly
shrink the count; if Oses opens more branches abroad it will trip, and the fix then is to
drop the foreign rows by name before placing them, not to raise the limit.

**The brands are not a sample of anything.** Burger King and McDonald's are the two global
burger chains here; Oses, Ziyafet and Komagene are three of several çiğ köfte chains, and
the trade also runs on thousands of independent shops that no list covers. These counts
answer "how many branches of these brands", never "how many burger or çiğ köfte shops" —
çiğ köfte has no registry at all, which is why the chains are the only countable part of
it. Adding the brands together is the caller's decision; the indicator keeps them apart.

Snapshots, not series: store finders show what is open now and none keeps a history. Rows
are filed under the snapshot's year and replaced, not appended to.
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
RETRIEVED = dt.date(2026, 9, 20)
#: The snapshot's own date, and the year its rows are filed under.
SNAPSHOT = dt.date(2026, 9, 18)
VINTAGE = "2026-09"

#: Brand -> where its dump lives, as a glob under `RAW`. Every file carries `lat` and
#: `lng` columns and nothing else this adapter needs. The çiğ köfte dumps are dated in
#: their name (`scripts/fetch_cigkofte.py` writes one per run) and the newest match wins;
#: the two burger chains were saved once, under a fixed name.
BRANDS = {
    "burger_king": "burgerking/restaurants.csv",
    "mcdonalds": "mcdonalds/restaurants.csv",
    "oses": "cigkofte/oses_*.csv",
    "ziyafet": "cigkofte/ziyafet_*.csv",
    "komagene": "cigkofte/komagene_*.csv",
    "starbucks": "marketler/starbucks_*.csv",
    "espressolab": "marketler/espressolab_*.csv",
    "dominos": "dominos/subeler_*.csv",
}

#: KFC is fetched by `scripts/fetch_kfc.py` and deliberately left out: the 2026-09-20 run
#: returned 41 restaurants across 6 provinces, and the chain has several hundred. A dump
#: that stops early is not a small chain, and counting it would publish a shortfall as a
#: measurement. It goes in when the fetcher returns the whole list.

#: Retail chains that publish a coordinate per store, from `scripts/fetch_marketler.py`.
#: Three more chains are fetched by that script and deliberately left out here — Bizim
#: Toptan, Onur Market and Happy Center give no coordinate, so their district would come
#: from the source's own label, and Happy Center names no province at all. Placing them
#: needs registry matching, which is a different job from this one.
STORE_BRANDS = {
    "gratis": "marketler/gratis_*.csv",
    "madame_coco": "marketler/madame_coco_*.csv",
    "rossmann": "marketler/rossmann_*.csv",
    "karaca": "marketler/karaca_*.csv",
    "vatan": "marketler/vatan_*.csv",
    "sok": "sok/magazalar_*.csv",
    "koctas": "koctas/magazalar_*.csv",
    "vestel": "vestel/magazalar_*.csv",
    "tarim_kredi": "tarimkredi/magazalar_*.csv",
    "mopas": "mopas/magazalar_*.csv",
}

#: Mobile operator dealers. Kept out of `chain_stores` for the same reason fuel stations
#: are: a dealer sells subscriptions, is franchised in its own company's name, and a
#: district's count reads as where an operator sells rather than where people shop.
DEALER_BRANDS = {
    "vodafone": "vodafone/bayiler_*.csv",
}

#: Fuel stations, a third family. A filling station is not a shop and not a restaurant:
#: it serves a road rather than a neighbourhood, so its district count reads as traffic,
#: not as retail density. Summing it into `chain_stores` would blur both.
STATION_BRANDS = {
    "petrol_ofisi": "petrol_ofisi/istasyonlar_*.csv",
}

#: Brands whose dump names the coordinate columns in Turkish. Everything else writes
#: `lat` and `lng`, which is what the reader expects.
COORDINATE_COLUMNS = {
    "petrol_ofisi": ("boylam", "enlem"),
}

#: The share of a brand's branches allowed to fall outside every polygon *while standing
#: inside Türkiye*. Measured at 1,4% (Burger King) and 0,3% (McDonald's).
MAX_UNPLACED = 0.03

#: Türkiye's bounding box, rounded outward. A store outside it is abroad, not misplaced:
#: Madame Coco lists Moscow, Almaty, Beirut and Brussels in the same file as Adana, and
#: Oses labels 33 rows `Yurtdışı`. Foreign rows leave the count without counting against
#: `MAX_UNPLACED` — that threshold is there to catch a boundary file that stopped
#: matching, and a shop in Kazakhstan says nothing about the boundary file.
TURKEY = (25.5, 35.5, 45.0, 42.5)


def dump(brand: str) -> Path:
    """The newest saved dump for a brand, from either family."""
    pattern = (BRANDS | STORE_BRANDS | STATION_BRANDS | DEALER_BRANDS)[brand]
    found = sorted(RAW.glob(pattern))
    if not found:
        raise FileNotFoundError(f"{brand} dökümü yok: {RAW / pattern}")
    return found[-1]


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
    path = cached_copy(dump(brand), FOLDER / f"{brand}.csv")
    placed: dict[str, int] = {}
    total = unplaced = abroad = 0
    x0, y0, x1, y1 = TURKEY
    lng_column, lat_column = COORDINATE_COLUMNS.get(brand, ("lng", "lat"))
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                lng, lat = float(row[lng_column]), float(row[lat_column])
            except ValueError:  # the source left the coordinate blank
                total += 1
                unplaced += 1
                continue
            if not (x0 <= lng <= x1 and y0 <= lat <= y1):
                abroad += 1
                continue
            total += 1
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
            f"(sınır %{MAX_UNPLACED:.0%}); yurt dışı {abroad}"
        )
    return placed


class ChainRestaurants:
    """Every brand's branches, as one indicator broken down by brand."""

    indicator_id = "chain_restaurants"
    source_id = SOURCE
    #: Subclasses swap these two and inherit everything else.
    brands = BRANDS
    dim = "restaurant_brand"

    def fetch(self) -> Path:
        """Every brand's dump, gathered into one folder.

        `ingest` checksums whatever this returns, and it walks a directory to do it, so
        returning `RAW` would hash the entire raw store — hundreds of gigabytes for a
        few hundred kilobytes of CSV. The copies are what the manifest describes.
        """
        for brand in self.brands:
            cached_copy(dump(brand), FOLDER / f"{brand}.csv")
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        areas: list[str] = []
        levels: list[str] = []
        brands: list[str] = []
        values: list[float] = []
        for brand in self.brands:
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
                    brands.append(f"{self.dim}={brand}")
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


class OperatorDealers(ChainRestaurants):
    """Mobile operator dealers of the brands that publish a coordinate per dealer."""

    indicator_id = "operator_dealers"
    source_id = "chain_store_finders"
    brands = DEALER_BRANDS
    dim = "operator_brand"


class FuelStations(ChainRestaurants):
    """Filling stations of the brands that publish a coordinate per station."""

    indicator_id = "fuel_stations"
    source_id = "chain_store_finders"
    brands = STATION_BRANDS
    dim = "fuel_brand"


class ChainStores(ChainRestaurants):
    """Retail chains, counted the same way and kept apart from the restaurants.

    A separate indicator rather than another brand in `chain_restaurants`: a cosmetics
    shop and a burger branch answer different questions, and a reader summing them would
    be summing nothing. The machinery is identical — the coordinate decides the district —
    so only the brand list and the dimension differ.
    """

    indicator_id = "chain_stores"
    source_id = "chain_store_finders"
    brands = STORE_BRANDS
    dim = "store_brand"


CHAIN_STORE_ADAPTERS = {
    "chain_restaurants": ChainRestaurants,
    "chain_stores": ChainStores,
    "fuel_stations": FuelStations,
    "operator_dealers": OperatorDealers,
}
