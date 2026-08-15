"""Build the village registry from the MEDAS settlement exports themselves.

Same move as the neighbourhood registry (K11): there is no published list of villages with
stable ids, so the register is derived from the observations — each year's export is that
year's administrative map.

The identity is the MEDAS code, never the name (K15). Villages need that even more than
neighbourhoods do: a district holds several `Yeni Köy.` and the bucak that told them apart
stops being written in 2017, so from that year on the name alone identifies nothing.

`name_tr` is the newest name seen; older ones go to `docs/koy-adlari.md` the way district
and neighbourhood renames do. `bucak` is the last one written before MEDAS dropped the
field — the village did not leave the bucak, the label did.

Run:  uv run python scripts/build_village_registry.py
"""

import csv
import sys

sys.path.insert(0, "src")

from veriatlas.adapters.tuik_villages import DOWNLOADS, read_export
from veriatlas.areas import load_areas, load_districts
from veriatlas.config import DATA, DOCS

REGISTRY = DATA / "areas_tr_villages.csv"
RENAMES = DOCS / "koy-adlari.md"

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
    for path in sorted(DOWNLOADS.glob("nufus-koy-*.csv")):
        records.extend(read_export(path))
    if not records:
        raise SystemExit("indirilmis koy dosyasi yok: " + str(DOWNLOADS))

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
        # MEDAS says "Merkez"; the boundary registry gives the central district the
        # province's own name.
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
                "area_level": "village",
                "name_tr": record.name,
                "parent_id": parent,
                "bucak": record.bucak or "",
                "medas_code": record.code,
                "first_seen": record.year,
                "last_seen": record.year,
                "source_id": SOURCE_ID,
            }
            history[record.code] = [(record.year, record.name)]
            continue

        entry["first_seen"] = min(entry["first_seen"], record.year)
        # The newest name wins, and the bucak survives the year MEDAS stopped writing it.
        if record.year >= entry["last_seen"]:
            entry["last_seen"] = record.year
            entry["name_tr"] = record.name
        if record.bucak:
            entry["bucak"] = record.bucak
        if record.name != history[record.code][-1][1]:
            history[record.code].append((record.year, record.name))

    rows = sorted(seen.values(), key=lambda row: row["area_id"])
    with REGISTRY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("yazildi:", REGISTRY, len(rows), "koy")

    renamed = {code: names for code, names in history.items() if len(names) > 1}
    lines = [
        "# Köy adı değişiklikleri",
        "",
        "MEDAS kodu sabit kalırken adın değiştiği köyler, gözlemden çıkarıldı.",
        "İlk sütun kimlik, sonra yıl ve o yıldan itibaren görülen ad.",
        "",
        "| Kimlik | Yıl | Ad |",
        "| --- | --- | --- |",
    ]
    for code in sorted(renamed, key=lambda c: seen[c]["area_id"]):
        for year, name in renamed[code]:
            lines.append(
                "| " + seen[code]["area_id"] + " | " + str(year) + " | " + name + " |"
            )
    RENAMES.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("yazildi:", RENAMES, len(renamed), "ad degisikligi")


if __name__ == "__main__":
    main()
