"""Settle the suggested class of the former-municipality ("belde") settlements by size.

The user's rule (2026-10-01/02): a rural belde is a former belde whose group holds about 2,000
people or more; a smaller one is a village, and "kasaba" is no class. The automatic building
method still says "kasaba" for a separate patch of 2,000-5,000 and "kırsal belde" for any
former belde whatever its size, so the check table showed classes the user does not use
(Akalan, İnceler as "Kasaba", Dedebağı 1.618 as "Kırsal belde").

The group is the settlement the check table puts the unit in (`yer`): a belde with several
neighbourhoods is judged by the sum. A unit that is no former belde (its TÜİK status is
not "Belde") cannot be a rural belde, so it falls to village.

Run on an existing table:  python oneri_esik.py public/kentkir_kontrol.json
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

THRESHOLD = (
    1950  # "about 2,000": Akalan, 1,982 in 2025, is a rural belde by the user's call
)
CLASS_TR = {"kirsal_belde": "Kırsal belde (kır)", "kir": "Köy (kır)"}
SUGGESTED = {"kirsal_belde": "Kırsal Belde", "kir": "Köy"}


BELDE_NAME = re.compile(r"eski belde[^()]*\(([^()]*?) Bel\.")


def group_of(v: dict) -> tuple:
    """The belde a unit belongs to. The table's `yer` can fold two beldes into one (Yeşildere
    sat under Darıveren, 17 km away), so the municipality named in the building note, when
    there is one, decides."""
    note = f"{v.get('not') or ''} {v.get('bnote') or ''}"
    found = BELDE_NAME.search(note)
    return (v["il"], v["ilce"], found.group(1) if found else v["yer"])


def settle(rows: list[dict]) -> dict:
    """Rewrite oneri / os / sinif of the kasaba and kırsal belde rows; return the change counts."""
    total: dict[tuple, float] = defaultdict(float)
    for v in rows:
        if v["oneri"] in ("Kasaba (kır)", "Kırsal belde (kır)"):
            total[group_of(v)] += v["n"] or 0
    changes: dict[str, int] = defaultdict(int)
    for v in rows:
        if v["oneri"] not in ("Kasaba (kır)", "Kırsal belde (kır)"):
            continue
        former_belde = str(v["stat"]).startswith("Belde")
        big = total[group_of(v)] >= THRESHOLD
        new = "kirsal_belde" if former_belde and big else "kir"
        label = CLASS_TR[new]
        if label != v["oneri"]:
            changes[f"{v['oneri']} -> {label}"] += 1
        v["oneri"] = label
        v["os"] = SUGGESTED[new]
        v["sinif"] = new
    return dict(changes)


def main(path: str) -> None:
    file = Path(path)
    table = json.loads(file.read_text(encoding="utf-8"))
    keys = table["keys"]
    rows = [dict(zip(keys, r, strict=True)) for r in table["rows"]]
    changes = settle(rows)
    table["rows"] = [[v.get(k) for k in keys] for v in rows]
    file.write_text(
        json.dumps(table, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(changes)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
