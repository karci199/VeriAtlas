"""Kalecik (Ankara) at settlement level, 1991-2023.

The urban/rural line is taken from the data rather than a hand-written list: a
settlement counts as rural if any pre-2012 report labelled it "Köyü". After the
2012 metropolitan law every settlement is labelled "Mah.", so that earlier
labelling is the only record of which places were villages.

Aggregate captions are matched exactly, because the same caption ("Belde/Köy",
"İl/İlçe merkezi") also appears at province level inside the same report and
would otherwise be added in.
"""

import collections
import csv
import pathlib
import re

BASE = pathlib.Path(__file__).parent
ILCE = "kalecik"
AGG = {"sandik", "kayitli_secmen", "oy_kullanan", "gecerli_oy"}
YS = ["1991", "1995", "1999", "2002", "2007", "2011", "2015h", "2015k", "2018", "2023"]
LAB = {"2015h": "2015-Haz", "2015k": "2015-Kas"}
SOL = {
    "CHP",
    "SHP",
    "DSP",
    "HADEP",
    "DEHAP",
    "HDP",
    "YEŞİL SOL PARTİ",
    "SOL PARTİ",
    "ÖDP",
    "EMEP",
    "TKP",
    "TKH",
    "TİP",
    "HKP",
    "SP",
    "KP",
    "İP",
    "VATAN PARTİSİ",
    "MEMLEKET",
    "YTP",
}
TOPLAM = re.compile(r"toplam|merkez|belde|bucak|cezaevi|ankara", re.IGNORECASE)


def norm(t):
    """Settlement key: the same place is written "X Köyü" before 2012 and
    "X Mah." after, so the type suffix is stripped."""
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("çğıöşü", "cgiosu"):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]", "", t)
    return re.sub(r"(mahallesi|mah|koyu|koy)$", "", t)


# The town's neighbourhoods are reported in merged pairs ("Ahikemal-Şenyurt",
# "Cuma-Saray", …) except in 2007, which lists them singly. Karahöyük, Gölköy,
# Hasayaz, Çandır and Arkbürk are separate settlements that only ever appear as
# "Mah.", so they cannot be told from town neighbourhoods by suffix alone and
# are named here explicitly.
MERKEZ = {
    "ahikemalsenyurt",
    "ahikemal",
    "cumasaray",
    "cuma",
    "yenidoganyesilyurt",
    "yenidogan",
    "yesildoganyesilyurt",
    "halilagatabakhane",
    "halilaga",
    "ahileryenice",
    "ahiler",
    "cansakale",
    "cansaemeklikent",
    "halitcevriaslangil",
    "tavsanli",
}


def load():
    hucre = collections.defaultdict(dict)
    koy = set()
    with open(BASE / "secim_mahalle.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        if r["ilce"] != ILCE:
            continue
        b = r["birim"]
        if TOPLAM.search(b) or norm(b) == ILCE:
            continue
        if "Köyü" in b:
            koy.add(norm(b))
        hucre[(r["yil"], norm(b))][r["olcut"]] = int(r["deger"])
    return hucre, koy


def sol_pay(c):
    n = sum(v for k, v in c.items() if k not in AGG and "İTTİFAK" not in k)
    s = sum(v for k, v in c.items() if k in SOL)
    return 100 * s / n if n else None


def main():
    hucre, koy = load()
    yer = {k for (_, k) in hucre}
    kent = yer & MERKEZ
    disarida = yer - koy - MERKEZ
    if disarida:
        print(
            "kasaba dışı sayılan, köy etiketi hiç görülmemiş birimler:",
            ", ".join(sorted(disarida)),
        )
    koy = yer - kent
    print(f"yerleşim: {len(yer)}  (köy {len(koy)}, kasaba mahallesi {len(kent)})")
    print(f"kasaba mahalleleri: {', '.join(sorted(kent))}\n")

    print(
        f"{'seçim':10}{'ilçe':>9}{'kasaba':>9}{'köyler':>9}{'kasaba%':>9}"
        f"{'sol kasaba':>12}{'sol köy':>9}"
    )
    seri = []
    for y in YS:

        def topla(grup, alan, y=y):
            return sum(hucre.get((y, k), {}).get(alan, 0) for k in grup)

        k_kay, v_kay = topla(kent, "kayitli_secmen"), topla(koy, "kayitli_secmen")
        if not k_kay:
            continue
        ck = collections.Counter()
        cv = collections.Counter()
        for k in kent:
            ck.update(hucre.get((y, k), {}))
        for k in koy:
            cv.update(hucre.get((y, k), {}))
        sk, sv = sol_pay(ck), sol_pay(cv)
        seri.append((y, k_kay, v_kay, sk, sv))
        print(
            f"{LAB.get(y, y):10}{k_kay + v_kay:>9,}{k_kay:>9,}{v_kay:>9,}"
            f"{100 * k_kay / (k_kay + v_kay):>8.1f}%{sk:>12.1f}{sv:>9.1f}"
        )

    print("\n### köyler — kayıtlı seçmen, 1991 → 2023")
    rows = []
    for k in sorted(koy):
        a = hucre.get(("1991", k), {}).get("kayitli_secmen")
        b = hucre.get(("2023", k), {}).get("kayitli_secmen")
        if a and b:
            rows.append((k, a, b, 100 * b / a))
    rows.sort(key=lambda r: r[3])
    print(f"  {'':20}{'1991':>7}{'2023':>7}{'kalan%':>8}")
    for k, a, b, p in rows[:12]:
        print(f"  {k:20}{a:>7,}{b:>7,}{p:>7.0f}%")
    print("  ...")
    for k, a, b, p in rows[-5:]:
        print(f"  {k:20}{a:>7,}{b:>7,}{p:>7.0f}%")
    print(
        f"  köy toplamı: {sum(r[1] for r in rows):,} → {sum(r[2] for r in rows):,} "
        f"(%{100 * sum(r[2] for r in rows) / sum(r[1] for r in rows):.0f})"
    )


if __name__ == "__main__":
    main()
