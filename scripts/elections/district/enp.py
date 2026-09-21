"""Effective number of parties nationally, by province and by district.

ENP is the Laakso-Taagepera index, 1 / sum(share^2). Computed for the country,
for each province and for each district in every election since 1961.

The gap between the national figure and the average local one is the point of
interest: if the country is fragmented but each district is not, the parties are
regional rather than national. Independents (BĞMZ) are a pooled column, not a
party, so they are excluded and the shares renormalised.
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
AD = {"2015_7_haziran": "2015-Haz", "2015_1_kasim": "2015-Kas"}


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
            if col in blok.AGG or "İTTİFAK" in col or col == "BĞMZ":
                continue
            ilce[(y, key)][col] += x
            il[(y, dg.eski_il(ilad))][col] += x
    return ilce, il


def enp(c, min_oy=3000):
    n = sum(c.values())
    if n < min_oy:
        return None
    return 1 / sum((v / n) ** 2 for v in c.values())


def main():
    ilce, il = topla()
    ulke = collections.defaultdict(collections.Counter)
    for (y, k), c in il.items():
        ulke[y].update(c)

    print(
        f"{'seçim':10}{'ülke':>7}{'il ort':>8}{'ilçe ort':>10}{'ülke−ilçe':>11}"
        f"{'ilçe min':>10}{'ilçe max':>10}"
    )
    seri = {}
    for y in YS:
        u = enp(ulke[y])
        ils = [e for k, c in il.items() if k[0] == y and (e := enp(c))]
        ilcs = [e for k, c in ilce.items() if k[0] == y and (e := enp(c))]
        seri[y] = (u, statistics.fmean(ils), statistics.fmean(ilcs))
        print(
            f"{AD.get(y, y):10}{u:>7.2f}{statistics.fmean(ils):>8.2f}"
            f"{statistics.fmean(ilcs):>10.2f}{u - statistics.fmean(ilcs):>11.2f}"
            f"{min(ilcs):>10.2f}{max(ilcs):>10.2f}"
        )

    for ad, acc, n in (("İL", il, 12), ("İLÇE", ilce, 15)):
        d = collections.defaultdict(list)
        for (y, k), c in acc.items():
            e = enp(c)
            if e:
                d[k].append(e)
        rows = [
            (k, statistics.fmean(v), min(v), max(v), len(v))
            for k, v in d.items()
            if len(v) >= 15
        ]
        rows.sort(key=lambda r: -r[1])
        print(f"\n### {ad} — ortalama etkin parti sayısı en YÜKSEK")
        print(f"  {'':20}{'ort':>7}{'en az':>7}{'en çok':>8}{'seçim':>7}")
        for r in rows[:n]:
            print(f"  {r[0]:20}{r[1]:>7.2f}{r[2]:>7.2f}{r[3]:>8.2f}{r[4]:>7}")
        print(f"### {ad} — en DÜŞÜK")
        for r in rows[-n:][::-1]:
            print(f"  {r[0]:20}{r[1]:>7.2f}{r[2]:>7.2f}{r[3]:>8.2f}{r[4]:>7}")
        if ad == "İL":
            with (BASE / "enp_il.csv").open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["il"] + [AD.get(y, y) for y in YS])
                for k in sorted(d):
                    w.writerow(
                        [k]
                        + [
                            round(enp(acc[(y, k)]) or 0, 2) if (y, k) in acc else ""
                            for y in YS
                        ]
                    )
            print("\n-> enp_il.csv")


if __name__ == "__main__":
    main()
