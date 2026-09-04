"""Relative left lean by province and district, 1961-2023.

A place's raw left share mostly tracks the national swing: 1977 was the left's
best election anywhere, 2002 its worst, so comparing raw shares across eras
measures the country's mood rather than the place. Each unit is therefore
measured as its deviation from the national left share in the same election
("lean"), and compared across eras rather than between single elections.

Three data quirks are handled explicitly:
  * 2007 and 2011 - Kurdish politics ran on independent candidacies, which fall
    outside both blocs, so those elections are dropped.
  * 2023 - CHP fielded no list in seven provinces; those province-years are
    dropped rather than read as a collapse of the left.
  * Provinces created after 1989 are folded into the province they came from.
"""

import collections
import csv
import importlib.util
import pathlib
import statistics

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("degisim", BASE / "degisim.py")
dg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dg)
blok = dg.blok

ATLA_YIL = {"2007", "2011"}
DONEM = {
    "1961-77": ["1961", "1965", "1969", "1973", "1977"],
    "1983-95": ["1983", "1987", "1991", "1995"],
    "1999-23": ["1999", "2002", "2015_7_haziran", "2015_1_kasim", "2018", "2023"],
}


def chp_yok():
    """(year, cevre) pairs where CHP fielded no list while running nationally."""
    first, out = {}, set()
    with open(BASE / "secim_ilce.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        k = (r["yil"], r["cevre"])
        first.setdefault(k, r["birim"])
        if r["birim"] == first[k] and r["olcut"] == "CHP" and int(r["deger"]) == 0:
            out.add(k)
    return out


def seriler(kurtsuz=False):
    """(unit -> {year: lean}) for provinces and districts, plus national shares."""
    yok = {c for (y, c) in chp_yok() if y == "2023"}
    il_acc, ilce_acc = dg.toplama()
    ulke = collections.defaultdict(collections.Counter)
    for (y, k), t in il_acc.items():
        ulke[y].update(t)

    def pay(t):
        n = t["sol"] + t["sag"] + t["diger"]
        if n < 1000:
            return None
        return 100 * (t["sol"] - (t["kurt"] if kurtsuz else 0)) / n

    ref = {y: pay(t) for y, t in ulke.items()}
    out = {}
    for ad, acc in (("il", il_acc), ("ilce", ilce_acc)):
        seri = collections.defaultdict(dict)
        for (y, k), t in acc.items():
            if y in ATLA_YIL:
                continue
            if y == "2023" and ad == "il" and (k in yok or f"{k}_1" in yok):
                continue
            v = pay(t)
            if v is not None:
                seri[k][y] = v - ref[y]
        out[ad] = seri
    return out, ref


def donem_ort(seri, ad):
    vals = [seri[y] for y in DONEM[ad] if y in seri]
    return statistics.fmean(vals) if len(vals) >= max(2, len(DONEM[ad]) - 2) else None


def rapor(seri, baslik, n=14):
    rows = []
    for k, d in seri.items():
        a, b = donem_ort(d, "1961-77"), donem_ort(d, "1999-23")
        if a is None or b is None:
            continue
        vals = list(d.values())
        rows.append((k, a, b, b - a, statistics.pstdev(vals), len(vals)))
    print(f"\n### {baslik}   ({len(rows)} birim)")
    print(f"{'':24}{'1961-77':>9}{'1999-23':>9}{'kayma':>8}{'sapma':>7}{'seçim':>6}")
    rows.sort(key=lambda r: r[3])
    print("  -- ülkeye göre SAĞA kayanlar --")
    for k, a, b, d_, s, n_ in rows[:n]:
        print(f"  {k:22}{a:>+9.1f}{b:>+9.1f}{d_:>+8.1f}{s:>7.1f}{n_:>6}")
    print("  -- ülkeye göre SOLA kayanlar --")
    for k, a, b, d_, s, n_ in rows[-n:][::-1]:
        print(f"  {k:22}{a:>+9.1f}{b:>+9.1f}{d_:>+8.1f}{s:>7.1f}{n_:>6}")
    kal = sorted(rows, key=lambda r: abs(r[3]))
    print("  -- yerinde duranlar (kayma ~0, düşük sapma) --")
    for k, a, b, d_, s, n_ in sorted(kal[:40], key=lambda r: r[4])[:n]:
        print(f"  {k:22}{a:>+9.1f}{b:>+9.1f}{d_:>+8.1f}{s:>7.1f}{n_:>6}")
    return rows


def main():
    s, ref = seriler()
    print(
        "ülke sol payı:",
        {
            blok.LABEL.get(y, y): round(v, 1)
            for y, v in sorted(ref.items())
            if y not in ATLA_YIL
        },
    )
    rapor(s["il"], "İL — ülke ortalamasına göre sol eğilim")
    sk, _ = seriler(kurtsuz=True)
    rapor(sk["il"], "İL — Kürt partileri hariç, ülkeye göre sol eğilim")
    rapor(s["ilce"], "İLÇE — ülkeye göre sol eğilim", n=15)


if __name__ == "__main__":
    main()
