"""Voter migration: where the registered voters and the residents drift apart, over time.

usage: secmen_gocu.py

Registered voters (tiles, mahalle level, one per election) against adult population (warehouse
neighbourhood age=18+, every year; villages only carry totals). A voter list is drawn from the
ADNKS register of the year before, so the population year of an election is its year - 1.

  1. national ratio registered / 18+ per election, all places and by class (city / rural)
  2. net drift 2014 -> 2023: the change of (registered - 18+ residents) in people, by province,
     by class and the biggest single places
  3. age-specific ratio (district level): voters of an age group / residents of that group,
     elections 2011..2023, national curve and the districts with the largest gaps

Reads only; writes csv tables to C:/veri-ham/analiz/secmen_gocu/.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[3]
FACT = "C:/veri/public/fact.parquet"
TILES = Path("C:/veri/public/tiles")
OUT = Path("C:/veri-ham/analiz/secmen_gocu")
OUT.mkdir(parents=True, exist_ok=True)
URB = {"İl Merkezi", "İlçe Merkezi", "Kentsel Belde"}
# election -> year of the population it is compared with
ELECTIONS = {"yerel_bsb_2014": 2013, "cb2014": 2013, "mv2015h": 2014, "mv2015k": 2014, "mv2018": 2017, "cb2018": 2017,
             "yerel_bsb_2019": 2018, "mv2023": 2022, "cb2023t1": 2022, "yerel_bsb_2024": 2023}
LABEL = {"yerel_bsb_2014": "Yerel 2014", "cb2014": "CB 2014", "mv2015h": "MV Haz 2015", "mv2015k": "MV Kas 2015", "mv2018": "MV 2018",
         "cb2018": "CB 2018", "yerel_bsb_2019": "Yerel 2019", "mv2023": "MV 2023", "cb2023t1": "CB 2023", "yerel_bsb_2024": "Yerel 2024"}

data = json.loads((ROOT / "public/kentkir_kontrol.json").read_text(encoding="utf-8"))
K = {k: i for i, k in enumerate(data["keys"])}
rows = data["rows"]
g = lambda r, k: r[K[k]]  # noqa: E731
prefix = lambda aid: aid.rsplit("-", 1)[0]  # noqa: E731

# --- tiles: registered voters per election; anchor the tile keys to the page's rows through the
# 2023 general election (district, registered, valid votes), which the page already matched
tile_k = {e: {} for e in ELECTIONS}
anchor_tile = {}
for e in ELECTIONS:
    for f in TILES.glob(f"secim-{e}-mahalle-TR-*.json"):
        for key, v in json.loads(f.read_text(encoding="utf-8")).items():
            if "~" in key or not v.get("k"):
                continue
            tile_k[e][key] = v["k"]
            if e == "mv2023":
                anchor_tile[(prefix(key), v["k"], v.get("g"))] = key
row_of = defaultdict(list)
for i, r in enumerate(rows):
    if g(r, "k23"):
        row_of[(prefix(g(r, "id")), g(r, "k23"), g(r, "g23"))].append(i)
tile_row = {}
for t, key in anchor_tile.items():
    if len(row_of.get(t, [])) == 1:
        tile_row[key] = row_of[t][0]
print(f"seçim karosu -> sayfa satırı: {len(tile_row)} / {len(anchor_tile)} (2023 karosu), satır {len(rows)}")
kser = defaultdict(dict)  # row index -> {election: registered}
for e in ELECTIONS:
    hit = 0
    for key, k in tile_k[e].items():
        i = tile_row.get(key)
        if i is not None:
            kser[i][e] = k
            hit += 1
    print(f"  {LABEL[e]:12} karo {len(tile_k[e]):6}  eşleşen {hit:6}")

# --- population: 18+ for neighbourhoods, totals for both
p18, ptot = {}, {}
for aid, y, v in duckdb.sql(f"""select area_id, year(period_start), sum(value) from read_parquet('{FACT}') where indicator_id='population'
   and area_level='neighbourhood' and dims='age=18+' group by 1,2""").fetchall():
    p18[(aid, y)] = v
for aid, y, v in duckdb.sql(f"""select area_id, year(period_start), sum(value) from read_parquet('{FACT}') where indicator_id='population'
   and area_level in ('neighbourhood','village') group by 1,2""").fetchall():
    ptot[(aid, y)] = v


def wid(aid):
    p, c = aid.rsplit("-", 1)
    return f"{p}-{int(c) - 2000000}" if c.isdigit() and int(c) > 2000000 else aid


def look(d, aid, y):
    return d.get((aid, y)) or d.get((wid(aid), y))


cls = np.array([g(r, "os") in URB for r in rows])
tur = np.array([g(r, "tur") for r in rows])
il = np.array([g(r, "il") for r in rows])
mah = tur == "Mahalle"

# ---------------------------------------------------------------- 1. ratio per election
print("\n1. kayıtlı / 18+ nüfus (mahalleler; köylerde 18+ yok), seçim yılının bir önceki yıl nüfusuyla")
tab = []
for e, y in ELECTIONS.items():
    tot = {"hepsi": [0, 0], "kent": [0, 0], "kir": [0, 0]}
    for i, r in enumerate(rows):
        k = kser[i].get(e)
        a = look(p18, g(r, "id"), y) if mah[i] else None
        if not k or not a:
            continue
        for grp in ("hepsi", "kent" if cls[i] else "kir"):
            tot[grp][0] += k
            tot[grp][1] += a
    tab.append((LABEL[e], y, *[tot[x][0] / tot[x][1] * 100 for x in ("hepsi", "kent", "kir")], tot["hepsi"][0], tot["hepsi"][1]))
print(f"{'seçim':13} {'nüfus yılı':>10} {'hepsi %':>8} {'kent %':>8} {'kır %':>8} {'kayıtlı':>12} {'18+':>12}")
for t in tab:
    print(f"{t[0]:13} {t[1]:>10} {t[2]:8.1f} {t[3]:8.1f} {t[4]:8.1f} {t[5]:12,.0f} {t[6]:12,.0f}")
pl.DataFrame(tab, schema=["secim", "nufus_yili", "hepsi", "kent", "kir", "kayitli", "yetiskin"], orient="row").write_csv(OUT / "oran_secim.csv")

# ---------------------------------------------------------------- 2. net drift 2014 -> 2023
E1, E2 = "cb2014", "cb2023t1"
Y1, Y2 = ELECTIONS[E1], ELECTIONS[E2]
recs = []
for i, r in enumerate(rows):
    if not mah[i]:
        continue
    k1, k2 = kser[i].get(E1), kser[i].get(E2)
    a1, a2 = look(p18, g(r, "id"), Y1), look(p18, g(r, "id"), Y2)
    if not (k1 and k2 and a1 and a2):
        continue
    recs.append(dict(il=g(r, "il"), ilce=g(r, "ilce"), ad=g(r, "ad"), kent=bool(cls[i]), k1=k1, k2=k2, a1=a1, a2=a2, os=g(r, "os"),
                     ort=g(r, "ort") if "ort" in K else None, kurum=g(r, "kurum")))
df = pl.DataFrame(recs).with_columns(
    dk=pl.col("k2") - pl.col("k1"), da=pl.col("a2") - pl.col("a1"),
    r1=pl.col("k1") / pl.col("a1") * 100, r2=pl.col("k2") / pl.col("a2") * 100)
df = df.with_columns(drift=pl.col("dk") - pl.col("da"), dr=pl.col("r2") - pl.col("r1"))
print(f"\n2. {LABEL[E1]} -> {LABEL[E2]} (nüfus {Y1} -> {Y2}), {df.height} mahalle")
print(f"   kayıtlı {df['k1'].sum():,.0f} -> {df['k2'].sum():,.0f} ({df['dk'].sum():+,.0f}); 18+ {df['a1'].sum():,.0f} -> {df['a2'].sum():,.0f} ({df['da'].sum():+,.0f})")
print(f"   oran %{df['k1'].sum() / df['a1'].sum() * 100:.1f} -> %{df['k2'].sum() / df['a2'].sum() * 100:.1f}")
for nm, sub in (("kent", df.filter(pl.col("kent"))), ("kır", df.filter(~pl.col("kent")))):
    print(f"   {nm:5} {sub.height:6} yer: kayıtlı {sub['dk'].sum():+,.0f}, 18+ {sub['da'].sum():+,.0f}, oran %{sub['k1'].sum() / sub['a1'].sum() * 100:.1f} -> %{sub['k2'].sum() / sub['a2'].sum() * 100:.1f}")
byil = (df.group_by("il").agg(pl.col("k1").sum(), pl.col("k2").sum(), pl.col("a1").sum(), pl.col("a2").sum(), pl.len().alias("yer"))
        .with_columns(r1=pl.col("k1") / pl.col("a1") * 100, r2=pl.col("k2") / pl.col("a2") * 100)
        .with_columns(dr=pl.col("r2") - pl.col("r1"), drift=(pl.col("k2") - pl.col("k1")) - (pl.col("a2") - pl.col("a1"))).sort("dr"))
byil.write_csv(OUT / "il_kayma_2014_2023.csv")
print("\n   iller: oran değişimi en düşük (kayıtlı 18+'dan daha yavaş büyüdü = seçmen kaybı) ve en yüksek (seçmen birikti)")
for lab, sub in (("düşük", byil.head(8)), ("yüksek", byil.tail(8).reverse())):
    for r in sub.iter_rows(named=True):
        print(f"   {lab:7} {r['il']:15} %{r['r1']:5.1f} -> %{r['r2']:5.1f} ({r['dr']:+5.1f} puan)  kayıtlı {r['k2'] - r['k1']:+9,.0f}  18+ {r['a2'] - r['a1']:+9,.0f}  ({r['yer']} mahalle)")
big = df.filter((pl.col("a1") >= 1500) & (pl.col("a2") >= 1500))
for lab, sub in (("seçmen birikti (oran arttı)", big.sort("dr", descending=True).head(8)), ("seçmen kaybı (oran düştü)", big.sort("dr").head(8))):
    print(f"\n   tek tek mahalleler, {lab} (18+ >= 1.500):")
    for r in sub.iter_rows(named=True):
        print(f"   {r['il']}/{r['ilce']}/{r['ad'][:20]:20} %{r['r1']:5.0f} -> %{r['r2']:5.0f}  kayıtlı {r['k1']:>6,} -> {r['k2']:>6,}  18+ {r['a1']:>6,.0f} -> {r['a2']:>6,.0f} {r['os']}")
df.write_csv(OUT / "mahalle_kayma_2014_2023.csv")

# ---------------------------------------------------------------- 3. age-specific, district level
print("\n3. ilçe düzeyi, yaşa göre seçmen / nüfus (yaş grubu)")
prof = pl.read_parquet("C:/veri-ham/secim/profil/secmen_yas_egitim.parquet").group_by("election", "province", "district", "age").agg(pl.col("n").sum())
areas = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr.csv", infer_schema_length=0)
prov = areas.filter(pl.col("area_level") == "province")
dist = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_districts.csv", infer_schema_length=0)


def fold(t):
    t = (t or "").replace("İ", "i").replace("I", "ı").lower()
    for x, y in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(x, y)
    return "".join(ch for ch in t if ch.isalpha())


PK = {fold(r["name_tr"]).replace("afyonkarahisar", "afyon"): r["area_id"] for r in prov.iter_rows(named=True)}
DK = {(r["area_id"][:5], fold(r["name_tr"])): r["area_id"] for r in dist.filter(pl.col("valid_to").is_null()).iter_rows(named=True)}
AGES = ["18-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75+"]
ELE_Y = {"2011": 2010, "2015_1_kasim": 2014, "2018": 2017, "2023": 2022}  # election -> population year
# district population by five-year band (sexes added)
dp = defaultdict(float)
for aid, y, dims, v in duckdb.sql(f"""select area_id, year(period_start), dims, value from read_parquet('{FACT}') where indicator_id='population'
   and area_level='district' and dims like 'age=%' and year(period_start) in (2010,2014,2017,2022)""").fetchall():
    dp[(aid, y, dims.split(";")[0][4:])] += v


def pop_group(did, y, grp):
    if grp == "18-24":
        return 0.4 * dp[(did, y, "15-19")] + dp[(did, y, "20-24")]
    if grp == "75+":
        return sum(dp[(did, y, b)] for b in ("75-79", "80-84", "85-89", "90+"))
    return dp[(did, y, grp)]


vote = defaultdict(float)  # (district id, election, age) -> voters
for r in prof.iter_rows(named=True):
    if r["election"] not in ELE_Y or r["age"] not in AGES:
        continue
    pid = PK.get(fold(r["province"]).replace("afyonkarahisar", "afyon"))
    if not pid:
        continue
    did = DK.get((pid, fold(r["district"]))) or DK.get((pid, fold(r["district"]).removesuffix("merkez")))
    if did:
        vote[(did, r["election"], r["age"])] += r["n"]
dids = sorted({k[0] for k in vote})
name_d = {r["area_id"]: (r["name_tr"], next((p["name_tr"] for p in prov.iter_rows(named=True) if p["area_id"] == r["area_id"][:5]), "")) for r in dist.iter_rows(named=True)}
# a district-year whose voters fall outside 50-150 % of its adults is a parser misplacement, dropped
ok = {}
for d in dids:
    for e in ELE_Y:
        vt = sum(vote.get((d, e, a), 0) for a in AGES)
        pt = sum(pop_group(d, ELE_Y[e], a) for a in AGES)
        ok[(d, e)] = bool(pt) and 0.5 <= vt / pt <= 1.5
print(f"   ilçe-yıl kullanılan {sum(ok.values())} / {len(ok)}")
print(f"   ulusal eğri: {'':13}" + "".join(f"{e:>14}" for e in ELE_Y))
for a in AGES:
    line = f"   {a:>6} yaş grubu:      "
    for e in ELE_Y:
        v = sum(vote.get((d, e, a), 0) for d in dids if ok[(d, e)])
        p = sum(pop_group(d, ELE_Y[e], a) for d in dids if ok[(d, e)])
        line += f"{v / p * 100:13.1f}%"
    print(line)
# district table: young (25-39) and old (65+) ratio, and their change 2011 -> 2023
rows3 = []
for d in dids:
    if not (ok[(d, "2011")] and ok[(d, "2023")]):
        continue

    def ratio(e, groups):
        v = sum(vote.get((d, e, a), 0) for a in groups)
        p = sum(pop_group(d, ELE_Y[e], a) for a in groups)
        return (v / p * 100, p) if p >= 300 else (None, p)

    y11, py11 = ratio("2011", AGES[1:4]); y23, py23 = ratio("2023", AGES[1:4])
    o11, po11 = ratio("2011", AGES[9:]); o23, po23 = ratio("2023", AGES[9:])
    a11, _ = ratio("2011", AGES); a23, _ = ratio("2023", AGES)
    rows3.append(dict(il=name_d[d][1], ilce=name_d[d][0], genc11=y11, genc23=y23, yasli11=o11, yasli23=o23, tum11=a11, tum23=a23, genc_pop=py23, yasli_pop=po23))
d3 = pl.DataFrame(rows3)
d3.write_csv(OUT / "ilce_yas_orani.csv")
print(f"\n   {d3.height} ilçe (2011 ve 2023 ikisi de var)")
for lab, col, sub in (("gençlerde (25-39) en düşük 2023", "genc23", d3.drop_nulls("genc23").filter(pl.col("genc_pop") >= 5000).sort("genc23").head(8)),
                      ("gençlerde (25-39) en yüksek 2023", "genc23", d3.drop_nulls("genc23").filter(pl.col("genc_pop") >= 5000).sort("genc23", descending=True).head(8)),
                      ("yaşlılarda (65+) en yüksek 2023", "yasli23", d3.drop_nulls("yasli23").filter(pl.col("yasli_pop") >= 3000).sort("yasli23", descending=True).head(8)),
                      ("yaşlılarda (65+) en düşük 2023", "yasli23", d3.drop_nulls("yasli23").filter(pl.col("yasli_pop") >= 3000).sort("yasli23").head(8))):
    print(f"\n   {lab}:")
    for r in sub.iter_rows(named=True):
        print(f"   {r['il']}/{r['ilce']:16} genç %{r['genc11'] or 0:5.0f} -> %{r['genc23'] or 0:5.0f}   yaşlı %{r['yasli11'] or 0:5.0f} -> %{r['yasli23'] or 0:5.0f}   tüm 18+ %{r['tum11'] or 0:5.0f} -> %{r['tum23'] or 0:5.0f}")
