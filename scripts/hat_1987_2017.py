"""How much of today's political map was already drawn in 1987.

The 1987 referendum asked one thing: should the political bans the junta imposed on the
old party leaders be lifted. It passed by 50.2 to 49.8 -- the closest national vote in
Turkish history, and for that reason the most informative: a question that splits the
country in half separates it along its real seam, while a 91 per cent vote separates
nothing.

This script asks whether that seam is still the seam, and how much of the answer is
1987's own rather than something later standing in for it:

* the plain correlation with 2017,
* the same correlation with 2010 held constant -- if 1987 only predicts 2017 because both
  resemble 2010, holding 2010 constant should collapse it,
* region by region, because a national correlation can be produced entirely by two blocs
  sitting at opposite ends while nothing inside either bloc lines up,
* and against the 2023 party vote, to see whether the seam is about a constitution or
  about who people vote for.

Run:  uv run python scripts/hat_1987_2017.py
"""

from __future__ import annotations

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TILES = ROOT / "public" / "tiles"

REGIONS = {
    "Marmara": "TR-10 TR-11 TR-14 TR-16 TR-17 TR-22 TR-34 TR-39 TR-41 TR-54 TR-59 TR-77 TR-81",
    "Ege": "TR-03 TR-09 TR-20 TR-35 TR-43 TR-45 TR-48 TR-64",
    "Akdeniz": "TR-01 TR-07 TR-15 TR-31 TR-32 TR-33 TR-46 TR-80",
    "İç Anadolu": "TR-06 TR-18 TR-26 TR-38 TR-40 TR-42 TR-50 TR-51 TR-58 TR-66 TR-68 TR-70 TR-71",
    "Karadeniz": "TR-05 TR-08 TR-19 TR-28 TR-29 TR-37 TR-52 TR-53 TR-55 TR-57 TR-60 TR-61 TR-67 TR-69 TR-74 TR-78",
    "Doğu": "TR-04 TR-12 TR-13 TR-23 TR-24 TR-25 TR-30 TR-36 TR-44 TR-49 TR-62 TR-65 TR-75 TR-76",
    "Güneydoğu": "TR-02 TR-21 TR-27 TR-47 TR-56 TR-63 TR-72 TR-73 TR-79",
}


def yes_share(vote: str) -> dict[str, tuple[float, int]]:
    path = TILES / f"secim-{vote}-ilce.json"
    out: dict[str, tuple[float, int]] = {}
    for area, row in json.loads(path.read_text(encoding="utf-8")).items():
        votes = row.get("v") or {}
        yes = sum(v for k, v in votes.items() if k.startswith("Evet"))
        no = sum(v for k, v in votes.items() if k.startswith("Hayır"))
        if yes + no >= 500:
            out[area] = (100 * yes / (yes + no), yes + no)
    return out


def party_share(vote: str, party: str) -> dict[str, tuple[float, int]]:
    path = TILES / f"secim-{vote}-ilce.json"
    out: dict[str, tuple[float, int]] = {}
    for area, row in json.loads(path.read_text(encoding="utf-8")).items():
        votes = row.get("v") or {}
        total = sum(votes.values())
        got = sum(v for k, v in votes.items() if party.casefold() in k.casefold())
        if total >= 500:
            out[area] = (100 * got / total, total)
    return out


def corr(pairs: list[tuple[float, float]]) -> float:
    n = len(pairs)
    if n < 3:
        return 0.0
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    top = sum((a - mx) * (b - my) for a, b in pairs)
    l = sum((a - mx) ** 2 for a, _ in pairs) ** 0.5
    r = sum((b - my) ** 2 for _, b in pairs) ** 0.5
    return top / (l * r) if l and r else 0.0


def partial(x: list[float], y: list[float], z: list[float]) -> float:
    """Correlation of x and y with z held constant."""
    rxy = corr(list(zip(x, y, strict=False)))
    rxz = corr(list(zip(x, z, strict=False)))
    ryz = corr(list(zip(y, z, strict=False)))
    bottom = ((1 - rxz**2) * (1 - ryz**2)) ** 0.5
    return (rxy - rxz * ryz) / bottom if bottom else 0.0


def province_names() -> dict[str, str]:
    out: dict[str, str] = {}
    path = ROOT / "src" / "veriatlas" / "data" / "areas_tr.csv"
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("area_level") == "province":
                out[row["area_id"]] = row["name_tr"]
    return out


def main() -> None:
    y87, y10, y17 = yes_share("ho1987"), yes_share("ho2010"), yes_share("ho2017")
    akp = party_share("mv2023", "AK PARTİ")
    chp = party_share("mv2023", "CHP")

    shared = sorted(set(y87) & set(y10) & set(y17))
    a = [y87[k][0] for k in shared]
    b = [y17[k][0] for k in shared]
    c = [y10[k][0] for k in shared]
    print(f"{len(shared)} ilçe (1987, 2010 ve 2017'de birden var)")
    print(f"  1987 -> 2017            r = {corr(list(zip(a, b, strict=False))):+.2f}")
    print(f"  1987 -> 2010            r = {corr(list(zip(a, c, strict=False))):+.2f}")
    print(f"  2010 -> 2017            r = {corr(list(zip(c, b, strict=False))):+.2f}")
    print(f"  1987 -> 2017 | 2010 sabit  r = {partial(a, b, c):+.2f}")

    print("\n2023 milletvekili oyu ile")
    for name, table in (("AK Parti", akp), ("CHP", chp)):
        common = sorted(set(y87) & set(table))
        pairs = [(y87[k][0], table[k][0]) for k in common]
        print(f"  1987 evet -> {name:<9} r = {corr(pairs):+.2f}  ({len(common)} ilçe)")

    print("\nBÖLGE BÖLGE (1987 -> 2017)")

    print(f"{'Bölge':<14}{'ilçe':>6}{'r':>8}{'1987 ort':>10}{'2017 ort':>10}")
    for region, plates in REGIONS.items():
        codes = set(plates.split())
        part = [k for k in shared if k[:5] in codes]
        if len(part) < 10:
            continue
        pairs = [(y87[k][0], y17[k][0]) for k in part]
        m87 = sum(p for p, _ in pairs) / len(pairs)
        m17 = sum(q for _, q in pairs) / len(pairs)
        print(f"{region:<14}{len(part):>6}{corr(pairs):>8.2f}{m87:>9.1f}%{m17:>9.1f}%")

    print("\n1987'DEKİ ONDALIKLARA GÖRE 2017")
    ranked = sorted(shared, key=lambda k: y87[k][0])
    step = max(1, len(ranked) // 10)
    print(f"{'1987 dilimi':<14}{'ilçe':>6}{'1987 ort':>10}{'2017 ort':>10}")
    for i in range(0, len(ranked), step):
        part = ranked[i : i + step]
        if len(part) < step // 2:
            continue
        m87 = sum(y87[k][0] for k in part) / len(part)
        m17 = sum(y17[k][0] for k in part) / len(part)
        print(f"{i // step + 1:>2}. dilim{'':<5}{len(part):>6}{m87:>9.1f}%{m17:>9.1f}%")


if __name__ == "__main__":
    main()
