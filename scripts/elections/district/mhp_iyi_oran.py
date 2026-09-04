"""Where the MHP/İYİ balance is most lopsided, 2023 (with 2018 alongside).

The ratio alone misleads when one party is tiny, so a district is only ranked
when the two together clear 5% of the valid vote and the district has at least
3000 valid votes. Provinces where either party fielded no list are dropped.
"""

import csv
import importlib.util
import pathlib

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("mhp_iyi", BASE / "mhp_iyi.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def satirlar(ilce, nerede, liste, yil, min_oy=3000, min_ikili=5.0):
    yok = {
        il
        for (y, il), c in liste.items()
        if y == yil and (c.get("MHP", 0) == 0 or c.get("İYİ PARTİ", 0) == 0)
    }
    rows = []
    for (y, k), c in ilce.items():
        if y != yil or nerede.get(k) in yok:
            continue
        n = sum(v for kk, v in c.items() if kk != "_gecerli")
        if n < min_oy:
            continue
        mhp, iyi = 100 * c.get("MHP", 0) / n, 100 * c.get("İYİ PARTİ", 0) / n
        if mhp + iyi < min_ikili:
            continue
        rows.append(
            {
                "ilce": k,
                "il": nerede.get(k, ""),
                "mhp": mhp,
                "iyi": iyi,
                "oran": mhp / iyi if iyi > 0.05 else float("inf"),
                "fark": mhp - iyi,
                "toplam": mhp + iyi,
                "gecerli": n,
            }
        )
    return rows


def yaz(rows, baslik, n=18):
    print(f"\n### {baslik}   ({len(rows)} ilçe)")
    print(f"  {'':20}{'MHP':>7}{'İYİ':>7}{'MHP/İYİ':>9}{'fark':>8}{'ikili':>7}  il")
    for r in rows[:n]:
        o = "∞" if r["oran"] == float("inf") else f"{r['oran']:.2f}"
        print(
            f"  {r['ilce']:20}{r['mhp']:>7.1f}{r['iyi']:>7.1f}{o:>9}"
            f"{r['fark']:>+8.1f}{r['toplam']:>7.1f}  {r['il']}"
        )


def main():
    ilce, nerede, liste = m.topla()
    for yil in ("2023", "2018"):
        rows = satirlar(ilce, nerede, liste, yil)
        yaz(sorted(rows, key=lambda r: -r["oran"]), f"{m.AD[yil]} — MHP ağır basan", 18)
        yaz(sorted(rows, key=lambda r: r["oran"]), f"{m.AD[yil]} — İYİ ağır basan", 18)
        if yil == "2023":
            with (BASE / "mhp_iyi_oran.csv").open(
                "w", newline="", encoding="utf-8"
            ) as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(sorted(rows, key=lambda r: -r["oran"]))
            print("\n-> mhp_iyi_oran.csv")


if __name__ == "__main__":
    main()
