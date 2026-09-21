"""Which province and district votes most like Turkey as a whole, 1961-2023.

A single left/right number is too coarse to call a place "average": two places
with the same left share can have completely different party mixes. Each unit is
therefore compared with the country on its full party vector, using the
dissimilarity index

    D = 0.5 * sum |share_unit(party) - share_country(party)|

which is the share of the vote that would have to move between parties to make
the unit look exactly like Turkey. D = 0 is a perfect match; D = 40 means two
fifths of the vote sits in the wrong place. Averaging D over elections finds the
place that has tracked the country, not the one that happens to match today.

Kurdish parties change the answer for the south-east, so every ranking is
reported twice: on the full ballot, and with Kurdish parties dropped from both
the unit and the country (renormalised), which asks how average a place is
"setting the Kurdish question aside".

2007 and 2011 are excluded: Kurdish politics ran on independent candidacies then
and lands in the same column as unrelated independents everywhere else.
"""

import collections
import csv
import importlib.util
import pathlib
import statistics

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("egilim", BASE / "egilim.py")
eg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eg)
dg, blok = eg.dg, eg.blok

ATLA = {"2007", "2011"}
YILLAR = [y for y in blok.YEARS if y not in ATLA]


def oylar():
    """(year, province) and (year, district) -> Counter of votes per party."""
    first, cells = blok.load()
    il = collections.defaultdict(collections.Counter)
    ilce = collections.defaultdict(collections.Counter)
    for (y, ilad, cevre, birim), v in cells.items():
        if (
            y in ATLA
            or birim == first[(y, cevre)]
            or blok.SKIP.search(blok.tr_lower(birim))
        ):
            continue
        n = dg.norm(birim)
        if n == dg.norm(ilad):
            continue
        key = dg.norm(ilad) + "-merkez" if n == "merkez" or n.endswith("merkez") else n
        for col, x in v.items():
            if col in blok.AGG or "İTTİFAK" in col:
                continue
            il[(y, dg.eski_il(ilad))][col] += x
            ilce[(y, key)][col] += x
    return il, ilce


def paylar(c, kurtsuz):
    t = {k: v for k, v in c.items() if not (kurtsuz and k in blok.KURT)}
    n = sum(t.values())
    return {k: 100 * v / n for k, v in t.items()} if n >= 1000 else None


def fark(a, b):
    return 0.5 * sum(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b))


def sirala(acc, baslik, kurtsuz, n=15, min_secim=13):
    ulke = collections.defaultdict(collections.Counter)
    for (y, k), c in acc.items():
        ulke[y].update(c)
    ref = {y: paylar(c, kurtsuz) for y, c in ulke.items()}

    seri = collections.defaultdict(dict)
    for (y, k), c in acc.items():
        p = paylar(c, kurtsuz)
        if p and ref.get(y):
            seri[k][y] = fark(p, ref[y])

    rows = []
    for k, d in seri.items():
        vals = [d[y] for y in YILLAR if y in d]
        if len(vals) < min_secim:
            continue
        rows.append((k, statistics.fmean(vals), max(vals), min(vals), len(vals)))
    rows.sort(key=lambda r: r[1])
    print(f"\n### {baslik}")
    print(f"{'':24}{'ort fark':>10}{'en kötü':>9}{'en iyi':>8}{'seçim':>7}")
    for k, ort, mx, mn, c in rows[:n]:
        print(f"  {k:22}{ort:>10.1f}{mx:>9.1f}{mn:>8.1f}{c:>7}")
    print("  ... en uzak: " + ", ".join(f"{k} {ort:.0f}" for k, ort, *_ in rows[-4:]))
    return rows


def main():
    il, ilce = oylar()
    a = sirala(il, "İL — Türkiye'ye en benzer (tüm partiler)", False)
    b = sirala(il, "İL — Kürt partileri hariç", True)
    c = sirala(
        ilce, "İLÇE — Türkiye'ye en benzer (tüm partiler)", False, n=20, min_secim=13
    )
    d = sirala(ilce, "İLÇE — Kürt partileri hariç", True, n=20, min_secim=13)

    # A place is only convincingly "average" if it ranks well on both readings.
    for ad, x, y in (("İL", a, b), ("İLÇE", c, d)):
        rx = {k: i for i, (k, *_) in enumerate(x)}
        ry = {k: i for i, (k, *_) in enumerate(y)}
        ortak = sorted(set(rx) & set(ry), key=lambda k: rx[k] + ry[k])
        print(f"\n### {ad} — iki okumada da en önde (sıra toplamı)")
        for k in ortak[:10]:
            print(f"  {k:22} tüm partiler #{rx[k] + 1:<4} kürtsüz #{ry[k] + 1}")

    with (BASE / "ortalama_il.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["il", "ort_fark_tum", "ort_fark_kurtsuz"])
        bb = {k: o for k, o, *_ in b}
        for k, o, *_ in a:
            w.writerow([k, round(o, 2), round(bb.get(k, float("nan")), 2)])
    print("\n-> ortalama_il.csv")


if __name__ == "__main__":
    main()
