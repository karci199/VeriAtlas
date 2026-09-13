"""Hunt for shifted columns in the parsed election tables, using arithmetic that cannot lie.

A shifted column produces numbers, not errors, so it survives every check that only asks
whether a file parsed. What it cannot survive is the arithmetic the ballot itself imposes:

    oy kullanan <= kayitli secmen      more voters than registered is impossible
    gecerli     <= oy kullanan         more valid votes than voters is impossible
    parti toplami <= gecerli           parties cannot take more than the valid vote
    parti toplami >= gecerli * 0.9     and they should very nearly reach it

Each violation means a value was read from the wrong column. The counts below are of
districts, and a vote with a handful is a handful of bad rows; a vote with hundreds has a
structural fault and its numbers should not be used until it is found.

Run:  uv run python scripts/tile_denetim.py
      uv run python scripts/tile_denetim.py ho2007      # tek secim, ilceleri say
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TILES = ROOT / "public" / "tiles"


def check(row: dict) -> list[str]:
    registered = row.get("k", 0)
    voted = row.get("o", 0)
    valid = row.get("g", 0)
    party = sum((row.get("v") or {}).values())
    faults = []
    if registered and voted > registered:
        faults.append("oy>kayitli")
    if voted and valid > voted:
        faults.append("gecerli>oy")
    if valid and party > valid:
        faults.append("parti>gecerli")
    if valid and party and party < valid * 0.9:
        faults.append("parti<gecerli*0.9")
    return faults


def main(argv: list[str]) -> None:
    wanted = argv[0] if argv else None
    files = sorted(TILES.glob("secim-*-ilce.json"))
    print(f"{'Seçim':<22}{'ilçe':>7}{'kusurlu':>9}   en sık kusur")
    for path in files:
        vote = path.name[len("secim-") : -len("-ilce.json")]
        if wanted and vote != wanted:
            continue
        table = json.loads(path.read_text(encoding="utf-8"))
        tally: dict[str, int] = {}
        bad = 0
        examples: list[str] = []
        for area, row in table.items():
            faults = check(row)
            if not faults:
                continue
            bad += 1
            for fault in faults:
                tally[fault] = tally.get(fault, 0) + 1
            if len(examples) < 6:
                examples.append(f"{row.get('ad', area)}={','.join(faults)}")
        top = ", ".join(
            f"{k} {v}" for k, v in sorted(tally.items(), key=lambda x: -x[1])
        )
        mark = "  <<<" if bad > len(table) * 0.05 else ""
        print(f"{vote:<22}{len(table):>7}{bad:>9}   {top}{mark}")
        if wanted and examples:
            for line in examples:
                print(f"    {line}")


if __name__ == "__main__":
    main(sys.argv[1:])
