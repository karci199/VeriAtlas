"""Does the settlement table add up to the district table? The check tile_denetim.py lacks.

tile_denetim.py asks whether a row is arithmetically possible. It cannot see a row that is
missing: a settlement the parser dropped leaves every remaining row valid and the district
total quietly larger than the sum of its settlements. That is how the 2017 referendum lost
9.5% of Bursa and Ankara (rows with a round turnout, "87", were skipped) and how 2015
Kahramankazan lost every settlement (the report says "Kazan", the registry's old code).

Two numbers per election and province:

    gap      registered voters in the district file minus the sum over its settlements
    unbound  votes in settlement rows whose key holds "~": the report named a settlement
             the map's index does not know, so it cannot be tied to a unit id

A gap is dropped rows; unbound is rows that kept their votes but lost their identity.
Either one biases any urban/rural split built on unit ids.

Run:  uv run python scripts/tile_toplam_denetim.py            # every election, worst first
      uv run python scripts/tile_toplam_denetim.py mv2015k 06 16   # one election, chosen provinces
"""

from __future__ import annotations

import glob
import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
TILES = ROOT / "public" / "tiles"
#: Elections whose settlement tables exist and are meant to add up. The 1989-2009
#: municipal ones are district-level by construction and would all read as gaps.
CHECKED = ("mv", "cb", "ho")


def province_gaps(vote: str, provinces: set[str] | None) -> list[tuple]:
    district = json.loads(
        (TILES / f"secim-{vote}-ilce.json").read_text(encoding="utf-8")
    )
    registered: dict[str, int] = defaultdict(int)
    for key, row in district.items():
        if not row.get("eski"):  # a copy drawn on a successor district, already counted
            registered[key[:5]] += row["k"]
    summed: dict[str, int] = defaultdict(int)
    unbound: dict[str, int] = defaultdict(int)
    for path in glob.glob(str(TILES / f"secim-{vote}-mahalle-TR-*.json")):
        code = "TR-" + path.rsplit("-", 1)[1][:2]
        if provinces and code[3:] not in provinces:
            continue
        for key, row in json.loads(
            pathlib.Path(path).read_text(encoding="utf-8")
        ).items():
            summed[code] += row["k"]
            if "~" in key:
                unbound[code] += row["g"]
    out = []
    for code, total in registered.items():
        if provinces and code[3:] not in provinces or not total or code not in summed:
            continue
        out.append((100 * (total - summed[code]) / total, code, unbound[code]))
    return sorted(out, reverse=True)


def main(argv: list[str]) -> None:
    votes = (
        [argv[0]]
        if argv
        else sorted(
            pathlib.Path(p).name[len("secim-") : -len("-ilce.json")]
            for p in glob.glob(str(TILES / "secim-*-ilce.json"))
            if pathlib.Path(p).name[len("secim-") :].startswith(CHECKED)
        )
    )
    provinces = set(argv[1:]) or None
    for vote in votes:
        rows = province_gaps(vote, provinces)
        worst = " ".join(f"{c}:{g:.1f}%" for g, c, _ in rows[:4])
        unbound = sum(u for _, _, u in rows)
        print(f"{vote:12} worst gaps  {worst}   unbound votes {unbound}")


if __name__ == "__main__":
    main(sys.argv[1:])
