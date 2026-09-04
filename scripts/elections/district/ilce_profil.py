"""Turgutlu (Manisa) against Turkey, every election 1961-2023.

Turgutlu came top of the "most average place" ranking; this profiles it: how
closely its party mix tracked the country, whether it picked the national
winner, and how its electorate and turnout moved.
"""

import collections
import csv
import importlib.util
import pathlib

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("ortalama", BASE / "ortalama.py")
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
blok = o.blok

ILCE = __import__("sys").argv[1] if len(__import__("sys").argv) > 1 else "turgutlu"
IL_FILTRE = __import__("sys").argv[2] if len(__import__("sys").argv) > 2 else "manisa"
YEARS = [y for y in blok.YEARS]


def topla():
    """Votes and headline counts for Turgutlu, Manisa and Turkey."""
    first, cells = blok.load()
    t = collections.defaultdict(collections.Counter)
    man = collections.defaultdict(collections.Counter)
    tr = collections.defaultdict(collections.Counter)
    say = collections.defaultdict(collections.Counter)
    for (y, il, cevre, birim), v in cells.items():
        if birim == first[(y, cevre)] or blok.SKIP.search(blok.tr_lower(birim)):
            continue
        n = o.dg.norm(birim)
        if n == o.dg.norm(il):
            continue
        for col, x in v.items():
            if col in blok.AGG or "İTTİFAK" in col:
                continue
            tr[y][col] += x
            if il == IL_FILTRE:
                man[y][col] += x
            if n == ILCE:
                t[y][col] += x
        for col in blok.AGG:
            if col in v:
                say[(y, "tr")][col] += v[col]
                if n == ILCE:
                    say[(y, ILCE)][col] += v[col]
    return t, man, tr, say


def main():
    t, _man, tr, say = topla()
    rows = []
    print(
        f"{'seçim':10}{'kayıtlı':>9}{'katılım':>9}{'TR kat.':>9}"
        f"{'fark':>7}{'sol T':>7}{'sol TR':>7}{'1. parti':>24}{'  TR 1.':<12}"
    )
    for y in YEARS:
        if not t[y]:
            continue
        pt, ptr = o.paylar(t[y], False), o.paylar(tr[y], False)
        d = o.fark(pt, ptr)
        s_t = say[(y, ILCE)]
        s_tr = say[(y, "tr")]
        kat = 100 * s_t["Geçerli oy sayısı"] / s_t["Kayıtlı seçmen sayısı"]
        kat_tr = 100 * s_tr["Geçerli oy sayısı"] / s_tr["Kayıtlı seçmen sayısı"]
        sol_t = sum(v for k, v in t[y].items() if blok.bloc_of(k, y) == "sol")
        sol_tr = sum(v for k, v in tr[y].items() if blok.bloc_of(k, y) == "sol")
        n_t = sum(t[y].values())
        n_tr = sum(tr[y].values())
        b_t = max(pt, key=pt.get)
        b_tr = max(ptr, key=ptr.get)
        rows.append(
            {
                "secim": blok.LABEL.get(y, y),
                "fark": round(d, 1),
                "kayitli": s_t["Kayıtlı seçmen sayısı"],
                "katilim": round(kat, 1),
                "birinci": b_t,
                "tr_birinci": b_tr,
                "sol": round(100 * sol_t / n_t, 1),
                "sol_tr": round(100 * sol_tr / n_tr, 1),
            }
        )
        isaret = " " if b_t == b_tr else "✗"
        print(
            f"{blok.LABEL.get(y, y):10}{s_t['Kayıtlı seçmen sayısı']:>9,}{kat:>9.1f}{kat_tr:>9.1f}"
            f"{d:>7.1f}{100 * sol_t / n_t:>7.1f}{100 * sol_tr / n_tr:>7.1f}"
            f"{b_t + ' ' + format(pt[b_t], '.1f'):>24}  {b_tr} {ptr[b_tr]:.1f} {isaret}"
        )

    tut = sum(1 for r in rows if r["birinci"] == r["tr_birinci"])
    print(f"\nülkenin birincisini tutturma: {tut}/{len(rows)} seçim")

    print("\n### {ILCE} parti payları (%), Türkiye farkıyla")
    for y in ("1977", "1995", "2002", "2018", "2023"):
        pt, ptr = o.paylar(t[y], False), o.paylar(tr[y], False)
        buyuk = sorted(
            set(pt) | set(ptr), key=lambda k: -max(pt.get(k, 0), ptr.get(k, 0))
        )[:7]
        print(
            f"  {blok.LABEL.get(y, y):9} "
            + "  ".join(
                f"{k} {pt.get(k, 0):.1f}({pt.get(k, 0) - ptr.get(k, 0):+.1f})"
                for k in buyuk
            )
        )

    with (BASE / f"{ILCE}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\n-> turgutlu.csv")


if __name__ == "__main__":
    main()
