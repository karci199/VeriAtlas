"""Build a tidy quarterly mobile-subscriber dataset from BTK quarterly market reports.

Operator totals come from figure "Mobil Isletmeci Bazinda Toplam Abone Sayilari".
The prepaid/postpaid split per operator is not published directly; the reports give
(a) the distribution of prepaid subscribers across operators and (b) the same for
postpaid. With operator totals known, the national prepaid volume P solves
    s_i * P + f_i * (T - P) = total_i     for each operator i
which is overdetermined (3 equations, 1 unknown) and is fitted by least squares.
"""

import csv
import pathlib

RAW = pathlib.Path(__file__).resolve().parents[1] / "raw" / "btk"
OPS = ("turkcell", "vodafone", "ttmobil")

# Distribution of prepaid subscribers across operators, % (figure 4-15).
# Integer-valued rows come from the 2019 report, which rounds them.
PREPAID_SHARE = {
    "2015-1": (47.7, 30.6, 21.7), "2015-2": (47.0, 31.2, 21.8),
    "2015-3": (46.7, 31.5, 21.8), "2015-4": (45.7, 31.9, 22.4),
    "2016-1": (44.2, 32.3, 23.5), "2016-2": (43.1, 32.9, 24.0),
    "2016-3": (42.9, 32.9, 24.2), "2016-4": (43.2, 32.7, 24.1),
    "2017-1": (43.0, 32.3, 24.0), "2017-2": (44.0, 32.0, 24.0),
    "2017-3": (44.0, 32.0, 24.0), "2017-4": (44.0, 32.0, 25.0),
    "2018-1": (45.0, 31.0, 24.0), "2018-2": (45.0, 30.0, 25.0),
    "2018-3": (45.0, 30.0, 25.0), "2018-4": (43.0, 30.0, 27.0),
    "2019-1": (43.7, 29.3, 27.0), "2019-2": (44.2, 29.0, 26.8),
    "2019-3": (44.0, 29.0, 27.0), "2019-4": (40.2, 29.7, 30.1),
    "2020-1": (40.1, 32.3, 30.2), "2020-2": (40.9, 30.0, 29.1),
    "2020-3": (40.9, 30.3, 28.8), "2020-4": (41.0, 29.0, 30.0),
    "2021-1": (41.5, 29.0, 29.6), "2021-2": (41.6, 29.2, 29.2),
    "2021-3": (42.3, 29.1, 28.6), "2021-4": (42.6, 27.3, 30.0),
    "2022-1": (43.0, 26.8, 30.2), "2022-2": (43.3, 26.6, 30.0),
    "2022-3": (43.5, 26.3, 30.2), "2022-4": (44.4, 32.3, 31.8),
    "2023-1": (44.2, 23.8, 32.0), "2023-2": (44.1, 24.3, 31.6),
    "2023-3": (44.5, 23.8, 31.6), "2023-4": (45.5, 22.3, 32.2),
    "2024-1": (45.6, 23.1, 31.3), "2024-2": (45.8, 23.5, 30.7),
    "2024-3": (45.3, 23.1, 31.6), "2024-4": (44.7, 22.0, 33.3),
    "2025-1": (44.8, 21.7, 33.6), "2025-2": (44.1, 22.1, 33.8),
    "2025-3": (43.4, 21.1, 35.4), "2025-4": (43.5, 20.4, 36.1),
}

# Distribution of postpaid subscribers across operators, % (figure 4-16).
POSTPAID_SHARE = {
    "2015-1": (47.4, 27.8, 24.8), "2015-2": (47.1, 28.1, 24.8),
    "2015-3": (46.8, 28.5, 24.7), "2015-4": (46.7, 28.7, 24.6),
    "2016-1": (46.1, 29.2, 24.7), "2016-2": (45.3, 29.7, 25.0),
    "2016-3": (45.0, 29.9, 25.1), "2016-4": (44.9, 29.8, 25.3),
    "2017-1": (45.0, 30.0, 25.0), "2017-2": (45.0, 30.0, 25.0),
    "2017-3": (45.0, 30.0, 25.0), "2017-4": (44.0, 31.0, 26.0),
    "2018-1": (43.0, 31.0, 26.0), "2018-2": (43.0, 31.0, 26.0),
    "2018-3": (42.0, 31.0, 26.0), "2018-4": (41.0, 32.0, 27.0),
    "2019-1": (40.1, 32.4, 27.5), "2019-2": (39.6, 32.5, 27.9),
    "2019-3": (39.8, 32.4, 27.8), "2019-4": (40.7, 31.9, 27.4),
    "2020-1": (41.0, 31.7, 27.2), "2020-2": (40.8, 31.9, 27.2),
    "2020-3": (40.6, 32.0, 27.4), "2020-4": (40.5, 32.2, 27.3),
    "2021-1": (40.4, 32.6, 27.0), "2021-2": (40.4, 32.8, 26.8),
    "2021-3": (40.4, 32.7, 26.9), "2021-4": (40.6, 32.5, 26.8),
    "2022-1": (40.6, 32.6, 26.8), "2022-2": (40.4, 32.8, 26.8),
    "2022-3": (40.3, 32.9, 26.8), "2022-4": (40.3, 32.9, 26.7),
    "2023-1": (40.2, 33.1, 26.7), "2023-2": (40.1, 33.3, 26.6),
    "2023-3": (39.9, 33.3, 26.8), "2023-4": (39.7, 33.2, 27.1),
    "2024-1": (39.7, 33.1, 27.2), "2024-2": (39.8, 32.8, 27.4),
    "2024-3": (39.6, 32.7, 27.6), "2024-4": (39.5, 32.7, 27.8),
    "2025-1": (39.1, 32.8, 28.2), "2025-2": (39.1, 32.4, 28.5),
    "2025-3": (38.4, 31.6, 30.0), "2025-4": (38.3, 31.0, 30.6),
}

# Reported prepaid share inside each operator, % (figure 4-14), fourth quarters only.
# Used to check the fitted split, never to produce it.
INTERNAL_PREPAID_Q4 = {
    "2011-4": (66.2, 68.1, 56.0), "2013-4": (60.2, 61.7, 55.0),
    "2015-4": (51.3, 54.5, 49.5), "2016-4": (47.5, 50.7, 47.2),
    "2019-4": (37.8, 36.4, 40.3), "2021-4": (33.6, 28.8, 35.0),
    "2023-4": (28.5, 18.9, 29.2), "2025-4": (19.3, 12.1, 19.9),
}


def read_totals():
    rows = {}
    with open(RAW / "mobil_abone_isletmeci.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows[r["donem"]] = (
                float(r["turkcell_milyon"]),
                float(r["vodafone_milyon"]),
                float(r["ttmobil_avea_milyon"]),
                float(r["toplam_milyon"]),
            )
    return rows


def fit_prepaid_total(totals, prepaid_share, postpaid_share):
    """Least-squares P for s_i*P + f_i*(T-P) = total_i."""
    t_all = totals[3]
    num = den = 0.0
    for i in range(3):
        s, f = prepaid_share[i] / 100, postpaid_share[i] / 100
        slope = s - f
        resid = totals[i] - f * t_all
        num += slope * resid
        den += slope * slope
    return num / den


def main():
    totals = read_totals()
    out = []
    for donem in sorted(totals):
        tc, vf, tt, tot = totals[donem]
        row = {
            "donem": donem,
            "turkcell_toplam": tc, "vodafone_toplam": vf, "ttmobil_toplam": tt,
            "toplam": tot,
        }
        if donem in PREPAID_SHARE:
            p_share = PREPAID_SHARE[donem]
            f_share = POSTPAID_SHARE[donem]
            p_total = fit_prepaid_total((tc, vf, tt, tot), p_share, f_share)
            row["on_odemeli_toplam"] = round(p_total, 3)
            row["faturali_toplam"] = round(tot - p_total, 3)
            for name, sp, sf in zip(OPS, p_share, f_share):
                row[f"{name}_on_odemeli"] = round(p_total * sp / 100, 3)
                row[f"{name}_faturali"] = round((tot - p_total) * sf / 100, 3)
                row[f"{name}_on_odemeli_pay"] = sp
                row[f"{name}_faturali_pay"] = sf
        out.append(row)

    cols = ["donem", "toplam", "on_odemeli_toplam", "faturali_toplam"]
    for name in OPS:
        cols += [f"{name}_toplam", f"{name}_on_odemeli", f"{name}_faturali",
                 f"{name}_on_odemeli_pay", f"{name}_faturali_pay"]
    dest = RAW / "mobil_abone_detay.csv"
    with open(dest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for row in out:
            w.writerow({c: row.get(c, "") for c in cols})

    print(f"{dest.name}: {len(out)} quarters")
    print("\ncheck: fitted vs reported prepaid share inside each operator (Q4)")
    print("donem     Turkcell     Vodafone     TT Mobil   (fitted / reported)")
    for donem, reported in INTERNAL_PREPAID_Q4.items():
        row = next((r for r in out if r["donem"] == donem), None)
        if not row or "turkcell_on_odemeli" not in row:
            continue
        parts = []
        for name, rep in zip(OPS, reported):
            fitted = 100 * row[f"{name}_on_odemeli"] / row[f"{name}_toplam"]
            parts.append(f"{fitted:5.1f}/{rep:5.1f}")
        print(f"{donem}  " + "  ".join(parts))


if __name__ == "__main__":
    main()
