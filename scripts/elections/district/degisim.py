"""Where the left/right balance moved most between 1977 and 2023.

Provinces are compared on the 67 pre-1989 boundaries: the fourteen provinces
created after 1989 are folded back into the province they were carved from, so
both ends of the comparison cover the same territory.

Districts are compared from 1995 (the first election where every row carries a
real district name rather than "Merkez") and are matched on the district name;
province-centre rows are keyed to their province.
"""

import collections
import importlib.util
import pathlib
import re

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("blok", BASE / "blok.py")
blok = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blok)

# Provinces created after 1989 -> the province they were carved out of.
YENI_IL = {
    "aksaray": "nigde",
    "bayburt": "gumushane",
    "karaman": "konya",
    "kirikkale": "ankara",
    "batman": "siirt",
    "sirnak": "siirt",
    "bartin": "zonguldak",
    "ardahan": "kars",
    "igdir": "kars",
    "yalova": "istanbul",
    "karabuk": "zonguldak",
    "kilis": "gaziantep",
    "osmaniye": "adana",
    "duzce": "bolu",
}


def norm(t):
    t = blok.tr_lower(t)
    for a, b in zip("çğıöşü", "cgiosu"):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", t)


def eski_il(il):
    return YENI_IL.get(il, il)


def toplama():
    """(scope, year, key) -> Counter of bloc votes."""
    first, cells = blok.load()
    il_acc = collections.defaultdict(collections.Counter)
    ilce_acc = collections.defaultdict(collections.Counter)
    for (y, il, cevre, birim), v in cells.items():
        if birim == first[(y, cevre)] or blok.SKIP.search(blok.tr_lower(birim)):
            continue
        n = norm(birim)
        if n == norm(il):
            continue  # pre-1991 reports repeat the province total as a row
        ilce = norm(il) + "-merkez" if n == "merkez" or n.endswith("merkez") else n
        for col, x in v.items():
            if col in blok.AGG or "İTTİFAK" in col:
                continue
            b = blok.bloc_of(col, y)
            il_acc[(y, eski_il(il))][b] += x
            ilce_acc[(y, ilce)][b] += x
            if col in blok.KURT:
                il_acc[(y, eski_il(il))]["kurt"] += x
                ilce_acc[(y, ilce)]["kurt"] += x
    return il_acc, ilce_acc


def pay(t, kurtsuz=False):
    n = t["sol"] + t["sag"] + t["diger"]
    if n < 1000:
        return None
    sol = t["sol"] - (t["kurt"] if kurtsuz else 0)
    return 100 * sol / n


def tablo(acc, y1, y2, baslik, n=12, kurtsuz=False):
    ortak = {k for (y, k) in acc if y == y1} & {k for (y, k) in acc if y == y2}
    rows = []
    for k in ortak:
        a, b = pay(acc[(y1, k)], kurtsuz), pay(acc[(y2, k)], kurtsuz)
        if a is None or b is None:
            continue
        rows.append((k, a, b, b - a))
    rows.sort(key=lambda r: r[3])
    print(f"\n### {baslik}  ({len(rows)} birim)")
    print(f"{'':26}{'sol ' + y1:>10}{'sol ' + y2:>10}{'değişim':>10}")
    print("  -- sağa en çok kayanlar --")
    for k, a, b, d in rows[:n]:
        print(f"  {k:24}{a:>10.1f}{b:>10.1f}{d:>+10.1f}")
    print("  -- sola en çok kayanlar --")
    for k, a, b, d in rows[-n:][::-1]:
        print(f"  {k:24}{a:>10.1f}{b:>10.1f}{d:>+10.1f}")
    return rows


def sabitlik(acc, yillar, n=12, esik=8):
    """Units whose left share moved least across every election covered."""
    seri = collections.defaultdict(dict)
    for (y, k), t in acc.items():
        v = pay(t)
        if v is not None:
            seri[k][y] = v
    rows = []
    for k, d in seri.items():
        vals = [d[y] for y in yillar if y in d]
        if len(vals) < esik:
            continue
        rows.append(
            (
                k,
                len(vals),
                min(vals),
                max(vals),
                max(vals) - min(vals),
                sum(vals) / len(vals),
            )
        )
    rows.sort(key=lambda r: r[4])
    print()
    print("### EN SABİT — sol payının en dar aralıkta kaldığı yerler")
    print(
        f"{'':26}{'seçim':>7}{'en düşük':>10}{'en yüksek':>10}{'aralık':>8}{'ort':>7}"
    )
    for k, n_, lo, hi, rng, avg in rows[:n]:
        print(f"  {k:24}{n_:>7}{lo:>10.1f}{hi:>10.1f}{rng:>8.1f}{avg:>7.1f}")
    print("  -- en oynak --")
    for k, n_, lo, hi, rng, avg in rows[-n:][::-1]:
        print(f"  {k:24}{n_:>7}{lo:>10.1f}{hi:>10.1f}{rng:>8.1f}{avg:>7.1f}")


# 2007 and 2011 are left out of the volatility ranking: Kurdish politics ran on
# independent candidacies then, which lands in "diğer" and fakes a huge swing.
# 2023 is not used as an endpoint either: CHP fielded no list in seven provinces.
OYNAKLIK_YILLARI = [y for y in blok.YEARS if y not in ("2007", "2011")]


def main():
    il_acc, ilce_acc = toplama()
    tablo(il_acc, "1977", "2018", "İL — sol blok payı, 1977 → 2018 (67 tarihsel il)")
    tablo(
        il_acc,
        "1977",
        "2018",
        "İL — Kürt partileri hariç sol pay, 1977 → 2018",
        kurtsuz=True,
    )
    tablo(ilce_acc, "1995", "2018", "İLÇE — sol blok payı, 1995 → 2018", n=15)
    sabitlik(il_acc, OYNAKLIK_YILLARI, n=10, esik=15)
    sabitlik(ilce_acc, [y for y in OYNAKLIK_YILLARI if y >= "1995"], n=15, esik=7)


if __name__ == "__main__":
    main()
