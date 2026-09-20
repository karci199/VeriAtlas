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
from typing import ClassVar

import polars as pl

from ..areas import load_areas, load_districts
from ..config import PUBLIC, RAW
from .base import cached_copy

#: The copies `ingest` checksums; the brand dumps themselves live one folder up each.
FOLDER = RAW / "zincir"
SOURCE = "chain_store_finders"
RETRIEVED = dt.date(2026, 9, 18)
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
}

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
}

#: Chains that publish a district *count* instead of a list of branches. BİM's finder
#: answers per district and never says where a store stands; Migros' dropdown is the same
#: shape. There is no coordinate to place, so the district has to come from the source's
#: own label — which is the job the two of them were held back from the adapter for.
#:
#: BİM's number covers **BİM and FİLE together**: the finder has one checkbox for bakeries
#: and none for the brand, so the two cannot be told apart and are not claimed to be.
COUNT_BRANDS = {
    "bim": "bim/district_counts.csv",
    "migros": "migros/district_counts.csv",
}

#: Province names these two write differently from the registry. Four of them, and all
#: four are older or shortened names rather than misspellings: `İçel` is what Mersin was
#: called until 2002, `K.Maraş` and `Afyon` are the short forms, `Agri` is `Ağrı` with the
#: Turkish letters dropped. They are listed one by one rather than normalised away: two
#: spellings of one province silently becoming two areas is exactly what `resolve` exists
#: to prevent, and an alias is a decision, not a transformation.
PROVINCE_ALIASES = {
    "Afyon": "Afyonkarahisar",
    "Agri": "Ağrı",
    "İçel": "Mersin",
    "K.Maraş": "Kahramanmaraş",
}

#: District names the same way. Two kinds: the circumflex the registry keeps and the
#: sources drop (`Kâhta`, `Lâpseki`, `Devrekâni`, `Lâçin`), and the space the registry
#: keeps and the sources close up (`Gazi Osmanpaşa`, `Marmara Ereğlisi`, `Oniki Şubat`,
#: `19 Mayıs`). Keyed by (province id, source's spelling) because a district name is only
#: unique inside its province.
DISTRICT_ALIASES = {
    ("TR-02", "Kahta"): "Kâhta",
    ("TR-16", "MustafaKemalPaşa"): "Mustafakemalpaşa",
    ("TR-17", "Lapseki"): "Lâpseki",
    ("TR-19", "Laçin"): "Lâçin",
    ("TR-34", "Gaziosmanpaşa"): "Gazi Osmanpaşa",
    ("TR-37", "Devrekani"): "Devrekâni",
    ("TR-46", "Onikişubat"): "Oniki Şubat",
    ("TR-55", "19 mayıs"): "19 Mayıs",
    ("TR-59", "Marmaraereğlisi"): "Marmara Ereğlisi",
    ("TR-71", "Bahşılı"): "Bahşili",
}

#: What both sources call the central district of a province that has one. The registry
#: names it after the province itself — `Bolu`, `Afyonkarahisar` — and never carries a
#: district called `Merkez`. The rule is safe because the 30 provinces with no district of
#: their own name are exactly the 30 metropolitan ones, and those have no `Merkez` either:
#: their whole territory is divided into named districts.
CENTRE = "Merkez"

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
    pattern = (BRANDS | STORE_BRANDS | COUNT_BRANDS)[brand]
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
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                lng, lat = float(row["lng"]), float(row["lat"])
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


@cache
def _registry() -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """(province name -> id, (province id, district name) -> id), read once."""
    areas = load_areas()
    provinces = {
        row["name_tr"]: row["area_id"]
        for row in areas.filter(pl.col("area_level") == "province").iter_rows(
            named=True
        )
    }
    districts = {
        (row["parent_id"], row["name_tr"]): row["area_id"]
        for row in load_districts().iter_rows(named=True)
    }
    return provinces, districts


@cache
def label_counts(brand: str) -> dict[str, int]:
    """District id -> the brand's store count, for the two that publish counts by name.

    Nothing is guessed and nothing is dropped: a name this cannot place raises, because a
    count silently falling off the table is invisible in the result — the indicator would
    simply show a district with no BİM, which is a claim about the country rather than a
    gap in the parsing. The three ways the sources differ from the registry (the central
    district, four province aliases, ten district spellings) are each written out above.
    """
    path = cached_copy(dump(brand), FOLDER / f"{brand}.csv")
    provinces, districts = _registry()
    placed: dict[str, int] = {}
    unknown: list[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            published = row["il"].strip()
            province = provinces.get(PROVINCE_ALIASES.get(published, published))
            if province is None:
                unknown.append(f"il {published!r}")
                continue
            name = row["ilce"].strip()
            if name == CENTRE:
                # The registry calls it by the province's own name.
                name = PROVINCE_ALIASES.get(published, published)
            name = DISTRICT_ALIASES.get((province, name), name)
            area = districts.get((province, name))
            if area is None:
                unknown.append(f"{published} / {row['ilce']!r}")
                continue
            count = int(row["magaza_sayisi"])
            if count:
                placed[area] = placed.get(area, 0) + count
    if unknown:
        raise KeyError(
            f"{brand}: kayıt defterinde olmayan ad(lar): "
            + ", ".join(sorted(set(unknown)))
        )
    if not placed:
        raise ValueError(f"{brand}: döküm boş ({path})")
    return placed


class ChainRestaurants:
    """Every brand's branches, as one indicator broken down by brand."""

    indicator_id = "chain_restaurants"
    source_id = SOURCE
    #: Subclasses swap these three and inherit everything else.
    brands = BRANDS
    #: Brands whose district comes from the source's own label rather than a coordinate.
    count_brands: ClassVar[dict[str, str]] = {}
    dim = "restaurant_brand"

    def fetch(self) -> Path:
        """Every brand's dump, gathered into one folder.

        `ingest` checksums whatever this returns, and it walks a directory to do it, so
        returning `RAW` would hash the entire raw store — hundreds of gigabytes for a
        few hundred kilobytes of CSV. The copies are what the manifest describes.
        """
        for brand in list(self.brands) + list(self.count_brands):
            cached_copy(dump(brand), FOLDER / f"{brand}.csv")
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        areas: list[str] = []
        levels: list[str] = []
        brands: list[str] = []
        values: list[float] = []
        for brand in list(self.brands) + list(self.count_brands):
            districts = (
                label_counts(brand) if brand in self.count_brands else counts(brand)
            )
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
    count_brands = COUNT_BRANDS
    dim = "store_brand"


CHAIN_STORE_ADAPTERS = {
    "chain_restaurants": ChainRestaurants,
    "chain_stores": ChainStores,
}
