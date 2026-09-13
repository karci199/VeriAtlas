"""The same neighbourhood in two elections: how the vote moved between them.

Turkey votes twice for the same places within a year — a general election and a local one
— and the two are not the same vote. A neighbourhood that gives a party 55% for parliament
may give its mayor 35%, and the gap is not noise: it is the part of the vote that belongs
to the candidate rather than the party.

Both sides are read at settlement level and matched on the area id, so nothing is inferred
from names. Shares come from summed counts and every average is weighted by valid votes,
never by the number of settlements.

The pair must be comparable: comparing a mayoral race, which is not contested everywhere
by everyone, against a party-list election overstates movement where a party stood no
candidate. So a settlement is only counted when both elections have a real vote there, and
the count of dropped settlements is printed rather than hidden.

Run:  uv run python scripts/oy_kaymasi.py mv2023 yerel_bel_2024 [--n=15] [--min=1000]
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TILES = ROOT / "public" / "tiles"

ITTIFAK = "İTTİFAK"


def tablo(vote: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in TILES.glob(f"secim-{vote}-mahalle-TR-*.json"):
        for area, row in json.loads(path.read_text(encoding="utf-8")).items():
            if area.count("-") == 3:
                out[area] = row
    if not out:
        raise SystemExit(f"{vote}: mahalle dosyasi yok — once parse_secim.py {vote}")
    return out


def pay(row: dict, parti: str) -> float | None:
    v = {k: x for k, x in row.get("v", {}).items() if ITTIFAK not in k.upper()}
    toplam = sum(v.values())
    if toplam <= 0:
        return None
    return 100 * sum(x for k, x in v.items() if parti in k.upper()) / toplam


def main(argv: list[str]) -> None:
    args = [a for a in argv if not a.startswith("--")]
    onceki, sonraki = (args + ["mv2023", "yerel_bel_2024"])[:2]
    n = int(next((a.split("=")[1] for a in argv if a.startswith("--n=")), 15))
    floor = int(next((a.split("=")[1] for a in argv if a.startswith("--min=")), 1000))
    partiler = next(
        (a.split("=")[1] for a in argv if a.startswith("--parti=")), "AK PARTİ,CHP"
    ).split(",")

    a, b = tablo(onceki), tablo(sonraki)
    ortak = a.keys() & b.keys()
    print(f"{onceki} -> {sonraki}")
    print(f"ortak yerlesim: {len(ortak):,}  ({onceki}: {len(a):,} · {sonraki}: {len(b):,})")

    for parti in partiler:
        rows, atlanan = [], 0
        for area in ortak:
            if (a[area].get("k") or 0) < floor:
                continue
            p1, p2 = pay(a[area], parti), pay(b[area], parti)
            if p1 is None or p2 is None:
                atlanan += 1
                continue
            if p2 == 0 or p1 == 0:
                # No candidate is not a collapse. A party that stood nobody for mayor
                # reads as a fall from 55 to 0 and would fill the whole "biggest drop"
                # list with places where nothing happened. Counted, not compared.
                atlanan += 1
                continue
            g = sum(
                x for k, x in b[area].get("v", {}).items() if ITTIFAK not in k.upper()
            )
            rows.append((p2 - p1, a[area].get("ad", area), area, p1, p2, g))
        if not rows:
            print(f"\n{parti}: karsilastirilabilir yerlesim yok")
            continue
        agirlik = sum(r[5] for r in rows)
        ortalama = sum(r[0] * r[5] for r in rows) / agirlik
        print(f"\n=== {parti} · {len(rows):,} yerlesim · agirlikli kayma "
              f"{ortalama:+.1f} puan · aday yok/veri yok {atlanan:,} ===")
        rows.sort(reverse=True)
        print(f"  en cok ARTAN {n}:")
        for fark, ad, area, p1, p2, g in rows[:n]:
            print(f"    {ad[:22]:22} {area:16} {p1:5.1f} -> {p2:5.1f}  {fark:+6.1f}  "
                  f"{int(g):>7,} oy")
        print(f"  en cok DUSEN {n}:")
        for fark, ad, area, p1, p2, g in rows[-n:][::-1]:
            print(f"    {ad[:22]:22} {area:16} {p1:5.1f} -> {p2:5.1f}  {fark:+6.1f}  "
                  f"{int(g):>7,} oy")


if __name__ == "__main__":
    main(sys.argv[1:])
