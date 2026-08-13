"""Fetch province boundaries and key them to the area registry.

The map view needs one thing the fact table cannot carry: shape. This takes a copy of a
published boundary set, joins it to our own area ids and writes the result to
`public/areas.geojson`, so the page never talks to an outside host at render time.

The join is the whole point. A boundary file names its provinces the way its author
spelled them, and the spellings drift — Afyon / Afyonkarahisar, İçel / Mersin, Urfa /
Şanlıurfa. Names are matched folded, known aliases are declared below, and anything
still unmatched stops the run: a province quietly missing from the map would read as
"no data" rather than "we failed to look it up".

Boundaries are not a measurement, so they carry no quality flag. What they do carry is
provenance, written into the file itself.

Run:  uv run python scripts/fetch_geometry.py
"""

import datetime as dt
import json
import sys

import httpx

sys.path.insert(0, "src")

from veriatlas.areas import load_areas
from veriatlas.config import PUBLIC, RAW

SOURCE = "https://raw.githubusercontent.com/cihadturhan/tr-geojson/master/geo/tr-cities-utf8.json"
SOURCE_ID = "tr-geojson"
LICENCE = "MIT (cihadturhan/tr-geojson)"

#: Boundary-file spelling -> registry spelling. Every entry is a name that changed or a
#: shorthand the source kept; none of them are typos on our side.
ALIASES = {
    "afyon": "afyonkarahisar",
    "icel": "mersin",
    "urfa": "sanliurfa",
    "maras": "kahramanmaras",
    "hakkari": "hakkari",
}


def fold(name: str) -> str:
    """Turkish name to a comparable key: 'Şanlıurfa' -> 'sanliurfa'."""
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


def main() -> None:
    response = httpx.get(SOURCE, timeout=60)
    response.raise_for_status()
    retrieved_at = dt.datetime.now(tz=dt.UTC).date().isoformat()

    # The raw copy is kept for the same reason adapters keep theirs (K8): the parse can
    # be fixed and replayed, and the source may change or vanish in the meantime.
    RAW.mkdir(parents=True, exist_ok=True)
    raw_path = RAW / ("tr-cities." + retrieved_at + ".json")
    raw_path.write_bytes(response.content)

    payload = response.json()
    features = payload["features"]

    provinces = load_areas().filter(area_level="province")
    by_name = {fold(row["name_tr"]): row for row in provinces.to_dicts()}

    matched = []
    missing = []
    for feature in features:
        key = fold(feature["properties"].get("name", ""))
        key = ALIASES.get(key, key)
        area = by_name.get(key)
        if area is None:
            missing.append(feature["properties"].get("name"))
            continue

        matched.append(
            {
                "type": "Feature",
                "properties": {
                    "area_id": area["area_id"],
                    "name_tr": area["name_tr"],
                    "area_level": "province",
                },
                "geometry": feature["geometry"],
            }
        )

    unseen = sorted(set(by_name) - {fold(f["properties"]["name_tr"]) for f in matched})
    if missing or unseen:
        raise SystemExit(
            "eslesmeyen il var — harita eksik cizilirdi.\n"
            "  kaynakta karsiligi yok : "
            + ", ".join(sorted(filter(None, missing)))
            + "\n"
            "  kayitta karsiligi yok  : " + ", ".join(unseen)
        )

    target = PUBLIC / "areas.geojson"
    target.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "source_id": SOURCE_ID,
                "source_url": SOURCE,
                "licence": LICENCE,
                "retrieved_at": retrieved_at,
                "features": matched,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("ham   :", raw_path)
    print("yazildi:", target, len(matched), "il")
    print("kaynak:", SOURCE_ID, "| cekim:", retrieved_at)


if __name__ == "__main__":
    main()
