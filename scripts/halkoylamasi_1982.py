"""The 1982 referendum, read district by district — where the 91 per cent was not.

Held under military rule, with voting compulsory and campaigning against it a criminal
offence, the 1982 constitution passed with 91.4 per cent yes. A number produced under those
conditions says little on its own. What it can still say is **relative**: with the same
pressure everywhere, the places that dissented anyway are visible, and it can be asked
whether those places behaved consistently five years later.

The valence of "yes" is not the same in each of these votes, and reading them as one
series would be wrong:

    1961  yes = adopt the constitution written after the 1960 coup
    1982  yes = adopt the constitution written under the 1980 junta
    1987  yes = LIFT the political bans the junta imposed -- here yes is the
                anti-junta answer, the opposite way round from 1982
    2010  yes = amend the 1982 constitution
    2017  yes = the presidential system

So 1982-versus-1987 is the test of a consistent stance: a district that resisted in 1982
should be *high* in 1987, and the correlation between them should come out negative.

Run:  uv run python scripts/halkoylamasi_1982.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TILES = ROOT / "public" / "tiles"


def load(vote: str) -> dict[str, tuple[str, float, int]]:
    """{district id: (name, yes share, valid votes)}."""
    path = TILES / f"secim-{vote}-ilce.json"
    if not path.exists():
        raise SystemExit(f"{path} yok — once parse_secim.py {vote}")
    out: dict[str, tuple[str, float, int]] = {}
    for area, row in json.loads(path.read_text(encoding="utf-8")).items():
        votes = row.get("v") or {}
        yes = sum(v for k, v in votes.items() if k.startswith("Evet"))
        no = sum(v for k, v in votes.items() if k.startswith("Hayır"))
        if yes + no < 500:
            continue
        out[area] = (row.get("ad", area), 100 * yes / (yes + no), yes + no)
    return out


def correlation(pairs: list[tuple[float, float]]) -> float:
    n = len(pairs)
    if n < 3:
        return 0.0
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    top = sum((a - mx) * (b - my) for a, b in pairs)
    left = sum((a - mx) ** 2 for a, _ in pairs) ** 0.5
    right = sum((b - my) ** 2 for _, b in pairs) ** 0.5
    return top / (left * right) if left and right else 0.0


def province_view() -> None:
    """The 1987 and 2017 votes side by side, aggregated to provinces.

    Districts are summed into their province rather than averaged: a province is its
    voters, not its districts, and averaging would let a village of two thousand weigh as
    much as a city of three hundred thousand.
    """
    votes = {v: load(v) for v in ("ho1982", "ho1987", "ho2017")}
    names = province_names()
    rows = []
    for province in sorted({k[:5] for k in votes["ho1987"]}):
        line = []
        for vote in ("ho1982", "ho1987", "ho2017"):
            yes = total = 0.0
            for area, (_ad, share, count) in votes[vote].items():
                if area.startswith(province):
                    yes += share * count
                    total += count
            line.append(yes / total if total else None)
        if line[1] is None or line[2] is None:
            continue
        rows.append((line[1], line[2], line[0], names.get(province, province)))

    pairs = [(a, b) for a, b, *_ in rows]
    print(f"1987 evet (yasaklar kalksin) -> 2017 evet · {len(rows)} il")
    print(f"il duzeyinde r = {correlation(pairs):+.2f}")
    print()
    print(f"{'İl':<16}{'1982':>8}{'1987':>8}{'2017':>8}{'kalıntı':>10}")
    # The line itself, so a province can be placed against it rather than only ranked.
    n = len(pairs)
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    slope = sum((a - mx) * (b - my) for a, b in pairs) / sum(
        (a - mx) ** 2 for a, _ in pairs
    )
    scored = []
    for y87, y17, y82, name in rows:
        expected = my + slope * (y87 - mx)
        scored.append((y17 - expected, y82, y87, y17, name))
    scored.sort()
    for title, part in (
        (
            "HATTIN ALTINDA — 1987'e göre beklenenden çok daha az evet (2017)",
            scored[:12],
        ),
        ("HATTIN ÜSTÜNDE — beklenenden çok daha fazla evet", scored[-12:]),
    ):
        print()
        print(f"{title}")
        for residual, y82, y87, y17, name in part:
            y82text = f"{y82:>7.1f}%" if y82 is not None else f"{'—':>8}"
            print(f"{name:<16}{y82text}{y87:>7.1f}%{y17:>7.1f}%{residual:>+9.1f}")


def province_names() -> dict[str, str]:
    import csv

    out: dict[str, str] = {}
    path = ROOT / "src" / "veriatlas" / "data" / "areas_tr.csv"
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("area_level") == "province":
                out[row["area_id"]] = row["name_tr"]
    return out


def main() -> None:
    if "--il" in sys.argv[1:]:
        province_view()
        return
    votes = {v: load(v) for v in ("ho1961", "ho1982", "ho1987", "ho2010", "ho2017")}
    y82 = votes["ho1982"]
    total_yes = sum(s * n for _, s, n in y82.values()) / sum(
        n for *_, n in y82.values()
    )
    print(f"1982 · {len(y82)} ilçe · ülke geneli evet {total_yes:.1f}%")

    ranked = sorted((share, name, n, area) for area, (name, share, n) in y82.items())
    print("\nEN DÜŞÜK EVET — 1982")
    print(
        f"{'İlçe':<20}{'geçerli oy':>12}{'1982 evet':>11}{'1987 evet':>11}{'2017 evet':>11}"
    )
    for share, name, n, area in ranked[:20]:
        later = []
        for vote in ("ho1987", "ho2017"):
            row = votes[vote].get(area)
            later.append(f"{row[1]:>10.1f}%" if row else f"{'—':>11}")
        print(f"{name:<20}{n:>12,}{share:>10.1f}%" + "".join(later))

    print("\nEN YÜKSEK EVET — 1982")
    for share, name, n, area in ranked[-10:]:
        later = []
        for vote in ("ho1987", "ho2017"):
            row = votes[vote].get(area)
            later.append(f"{row[1]:>10.1f}%" if row else f"{'—':>11}")
        print(f"{name:<20}{n:>12,}{share:>10.1f}%" + "".join(later))

    print("\nİLİŞKİLER (ortak ilçeler üzerinden)")
    for a, b, note in (
        ("ho1982", "ho1987", "aynı duruş ise negatif beklenir"),
        ("ho1961", "ho1982", "iki darbe anayasası"),
        ("ho1982", "ho2010", ""),
        ("ho1982", "ho2017", ""),
        ("ho1987", "ho2017", ""),
    ):
        shared = [
            (votes[a][k][1], votes[b][k][1]) for k in votes[a].keys() & votes[b].keys()
        ]
        print(
            f"  {a} -> {b}: r = {correlation(shared):+.2f}  ({len(shared)} ilçe) {note}"
        )

    print("\nDAĞILIM — 1982")
    edges = [(0, 70), (70, 80), (80, 85), (85, 90), (90, 95), (95, 101)]
    for low, high in edges:
        part = [x for x in ranked if low <= x[0] < high]
        people = sum(x[2] for x in part)
        print(
            f"  %{low}-{high if high < 101 else 100}: {len(part):>3} ilçe, {people:>10,} oy"
        )


if __name__ == "__main__":
    sys.exit(main())
