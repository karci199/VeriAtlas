"""Winning party's vote share against valid votes, the electorate and population.

Election figures come from this repository's own scrape (secim_ilce.csv) and are
exact. Population figures do NOT: they are published TUIK census (1960-2000) and
ADNKS (2007+) totals, linearly interpolated to the election date, and are marked
approximate. The 18+ column is an estimate derived from those totals; the
measured voting-age count for each election is "kayitli secmen", whose legal age
threshold changed over time (21 until 1983, 20 in 1987-1991, 18 from 1995).
"""

import collections
import csv
import datetime as dt
import itertools
import pathlib

BASE = pathlib.Path(__file__).parent
AGG = {
    "Sandık sayısı",
    "Kayıtlı seçmen sayısı",
    "Oy kullanan seçmen sayısı",
    "Geçerli oy sayısı",
}
OLD = {"1961", "1965", "1969", "1973", "1977", "1983", "1987"}

# Election dates, and the legal voting age in force.
SECIM = [
    ("1961", dt.date(1961, 10, 15), 21),
    ("1965", dt.date(1965, 10, 10), 21),
    ("1969", dt.date(1969, 10, 12), 21),
    ("1973", dt.date(1973, 10, 14), 21),
    ("1977", dt.date(1977, 6, 5), 21),
    ("1983", dt.date(1983, 11, 6), 21),
    ("1987", dt.date(1987, 11, 29), 20),
    ("1991", dt.date(1991, 10, 20), 20),
    ("1995", dt.date(1995, 12, 24), 18),
    ("1999", dt.date(1999, 4, 18), 18),
    ("2002", dt.date(2002, 11, 3), 18),
    ("2007", dt.date(2007, 7, 22), 18),
    ("2011", dt.date(2011, 6, 12), 18),
    ("2015_7_haziran", dt.date(2015, 6, 7), 18),
    ("2015_1_kasim", dt.date(2015, 11, 1), 18),
    ("2018", dt.date(2018, 6, 24), 18),
    ("2023", dt.date(2023, 5, 14), 18),
]

# Published TUIK totals: censuses to 2000, ADNKS (31 December) from 2007.
# External to this dataset — treat as approximate.
NUFUS = {
    1960: 27_754_820,
    1965: 31_391_421,
    1970: 35_605_176,
    1975: 40_347_719,
    1980: 44_736_957,
    1985: 50_664_458,
    1990: 56_473_035,
    2000: 67_803_927,
    2007: 70_586_256,
    2011: 74_724_269,
    2015: 78_741_053,
    2018: 82_003_882,
    2023: 85_372_377,
}


def nufus(date):
    """Linear interpolation between the two nearest published totals."""
    years = sorted(NUFUS)
    t = date.year + (date.timetuple().tm_yday - 1) / 365.25
    if t <= years[0]:
        return NUFUS[years[0]]
    for a, b in itertools.pairwise(years):
        if t <= b:
            return NUFUS[a] + (NUFUS[b] - NUFUS[a]) * (t - a) / (b - a)
    return NUFUS[years[-1]]


def load():
    first, vals = {}, collections.defaultdict(dict)
    with open(BASE / "secim_ilce.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        k = (r["yil"], r["cevre"])
        first.setdefault(k, r["birim"])
        vals[(r["yil"], r["cevre"], r["birim"])][r["olcut"]] = int(r["deger"])
    return first, vals


def main():
    first, vals = load()
    rows = []
    for y, tarih, yas in SECIM:
        oy = collections.Counter()
        kay = gec = 0
        if y in OLD:
            v = next(vv for kk, vv in vals.items() if kk[0] == y and kk[2] == "Türkiye")
            kay, gec = v["Kayıtlı seçmen sayısı"], v["Geçerli oy sayısı"]
            for c, x in v.items():
                if c not in AGG:
                    oy[c] += x
        else:
            for k in (k for k in first if k[0] == y):
                v = vals[(k[0], k[1], first[k])]
                kay += v.get("Kayıtlı seçmen sayısı", 0)
                gec += v.get("Geçerli oy sayısı", 0)
                for c, x in v.items():
                    if c not in AGG and "İTTİFAK" not in c:
                        oy[c] += x
        parti, puan = oy.most_common(1)[0]
        n = nufus(tarih)
        rows.append(
            {
                "secim": y,
                "tarih": tarih.isoformat(),
                "parti": parti,
                "oy": puan,
                "gecerli_oy": gec,
                "kayitli_secmen": kay,
                "secme_yasi": yas,
                "nufus_yaklasik": round(n),
                "pay_gecerli": round(100 * puan / gec, 1),
                "pay_kayitli": round(100 * puan / kay, 1),
                "pay_nufus": round(100 * puan / n, 1),
                "kayitli_nufus_orani": round(100 * kay / n, 1),
            }
        )

    hdr = (
        f"{'seçim':15}{'parti':<11}{'kazanan oy':>12}{'/geçerli':>9}{'/kayıtlı':>9}"
        f"{'/nüfus':>8}{'yaş':>5}{'kayıtlı/nüfus':>14}{'nüfus~':>13}"
    )
    print(hdr)
    for r in rows:
        print(
            f"{r['secim']:15}{r['parti']:<11}{r['oy']:>12,}{r['pay_gecerli']:>8.1f}%"
            f"{r['pay_kayitli']:>8.1f}%{r['pay_nufus']:>7.1f}%{r['secme_yasi']:>5}"
            f"{r['kayitli_nufus_orani']:>13.1f}%{r['nufus_yaklasik']:>13,}"
        )

    dest = BASE / "kazanan_parti.csv"
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main()
