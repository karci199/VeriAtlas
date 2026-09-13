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

#: MEDAS writes a district under a name the boundary registry does not carry, the same
#: way it does for neighbourhoods (`build_neighbourhood_registry.ILCE_ADI`). Each of
#: these was confirmed from the export itself rather than from the name: the same MEDAS
#: village codes appear under both names -- Ilıca's 49 under Aziziye, Aydınlar's 6 under
#: Tillo, Çağlıyancerit's 9 under the spelling with an `a`. Two carry no overlap because
#: the villages stopped being villages when the province became metropolitan, so they
#: were followed into the neighbourhood registry instead: Ondokuzmayıs is written
#: `19 Mayıs` there, and Akköy's five villages are all Pamukkale neighbourhoods from
#: 2013 (Akçapınar, Belenardıç, Kavakbaşı, Yukarışamlı, Çeşmebaşı).
ILCE_ADI = {
    ("erzurum", "ilica"): "aziziye",
    ("siirt", "aydinlar"): "tillo",
    ("kahramanmaras", "cagliyancerit"): "caglayancerit",
    ("samsun", "ondokuzmayis"): "19mayis",
    ("denizli", "akkoy"): "pamukkale",
}


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
        adi = ILCE_ADI.get((fold(province), fold(district)), fold(district))
        found = districts.get((parent, adi))
        if found is not None:
            return found
        # MEDAS says "Merkez"; the boundary registry gives the central district the
        # province's own name.
        if fold(district) == "merkez":
            return districts.get((parent, fold(province)))
        return None

    seen: dict[str, dict] = {}
    parent_years: dict[str, dict[str, list[int]]] = {}
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

        # Every district the settlement was written under, with its years (K32): the
        # id follows the newest district so the series runs unbroken, and this keeps the
        # district it actually sat in — a closed one such as `TR-01-x1284` included.
        span = parent_years.setdefault(record.code, {}).setdefault(
            parent, [record.year, record.year]
        )
        span[0] = min(span[0], record.year)
        span[1] = max(span[1], record.year)

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
        # A settlement follows its district. When a district splits -- Derecik out of
        # Şemdinli in 2018, Kemalpaşa out of Hopa in 2017 -- MEDAS starts writing the new
        # district for the settlements that moved, but the parent was frozen at first
        # sighting, so they stayed under the old one and the district's own figure never
        # matched the sum of its settlements (Derecik held 1 of its 66). The newest year
        # names the district the same way it names the settlement.
        if record.year >= entry["last_seen"] and parent != entry["parent_id"]:
            entry["parent_id"] = parent
            entry["area_id"] = parent + "-" + record.code
        # The newest name wins, and the bucak survives the year MEDAS stopped writing it.
        if record.year >= entry["last_seen"]:
            entry["last_seen"] = record.year
            entry["name_tr"] = record.name
        if record.bucak:
            entry["bucak"] = record.bucak
        if record.name != history[record.code][-1][1]:
            history[record.code].append((record.year, record.name))

    for code, entry in seen.items():
        spans = sorted(parent_years[code].items(), key=lambda kv: kv[1][0])
        entry["parent_history"] = ";".join(
            parent + ":" + str(first) + ("" if first == last else "-" + str(last))
            for parent, (first, last) in spans
        )

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
