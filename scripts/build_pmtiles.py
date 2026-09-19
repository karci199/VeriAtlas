"""Pack the boundary geometry into one PMTiles archive per layer.

972 GeoJSON files and 220 MB is fine for a page that opens one district at a time, and
hopeless for a map of the whole country: the browser cannot hold fifty thousand polygons,
and a static host cannot answer "give me what is on screen". PMTiles solves exactly that —
one file, vector tiles inside, and the browser asks for the byte range it needs over plain
HTTP. No tile server.

Tiles are built here rather than with tippecanoe because the machine has no build tools:
shapely clips, mapbox_vector_tile encodes, pmtiles writes.

Zoom plan: districts z0-9, neighbourhoods z8-12. Overlapping bands so the neighbourhood
layer can fade in over the district one.

Levels above the province are dissolved from the same district shapes, through the İBBS
membership table, so a region's border is always exactly its provinces' outer edge — no
second geometry that can disagree.

Run:  uv run python scripts/build_pmtiles.py ilce
      uv run python scripts/build_pmtiles.py mahalle
      uv run python scripts/build_pmtiles.py ibbs1 ibbs2 tr
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
from collections import defaultdict

import mapbox_vector_tile
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer
from shapely.geometry import box, shape
from shapely.ops import transform

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEO = ROOT / "public" / "geo"
OUT = ROOT / "public" / "tiles"
EXTENT = 4096

LAYERS = {
    # Provinces are not a separate source: they are the districts dissolved, so the two
    # layers can never disagree about where a border runs.
    "il": {
        "dir": GEO / "districts",
        "min": 0,
        "max": 7,
        "layer": "il",
        "birlestir": True,
    },
    "ilce": {"dir": GEO / "districts", "min": 0, "max": 9, "layer": "ilce"},
    # İBBS-1 (12 regions) and İBBS-2 (26) are the provinces grouped; İBBS-3 *is* the
    # province, so it is not a separate layer. The country outline is the same dissolve
    # taken one step further.
    "ibbs2": {"dir": GEO / "districts", "min": 0, "max": 7, "layer": "ibbs2", "ibbs": 2},
    "ibbs1": {"dir": GEO / "districts", "min": 0, "max": 6, "layer": "ibbs1", "ibbs": 1},
    "tr": {"dir": GEO / "districts", "min": 0, "max": 6, "layer": "tr", "ibbs": 0},
    # From zoom 5 so the whole country can be seen at neighbourhood level; the low
    # zooms are few tiles, each simplified to about a pixel.
    "mahalle": {"dir": GEO / "neighbourhoods", "min": 5, "max": 12, "layer": "mahalle"},
}


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    n = 2**z
    west = x / n * 360 - 180
    east = (x + 1) / n * 360 - 180
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180) / 360 * n)
    lat = max(min(lat, 85.05), -85.05)
    y = int(
        (
            1
            - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat)))
            / math.pi
        )
        / 2
        * n
    )
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def simplify_for(zoom: int) -> float:
    """Tolerance in degrees: about half a pixel at that zoom."""
    return 360 / (2**zoom * EXTENT) * 2


def features_of(directory: pathlib.Path):
    for path in sorted(directory.glob("*.geojson")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            keep = {
                "id": props.get("area_id"),
                "ad": props.get("name_tr"),
                "ust": props.get("parent_id"),
            }
            # Villages and neighbourhoods share a layer and a geometry file; the source's
            # own flag is the only thing that tells them apart, and a map that offers
            # "köy" as a level needs it in the tile.
            if props.get("kind"):
                keep["tur"] = "koy" if props["kind"] == "village" else "mahalle"
            yield keep, shape(feature["geometry"])


def ibbs_table() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """province name → (İBBS-2 id, İBBS-1 id), plus the regions' own names."""
    import csv

    table = ROOT / "src" / "veriatlas" / "data" / "nuts_tr.csv"
    areas = ROOT / "src" / "veriatlas" / "data" / "areas_tr.csv"
    ids = {}
    with areas.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["area_level"] == "province":
                ids[row["name_tr"]] = row["area_id"]
    province_region, names = {}, {}
    with table.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            area_id = ids.get(row["province_name"])
            if not area_id:
                raise KeyError("İBBS tablosunda tanınmayan il: " + row["province_name"])
            province_region[area_id] = (row["nuts2_id"], row["nuts1_id"])
            names[row["nuts2_id"]] = row["nuts2_name"]
            names[row["nuts1_id"]] = row["nuts1_name"]
    return province_region, names, ids


def build(name: str) -> None:
    spec = LAYERS[name]
    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / f"{name}.pmtiles"
    # Written aside and swapped in: the page reads byte ranges from the live file.
    target = OUT / f"{name}.pmtiles.tmp"

    items = list(features_of(spec["dir"]))
    if "ibbs" in spec:
        from shapely.ops import unary_union

        province_region, names, _ = ibbs_table()
        level = spec["ibbs"]
        groups: dict[str, list] = defaultdict(list)
        for props, geom in items:
            province = props.get("ust") or ""
            if level == 0:
                key = "TR"
            else:
                region = province_region.get(province)
                if region is None:
                    raise KeyError("İBBS eşleşmeyen il: " + province)
                key = region[0] if level == 2 else region[1]
            groups[key].append(geom)
        items = [
            (
                {
                    "id": key,
                    "ad": "Türkiye" if key == "TR" else names.get(key, key),
                    "ust": "TR",
                },
                unary_union(geoms).buffer(0),
            )
            for key, geoms in groups.items()
        ]
    elif spec.get("birlestir"):
        from shapely.ops import unary_union

        gruplar: dict[str, list] = defaultdict(list)
        adlar: dict[str, str] = {}
        for props, geom in items:
            parent = props.get("ust") or ""
            gruplar[parent].append(geom)
            adlar.setdefault(parent, parent)
        items = [
            (
                {"id": parent, "ad": adlar.get(parent, parent), "ust": "TR"},
                unary_union(geoms).buffer(0),
            )
            for parent, geoms in gruplar.items()
            if parent
        ]
    print(f"{len(items):,} sekil okundu")

    with target.open("wb") as fh:
        writer = Writer(fh)
        minx, miny, maxx, maxy = 180.0, 90.0, -180.0, -90.0
        for _, geom in items:
            b = geom.bounds
            minx, miny = min(minx, b[0]), min(miny, b[1])
            maxx, maxy = max(maxx, b[2]), max(maxy, b[3])

        for zoom in range(spec["min"], spec["max"] + 1):
            tolerance = simplify_for(zoom)
            buckets: dict[tuple[int, int], list] = defaultdict(list)
            for props, geom in items:
                small = geom.simplify(tolerance, preserve_topology=True)
                if small.is_empty:
                    continue
                b = small.bounds
                x0, y1 = lonlat_to_tile(b[0], b[3], zoom)
                x1, y0 = lonlat_to_tile(b[2], b[1], zoom)
                for x in range(x0, x1 + 1):
                    for y in range(y1, y0 + 1):
                        buckets[(x, y)].append((props, small))

            written = 0
            for (x, y), members in sorted(buckets.items()):
                west, south, east, north = tile_bounds(zoom, x, y)
                # Clipped a little wider than the tile: cutting exactly on the seam turns
                # the cut itself into an edge, and the border layer then draws the tile
                # grid across the country as straight lines. Coordinates outside 0..extent
                # are allowed by the format and the renderer clips them away.
                pay_x, pay_y = (east - west) * 0.05, (north - south) * 0.05
                clip = box(west - pay_x, south - pay_y, east + pay_x, north + pay_y)
                features = []
                for props, geom in members:
                    piece = geom.intersection(clip)
                    if piece.is_empty:
                        continue

                    # Tile-local coordinates, y down, 0..EXTENT.
                    def to_tile(px, py, west=west, south=south, east=east, north=north):
                        return (
                            (px - west) / (east - west) * EXTENT,
                            (north - py) / (north - south) * EXTENT,
                        )

                    features.append(
                        {
                            "geometry": transform(to_tile, piece),
                            "properties": {
                                k: v for k, v in props.items() if v is not None
                            },
                        }
                    )
                if not features:
                    continue
                blob = mapbox_vector_tile.encode(
                    {"name": spec["layer"], "features": features},
                    extents=EXTENT,
                    default_options={"y_coord_down": True},
                )
                writer.write_tile(zxy_to_tileid(zoom, x, y), blob)
                written += 1
            print(f"  z{zoom}: {written} karo")

        writer.finalize(
            {
                "tile_type": TileType.MVT,
                "tile_compression": Compression.NONE,
                "min_zoom": spec["min"],
                "max_zoom": spec["max"],
                "min_lon_e7": int(minx * 1e7),
                "min_lat_e7": int(miny * 1e7),
                "max_lon_e7": int(maxx * 1e7),
                "max_lat_e7": int(maxy * 1e7),
                "center_zoom": spec["min"],
                "center_lon_e7": int((minx + maxx) / 2 * 1e7),
                "center_lat_e7": int((miny + maxy) / 2 * 1e7),
            },
            {
                "attribution": "TÜİK / Endeksa",
                "vector_layers": [
                    {
                        "id": spec["layer"],
                        "minzoom": spec["min"],
                        "maxzoom": spec["max"],
                        "fields": {"id": "String", "ad": "String", "ust": "String"},
                    }
                ],
            },
        )
    size = target.stat().st_size / 1e6
    try:
        target.replace(final)
    except PermissionError:
        # Windows will not replace a file the local server holds open; stop it and
        # rename `<name>.pmtiles.tmp` by hand.
        print("DEGISTIRILEMEDI (dosya acik):", final)
        return
    print(f"yazildi: {final} ({size:.1f} MB)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "ilce")
