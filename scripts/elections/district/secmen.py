"""Electorate and valid votes by province and district, 1961-2023.

Everything here is aggregated from the scraped district reports. The one figure
that is NOT from this dataset is the size of parliament: seat counts per
election are external, well-established numbers, marked as such, and are only
used for the national votes-per-seat line. Seats per province live in a
different TUIK table that starts in 1991, so a per-province votes-per-seat
series cannot be built back to 1961 from what we have.
"""

import collections
import csv
import importlib.util
import pathlib

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

# Size of the Grand National Assembly — external to this dataset.
SANDALYE = {
    "1961": 450,
    "1965": 450,
    "1969": 450,
    "1973": 450,
    "1977": 450,
    "1983": 400,
    "1987": 450,
    "1991": 450,
    "1995": 550,
    "1999": 550,
    "2002": 550,
    "2007": 550,
    "2011": 550,
    "2015_7_haziran": 550,
    "2015_1_kasim": 550,
    "2018": 600,
    "2023": 600,
}


def topla():
    first, cells = blok.load()
    il = collections.defaultdict(collections.Counter)
    ilce = collections.defaultdict(collections.Counter)
    for (y, ilad, cevre, birim), v in cells.items():
        if birim == first[(y, cevre)] or blok.SKIP.search(blok.tr_lower(birim)):
            continue
        n = dg.norm(birim)
        if n == dg.norm(ilad):
            continue
        key = dg.norm(ilad) + "-merkez" if n == "merkez" or n.endswith("merkez") else n
        for alan in (
            "Kayıtlı seçmen sayısı",
            "Oy kullanan seçmen sayısı",
            "Geçerli oy sayısı",
        ):
            if alan in v:
                il[(y, dg.eski_il(ilad))][alan] += v[alan]
                ilce[(y, key)][alan] += v[alan]
    return il, ilce


def main():
    il, ilce = topla()
    ulke = collections.defaultdict(collections.Counter)
    for (y, k), c in il.items():
        ulke[y].update(c)

    print("### ÜLKE — sandalye başına geçerli oy  (sandalye sayısı dış kaynak)")
    print(
        f"{'seçim':10}{'kayıtlı':>12}{'geçerli oy':>12}{'katılım':>8}"
        f"{'sandalye':>9}{'sandalye başına':>16}"
    )
    for y in YS:
        c = ulke[y]
        kay, gec = c["Kayıtlı seçmen sayısı"], c["Geçerli oy sayısı"]
        s = SANDALYE[y]
        print(
            f"{AD.get(y, y):10}{kay:>12,}{gec:>12,}{100 * gec / kay:>7.1f}%"
            f"{s:>9}{gec // s:>16,}"
        )

    print("\n### İL — kayıtlı seçmen ve geçerli oy (seçilmiş yıllar)")
    yillar = ["1961", "1977", "1991", "2002", "2023"]
    rows = sorted(
        {k for (_, k) in il}, key=lambda k: -il[("2023", k)]["Kayıtlı seçmen sayısı"]
    )
    print(f"  {'':16}" + "".join(f"{AD.get(y, y):>22}" for y in yillar))
    print(f"  {'':16}" + "".join(f"{'kayıtlı':>11}{'geçerli':>11}" for _ in yillar))
    for k in rows[:15]:
        s = f"  {k:16}"
        for y in yillar:
            c = il.get((y, k), {})
            s += f"{c.get('Kayıtlı seçmen sayısı', 0):>11,}{c.get('Geçerli oy sayısı', 0):>11,}"
        print(s)

    for ad, acc, dosya in (
        ("il", il, "secmen_il.csv"),
        ("ilce", ilce, "secmen_ilce.csv"),
    ):
        with (BASE / dosya).open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                [ad, "yil", "kayitli_secmen", "oy_kullanan", "gecerli_oy", "katilim"]
            )
            for y, k in sorted(acc, key=lambda t: (t[1], YS.index(t[0]))):
                c = acc[(y, k)]
                kay = c["Kayıtlı seçmen sayısı"]
                if not kay:
                    continue
                w.writerow(
                    [
                        k,
                        AD.get(y, y),
                        kay,
                        c["Oy kullanan seçmen sayısı"],
                        c["Geçerli oy sayısı"],
                        round(100 * c["Geçerli oy sayısı"] / kay, 2),
                    ]
                )
        print(f"-> {dosya}")


if __name__ == "__main__":
    main()
