"""Nationwide detection of institutional population (prison, barracks, dormitory/university)
per neighbourhood/village, and what it does to the urban/rural class.

usage: kurum_tespit.py

Signals, each kept as its own column so a reader can see why a place was flagged:
  cezaevi      prisons from kamuyar.org.tr/prison (C:/veri-ham/cezaevi/cezaevi_mahalle.csv,
               point-in-polygon on public/geo/neighbourhoods)
  sicrama      largest one-year population jump 2008-2025 (ratio, year) -- an institution
               opening shows as a step, a town grows smoothly
  cocuk        0-17 share 2013 and 2025 (neighbourhoods only; villages have totals only) and
               Endeksa 0-14 share 2024 -- inmates, soldiers and students bring no children
  ek, genc     Endeksa 2024 men per woman and 20-29 share (sex by year is not kept below
               the district)
  kayit_nufus  registered voters / residents, mv2015k .. 2024 local -- conscripts and
               students vote at home, TR level is ~0.72
  oy_kayit     votes / registered; >1 marks a box brought in from an institution

Estimated institutional head count: men over women for a male institution, the 20-29 excess
over 15% for a campus, residents not on the register over the TR ratio otherwise. The class
effect: a kentsel belde / kasaba that falls below its threshold without that head count.

Writes C:/veri-ham/analiz/kent_kir/_kurum_tespit.csv.
"""
import json
import sys
from pathlib import Path

import duckdb
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
sys.argv = sys.argv[:1] + ["06"]  # il.py wants a plate; only wh() is used here
from il import wh  # noqa: E402

BASE = Path("C:/veri-ham/analiz/kent_kir")
FACT = "C:/veri/public/fact.parquet"
TILES = Path("C:/veri/public/tiles")
ELECTIONS = ["mv2015k", "mv2018", "mv2023", "yerel_belmec_2024"]
TR_REG = 0.72

plates = sorted(p.name for p in BASE.iterdir() if (p / f"kent_{p.name}_son.csv").exists())
cls = pl.concat([pl.read_csv(BASE / p / f"kent_{p}_son.csv", infer_schema_length=0)
                 .select("area_id", "district", "name", "son_sinif").with_columns(pl.lit(p).alias("plate")) for p in plates])
cls = cls.with_columns(pl.col("area_id").map_elements(wh, return_dtype=pl.Utf8).alias("wid"))

# population by year, and children where kept
pop = duckdb.sql(f"""select area_id, year(period_start) y, sum(value) v, sum(value) filter (where dims='age=0-17') c
  from read_parquet('{FACT}') where indicator_id='population' and area_level in ('neighbourhood','village') group by 1,2""").pl()
series = {}
for r in pop.iter_rows(named=True):
    series.setdefault(r["area_id"], {})[r["y"]] = (r["v"], r["c"])


def jump(s):
    best = (1.0, None)
    ys = sorted(s)
    for a, b in zip(ys, ys[1:]):
        va, vb = s[a][0] or 0, s[b][0] or 0
        if va >= 100 and vb - va >= 500 and vb / va > best[0]:
            best = (vb / va, b)
    return best


# Endeksa 2024 snapshot
END = {}
for fn in Path("C:/veri-ham/endeksa/demography").glob("TR-*.json"):
    for k, v in json.loads(fn.read_text(encoding="utf-8")).items():
        e = v.get("demography") or {}
        if e.get("PopulationTotal"):
            END[f"{fn.stem}-{k}"] = e


def endeksa(aid):
    e = END.get(aid)
    if not e:
        did, code = aid.rsplit("-", 1)
        e = END.get(f"{did}-{int(code) + 2000000}") if code.isdigit() else None
    return e


# elections: registered and votes per place
REG = {}
for e in ELECTIONS:
    for f in TILES.glob(f"secim-{e}-mahalle-TR-*.json"):
        for key, v in json.loads(f.read_text(encoding="utf-8")).items():
            if "~" in key:
                continue
            REG.setdefault(wh(key), {})[e] = (v["k"], v["o"])

# institutions checked on the web (2026-09-29) where the signals could not tell the type;
# prisons opened after the 2022 directory are added to cezaevi_mahalle.csv itself
WEB = {
    ("06", "Çankaya", "Ahlatlıbel"): "askeri okul (Jandarma ve Sahil Güvenlik Akademisi)",
    ("59", "Çorlu", "Hatip"): "kışla (66. Mekanize Piyade Tugayı)",
    ("19", "Çorum", "Ak Kent"): "cezaevi (Çorum L tipi, web)",
    ("40", "Kırşehir", "Kuşdilli"): "cezaevi (Kırşehir kampüs, web)",
    ("33", "Gülnar", "Büyükeceli"): "şantiye işçileri (Akkuyu nükleer santrali)",
}

# prisons
cz = pl.read_csv("C:/veri-ham/cezaevi/cezaevi_mahalle.csv")
PRISON = {}
for r in cz.iter_rows(named=True):
    PRISON.setdefault(r["area_id"], []).append(r["ad"])

rows = []
for r in cls.iter_rows(named=True):
    aid = r["wid"]
    s = series.get(aid, {})
    p25 = (s.get(2025) or (None, None))[0] or 0
    if p25 < 200 and aid not in PRISON:
        continue
    j, jy = jump(s)
    c13 = s.get(2013, (None, None))
    c25 = s.get(2025, (None, None))
    cs13 = c13[1] / c13[0] if c13[0] and c13[1] is not None else None
    cs25 = c25[1] / c25[0] if c25[0] and c25[1] is not None else None
    e = endeksa(aid) or {}
    n = e.get("PopulationTotal") or 0
    m = e.get("PopulationMale") or 0
    ek = m / (n - m) if n and n > m else None
    genc = ((e.get("Age_20_24_Total") or 0) + (e.get("Age_25_29_Total") or 0)) / n if n else None
    c014 = (e.get("Age_Group_0_14") or 0) / n if n else None
    reg = REG.get(aid, {})
    k23 = (reg.get("mv2023") or (None, None))[0]
    kn = k23 / p25 if k23 and p25 else None
    over = max(((o - k) for k, o in reg.values() if k is not None and o is not None), default=0)
    types, est = [], 0.0
    web = WEB.get((r["plate"], r["district"], r["name"]))
    if web:
        types.append(web)
    if aid in PRISON:
        types.append("cezaevi")
    if ek and ek >= 1.5 and n >= 200:
        types.append("erkek ağırlıklı" if aid in PRISON or web else "erkek ağırlıklı (kışla/işçi/cezaevi?)")
        est = max(est, (m - (n - m)) * p25 / n)
    if genc and genc >= 0.33 and ek and 0.6 <= ek < 1.5 and n >= 500:
        types.append("genç ağırlıklı (üniversite/yurt)")
        est = max(est, (genc - 0.15) * p25)
    yab = 0.0
    if kn is not None and kn < 0.45 and p25 >= 500:
        # off the register with children and an even sex ratio is a family population
        # (foreign nationals -- Gaziantep, Şanlıurfa, Hatay), not an institution
        if not types and c014 is not None and c014 >= 0.25 and ek and 0.8 <= ek <= 1.25:
            types.append("seçmen olmayan aile nüfusu (yabancı?)")
            yab = p25 - k23 / TR_REG
        else:
            types.append("seçmen dışı nüfus")
            est = max(est, p25 - k23 / TR_REG)
    if over >= 20:
        types.append("oy > kayıtlı (kurum sandığı)")
    if not types:
        continue
    est = min(max(est, 0), p25)
    civil = p25 - est
    sc = r["son_sinif"]
    effect = ""
    if sc == "kentsel_belde" and civil < 5000:
        effect = "kurumsuz 5.000 altı: kasaba/kır olurdu" if civil >= 2000 else "kurumsuz 2.000 altı: kır olurdu"
    elif sc == "kasaba" and civil < 2000:
        effect = "kurumsuz 2.000 altı: köy olurdu"
    rows.append(dict(plate=r["plate"], district=r["district"], name=r["name"], area_id=aid, sinif=sc, nufus_2025=int(p25),
                     tip="; ".join(types), cezaevi=" | ".join(PRISON.get(aid, [])), kurum_tahmini=int(est), yabanci_tahmini=int(max(yab, 0)), sivil=int(civil),
                     etki=effect, sicrama=round(j, 2), sicrama_yili=jy, cocuk_2013=round(cs13, 3) if cs13 is not None else None,
                     cocuk_2025=round(cs25, 3) if cs25 is not None else None, cocuk014_2024=round(c014, 3) if c014 is not None else None,
                     erkek_kadin=round(ek, 2) if ek else None, genc_20_29=round(genc, 3) if genc else None,
                     kayit_nufus_2023=round(kn, 2) if kn is not None else None, oy_fazlasi=int(over)))
d = pl.DataFrame(rows)
d.write_csv(BASE / "_kurum_tespit.csv")
print("işaretli yer:", d.height, "| nüfus", d["nufus_2025"].sum(), "| tahmini kurum nüfusu", d["kurum_tahmini"].sum())
