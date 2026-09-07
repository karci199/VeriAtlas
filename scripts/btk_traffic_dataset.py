"""Build call-traffic datasets from the BTK quarterly market reports.

Three series, from three different kinds of source:

* ANNUAL - total call minutes split mobile/fixed, 2009-2025. This lives only in
  figure "Sekil 1-3", which is an image from the 2017 report on, so the bar
  labels were read off rendered pages: 2009-2012 from the 2019 report, 2013-2025
  from the 2026-Q1 report. The two charts overlap on 2013-2019 and agree on
  every value, which is the cross-check.

* TT_TRAFFIC - Turk Telekom's fixed voice traffic by destination, quarterly from
  2014-4. This one is a real table ("Cizelge 2-6"), so it comes from the text
  layer. Figures are rounded to whole million minutes in the source, so the
  reported total can miss the sum of its parts by one or two.

* MOBILE - total mobile traffic and its split between the three operators. The
  volume figure (Sekil 4-19) prints overlapping labels, so only the total is
  taken from it; operator volumes are derived from the clean share figure
  (Sekil 4-20). Only nine quarters are published.

Every quarter is taken from the newest report that still prints it.
"""

import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"

# yil: (mobil, sabit, toplam) in billion minutes, and the report read from.
ANNUAL = (
    (2009, 108.2, 23.9, 132.2, "2019"),
    (2010, 125.8, 23.6, 149.5, "2019"),
    (2011, 147.1, 21.8, 168.9, "2019"),
    (2012, 169.8, 19.4, 189.2, "2019"),
    (2013, 185.9, 16.7, 202.6, "2026-Q1"),
    (2014, 205.2, 14.0, 219.1, "2026-Q1"),
    (2015, 222.6, 11.3, 233.9, "2026-Q1"),
    (2016, 240.7, 9.2, 249.9, "2026-Q1"),
    (2017, 256.7, 7.6, 264.3, "2026-Q1"),
    (2018, 267.6, 6.7, 274.3, "2026-Q1"),
    (2019, 273.8, 6.3, 280.0, "2026-Q1"),
    (2020, 296.9, 5.7, 302.6, "2026-Q1"),
    (2021, 313.2, 5.2, 318.4, "2026-Q1"),
    (2022, 314.7, 4.9, 319.6, "2026-Q1"),
    (2023, 316.8, 4.6, 321.4, "2026-Q1"),
    (2024, 318.0, 5.1, 323.1, "2026-Q1"),
    (2025, 312.5, 5.1, 317.5, "2026-Q1"),
)

# donem: (on-net, to mobile, to STH, international, directory, reported total)
# in million minutes. The directory-enquiry row is only broken out 2016-2021.
TT_TRAFFIC = (
    ("2014-4", 1645, 523, 89, 46, None, 2303, "2015"),
    ("2015-1", 1501, 509, 92, 47, None, 2150, "2015"),
    ("2015-2", 1385, 531, 87, 49, None, 2052, "2015"),
    ("2015-3", 1165, 507, 82, 46, None, 1800, "2015"),
    ("2015-4", 1229, 519, 90, 44, None, 1881, "2016"),
    ("2016-1", 1015, 502, 85, 38, 3, 1643, "2016"),
    ("2016-2", 1042, 515, 79, 35, 3, 1675, "2016"),
    ("2016-3", 826, 458, 71, 31, 2, 1389, "2016"),
    ("2016-4", 896, 479, 82, 31, 2, 1491, "2017"),
    ("2017-1", 807, 458, 86, 29, 2, 1382, "2017"),
    ("2017-2", 735, 446, 81, 29, 2, 1292, "2017"),
    ("2017-3", 648, 435, 83, 26, 1, 1193, "2018"),
    ("2017-4", 654, 422, 86, 25, 1, 1189, "2018"),
    ("2018-1", 602, 396, 83, 23, 1, 1104, "2018"),
    ("2018-2", 567, 399, 76, 23, 1, 1065, "2018"),
    ("2018-3", 490, 389, 74, 20, 1, 975, "2018"),
    ("2018-4", 487, 383, 76, 20, 1, 966, "2019"),
    ("2019-1", 447, 365, 74, 18, 1, 905, "2019"),
    ("2019-2", 395, 350, 71, 18, 0.5, 835, "2019"),
    ("2019-3", 352, 346, 72, 16, 0.5, 787, "2019"),
    ("2019-4", 353, 338, 75, 16, 0.4, 782, "2020"),
    ("2020-1", 343, 331, 72, 15, 0.4, 761, "2020"),
    ("2020-2", 337, 368, 52, 13, 0, 769, "2020"),
    ("2020-3", 295, 359, 57, 13, 0, 724, "2020"),
    ("2020-4", 293, 360, 54, 12, 0, 718, "2021"),
    ("2021-1", 263, 333, 48, 11, 0, 655, "2021"),
    ("2021-2", 239, 331, 45, 10, 0, 625, "2021"),
    ("2021-3", 212, 327, 48, 9, 0, 598, "2021"),
    ("2021-4", 198, 323, 47, 9, 0, 578, "2022"),
    ("2022-1", 195, 313, 45, 9, None, 562, "2022"),
    ("2022-2", 174, 303, 42, 9, None, 528, "2022"),
    ("2022-3", 157, 300, 42, 8, None, 506, "2022"),
    ("2022-4", 118, 310, 41, 8, None, 475, "2023"),
    ("2023-1", 137, 307, 41, 7, None, 491, "2023"),
    ("2023-2", 130, 297, 39, 8, None, 474, "2023"),
    ("2023-3", 115, 305, 38, 8, None, 466, "2023"),
    ("2023-4", 110, 294, 34, 6, None, 444, "2024"),
    ("2024-1", 100, 289, 31, 5, None, 425, "2024"),
    ("2024-2", 90, 275, 29, 9, None, 399, "2024"),
    ("2024-3", 86, 300, 31, 5, None, 422, "2024"),
    ("2024-4", 82, 294, 30, 5, None, 410, "2025"),
    ("2025-1", 74, 283, 27, 5, None, 389, "2026-Q1"),
    ("2025-2", 68, 294, 26, 5, None, 393, "2026-Q1"),
    ("2025-3", 64, 303, 28, 5, None, 401, "2026-Q1"),
    ("2025-4", 62, 306, 26, 4, None, 399, "2026-Q1"),
    ("2026-1", 55, 282, 25, 4, None, 366, "2026-Q1"),
)

# donem: total mobile traffic in billion minutes (Sekil 4-19) and the operator
# shares in percent (Sekil 4-20), all from the 2026-Q1 report.
MOBILE = (
    ("2024-1", 76.7, 36.4, 34.7, 28.9),
    ("2024-2", 80.2, 36.5, 34.7, 28.8),
    ("2024-3", 83.2, 35.5, 36.2, 28.3),
    ("2024-4", 77.9, 35.9, 34.8, 29.3),
    ("2025-1", 73.9, 35.4, 34.7, 29.8),
    ("2025-2", 80.4, 35.5, 34.8, 29.8),
    ("2025-3", 81.3, 35.9, 34.0, 30.1),
    ("2025-4", 76.8, 35.5, 34.2, 30.3),
    ("2026-1", 71.8, 35.4, 34.3, 30.3),
)

TT_PARTS = ("sebeke_ici", "mobil", "sth", "uluslararasi", "rehberlik")


def build_annual():
    keys = ("yil", "mobil", "sabit", "toplam", "kaynak_rapor")
    rows = [dict(zip(keys, r)) for r in ANNUAL]
    for row in rows:
        row["mobil_pay"] = round(100 * row["mobil"] / row["toplam"], 1)
    return rows


def build_tt():
    keys = ("donem", *TT_PARTS, "toplam", "kaynak_rapor")
    rows = [dict(zip(keys, r)) for r in TT_TRAFFIC]
    for row in rows:
        row["bilesen_toplami"] = sum(row[k] or 0 for k in TT_PARTS)
    return rows


def build_mobile():
    keys = ("donem", "toplam", "turkcell_pay", "vodafone_pay", "ttmobil_pay")
    rows = [dict(zip(keys, r)) for r in MOBILE]
    for row in rows:
        # Operator volumes are not printed legibly; derive them from the shares.
        for op in ("turkcell", "vodafone", "ttmobil"):
            row[op] = round(row["toplam"] * row[op + "_pay"] / 100, 2)
    return rows


def write(name, rows, fieldnames):
    out = RAW / name
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if row[k] is None else row[k]) for k in fieldnames})
    print(f"{out} yazildi")


def main():
    write("trafik_yillik.csv", build_annual(),
          ("yil", "mobil", "sabit", "toplam", "mobil_pay", "kaynak_rapor"))
    write("tt_trafik_dagilimi.csv", build_tt(),
          ("donem", *TT_PARTS, "bilesen_toplami", "toplam", "kaynak_rapor"))
    write("mobil_trafik_isletmeci.csv", build_mobile(),
          ("donem", "toplam", "turkcell", "vodafone", "ttmobil",
           "turkcell_pay", "vodafone_pay", "ttmobil_pay"))


if __name__ == "__main__":
    main()
