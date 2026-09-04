"""How much of İYİ Parti's vote came out of MHP, district by district.

İYİ split from MHP in 2017, so the Nov-2015 MHP share is the baseline. Two
steps are measured:

  2015-Kas -> 2018   the split itself: MHP's fall against İYİ's first result
  2018 -> 2023       what happened afterwards

"net" is ΔMHP + ΔİYİ. Near zero means the vote moved between the two and stayed
inside; positive means the pair grew on top of the swap (drew from elsewhere);
negative means the pair shrank overall.

"takas payı" is the share of İYİ's vote that MHP's fall can account for,
min(-ΔMHP, ΔİYİ) / ΔİYİ — 100% is a pure swap.

Districts in provinces where either party fielded no list are dropped for the
step concerned, not read as a collapse to zero.
"""

import collections
import csv
import importlib.util
import pathlib
import statistics

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("degisim1523", BASE / "degisim1523.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
blok, dg = d.blok, d.dg

YILLAR = ["2015_1_kasim", "2018", "2023"]
AD = {"2015_1_kasim": "2015-Kas", "2018": "2018", "2023": "2023"}


def topla():
    first, cells = blok.load()
    ilce = collections.defaultdict(collections.Counter)
    nerede = {}
    liste = collections.defaultdict(
        collections.Counter
    )  # (year, province) -> party votes
    for (y, ilad, cevre, birim), v in cells.items():
        if (
            y not in YILLAR
            or birim == first[(y, cevre)]
            or blok.SKIP.search(blok.tr_lower(birim))
        ):
            continue
        n = dg.norm(birim)
        if n == dg.norm(ilad):
            continue
        key = dg.norm(ilad) + "-merkez" if n == "merkez" or n.endswith("merkez") else n
        nerede[key] = ilad
        for col, x in v.items():
            if col in blok.AGG or "İTTİFAK" in col:
                continue
            ilce[(y, key)][col] += x
            liste[(y, ilad)][col] += x
        ilce[(y, key)]["_gecerli"] += v.get("Geçerli oy sayısı", 0)
    return ilce, nerede, liste


def pay(c, parti):
    n = sum(v for k, v in c.items() if k != "_gecerli")
    return 100 * c.get(parti, 0) / n if n >= 1000 else None


def adim(ilce, nerede, liste, y1, y2, n=15):
    yok = {
        il
        for (y, il), c in liste.items()
        if y in (y1, y2)
        and (
            c.get("MHP", 0) == 0
            or (y == y2 and c.get("İYİ PARTİ", 0) == 0)
            or (y1 != "2015_1_kasim" and c.get("İYİ PARTİ", 0) == 0)
        )
    }
    rows = []
    ortak = {k for (y, k) in ilce if y == y1} & {k for (y, k) in ilce if y == y2}
    for k in ortak:
        if nerede.get(k) in yok:
            continue
        m1, m2 = pay(ilce[(y1, k)], "MHP"), pay(ilce[(y2, k)], "MHP")
        i1, i2 = pay(ilce[(y1, k)], "İYİ PARTİ"), pay(ilce[(y2, k)], "İYİ PARTİ")
        if None in (m1, m2, i1, i2):
            continue
        dm, di = m2 - m1, i2 - i1
        takas = 100 * min(-dm, di) / di if di > 0 and dm < 0 else 0.0
        rows.append(
            (
                k,
                m1,
                m2,
                i1,
                i2,
                dm,
                di,
                dm + di,
                takas,
                ilce[(y2, k)]["_gecerli"],
                nerede.get(k, ""),
            )
        )
    print(
        f"\n### {AD[y1]} → {AD[y2]}   ({len(rows)} ilçe; liste eksiği olan iller dışarıda)"
    )
    print(
        f"{'':20}{'MHP ' + AD[y1]:>10}{'MHP ' + AD[y2]:>10}"
        f"{'İYİ ' + AD[y2]:>10}{'ΔMHP':>8}{'ΔİYİ':>8}{'net':>7}{'takas%':>8}  il"
    )
    rows.sort(key=lambda r: r[5])  # ΔMHP en negatif
    print("  -- MHP'nin en çok düştüğü --")
    for r in rows[:n]:
        print(
            f"  {r[0]:18}{r[1]:>10.1f}{r[2]:>10.1f}{r[4]:>10.1f}"
            f"{r[5]:>+8.1f}{r[6]:>+8.1f}{r[7]:>+7.1f}{r[8]:>8.0f}  {r[10]}"
        )
    tam = [r for r in rows if r[5] < -5 and r[6] > 5]
    tam.sort(key=lambda r: (abs(r[7]), r[5]))
    print("  -- en 'temiz' takas (MHP düşüşü ≈ İYİ yükselişi, net≈0) --")
    for r in tam[:n]:
        print(
            f"  {r[0]:18}{r[1]:>10.1f}{r[2]:>10.1f}{r[4]:>10.1f}"
            f"{r[5]:>+8.1f}{r[6]:>+8.1f}{r[7]:>+7.1f}{r[8]:>8.0f}  {r[10]}"
        )
    net = [r[7] for r in rows]
    print(
        f"  medyan net {statistics.median(net):+.1f} | "
        f"ΔMHP ↔ ΔİYİ korelasyonu r = "
        f"{statistics.correlation([r[5] for r in rows], [r[6] for r in rows]):+.2f}"
    )
    return rows


def main():
    ilce, nerede, liste = topla()
    a = adim(ilce, nerede, liste, "2015_1_kasim", "2018")
    adim(ilce, nerede, liste, "2018", "2023")
    with (BASE / "mhp_iyi.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "ilce",
                "il",
                "mhp_2015k",
                "mhp_2018",
                "iyi_2018",
                "d_mhp",
                "d_iyi",
                "net",
                "takas_yuzde",
                "gecerli_2018",
            ]
        )
        for r in sorted(a, key=lambda r: r[5]):
            w.writerow(
                [
                    r[0],
                    r[10],
                    round(r[1], 2),
                    round(r[2], 2),
                    round(r[4], 2),
                    round(r[5], 2),
                    round(r[6], 2),
                    round(r[7], 2),
                    round(r[8]),
                    r[9],
                ]
            )
    print("\n-> mhp_iyi.csv")


if __name__ == "__main__":
    main()
