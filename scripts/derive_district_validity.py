"""Fill district validity from what the yearly MEDAS exports actually contain.

Every year's district list *is* that year's administrative map. If a district is absent
in 2013 and present from 2014 on, it was created — we saw it happen. That is the
observation route K11 chose over hand-copying legislation, and it comes free with data
we already fetch.

The rule is deliberately timid, because the observation window has edges:

* A district present in the earliest year we hold gets **no** `valid_from`. It existed
  before we started looking; how long before, we do not know.
* A district present in the latest year gets **no** `valid_to`. It still exists.
* Only a district that appears late, or disappears early, gets a date — and `basis` says
  `observed`, never `legal`. The 6360 changes take effect at the 2014 local elections,
  so a district first seen in the 2014 file is consistent with that law, but this script
  records what it saw, not why.

What this cannot see is succession: a district split in two looks like "one kept its
name, one appeared". Linking them is a separate table and a separate decision.

Run:  uv run python scripts/derive_district_validity.py
"""

import csv
import sys
from collections import defaultdict

sys.path.insert(0, "src")

from veriatlas.adapters.tuik_district_population import DOWNLOADS, fold, read_export
from veriatlas.areas import DISTRICTS_PATH, load_areas, load_districts


def main() -> None:
    exports = sorted(DOWNLOADS.glob("nufus-ilce-*.csv"))
    if not exports:
        raise SystemExit("indirilmis yil yok: once scripts/fetch_medas_districts.py")

    provinces = {
        fold(row["name_tr"]): row["area_id"] for row in load_areas().to_dicts()
    }
    registry = load_districts().to_dicts()
    by_key = {(row["parent_id"], fold(row["name_tr"])): row for row in registry}

    seen: dict[tuple[str, str], set[int]] = defaultdict(set)
    codes: dict[tuple[str, str], str] = {}
    #: Districts the exports carry that today's boundary file does not: abolished centres
    #: (Antalya(Merkez), gone when the province became a metropolitan municipality) and
    #: renames (Ankara(Kazan) → Kahramankazan). They belong in the registry — the fact
    #: rows that reference them are real observations — with a `valid_to` and no geometry.
    gone: dict[tuple[str, str], dict] = {}

    for path in exports:
        for year, province, district, code, _ in read_export(path):
            parent = provinces.get(fold(province))
            if parent is None:
                continue

            key = (parent, fold(district))
            if key not in by_key and fold(district) == "merkez":
                key = (parent, fold(province))

            if key not in by_key:
                record = gone.setdefault(
                    (parent, code),
                    {
                        "parent_id": parent,
                        "name_tr": district,
                        "code": code,
                        "years": set(),
                    },
                )
                record["years"].add(year)
                continue

            seen[key].add(year)
            codes[key] = code

    observed = sorted({y for years in seen.values() for y in years})
    first_seen, last_seen = observed[0], observed[-1]
    print(
        "gozlem araligi:", first_seen, "-", last_seen, "|", len(exports), "yil dosyasi"
    )

    created: list[str] = []
    closed: list[str] = []

    for row in registry:
        key = (row["parent_id"], fold(row["name_tr"]))
        years = seen.get(key)
        row["medas_code"] = codes.get(key, "")

        if not years:
            # In the boundary file but in no export we hold: neither created nor closed
            # as far as we can tell, so nothing is claimed.
            row["valid_from"] = ""
            row["valid_to"] = ""
            row["basis"] = ""
            continue

        appears, disappears = min(years), max(years)
        row["valid_from"] = str(appears) if appears > first_seen else ""
        row["valid_to"] = str(disappears) if disappears < last_seen else ""
        row["basis"] = "observed" if (row["valid_from"] or row["valid_to"]) else ""

        if row["valid_from"]:
            created.append(
                row["name_tr"] + " (" + row["parent_id"] + ") " + row["valid_from"]
            )
        if row["valid_to"]:
            closed.append(
                row["name_tr"] + " (" + row["parent_id"] + ") " + row["valid_to"]
            )

    # Historical districts, keyed by MEDAS's own code so the id survives the rename that
    # removed the name. The "-x" marks an area with no geometry in today's file.
    for (parent, code), record in sorted(gone.items()):
        appears, disappears = min(record["years"]), max(record["years"])
        registry.append(
            {
                "area_id": parent + "-x" + code,
                "area_level": "district",
                "name_tr": record["name_tr"],
                "parent_id": parent,
                "valid_from": str(appears) if appears > first_seen else "",
                "valid_to": str(disappears) if disappears < last_seen else "",
                "basis": "observed",
                "source_id": "tuik_medas",
                "source_area_id": "",
                "medas_code": code,
            }
        )

    registry.sort(key=lambda row: row["area_id"])

    fields = [
        "area_id",
        "area_level",
        "name_tr",
        "parent_id",
        "valid_from",
        "valid_to",
        "basis",
        "source_id",
        "source_area_id",
        "medas_code",
    ]
    with DISTRICTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {field: row.get(field, "") for field in fields} for row in registry
        )

    print("kayit :", DISTRICTS_PATH, len(registry), "ilce")
    print("sonradan gorunen:", len(created))
    for line in created[:25]:
        print("   +", line)
    print("gorunmez olan:", len(closed))
    for line in closed[:25]:
        print("   -", line)

    print("bugun olmayan (tarihsel kayit):", len(gone))
    for (parent, _), record in sorted(gone.items())[:25]:
        print(
            "   ~",
            record["name_tr"],
            parent,
            min(record["years"]),
            "-",
            max(record["years"]),
        )


if __name__ == "__main__":
    main()
