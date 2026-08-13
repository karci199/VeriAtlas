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

from veriatlas.areas import NUTS_PATH, PARENTS_PATH, REGISTRY_PATH, WEIGHTS_PATH

SOURCE = "https://api.turkiyeapi.dev/v2/provinces"
SOURCE_ID = "turkiyeapi"


def read_nuts() -> dict[str, dict[str, str]]:
    """İBBS membership, keyed by province name.

    Hand-maintained: TurkiyeAPI carries the geographic regions but not the statistical
    ones, and TÜİK publishes at İBBS level, so we need both.
    """
    with NUTS_PATH.open(encoding="utf-8") as handle:
        return {row["province_name"]: row for row in csv.DictReader(handle)}


def write_csv(path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


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
    nuts = read_nuts()
    id_of = {p["name"]: f"TR-{p['id']:02d}" for p in provinces}

    unmatched = set(nuts) ^ set(id_of)
    if unmatched:
        raise SystemExit(
            "İBBS ve il adları eşleşmiyor: " + ", ".join(sorted(unmatched))
        )

    areas = [{"area_id": "TR", "area_level": "country", "name_tr": "Türkiye"}]
    areas += [
        {"area_id": area_id, "area_level": "region", "name_tr": name}
        for name, area_id in sorted(regions.items(), key=lambda kv: kv[1])
    ]
    areas += [
        {"area_id": code, "area_level": "nuts1", "name_tr": name}
        for code, name in sorted(
            {(n["nuts1_id"], n["nuts1_name"]) for n in nuts.values()}
        )
    ]
    areas += [
        {"area_id": code, "area_level": "nuts2", "name_tr": name}
        for code, name in sorted(
            {(n["nuts2_id"], n["nuts2_name"]) for n in nuts.values()}
        )
    ]
    areas += [
        {
            "area_id": f"TR-{p['id']:02d}",
            "area_level": "province",
            "name_tr": p["name"],
        }
        for p in sorted(provinces, key=lambda p: p["id"])
    ]

    # Membership is its own table because a province belongs to two hierarchies at once:
    # a geographic region (Marmara) and a statistical one (TR41). A single parent column
    # would force us to pick one and lose the other.
    parents = [
        {"area_id": area_id, "parent_id": "TR", "hierarchy": "geographic"}
        for area_id in regions.values()
    ]
    parents += [
        {
            "area_id": id_of[name],
            "parent_id": regions[p["region"]["tr"]],
            "hierarchy": "geographic",
        }
        for p in provinces
        for name in [p["name"]]
    ]
    parents += [
        {"area_id": code, "parent_id": "TR", "hierarchy": "nuts"}
        for code in sorted({n["nuts1_id"] for n in nuts.values()})
    ]
    parents += [
        {"area_id": n2, "parent_id": n1, "hierarchy": "nuts"}
        for n2, n1 in sorted({(n["nuts2_id"], n["nuts1_id"]) for n in nuts.values()})
    ]
    parents += [
        {"area_id": id_of[name], "parent_id": row["nuts2_id"], "hierarchy": "nuts"}
        for name, row in sorted(nuts.items())
    ]

    write_csv(REGISTRY_PATH, areas)
    write_csv(PARENTS_PATH, parents)

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
    write_csv(WEIGHTS_PATH, weights)

    print("bolge :", len(regions), "->", ", ".join(sorted(regions)))
    print("ibbs1 :", len({n["nuts1_id"] for n in nuts.values()}))
    print("ibbs2 :", len({n["nuts2_id"] for n in nuts.values()}))
    print("il    :", len(provinces))
    print("surum :", payload["meta"]["datasetVersion"], "| cekim:", retrieved_at)


if __name__ == "__main__":
    main()
