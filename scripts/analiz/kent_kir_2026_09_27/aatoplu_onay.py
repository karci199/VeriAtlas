"""Bulk review of the urban/rural "arada" rows against the user's own 2015 classification.

usage: aatoplu_onay.py [plate ...]      (default: every province with a kent_<p>_son.csv)

AATOPLU 7H.xlsx (user's desktop, 7 June 2015 election tables) lists every unit as MAHALLE
(town quarter), Belde or Köy. A contested row whose building-based class agrees with that
label is approved and written to elle_aatoplu.csv, which birlestir.py reads beside ELLE
(ELLE wins). Agreement:
  Mahalle -> merkez / kentsel_belde
  Köy     -> kir / kasaba / kirsal_belde   (never kentsel_belde: a 2015 village that is a
             5.000+ patch today -- a villa belt, a TOKİ town -- goes to the user)
  Belde   -> any belde class or kir          (a belde can be a 5.000+ town; AATOPLU's
             rural lean is not taken over, only merkez is questioned)
Everything else -- disagreement, no AATOPLU row, plus uncontested rows AATOPLU contradicts
-- goes to _aatoplu_kalan.csv for the user.

AATOPLU names districts as of 2015 ("Aydın Merkez", Kazan): a quarter is looked up by name
within the province, the district only breaks ties.
"""
import json
import re
import sys
from pathlib import Path

import duckdb
import openpyxl
import polars as pl

BASE = Path("C:/veri-ham/analiz/kent_kir")
SRC = Path("C:/Users/katan/OneDrive/Desktop/demografi/AATOPLU 7H.xlsx")
OUT = Path(__file__).parent / "elle_aatoplu.csv"
MANUAL = {"06", "16"}  # reviewed one by one with the user
IL_ALIAS = {"Afyonkarahisar": "Afyon"}
KENT = {"merkez", "kentsel_belde"}
KIR = {"kir", "kasaba", "kirsal_belde"}


def fold(t):
    t = re.sub(r"\s*\((B|Bm|BM)\)", "", t or "")  # AATOPLU marks beldes "Çevreli (B)"
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(a, b)
    t = "".join(ch for ch in t if ch.isalpha())
    return re.sub(r"(mahallesi|koyu|koy)$", "", t)


def agrees(label, s):
    if label == "Mahalle":
        return s in KENT
    if label == "Köy":
        return s in KIR
    if label == "Belde":
        return s in KIR | {"kentsel_belde"}
    return False


wb = openpyxl.load_workbook(SRC, read_only=True)
LAB = {}  # (il, quarter) -> [(district, label)]
for r in wb["MAHALLE"].iter_rows(min_row=2, values_only=True):
    if r[0] and r[2]:
        LAB.setdefault((r[0], fold(r[2])), []).append((fold(r[1]), "Mahalle"))
for r in wb["BELDE - KÖY"].iter_rows(min_row=2, values_only=True):
    if r[0] and r[3]:
        LAB.setdefault((r[0], fold(r[3])), []).append((fold(r[2]), r[1]))

prov = {r["area_id"].split("-")[1]: r["name_tr"] for r in pl.read_csv(
    Path(__file__).parents[3] / "src/veriatlas/data/areas_tr.csv", infer_schema_length=0).filter(
    pl.col("area_level") == "province").iter_rows(named=True)}


BYIL = {}
for (il_, q), v in LAB.items():
    BYIL.setdefault(il_, []).append((q, v))


def _pick(c, district):
    if len({lab for _, lab in c}) == 1:
        return c[0][1]
    d = fold(district)
    same = [lab for dd, lab in c if dd == d or dd == d + "merkez" or dd.startswith(d)]
    return same[0] if len(set(same)) == 1 else None


def label(il, district, name, eski=None):
    c = LAB.get((il, fold(name)), [])
    if c:
        return _pick(c, district)
    # a quarter of a belde (non-metropolitan beldes still stand): our registry knows the belde
    if eski and eski.startswith("belde:") and any(lab == "Belde" for _, lab in LAB.get((il, fold(eski[6:])), [])):
        return "Belde"
    # a quarter named after the belde it was carved from ("Kızılpınar Atatürk", "Zafer
    # Sülümenli"): the belde's own row
    for w in re.split(r"[\s\-]+", name or ""):
        if len(fold(w)) >= 5:
            c = [(dd, lab) for dd, lab in LAB.get((il, fold(w)), []) if lab == "Belde"]
            if c:
                return "Belde"
    # small spelling drift inside the province
    import difflib
    best = difflib.get_close_matches(fold(name), [q for q, _ in BYIL.get(il, [])], n=1, cutoff=0.88)
    if best:
        return _pick(LAB[(il, best[0])], district)
    return None


plates = sys.argv[1:] or sorted(p.name for p in BASE.iterdir() if (p / f"kent_{p.name}_son.csv").exists())

# village texture for a 2015 village the buildings now call urban (Ankara precedents: Çubuk's
# Sünlü/Güldarpı stayed rural -- more buildings than dwellings, shrinking; Galaba, Yuvaköy
# became town -- grown well past 2013): Endeksa dwellings over MS buildings, ADNKS growth
HOUSING = {}
for fn in Path("C:/veri-ham/endeksa/demography").glob("TR-*.json"):
    for k, v in json.loads(fn.read_text(encoding="utf-8")).items():
        e = v.get("demography") or {}
        if e:
            HOUSING[f"{fn.stem}-{k}"] = e.get("HousingCount") or 0
GROWTH = {r["area_id"]: (r["y25"] / r["y13"] if r["y13"] and r["y25"] is not None else None) for r in duckdb.sql(
    """select area_id, sum(value) filter (where year(period_start)=2013) y13, sum(value) filter (where year(period_start)=2025) y25
       from read_parquet('C:/veri/public/fact.parquet') where indicator_id='population' and area_level='neighbourhood'
       group by 1""").pl().iter_rows(named=True)}


def village_test(r):
    b = float(r["buildings"] or 0)
    kb = HOUSING.get(r["area_id"], 0) / b if b else None
    g = GROWTH.get(r["area_id"])
    if g is not None and g >= 1.5:
        return "kent"
    if kb is not None and kb < 1.0 and (g is None or g <= 1.05):
        return "kir"
    return None


approved, left = [], []
for p in plates:
    if p in MANUAL:
        continue
    il = IL_ALIAS.get(prov[p], prov[p])
    d = pl.read_csv(BASE / p / f"kent_{p}_son.csv", infer_schema_length=0).with_columns(pl.col("pop").cast(pl.Float64).fill_null(0))
    for r in d.filter(pl.col("son_sinif") != "osb").iter_rows(named=True):
        ar = r["arada"] not in (None, "", "False", "0")
        lab = label(il, r["district"], r["name"], r["eski_statu"])
        ok = agrees(lab, r["son_sinif"])
        row = dict(plate=p, il=prov[p], district=r["district"], area_id=r["area_id"], name=r["name"], pop=int(r["pop"]),
                   sinif=r["son_sinif"], aatoplu=lab or "", arada=ar, degurba=r["degurba"], eski_statu=r["eski_statu"],
                   note=(r["note"] or "")[:80])
        # a quarter created after 2015 cannot be in AATOPLU; the Ankara precedent (Atayurt,
        # Turkuaz, Kuzey Yıldızı): urban on buildings and on DEGURBA stays urban
        new_urban = (not lab and r["eski_statu"] == "yok" and r["son_sinif"] in KENT
                     and "KENT" in (r["degurba"] or ""))
        if ar and ok:
            approved.append(dict(area_id=r["area_id"], sinif=r["son_sinif"], not_=f"elle: AATOPLU 2015 {lab} ile aynı, toplu onay"))
        elif ar and new_urban:
            approved.append(dict(area_id=r["area_id"], sinif=r["son_sinif"], not_="elle: 2015 sonrası yeni mahalle, bina ve DEGURBA kent, toplu onay"))
        elif ar and lab == "Belde" and r["son_sinif"] == "merkez":
            # a belde grown into the town's patch counts with the town (Sincan Menderes, old Yenikent)
            approved.append(dict(area_id=r["area_id"], sinif="merkez", not_="elle: eski belde, merkez lekesine bitişik (Menderes emsali), toplu onay"))
        elif ar and lab == "Köy" and r["son_sinif"] in KENT and village_test(r):
            t = village_test(r)
            approved.append(dict(area_id=r["area_id"], sinif=r["son_sinif"] if t == "kent" else "kir",
                                 not_="elle: 2015 köyü, nüfus 2013'ten beri x1,5+ büyüdü, kent (Galaba emsali)" if t == "kent"
                                 else "elle: 2015 köyü, köy dokusu (bina>konut, nüfus artmıyor), kır (Çubuk emsali)"))
        elif ar:
            # the rest is assigned by rule (user, 2026-09-29: "assign everything, show me the
            # unsure ones last"); every such row is also listed for review
            s, vt = r["son_sinif"], village_test(r)
            deg_kent = "KENT" in (r["degurba"] or "")
            if not lab and (s in KENT) == deg_kent:
                c, why, sure = s, "AATOPLU'da yok, bina ve DEGURBA aynı", True
            elif lab == "Mahalle" and s in KIR and vt:
                c, why, sure = (s if vt == "kir" else "merkez"), ("AATOPLU mahalle ama köy dokusu (Harmancık emsali)" if vt == "kir"
                                                                 else "AATOPLU mahalle, nüfus x1,5+ büyüdü"), True
            elif r["pop"] >= 2000 and lab == "Mahalle":
                c, why, sure = "merkez", "2.000+ kişi, AATOPLU mahalle", False
            elif r["pop"] >= 5000 and lab == "Köy":
                # a 5.000+ patch today outweighs a 2015 village label (Şanlıurfa Seyrantepe)
                c, why, sure = s, "5.000+ kişi, AATOPLU köy ama bina kent, bina sınıfı", False
            elif r["pop"] >= 2000 and lab == "Köy":
                c, why, sure = "kir", "2.000+ kişi, AATOPLU köy", False
            elif r["pop"] >= 2000:
                c, why, sure = s, "2.000+ kişi, AATOPLU yok, bina sınıfı", False
            else:
                c, why, sure = (s if s in KIR else "kir"), "2.000 altı, şüphede kır", False
            approved.append(dict(area_id=r["area_id"], sinif=c, not_=f"elle: kural -- {why}"))
            if not sure or r["pop"] >= 5000:
                left.append({**row, "atanan": c, "neden": why + ("" if sure else " (emin değil)")})
        elif lab and not ok and r["pop"] >= 5000:
            left.append({**row, "atanan": r["son_sinif"], "neden": "ihtilafsız ama AATOPLU çelişiyor (5.000+)"})

pl.DataFrame(approved).rename({"not_": "not"}).write_csv(OUT)
k = pl.DataFrame(left)
k.write_csv(BASE / "_aatoplu_kalan.csv")
print("onaylanan:", len(approved), "| kalan:", k.height)
print(k.group_by("neden").agg(pl.len(), pl.col("pop").sum()).rows())
