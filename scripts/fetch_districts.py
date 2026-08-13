"""Fetch district boundaries, one file per province, keyed to our own area ids.

The published set is a single 14 MB file. Sending that to a browser to draw 973 shapes,
of which the reader looks at one province's worth at a time, is the wrong trade: this
splits it into 81 files that are fetched when a province is opened.

Two things this deliberately does not do:

- It does not invent history. The source is a snapshot of today's administrative map.
  Districts were created, merged and renamed — most visibly by law 6360, in force from
  the 2014 local elections — and none of that is in here. Validity columns are written
  empty and filled by hand as each change is verified; an empty `valid_from` means "not
  checked yet", never "has always existed".
- It does not smooth borders away. Simplification is a rendering concern, so the
  tolerance is small enough (~100 m) that a district keeps its shape and shared borders
  stay shared.

Source: ttezer/turkiye-harita-verisi, itself a pinned snapshot of HDX COD-AB-TUR
(OCHA), CC BY-IGO. Provenance is written into every file produced.

Run:  uv run python scripts/fetch_districts.py
"""

import csv
import datetime as dt
import json
import sys

import httpx

sys.path.insert(0, "src")

from veriatlas.areas import REGISTRY_PATH, load_areas
from veriatlas.config import PUBLIC, RAW

BASE = "https://raw.githubusercontent.com/ttezer/turkiye-harita-verisi/HEAD/"
GEOMETRY = BASE + "dist/geojson/districts.geojson"
NAMES = BASE + "dist/csv/districts.csv"

SOURCE_ID = "hdx_cod_ab_tur"
LICENCE = "CC BY-IGO (HDX COD-AB-TUR, ttezer/turkiye-harita-verisi anlik kopyasi)"

#: Simplification tolerance in degrees. 0.001° is roughly 100 m at this latitude — below
#: what a reader can see at country or province zoom, above what the file needs to carry.
TOLERANCE = 0.001

DISTRICTS_PATH = REGISTRY_PATH.parent / "areas_tr_districts.csv"
OUT_DIR = PUBLIC / "geo" / "districts"


def download(url: str, path):
    """Fetch once and keep the raw copy; re-runs read from disk."""
    if not path.exists():
        response = httpx.get(url, timeout=300, follow_redirects=True)
        response.raise_for_status()
        path.write_bytes(response.content)
    return path


def simplify(points: list, tolerance: float) -> list:
    """Douglas-Peucker. Keeps the points that carry the shape, drops the rest.

    Written out rather than pulled in: it is fifteen lines, and a geometry dependency
    would have to be justified to everyone who installs the project.
    """
    if len(points) < 3:
        return points

    first, last = points[0], points[-1]
    dx, dy = last[0] - first[0], last[1] - first[1]
    span = (dx * dx + dy * dy) ** 0.5

    worst, index = 0.0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i][0] - first[0], points[i][1] - first[1]
        # Distance to the chord; a degenerate chord falls back to distance from its start.
        distance = abs(px * dy - py * dx) / span if span else (px * px + py * py) ** 0.5
        if distance > worst:
            worst, index = distance, i

    if worst <= tolerance:
        return [first, last]

    left = simplify(points[: index + 1], tolerance)
    right = simplify(points[index:], tolerance)
    return left[:-1] + right


def simplify_geometry(geometry: dict) -> dict:
    """Apply the above to every ring, keeping rings closed and polygons whole."""

    def ring(points):
        thinned = simplify(points, TOLERANCE)
        if thinned[0] != thinned[-1]:
            thinned.append(thinned[0])
        # A ring needs four points to still be a ring; below that, keep the original.
        return thinned if len(thinned) >= 4 else points

    if geometry["type"] == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [ring(r) for r in geometry["coordinates"]],
        }
    return {
        "type": "MultiPolygon",
        "coordinates": [[ring(r) for r in poly] for poly in geometry["coordinates"]],
    }


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    geometry_path = download(GEOMETRY, RAW / "ttezer-districts.geojson")
    names_path = download(NAMES, RAW / "ttezer-districts.csv")
    retrieved_at = dt.datetime.now(tz=dt.UTC).date().isoformat()

    # The published CSV carries a BOM; utf-8-sig eats it so the first column is not
    # named "﻿id".
    with names_path.open(encoding="utf-8-sig") as handle:
        names = {row["id"]: row for row in csv.DictReader(handle)}

    provinces = {
        row["area_id"]: row["name_tr"]
        for row in load_areas().filter(area_level="province").to_dicts()
    }

    payload = json.loads(geometry_path.read_text(encoding="utf-8"))
    by_province: dict[str, list] = {}
    registry: list[dict] = []

    for feature in payload["features"]:
        source_id = feature["properties"]["id"]
        row = names.get(source_id)
        if row is None:
            raise SystemExit("ilce adi bulunamadi: " + source_id)

        # Our own id, built the way province ids are: plate code, then the district's
        # own two-digit code. The source id stays alongside it so the join is auditable.
        province_id = "TR-" + row["plate_code"]
        area_id = province_id + "-" + row["district_local_code"]
        if province_id not in provinces:
            raise SystemExit(
                "kayitta olmayan il: " + province_id + " (" + source_id + ")"
            )

        by_province.setdefault(province_id, []).append(
            {
                "type": "Feature",
                "properties": {
                    "area_id": area_id,
                    "name_tr": row["name"],
                    "area_level": "district",
                    "parent_id": province_id,
                },
                "geometry": simplify_geometry(feature["geometry"]),
            }
        )

        registry.append(
            {
                "area_id": area_id,
                "area_level": "district",
                "name_tr": row["name"],
                "parent_id": province_id,
                # Left empty on purpose: see the module docstring. Filling these is the
                # hand-verified half of open item 3.
                "valid_from": "",
                "valid_to": "",
                "source_id": SOURCE_ID,
                "source_area_id": source_id,
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for province_id, features in sorted(by_province.items()):
        (OUT_DIR / (province_id + ".geojson")).write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "area_id": province_id,
                    "name_tr": provinces[province_id],
                    "source_id": SOURCE_ID,
                    "licence": LICENCE,
                    "retrieved_at": retrieved_at,
                    "features": features,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    registry.sort(key=lambda r: r["area_id"])
    with DISTRICTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(registry[0]))
        writer.writeheader()
        writer.writerows(registry)

    total = sum(len(f) for f in by_province.values())
    written = sum((OUT_DIR / (p + ".geojson")).stat().st_size for p in by_province)
    print("ilce  :", total, "| il dosyasi:", len(by_province))
    print("boyut :", round(written / 1e6, 1), "MB (kaynak 14.7 MB)")
    print("kayit :", DISTRICTS_PATH)
    print("kaynak:", SOURCE_ID, "| cekim:", retrieved_at)


if __name__ == "__main__":
    main()
