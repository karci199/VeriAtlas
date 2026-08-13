"""Rebuild the area registry from TurkiyeAPI, adding the region level.

Why fetch rather than depend on it at runtime: an outside service can go down or
renumber itself. We take a copy once, record where it came from and when, and the
registry stays ours.

What it does NOT give us is history. TurkiyeAPI describes the country as it is today —
no pre-6360 districts, no closed villages, no renamings. That half of the geography
registry still has to be built by hand (open item 3).

Run:  uv run python scripts/fetch_areas.py
"""

import csv
import datetime as dt
import sys
import unicodedata

import httpx

sys.path.insert(0, "src")

from veriatlas.areas import REGISTRY_PATH, WEIGHTS_PATH

SOURCE = "https://api.turkiyeapi.dev/v2/provinces"
SOURCE_ID = "turkiyeapi"


def slug(name: str) -> str:
    """Turkish name to an ascii id: 'İç Anadolu' -> 'ic_anadolu'."""
    folded = name.lower().replace("ı", "i").replace("ğ", "g").replace("ü", "u")
    folded = folded.replace("ş", "s").replace("ö", "o").replace("ç", "c")
    stripped = unicodedata.normalize("NFKD", folded).encode("ascii", "ignore").decode()
    return "_".join(stripped.split())


def main() -> None:
    response = httpx.get(SOURCE, params={"limit": 100}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    provinces = payload["data"]
    retrieved_at = dt.datetime.now(tz=dt.UTC).date().isoformat()

    if len(provinces) != 81:
        raise SystemExit("beklenen 81 il, gelen: " + str(len(provinces)))

    regions = {p["region"]["tr"]: "TR-R-" + slug(p["region"]["tr"]) for p in provinces}

    rows = [
        {
            "area_id": "TR",
            "area_level": "country",
            "name_tr": "Türkiye",
            "parent_id": "",
        }
    ]
    rows += [
        {"area_id": area_id, "area_level": "region", "name_tr": name, "parent_id": "TR"}
        for name, area_id in sorted(regions.items(), key=lambda kv: kv[1])
    ]
    rows += [
        {
            "area_id": f"TR-{p['id']:02d}",
            "area_level": "province",
            "name_tr": p["name"],
            "parent_id": regions[p["region"]["tr"]],
        }
        for p in sorted(provinces, key=lambda p: p["id"])
    ]

    with REGISTRY_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    # Weights, kept apart from the registry: a name is permanent, a population is an
    # observation with a date on it.
    weights = [
        {
            "area_id": f"TR-{p['id']:02d}",
            "population": p["population"],
            "source_id": SOURCE_ID,
            "vintage": str(payload["meta"]["datasetVersion"]),
            "retrieved_at": retrieved_at,
        }
        for p in sorted(provinces, key=lambda p: p["id"])
    ]
    with WEIGHTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(weights[0]))
        writer.writeheader()
        writer.writerows(weights)

    print("bolge :", len(regions), "->", ", ".join(sorted(regions)))
    print("il    :", len(provinces))
    print("surum :", payload["meta"]["datasetVersion"], "| cekim:", retrieved_at)


if __name__ == "__main__":
    main()
