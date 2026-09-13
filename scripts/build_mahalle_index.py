"""A name-to-area-id lookup for neighbourhoods, built from the geometry the map draws.

The election reports name settlements; the map knows them by area id. Matching the two
through the MEDAS registry looked reasonable and was wrong: the tiles carry Endeksa ids
and the registry carries MEDAS codes, so most settlements silently failed to match and the
map came out grey.

So the lookup is built from `public/geo/neighbourhoods/*.geojson` — the same file the tiles
were made from. One JSON: {district_id: {folded name: area_id}}.

Run:  uv run python scripts/build_mahalle_index.py
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
GEO = ROOT / "public" / "geo" / "neighbourhoods"
OUT = ROOT / "public" / "tiles" / "mahalle-adlari.json"

SUFFIX = re.compile(r"\s+(mah\.?|mahallesi|köy\.?|köyü|belde|bel\.)\s*$", re.IGNORECASE)


def fold(name: str) -> str:
    text = SUFFIX.sub("", (name or "").strip()).lower()
    for a, b in zip("İIÇĞÖŞÜçğıöşüâîûÂÎÛ", "iicgosucgiosuaiuaiu", strict=False):
        text = text.replace(a, b)
    return "".join(ch for ch in text if ch.isalnum())


def main() -> None:
    out: dict[str, dict[str, str]] = {}
    for path in sorted(GEO.glob("TR-*.geojson")):
        district = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        table = out.setdefault(district, {})
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            area_id = props.get("area_id")
            name = props.get("name_tr")
            if area_id and name:
                table[fold(name)] = area_id
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    total = sum(len(v) for v in out.values())
    print(f"{len(out)} ilce, {total:,} mahalle -> {OUT.name} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
