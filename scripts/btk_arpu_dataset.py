"""Build a quarterly per-operator ARPU dataset, prepaid and postpaid, 2011-1 to 2026-1.

BTK publishes these only as chart labels ("Sekil 4-30 On Odemeli Mobil ARPU" and
"Sekil 4-31/4-32 Faturali Mobil ARPU"), and from the 2017 report on the charts
are images with no text layer, so every figure below was read off a rendered
page by eye. Each report shows a different window - three months in the 2010
report, eight quarters in most, sixteen in the 2019 one, five in the newest -
and the windows overlap, which is what makes the transcription checkable: where
two reports print the same quarter they agree, and REVISIONS lists the handful
of places they do not.

Coverage starts at 2011-1. Earlier than that only the 2010 report has anything,
and it reports three separate months rather than quarters, so it is left out.

BTK never publishes a sector total for either series, and the per-operator
prepaid/postpaid subscriber counts needed to weight one are not published
either, so no total is derived here.

Avea was renamed TT Mobil in 2016; it is one operator and one column throughout.
"""

import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "btk"
REF = ROOT / "raw" / "ref"
BASE = "2025-4"

OPERATORS = ("turkcell", "vodafone", "ttmobil")

# donem: (turkcell, vodafone, ttmobil/avea) in lira, and the report read from.
PREPAID = (
    ("2011-1", 9.80, 11.90, 10.90, "2012"),
    ("2011-2", 11.20, 13.30, 10.90, "2012"),
    ("2011-3", 12.16, 14.50, 11.15, "2012"),
    ("2011-4", 11.00, 12.03, 11.09, "2012"),
    ("2012-1", 10.13, 11.50, 10.92, "2013"),
    ("2012-2", 11.31, 12.70, 12.10, "2013"),
    ("2012-3", 12.56, 13.96, 13.03, "2013"),
    ("2012-4", 12.08, 13.47, 13.56, "2013"),
    ("2013-1", 11.46, 12.37, 12.88, "2013"),
    ("2013-2", 12.20, 13.99, 14.67, "2013"),
    ("2013-3", 12.33, 13.72, 13.33, "2013"),
    ("2013-4", 11.26, 12.94, 13.10, "2013"),
    ("2014-1", 10.7, 11.9, 12.7, "2015"),
    ("2014-2", 11.6, 12.6, 13.7, "2015"),
    ("2014-3", 12.2, 13.2, 14.7, "2015"),
    ("2014-4", 11.4, 13.0, 14.4, "2015"),
    ("2015-1", 11.0, 12.7, 14.0, "2015"),
    ("2015-2", 11.0, 13.8, 15.0, "2015"),
    ("2015-3", 13.3, 14.8, 15.8, "2015"),
    ("2015-4", 12.6, 14.3, 15.3, "2015"),
    ("2016-1", 12.1, 14.0, 15.3, "2019"),
    ("2016-2", 13.1, 14.5, 16.4, "2019"),
    ("2016-3", 14.5, 15.6, 16.8, "2019"),
    ("2016-4", 15.3, 15.1, 17.1, "2019"),
    ("2017-1", 14.3, 14.7, 16.9, "2019"),
    ("2017-2", 14.6, 15.6, 17.9, "2019"),
    ("2017-3", 15.7, 16.8, 18.4, "2019"),
    ("2017-4", 15.1, 16.2, 18.4, "2019"),
    ("2018-1", 14.9, 16.4, 18.5, "2020"),
    ("2018-2", 15.5, 17.5, 19.7, "2020"),
    ("2018-3", 18.4, 18.8, 20.0, "2020"),
    ("2018-4", 17.0, 18.2, 19.2, "2020"),
    ("2019-1", 16.8, 18.3, 19.6, "2020"),
    ("2019-2", 17.5, 19.5, 20.7, "2020"),
    ("2019-3", 19.1, 20.5, 21.3, "2020"),
    ("2019-4", 18.5, 19.4, 18.9, "2020"),
    ("2020-1", 19.6, 20.2, 20.6, "2020"),
    ("2020-2", 19.7, 20.6, 21.4, "2020"),
    ("2020-3", 23.8, 22.6, 24.2, "2020"),
    ("2020-4", 22.2, 22.2, 23.9, "2020"),
    ("2021-1", 22.2, 22.1, 23.1, "2022"),
    ("2021-2", 24.3, 23.3, 25.5, "2022"),
    ("2021-3", 28.3, 26.0, 28.2, "2022"),
    ("2021-4", 26.9, 25.3, 27.3, "2022"),
    ("2022-1", 27.8, 28.1, 28.2, "2022"),
    ("2022-2", 33.2, 33.6, 34.8, "2022"),
    ("2022-3", 43.4, 38.0, 42.6, "2022"),
    ("2022-4", 43.9, 41.3, 46.9, "2023"),
    ("2023-1", 52.1, 49.2, 54.4, "2023"),
    ("2023-2", 65.8, 58.5, 65.7, "2023"),
    ("2023-3", 83.5, 69.2, 82.6, "2023"),
    ("2023-4", 87.6, 80.7, 93.6, "2024"),
    ("2024-1", 97.1, 90.9, 109.6, "2024"),
    ("2024-2", 112.5, 106.5, 126.3, "2024"),
    ("2024-3", 140.4, 120.8, 134.4, "2024"),
    ("2024-4", 129.1, 119.6, 132.6, "2024"),
    ("2025-1", 133.2, 122.0, 141.4, "2026-Q1"),
    ("2025-2", 146.0, 138.4, 148.3, "2026-Q1"),
    ("2025-3", 173.8, 152.9, 161.1, "2026-Q1"),
    ("2025-4", 153.0, 139.3, 154.3, "2026-Q1"),
    ("2026-1", 162.7, 148.4, 166.5, "2026-Q1"),
)

POSTPAID = (
    ("2011-1", 37.90, 35.50, 30.20, "2012"),
    ("2011-2", 38.20, 37.00, 31.80, "2012"),
    ("2011-3", 40.40, 38.40, 32.56, "2012"),
    ("2011-4", 37.50, 37.56, 31.70, "2012"),
    ("2012-1", 36.52, 35.70, 30.60, "2013"),
    ("2012-2", 37.70, 37.16, 31.84, "2013"),
    ("2012-3", 38.38, 38.08, 32.65, "2013"),
    ("2012-4", 38.09, 37.43, 32.67, "2013"),
    ("2013-1", 36.44, 36.84, 32.66, "2013"),
    ("2013-2", 37.91, 37.87, 33.64, "2013"),
    ("2013-3", 38.47, 36.35, 31.92, "2013"),
    ("2013-4", 36.54, 36.23, 30.19, "2013"),
    ("2014-1", 36.0, 34.8, 29.2, "2015"),
    ("2014-2", 36.2, 35.4, 30.0, "2015"),
    ("2014-3", 38.5, 35.6, 30.6, "2015"),
    ("2014-4", 37.6, 35.1, 30.8, "2015"),
    ("2015-1", 36.7, 35.3, 30.1, "2015"),
    ("2015-2", 37.2, 36.4, 30.5, "2015"),
    ("2015-3", 39.1, 38.5, 31.8, "2015"),
    ("2015-4", 38.0, 38.7, 31.6, "2015"),
    ("2016-1", 37.2, 38.3, 32.0, "2019"),
    ("2016-2", 37.4, 38.8, 32.9, "2019"),
    ("2016-3", 39.2, 39.7, 33.7, "2019"),
    ("2016-4", 40.4, 39.8, 33.9, "2019"),
    ("2017-1", 40.5, 39.7, 34.9, "2019"),
    ("2017-2", 40.8, 40.7, 36.5, "2019"),
    ("2017-3", 43.5, 41.7, 36.7, "2019"),
    ("2017-4", 42.8, 41.2, 35.5, "2019"),
    ("2018-1", 44.0, 40.9, 35.7, "2020"),
    ("2018-2", 45.3, 41.6, 37.6, "2020"),
    ("2018-3", 47.8, 43.1, 39.5, "2020"),
    ("2018-4", 47.9, 42.4, 39.3, "2020"),
    ("2019-1", 49.4, 41.7, 38.2, "2020"),
    ("2019-2", 52.6, 43.6, 40.5, "2020"),
    ("2019-3", 58.4, 46.8, 42.7, "2020"),
    ("2019-4", 57.8, 46.3, 42.7, "2020"),
    ("2020-1", 55.3, 45.9, 40.0, "2020"),
    ("2020-2", 55.4, 47.2, 42.7, "2020"),
    ("2020-3", 59.3, 49.7, 44.3, "2020"),
    ("2020-4", 58.9, 50.0, 44.1, "2020"),
    ("2021-1", 57.1, 48.9, 43.5, "2022"),
    ("2021-2", 58.8, 50.9, 46.7, "2022"),
    ("2021-3", 62.3, 53.0, 48.6, "2022"),
    ("2021-4", 64.0, 54.6, 49.4, "2022"),
    ("2022-1", 64.9, 56.6, 49.9, "2022"),
    ("2022-2", 72.9, 62.3, 56.6, "2022"),
    ("2022-3", 86.0, 69.4, 65.2, "2022"),
    ("2022-4", 96.9, 77.7, 72.0, "2023"),
    ("2023-1", 105.9, 81.1, 78.1, "2023"),
    ("2023-2", 127.5, 102.9, 94.1, "2023"),
    ("2023-3", 154.3, 124.1, 110.8, "2023"),
    ("2023-4", 169.0, 141.9, 128.2, "2024"),
    ("2024-1", 193.1, 160.0, 146.5, "2024"),
    ("2024-2", 228.9, 196.3, 188.8, "2024"),
    ("2024-3", 253.4, 240.7, 212.1, "2024"),
    ("2024-4", 281.3, 262.5, 237.1, "2024"),
    ("2025-1", 317.9, 282.5, 259.1, "2026-Q1"),
    ("2025-2", 345.4, 310.2, 281.7, "2026-Q1"),
    ("2025-3", 371.4, 344.6, 287.7, "2026-Q1"),
    ("2025-4", 377.8, 345.4, 278.0, "2026-Q1"),
    ("2026-1", 401.1, 361.6, 283.2, "2026-Q1"),
)

# Quarters two reports both print but disagree on, kept as (tip, donem,
# operator) -> (older report value, newer value that is used here). Both were
# read back off the PDFs; the differences are at the second decimal.
REVISIONS = {
    ("on_odemeli", "2012-4", "turkcell"): (12.10, 12.08),
    ("faturali", "2012-4", "turkcell"): (38.10, 38.09),
}


def macro():
    with open(REF / "makro_ceyreklik.csv", encoding="utf-8") as fh:
        return {r["donem"]: r for r in csv.DictReader(fh)}


def num(row, key):
    v = row.get(key, "")
    return float(v) if v not in ("", None) else None


def build():
    fx = macro()
    base = fx[BASE]
    rows = []
    for tip, table in (("on_odemeli", PREPAID), ("faturali", POSTPAID)):
        for donem, *values in table:
            source = values[-1]
            m = fx[donem]
            for op, tl in zip(OPERATORS, values[:-1]):
                eur = tl / float(m["eur_try"])
                usd = tl / float(m["usd_try"])
                tr, us, ea = (num(m, k) for k in ("tufe_tr", "tufe_abd", "tufe_euro"))
                rows.append({
                    "donem": donem, "isletmeci": op, "tip": tip,
                    "tl": round(tl, 2),
                    "eur": round(eur, 2),
                    "usd": round(usd, 2),
                    # Constant BASE prices, each currency with its own deflator.
                    "tl_reel": (None if tr is None
                                else round(tl * float(base["tufe_tr"]) / tr, 2)),
                    "eur_reel": round(eur * float(base["tufe_euro"]) / ea, 2),
                    "usd_reel": round(usd * float(base["tufe_abd"]) / us, 2),
                    "kaynak_rapor": source,
                })
    return rows


def write(rows):
    out = RAW / "mobil_arpu_isletmeci.csv"
    fields = ("donem", "isletmeci", "tip", "tl", "eur", "usd",
              "tl_reel", "eur_reel", "usd_reel", "kaynak_rapor")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r[k] is None else r[k]) for k in fields})
    print(f"{out} yazildi ({len(rows)} satir)")


if __name__ == "__main__":
    write(build())
