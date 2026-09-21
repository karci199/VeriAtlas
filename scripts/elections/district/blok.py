"""Left/right bloc shares by province and district, 1961-2023.

Bloc labels are a judgement call; the classification is spelled out below so it
can be checked and overridden. Two abbreviations are reused by unrelated
parties, so YTP is resolved by year (right in 1961-69, İsmail Cem's centre-left
party in 2002).

Kurdish parties are counted on the left, which drives most of the largest
long-run shifts, so a second series excluding them is reported alongside.
"""

import collections
import csv
import pathlib
import re

BASE = pathlib.Path(__file__).parent
AGG = {
    "Sandık sayısı",
    "Kayıtlı seçmen sayısı",
    "Oy kullanan seçmen sayısı",
    "Geçerli oy sayısı",
}
YEARS = [
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
LABEL = {"2015_7_haziran": "2015-Haz", "2015_1_kasim": "2015-Kas"}

KURT = {"HADEP", "DEHAP", "HDP", "YEŞİL SOL PARTİ"}
SOL = {
    "CHP",
    "SHP",
    "HP",
    "DSP",
    "TİP",
    "TBP",
    "BİRLİK PARTİSİ",
    "SP",
    "SİP",
    "ÖDP",
    "EMEP",
    "TKP",
    "TKH",
    "KP",
    "HKP",
    "SOL PARTİ",
    "MEMLEKET",
    "İP",
    "VATAN PARTİSİ",
} | KURT
SAG = {
    "AP",
    "CKMP",
    "MİLLET PARTİSİ",
    "MİLLET",
    "GP",
    "CGP",
    "DEMOKRATİK PARTİ",
    "MSP",
    "MHP",
    "MÇP",
    "ANAP",
    "MDP",
    "IDP",
    "RP",
    "FP",
    "SAADET PARTİSİ",
    "DYP",
    "DP",
    "DTP",
    "BBP",
    "BÜYÜK BİRLİK",
    "LDP",
    "YDP",
    "YDH",
    "YENİ PARTİ",
    "AK PARTİ",
    "GENÇ PARTİ",
    "BTP",
    "HYP",
    "ATP",
    "YURT-P",
    "HEPAR",
    "HAS PARTİ",
    "MMP",
    "HÜDA PAR",
    "İYİ PARTİ",
    "YENİDEN REFAH",
    "ZAFER PARTİSİ",
    "ANADOLU PARTİSİ",
    "MİLLİ YOL",
}
# Aggregate rows and captions that are not districts.
SKIP = re.compile(
    r"toplam|türkiye|il/ilçe merkezi|belde|bucağ|seçim çevresi", re.IGNORECASE
)
IL_ALIAS = {"afyon": "afyonkarahisar", "icel": "mersin", "k_maras": "kahramanmaras"}


def tr_lower(t):
    return t.replace("İ", "i").replace("I", "ı").lower()


def bloc_of(col, year):
    if col == "YTP":
        return "sol" if year == "2002" else "sag"
    if col in SOL:
        return "sol"
    if col in SAG:
        return "sag"
    return "diger"


def load():
    """Rows keyed by (year, province, district) -> {column: votes}."""
    first, cells = {}, collections.defaultdict(dict)
    with open(BASE / "secim_ilce.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        il = re.sub(r"_\d+$", "", r["cevre"])
        il = IL_ALIAS.get(il, il)
        first.setdefault((r["yil"], r["cevre"]), r["birim"])
        cells[(r["yil"], il, r["cevre"], r["birim"])][r["olcut"]] = int(r["deger"])
    return first, cells


def shares(votes, year):
    tot = collections.Counter()
    for col, x in votes.items():
        if col in AGG or "İTTİFAK" in col:
            continue
        tot[bloc_of(col, year)] += x
        if col in KURT:
            tot["kurt"] += x
    n = tot["sol"] + tot["sag"] + tot["diger"]
    if not n:
        return None
    return {
        "sol": 100 * tot["sol"] / n,
        "sag": 100 * tot["sag"] / n,
        "diger": 100 * tot["diger"] / n,
        "sol_kurtsuz": 100 * (tot["sol"] - tot["kurt"]) / n,
        "gecerli": votes.get("Geçerli oy sayısı", 0),
    }


def main():
    first, cells = load()

    il_rows, ilce_rows = {}, {}
    for (y, il, cevre, birim), v in cells.items():
        if birim == first[(y, cevre)] or SKIP.search(tr_lower(birim)):
            continue  # province/constituency totals and section captions
        s = shares(v, y)
        if s:
            ilce_rows[(y, il, tr_lower(birim).strip())] = s

    # Province series: sum the district rows, so new provinces stay comparable
    # with the districts that formed them.
    acc = collections.defaultdict(collections.Counter)
    for (y, il, cevre, birim), v in cells.items():
        if birim == first[(y, cevre)] or SKIP.search(tr_lower(birim)):
            continue
        for col, x in v.items():
            if col in AGG or "İTTİFAK" in col:
                continue
            acc[(y, il)][bloc_of(col, y)] += x
            if col in KURT:
                acc[(y, il)]["kurt"] += x
    for k, t in acc.items():
        n = t["sol"] + t["sag"] + t["diger"]
        if n:
            il_rows[k] = {
                "sol": 100 * t["sol"] / n,
                "sag": 100 * t["sag"] / n,
                "diger": 100 * t["diger"] / n,
                "sol_kurtsuz": 100 * (t["sol"] - t["kurt"]) / n,
            }

    for name, rows, keylen in (("il", il_rows, 2), ("ilce", ilce_rows, 3)):
        dest = BASE / f"blok_{name}.csv"
        with dest.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            head = ["yil", "il"] + (["ilce"] if keylen == 3 else [])
            w.writerow(head + ["sol", "sag", "diger", "sol_kurtsuz"])
            for k in sorted(rows):
                s = rows[k]
                w.writerow(
                    list(k)
                    + [round(s[c], 2) for c in ("sol", "sag", "diger", "sol_kurtsuz")]
                )
        print(f"{dest.name}: {len(rows)} satır")
    return il_rows, ilce_rows


if __name__ == "__main__":
    main()
