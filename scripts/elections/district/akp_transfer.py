"""Did AKP's 2015-2023 losses stay inside the right, or leave the bloc?

For every district: the change in AKP's share, the change in MHP + İYİ +
Yeniden Refah, and their sum. A sum near zero means the vote moved between
right-wing parties; a negative sum means the right lost that much overall.

Two ballot facts shape the comparison and are reported separately:
  * İYİ Parti and Yeniden Refah did not exist in 2015 (both start from zero).
  * Saadet fielded no list in 2023, so its 2015 vote has no 2023 counterpart;
    a wider definition of the non-AKP right that includes Saadet and BBP on both
    sides is printed as a robustness check.
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

DAR = ["MHP", "İYİ PARTİ", "YENİDEN REFAH"]
GENIS = DAR + [
    "SAADET PARTİSİ",
    "BBP",
    "BÜYÜK BİRLİK",
    "ZAFER PARTİSİ",
    "GENÇ PARTİ",
    "MİLLİ YOL",
    "AP",
    "ANAP",
    "DP",
    "MİLLET",
]


def satirlar(acc, kolonlar):
    rows = []
    ortak = {k for (y, k) in acc if y == d.Y1} & {k for (y, k) in acc if y == d.Y2}
    for k in ortak:
        akp1, akp2 = (
            d.pay(acc[(d.Y1, k)], ["AK PARTİ"]),
            d.pay(acc[(d.Y2, k)], ["AK PARTİ"]),
        )
        s1, s2 = d.pay(acc[(d.Y1, k)], kolonlar), d.pay(acc[(d.Y2, k)], kolonlar)
        if None in (akp1, akp2, s1, s2):
            continue
        rows.append(
            (
                k,
                akp2 - akp1,
                s2 - s1,
                (akp2 - akp1) + (s2 - s1),
                acc[(d.Y2, k)]["_gecerli"],
            )
        )
    return rows


def yaz(rows, baslik, n=12):
    rows = sorted(rows, key=lambda r: r[3])
    print(f"\n### {baslik}")
    print(f"{'':22}{'ΔAKP':>8}{'Δsağ':>8}{'net':>8}{'geçerli oy':>12}")
    print("  -- sağ bloğun en çok küçüldüğü --")
    for k, a, s, net, g in rows[:n]:
        print(f"  {k:20}{a:>+8.1f}{s:>+8.1f}{net:>+8.1f}{g:>12,}")
    print("  -- sağ bloğun en çok büyüdüğü --")
    for k, a, s, net, g in rows[-n:][::-1]:
        print(f"  {k:20}{a:>+8.1f}{s:>+8.1f}{net:>+8.1f}{g:>12,}")
    net = [r[3] for r in rows]
    print(
        f"  medyan net {statistics.median(net):+.1f} | "
        f"net > 0 olan {sum(1 for x in net if x > 0)}/{len(net)} | "
        f"ΔAKP ↔ Δsağ korelasyonu r = {statistics.correlation([r[1] for r in rows], [r[2] for r in rows]):+.2f}"
    )


def main():
    ilce, il, _ = d.topla()
    ulke = collections.defaultdict(collections.Counter)
    for (y, k), c in il.items():
        ulke[y].update(c)
    for ad, kol in (("MHP+İYİ+YRP", DAR), ("AKP dışı tüm sağ", GENIS)):
        a1, a2 = d.pay(ulke[d.Y1], ["AK PARTİ"]), d.pay(ulke[d.Y2], ["AK PARTİ"])
        s1, s2 = d.pay(ulke[d.Y1], kol), d.pay(ulke[d.Y2], kol)
        print(
            f"ÜLKE — {ad:18} AKP {a1:.1f}→{a2:.1f} ({a2 - a1:+.1f})   "
            f"sağ {s1:.1f}→{s2:.1f} ({s2 - s1:+.1f})   net {(a2 - a1) + (s2 - s1):+.1f}"
        )

    yaz(satirlar(il, DAR), "İL — AKP kaybı vs MHP+İYİ+YRP", n=10)
    yaz(satirlar(ilce, DAR), "İLÇE — AKP kaybı vs MHP+İYİ+YRP", n=12)
    yaz(
        satirlar(il, GENIS),
        "İL — AKP kaybı vs AKP dışı tüm sağ (Saadet, BBP dahil)",
        n=10,
    )

    with (BASE / "akp_transfer.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ilce", "d_akp", "d_mhp_iyi_yrp", "net", "gecerli_2023"])
        for r in sorted(satirlar(ilce, DAR), key=lambda r: r[3]):
            w.writerow([r[0], round(r[1], 2), round(r[2], 2), round(r[3], 2), r[4]])
    print("\n-> akp_transfer.csv")


if __name__ == "__main__":
    main()
