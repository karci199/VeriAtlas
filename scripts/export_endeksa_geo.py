"""Neighbourhood boundaries from an Endeksa geo dump to per-district GeoJSON files.

Input: one JSON file per province under raw/endeksa/geo/<province_id>.json, holding
`{<CountyId>: <geo/map response>}` as pulled in the browser (docs/endeksa.md). Output:
public/geo/neighbourhoods/<district_id>.geojson in the shape atlas.js reads — the same
shape scripts/build_atlas_data.py writes for İznik, minus `kind`, which needs MEDAS.

Endeksa's CountyId is its own; the join to our district ids is by folded name against
public/geo/districts/<province_id>.geojson. An unmatched county stops the run rather than
writing a file under a guessed id.

District boundaries work the same way one level up: raw/endeksa/geo/districts.json holds
`{<plate>: <geo/map level=1 response>}`; each county is matched by folded name to the
district ids already in public/geo/districts/<province_id>.geojson (HDX), and the file is
rewritten with Endeksa geometry so district and neighbourhood edges come from one source
and sit edge to edge. A province with any unmatched county keeps its HDX file.

Run:  uv run python scripts/export_endeksa_geo.py TR-16          # neighbourhoods
      uv run python scripts/export_endeksa_geo.py --districts     # all provinces
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "endeksa" / "geo"
DISTRICTS = ROOT / "public" / "geo" / "districts"
OUT = ROOT / "public" / "geo" / "neighbourhoods"


def fold(name: str) -> str:
    lowered = name.strip().lower()
    for turkish, ascii_ in (
        ("ı", "i"),
        ("İ", "i"),
        ("ğ", "g"),
        ("ü", "u"),
        ("ş", "s"),
        ("ö", "o"),
        ("ç", "c"),
        ("â", "a"),
        ("î", "i"),
        ("û", "u"),
    ):
        lowered = lowered.replace(turkish, ascii_)
    return "".join(ch for ch in lowered if ch.isalnum())


def main(province_id: str) -> None:
    dump = json.loads((RAW / f"{province_id}.json").read_text(encoding="utf-8"))
    districts = json.loads(
        (DISTRICTS / f"{province_id}.geojson").read_text(encoding="utf-8")
    )
    by_name = {
        fold(f["properties"]["name_tr"]): f["properties"]["area_id"]
        for f in districts["features"]
    }

    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for county_id, geo in dump.items():
        feats = geo.get("features") or []
        if not feats:
            print("empty", county_id)
            continue
        county_name = feats[0]["properties"]["County"]
        district_id = by_name.get(fold(county_name))
        if district_id is None:
            raise SystemExit(
                f"county {county_id} {county_name!r} matches no district in {province_id}"
            )
        out_path = OUT / f"{district_id}.geojson"
        if out_path.exists() and district_id == "TR-16-006":
            continue  # İznik comes from build_atlas_data.py with kinds; keep it
        out = {
            "type": "FeatureCollection",
            "source_id": "endeksa",
            "retrieved_at": geo.get("retrieved_at"),
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "area_id": f"{district_id}-{f['id']}",
                        "name_tr": f["properties"]["description"].strip(),
                        "area_level": "neighbourhood",
                        "parent_id": district_id,
                        "endeksa_id": int(f["id"]),
                    },
                    "geometry": f["geometry"],
                }
                for f in feats
                if f.get("geometry")
            ],
        }
        out_path.write_text(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        written += 1
        print(district_id, county_name, len(out["features"]))
    print("written", written)


def districts() -> None:
    dump = json.loads((RAW / "districts.json").read_text(encoding="utf-8"))
    ok, kept = 0, []
    for plate, geo in sorted(dump.items(), key=lambda kv: int(kv[0])):
        province_id = f"TR-{int(plate):02d}"
        path = DISTRICTS / f"{province_id}.geojson"
        current = json.loads(path.read_text(encoding="utf-8"))
        by_name = {fold(f["properties"]["name_tr"]): f["properties"] for f in current["features"]}
        feats, missing = [], []
        for f in geo.get("features") or []:
            name = f["properties"]["description"].strip()
            props = by_name.get(fold(name))
            if props is None or not f.get("geometry"):
                missing.append(name)
                continue
            feats.append({"type": "Feature", "properties": {**props, "endeksa_id": int(f["id"])}, "geometry": f["geometry"]})
        if missing or len(feats) != len(current["features"]):
            kept.append((province_id, missing, len(feats), len(current["features"])))
            continue
        path.write_text(
            json.dumps({**current, "source_id": "endeksa", "licence": None, "retrieved_at": geo.get("retrieved_at"), "features": feats}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        ok += 1
    print("rewritten", ok)
    for province_id, missing, got, want in kept:
        print("kept HDX", province_id, f"{got}/{want}", "unmatched:", ", ".join(missing))


if __name__ == "__main__":
    if "--districts" in sys.argv:
        districts()
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else "TR-16")
