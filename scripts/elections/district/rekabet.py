"""Places that have stayed competitive across every election, 1961-2023.

Competitiveness is the gap between the first and second party, not the winner's
share: a district can be fragmented and still one-sided. "Always competitive"
means the gap stayed small even in the place's most lopsided election, so the
ranking is on the worst gap, with the mean shown alongside.

Independents (BĞMZ) are pooled candidates rather than a party, so they are not
counted as a contender for the gap, though their votes stay in the denominator.
The same gap is also computed between the left and right blocs, which is the
better read on whether a place is genuinely contested.
"""

import collections
import csv
import importlib.util
import pathlib
import statistics

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("ortalama", BASE / "ortalama.py")
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
blok, dg = o.blok, o.dg

YS = [
    "1961",
    "1965",
    "1969",
    "1973",
    "1977",
    "1983",
    "1987",
    "1991",
    "1995",
    "1999",
    "2002",
    "2007",
    "2011",
    "2015_7_haziran",
    "2015_1_kasim",
    "2018",
    "2023",
]


def topla():
    first, cells = blok.load()
    ilce = collections.defaultdict(collections.Counter)
    il = collections.defaultdict(collections.Counter)
    for (y, ilad, cevre, birim), v in cells.items():
        if birim == first[(y, cevre)] or blok.SKIP.search(blok.tr_lower(birim)):
            continue
        n = dg.norm(birim)
        if n == dg.norm(ilad):
            continue
        key = dg.norm(ilad) + "-merkez" if n == "merkez" or n.endswith("merkez") else n
        for col, x in v.items():
            if col in blok.AGG or "İTTİFAK" in col:
                continue
            ilce[(y, key)][col] += x
            il[(y, dg.eski_il(ilad))][col] += x
    return ilce, il


def farklar(c, yil):
    """(gap between the top two parties, gap between the blocs) in points."""
    n = sum(c.values())
    if n < 3000:
        return None
    partiler = sorted((v for k, v in c.items() if k != "BĞMZ"), reverse=True)
    if len(partiler) < 2:
        return None
    sol = sum(v for k, v in c.items() if blok.bloc_of(k, yil) == "sol")
    sag = sum(v for k, v in c.items() if blok.bloc_of(k, yil) == "sag")
    return 100 * (partiler[0] - partiler[1]) / n, 100 * abs(sol - sag) / n


def sirala(acc, ad, n=15, min_secim=15):
    seri = collections.defaultdict(list)
    for (y, k), c in acc.items():
        f = farklar(c, y)
        if f:
            seri[k].append(f)
    rows = []
    for k, v in seri.items():
        if len(v) < min_secim:
            continue
        p = [x[0] for x in v]
        b = [x[1] for x in v]
        rows.append(
            (k, statistics.fmean(p), max(p), statistics.fmean(b), max(b), len(v))
        )

    for etiket, i_ort, i_max in (("PARTİ farkı", 1, 2), ("SOL/SAĞ blok farkı", 3, 4)):
        rows.sort(key=lambda r: r[i_max])
        print(f"\n### {ad} — her zaman rekabetçi ({etiket}; en kötü seçimine göre)")
        print(f"  {'':20}{'ort fark':>10}{'en kötü':>9}{'seçim':>7}")
        for r in rows[:n]:
            print(f"  {r[0]:20}{r[i_ort]:>10.1f}{r[i_max]:>9.1f}{r[5]:>7}")
    return rows


def main():
    ilce, il = topla()
    r = sirala(il, "İL", n=12)
    sirala(ilce, "İLÇE", n=15)
    with (BASE / "rekabet_il.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["il", "parti_ort", "parti_max", "blok_ort", "blok_max", "secim"])
        for x in sorted(r, key=lambda r: r[2]):
            w.writerow(
                [
                    x[0],
                    round(x[1], 2),
                    round(x[2], 2),
                    round(x[3], 2),
                    round(x[4], 2),
                    x[5],
                ]
            )
    print("\n-> rekabet_il.csv")


if __name__ == "__main__":
    main()
