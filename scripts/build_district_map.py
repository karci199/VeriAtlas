"""Self-contained district map page: the district inside its province, and its
neighbourhoods, from the province geojson and the Endeksa neighbourhood polygons.

    python scripts/build_district_map.py --district TR-16-006 --out map.html

Modes: outline only / labels / population density. Clicking a neighbourhood opens a
side panel with the few figures the page carries inline (name, kind, 2024 population,
area, density). Everything is embedded; no network.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def norm(s: str) -> str:
    s = s.replace("I", "ı").replace("İ", "i").lower()
    return re.sub(r"\s*(mah\.|mahallesi|mah)$", "", s).strip()


def rounded(geom: dict, nd: int = 5) -> dict:
    def rec(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], nd), round(c[1], nd)]
        return [rec(x) for x in c]

    return {"type": geom["type"], "coordinates": rec(geom["coordinates"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--district", required=True)
    ap.add_argument("--raw", type=Path, default=Path("C:/veri/raw/endeksa"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    province = a.district.rsplit("-", 1)[0]

    prov = json.loads(
        (REPO / f"public/geo/districts/{province}.geojson").read_text("utf-8")
    )
    districts = [
        {
            "id": f["properties"]["area_id"],
            "name": f["properties"]["name_tr"],
            "geometry": rounded(f["geometry"]),
        }
        for f in prov["features"]
    ]
    dname = next(d["name"] for d in districts if d["id"] == a.district)
    pname = next(
        r["name_tr"]
        for r in csv.DictReader(
            open(REPO / "src/veriatlas/data/areas_tr.csv", encoding="utf-8")
        )
        if r["area_id"] == province
    )

    geo = json.loads((a.raw / a.district / "geo.json").read_text("utf-8"))
    areas = {
        norm(r["name_tr"]): r["area_id"]
        for r in csv.DictReader(
            open(
                REPO / "src/veriatlas/data/areas_tr_neighbourhoods.csv",
                encoding="utf-8",
            )
        )
        if r["parent_id"] == a.district
    }
    pop24: dict[str, int] = {}
    with gzip.open(
        REPO / "public/population-neighbourhood.csv.gz", "rt", encoding="utf-8"
    ) as f:
        for r in csv.DictReader(f):
            if (
                r["area_id"].startswith(a.district + "-")
                and r["year"] == "2024"
                and not r["sex"]
            ):
                pop24[r["area_id"]] = pop24.get(r["area_id"], 0) + int(r["value"])
    quarters = []
    outline = None
    for f in geo["features"]:
        p = f["properties"]
        if not p.get("DistrictId"):
            outline = rounded(f["geometry"])
            continue
        q = (
            json.loads(
                (
                    a.raw
                    / a.district
                    / f"{p['DistrictId']}-{slugify(p['District'])}.json"
                ).read_text("utf-8")
            )["Demography"]
            if (
                a.raw / a.district / f"{p['DistrictId']}-{slugify(p['District'])}.json"
            ).exists()
            else {}
        )
        area_id = areas.get(norm(p["District"]), "")
        quarters.append(
            {
                "id": area_id,
                "eid": p["DistrictId"],
                "name": p["District"],
                "kind": "merkez" if int(p["DistrictId"]) < 100000 else "kır",
                "pop": pop24.get(area_id, p.get("Population")),
                "area": q.get("Area"),
                "hh": q.get("HouseholdCount") or None,
                "geometry": rounded(f["geometry"]),
            }
        )
    data = {
        "district": {
            "id": a.district,
            "name": dname,
            "province": pname,
            "outline": outline,
        },
        "districts": districts,
        "quarters": quarters,
    }
    html = TEMPLATE.replace(
        "__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    )
    a.out.write_text(html, "utf-8")
    print(a.out, len(quarters), "mahalle")


def slugify(s: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    return re.sub(r"[^a-z0-9]+", "-", s.translate(tr).lower()).strip("-")


TEMPLATE = (REPO / "web" / "district_map.html").read_text("utf-8")


if __name__ == "__main__":
    main()
