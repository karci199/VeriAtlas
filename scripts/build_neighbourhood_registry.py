"""Build the neighbourhood registry from the MEDAS exports themselves.

There is no published list of Türkiye's neighbourhoods with stable ids, so the registry
is derived from the observations — the same move the district validity table makes
(K11): each year's export *is* that year's administrative map.

The identity is the MEDAS code, never the name (K15). Bursa alone shows why: between
2013 and 2025, forty of 1057 neighbourhoods changed name, a hundred names repeat inside
the province, and four different places were all called `Hamidiye (Merkez)` in 2013 and
four different things in 2025. The code went through all of that unchanged.

`name_tr` is the newest name seen. The older ones are not thrown away — they go to
`docs/mahalle-adlari.md`, the way district renames do, because a reader searching for
"Topselvi" should be able to find out it is now "Fatih".

`first_seen` / `last_seen` are what the exports show, not administrative dates. An
`first_seen` of 2025 means "absent from the years we hold", never "founded in 2025".

Run:  uv run python scripts/build_neighbourhood_registry.py
"""

import csv
import sys

sys.path.insert(0, "src")

from veriatlas.adapters.tuik_neighbourhoods import DOWNLOADS, read_export
from veriatlas.areas import load_areas, load_districts
from veriatlas.config import DATA, DOCS

REGISTRY = DATA / "areas_tr_neighbourhoods.csv"
RENAMES = DOCS / "mahalle-adlari.md"

SOURCE_ID = "tuik_medas"


def fold(name: str) -> str:
    """Turkish name to a comparable key. Same rule as the district join."""
    lowered = name.strip().lower()
    for turkish, plain in (
        ("ı", "i"),
        ("İ", "i"),
        ("ğ", "g"),
        ("ü", "u"),
        ("ş", "s"),
        ("ö", "o"),
        ("ç", "c"),
        ("â", "a"),
    ):
        lowered = lowered.replace(turkish, plain)
    return "".join(ch for ch in lowered if ch.isalnum())


def main() -> None:
    records = []
    for path in sorted(DOWNLOADS.glob("*.csv")):
        records.extend(read_export(path))
    if not records:
        raise SystemExit("indirilmis mahalle dosyasi yok: " + str(DOWNLOADS))

    provinces = {
        fold(row["name_tr"]): row["area_id"] for row in load_areas().to_dicts()
    }
    districts = {
        (row["parent_id"], fold(row["name_tr"])): row["area_id"]
        for row in load_districts().to_dicts()
    }

    def district_of(province: str, district: str) -> str | None:
        parent = provinces.get(fold(province))
        if parent is None:
            return None
        found = districts.get((parent, fold(district)))
        if found is not None:
            return found
        # The two sources name a central district differently: MEDAS says "Merkez", the
        # boundary registry gives it the province's own name.
        if fold(district) == "merkez":
            return districts.get((parent, fold(province)))
        return None

    seen: dict[str, dict] = {}
    history: dict[str, list[tuple[int, str]]] = {}

    for record in records:
        parent = district_of(record.province, record.district)
        if parent is None:
            raise KeyError(
                "kayitta karsiligi olmayan ilce: "
                + record.province
                + "/"
                + record.district
            )

        entry = seen.get(record.code)
        if entry is None:
            entry = seen[record.code] = {
                "area_id": parent + "-" + record.code,
                "area_level": "neighbourhood",
                "name_tr": record.name,
                "parent_id": parent,
                "municipality": record.municipality,
                "medas_code": record.code,
                "first_seen": record.year,
                "last_seen": record.year,
                "source_id": SOURCE_ID,
            }
        entry["first_seen"] = min(entry["first_seen"], record.year)
        if record.year >= entry["last_seen"]:
            entry["last_seen"] = record.year
            # The newest year wins the name; that is what "current name" means here.
            entry["name_tr"] = record.name
            entry["municipality"] = record.municipality

        names = history.setdefault(record.code, [])
        if not names or names[-1][1] != record.name:
            names.append((record.year, record.name))

    rows = sorted(seen.values(), key=lambda r: r["area_id"])
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("yazildi:", REGISTRY, len(rows), "mahalle")

    renamed = {code: sorted(names) for code, names in history.items() if len(names) > 1}
    lines = [
        "# Mahalle ad değişiklikleri",
        "",
        "MEDAS dışa aktarımlarından çıkarıldı, elle doğrulanmadı. Kimlik koddur (K15);",
        "bu tablo yalnızca eski adla arayan birinin bugünkü adı bulabilmesi için var.",
        "",
        "| kod | alan kimliği | yıl yıl ad |",
        "| --- | --- | --- |",
    ]
    for code, names in sorted(renamed.items(), key=lambda kv: seen[kv[0]]["area_id"]):
        trail = " → ".join(str(year) + ": " + name for year, name in names)
        lines.append("| " + code + " | " + seen[code]["area_id"] + " | " + trail + " |")
    RENAMES.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("yazildi:", RENAMES, len(renamed), "ad degisikligi")


if __name__ == "__main__":
    main()
