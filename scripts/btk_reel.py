"""Express BTK revenue and ARPU series in USD and in constant 2025 prices.

Nominal lira figures are meaningless across two decades of Turkish inflation, so
each series is restated three ways: divided by the annual average USD/TRY rate,
deflated by the Turkish CPI to 2025 lira, and deflated by the US CPI to 2025
dollars — current dollars are not a constant yardstick either, the dollar lost
about 40 percent of its purchasing power over this period.

Macro series: USD/TRY and Turkish CPI from the World Bank API, US CPI-U (CPIAUCNS)
from FRED. The 2025 US average covers 11 months; BLS published no October 2025
index during the government shutdown.
"""

import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
BASE_YEAR = 2025

# Fourth-quarter blended mobile ARPU, lira per month, as reported in each year's
# executive summary. Years without a clean reading are left out rather than guessed.
MOBILE_ARPU_Q4 = {
    2015: 24.5, 2016: 27.13, 2022: 70.4, 2023: 130.6, 2024: 230.2, 2025: 300.2,
}


def read(name, key="yil"):
    with open(RAW / name, encoding="utf-8") as fh:
        return {int(r[key]): r for r in csv.DictReader(fh)}


def main():
    macro = read("ref/makro.csv")
    revenue = read("btk/sektor_gelir.csv")
    fixed = read("btk/sabit_abone.csv")

    fx = {y: float(r["usd_try_ortalama"]) for y, r in macro.items()}
    cpi = {y: float(r["tufe_2010_100"]) for y, r in macro.items()}
    uscpi = {y: float(r["abd_tufe_1982_84_100"]) for y, r in macro.items()}
    deflate = lambda v, y: v * cpi[BASE_YEAR] / cpi[y]
    deflate_usd = lambda v, y: v * uscpi[BASE_YEAR] / uscpi[y]

    out = []
    for y in sorted(revenue):
        r = revenue[y]
        row = {"yil": y, "usd_try": fx[y], "tufe": cpi[y], "abd_tufe": uscpi[y]}
        for src, label in (("buyuk4_gelir_tl", "buyuk4"), ("sektor_gelir_tl", "sektor")):
            if not r[src]:
                continue
            tl = float(r[src])
            row[label + "_tl"] = tl
            row[label + "_usd"] = tl / fx[y]
            row[label + "_tl_2025"] = deflate(tl, y)
            row[label + "_usd_2025"] = deflate_usd(tl / fx[y], y)
        out.append(row)

    cols = ["yil", "usd_try", "tufe", "abd_tufe",
            "buyuk4_tl", "buyuk4_usd", "buyuk4_tl_2025", "buyuk4_usd_2025",
            "sektor_tl", "sektor_usd", "sektor_tl_2025", "sektor_usd_2025"]
    dest = RAW / "btk" / "sektor_gelir_reel.csv"
    with open(dest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for row in out:
            w.writerow({c: (round(row[c], 4) if isinstance(row.get(c), float) else row.get(c, ""))
                        for c in cols})

    def block(title, prefix):
        print(title)
        print("yil   nominal mlr TL   cari mlr $   2025 fiyat. mlr TL   2025 dolariyla mlr $")
        for row in out:
            if prefix + "_tl" not in row:
                continue
            print(f"{row['yil']} {row[prefix+'_tl']/1e9:13.1f} {row[prefix+'_usd']/1e9:12.2f}"
                  f" {row[prefix+'_tl_2025']/1e9:18.1f} {row[prefix+'_usd_2025']/1e9:20.2f}")

    block("BUYUK 4 ISLETMECI GELIRI", "buyuk4")
    print()
    block("TUM SEKTOR", "sektor")

    print("\nSABIT TELEFON ABONESI")
    print("yil    abone (mn)   yillik degisim")
    prev = None
    for y in sorted(fixed):
        v = int(fixed[y]["sabit_abone"])
        chg = f"{100*(v/prev-1):+6.1f}%" if prev else "     -"
        print(f"{y}  {v/1e6:10.2f}   {chg}")
        prev = v

    print("\nMOBIL ARPU (4. ceyrek)")
    print("yil       TL/ay   cari $/ay   2025 TL/ay   2025 dolariyla $/ay")
    for y in sorted(MOBILE_ARPU_Q4):
        a = MOBILE_ARPU_Q4[y]
        print(f"{y}  {a:9.2f} {a/fx[y]:11.2f} {deflate(a, y):12.2f}"
              f" {deflate_usd(a/fx[y], y):20.2f}")


if __name__ == "__main__":
    main()
