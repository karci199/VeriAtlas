"""Iznik: party vote shares for urban, rural and district totals, by election.

Parties below a threshold in every column are folded into "Diğer" so each table
stays readable; alliance-seal votes are reported as their own line because they
are cast for the alliance, not for a party.
"""

import collections
import csv
import importlib.util
import pathlib

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("iznik", BASE / "iznik.py")
iz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iz)

ESIK = 1.5  # percent; below this in every column a party is folded into Diğer


def main():
    units, _ = iz.load()
    rows_out = []
    for y in iz.YEARS:
        rows = [(n, v) for (yy, n), v in units.items() if yy == y]
        groups = {
            "kent": [v for n, v in rows if iz.norm(n) in iz.URBAN],
            "kır": [v for n, v in rows if iz.norm(n) not in iz.URBAN],
        }
        groups["toplam"] = groups["kent"] + groups["kır"]

        votes = {g: collections.Counter() for g in groups}
        valid = {}
        for g, vs in groups.items():
            valid[g] = sum(v.get("gecerli_oy", 0) for v in vs)
            for v in vs:
                for col, val in v.items():
                    if col not in iz.AGG:
                        votes[g][col] += val

        share = {
            g: {c: 100 * x / valid[g] for c, x in votes[g].items()} for g in groups
        }
        parties = [c for c in votes["toplam"] if "İTTİFAK" not in c]
        big = [c for c in parties if max(share[g].get(c, 0) for g in groups) >= ESIK]
        big.sort(key=lambda c: -share["toplam"][c])
        small = [c for c in parties if c not in big]
        allies = [c for c in votes["toplam"] if "İTTİFAK" in c]

        print(
            f"\n=== {iz.LABEL.get(y, y)}   (geçerli oy: kent {valid['kent']:,} | "
            f"kır {valid['kır']:,} | toplam {valid['toplam']:,})"
        )
        print(f"{'parti':<22}{'kent':>8}{'kır':>8}{'toplam':>9}{'kent-kır':>10}")
        for c in big:
            k, r, t = (share[g].get(c, 0) for g in ("kent", "kır", "toplam"))
            print(f"{c:<22}{k:>8.1f}{r:>8.1f}{t:>9.1f}{k - r:>+10.1f}")
            rows_out.append(
                {
                    "yil": iz.LABEL.get(y, y),
                    "parti": c,
                    "kent": round(k, 2),
                    "kir": round(r, 2),
                    "toplam": round(t, 2),
                }
            )
        for label, cols in (("Diğer (<%1,5)", small), ("İttifak mührü", allies)):
            if not cols:
                continue
            k, r, t = (
                sum(share[g].get(c, 0) for c in cols) for g in ("kent", "kır", "toplam")
            )
            print(f"{label:<22}{k:>8.1f}{r:>8.1f}{t:>9.1f}{k - r:>+10.1f}")
            rows_out.append(
                {
                    "yil": iz.LABEL.get(y, y),
                    "parti": label,
                    "kent": round(k, 2),
                    "kir": round(r, 2),
                    "toplam": round(t, 2),
                }
            )

    dest = BASE / "iznik_parti_kent_kir.csv"
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["yil", "parti", "kent", "kir", "toplam"])
        w.writeheader()
        w.writerows(rows_out)
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main()
