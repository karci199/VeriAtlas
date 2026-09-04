"""Party vote-share change between the Nov-2015 and 2023 general elections.

Parties are matched across the two ballots where a successor is unambiguous:
HDP -> Yeşil Sol Parti, and MHP is also reported combined with İYİ Parti, which
split from it in 2017 and did not exist in 2015.

CHP fielded no list in seven provinces in 2023 (Aksaray, Bayburt, Bitlis,
Çankırı, Gümüşhane, Muş, Yozgat); those are dropped from the CHP and left-bloc
comparisons rather than read as a collapse to zero.
"""

import collections
import importlib.util
import pathlib

BASE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("ortalama", BASE / "ortalama.py")
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
blok, dg = o.blok, o.dg

Y1, Y2 = "2015_1_kasim", "2023"
CHP_YOK = {"aksaray", "bayburt", "bitlis", "cankiri", "gumushane", "mus", "yozgat"}

GRUP = {
    "AK PARTİ": (["AK PARTİ"], ["AK PARTİ"]),
    "CHP": (["CHP"], ["CHP"]),
    "MHP": (["MHP"], ["MHP"]),
    "MHP+İYİ": (["MHP"], ["MHP", "İYİ PARTİ"]),
    "HDP→YSP": (["HDP"], ["YEŞİL SOL PARTİ"]),
}


def topla():
    first, cells = blok.load()
    ilce = collections.defaultdict(collections.Counter)
    il = collections.defaultdict(collections.Counter)
    nerede = {}
    for (y, ilad, cevre, birim), v in cells.items():
        if (
            y not in (Y1, Y2)
            or birim == first[(y, cevre)]
            or blok.SKIP.search(blok.tr_lower(birim))
        ):
            continue
        n = dg.norm(birim)
        if n == dg.norm(ilad):
            continue
        key = dg.norm(ilad) + "-merkez" if n == "merkez" or n.endswith("merkez") else n
        nerede[key] = ilad  # original province: CHP_YOK is defined on today's provinces
        for col, x in v.items():
            if col in blok.AGG or "İTTİFAK" in col:
                continue
            ilce[(y, key)][col] += x
            il[(y, dg.eski_il(ilad))][col] += x
        ilce[(y, key)]["_gecerli"] += v.get("Geçerli oy sayısı", 0)
        il[(y, dg.eski_il(ilad))]["_gecerli"] += v.get("Geçerli oy sayısı", 0)
    return ilce, il, nerede


def pay(c, kolonlar):
    n = sum(v for k, v in c.items() if k != "_gecerli")
    return 100 * sum(c.get(k, 0) for k in kolonlar) / n if n >= 1000 else None


def tablo(acc, ad, birim_adi, nerede=None, n=12):
    print(f"\n### {birim_adi} — {ad}: 2015-Kasım → 2023 (puan)")
    k1, k2 = GRUP[ad]
    rows = []
    for key in {k for (y, k) in acc if y == Y1} & {k for (y, k) in acc if y == Y2}:
        if ad == "CHP" and (nerede or {}).get(key, key) in CHP_YOK:
            continue
        a, b = pay(acc[(Y1, key)], k1), pay(acc[(Y2, key)], k2)
        if a is None or b is None:
            continue
        rows.append((key, a, b, b - a, acc[(Y2, key)]["_gecerli"]))
    rows.sort(key=lambda r: r[3])
    print(f"{'':22}{'2015-Kas':>10}{'2023':>8}{'değişim':>9}{'geçerli oy':>12}")
    print("  -- en çok DÜŞEN --")
    for k, a, b, d, g in rows[:n]:
        print(f"  {k:20}{a:>10.1f}{b:>8.1f}{d:>+9.1f}{g:>12,}")
    print("  -- en çok ARTAN --")
    for k, a, b, d, g in rows[-n:][::-1]:
        print(f"  {k:20}{a:>10.1f}{b:>8.1f}{d:>+9.1f}{g:>12,}")
    return rows


def main():
    ilce, il, nerede = topla()
    il_nerede = {k: k for (_, k) in il}
    for ad in GRUP:
        tablo(il, ad, "İL", il_nerede, n=10)
    for ad in GRUP:
        tablo(ilce, ad, "İLÇE", nerede, n=12)


if __name__ == "__main__":
    main()
