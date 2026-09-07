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

Run:  uv run python scripts/build_pmtiles.py ilce
      uv run python scripts/build_pmtiles.py mahalle
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
    "ilce": {"dir": GEO / "districts", "min": 0, "max": 9, "layer": "ilce"},
    "mahalle": {"dir": GEO / "neighbourhoods", "min": 7, "max": 12, "layer": "mahalle"},
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
        (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi)
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
            yield keep, shape(feature["geometry"])


def build(name: str) -> None:
    spec = LAYERS[name]
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{name}.pmtiles"

    items = list(features_of(spec["dir"]))
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
                clip = box(west, south, east, north)
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
                            "properties": {k: v for k, v in props.items() if v is not None},
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
    print(f"yazildi: {target} ({target.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "ilce")
