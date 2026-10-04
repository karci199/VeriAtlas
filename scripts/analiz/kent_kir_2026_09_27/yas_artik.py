"""Urban and rural age distribution per district by residual: rural = TÜİK district - urban.

TÜİK ADNKS 2025 gives every district in 5-year groups (exact). Urban neighbourhoods carry
usable Endeksa 2024 age bands (their band sum matches the TÜİK population within 10% for
~97% of urban people); each is rescaled to its TÜİK population. An urban neighbourhood
without usable bands takes the district's urban shape. Endeksa's 65+ is split with the
district's own 65-69 ... 90+ shape. Rural is what is left in each group; negatives are
clipped and reported. Small villages, where Endeksa is empty, are never read.

Check: rural 0-17 from the residual against TÜİK's 0-17 for the villages that have it.

usage: yas_artik.py 16 <dir with kent_16_ikili.csv>
"""

import json, sys
from pathlib import Path
import duckdb, polars as pl

PLATE, D = sys.argv[1], Path(sys.argv[2])
ROOT = Path("C:/veri")
G = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 35), (35, 40), (40, 45), (45, 50), (50, 55), (55, 60),
     (60, 65), (65, 70), (70, 75), (75, 80), (80, 85), (85, 90), (90, 100)]
LAB = [f"{a}-{b - 1}" if b < 100 else "90+" for a, b in G]
EK = ["0_4", "5_9", "10_14", "15_19", "20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54", "55_59", "60_64", "65"]

tuik = duckdb.sql(f"""select area_id, regexp_extract(dims, 'age=([^;]+)', 1) g, sum(value) v from read_parquet('{ROOT}/public/fact.parquet')
 where indicator_id='population' and area_id like 'TR-{PLATE}-___' and year(period_start)=2025 and dims like 'age=%sex=%' group by 1,2""").pl()
DIST = {}
for aid, g, v in tuik.iter_rows():
    DIST.setdefault(aid, [0.0] * len(G))[LAB.index(g)] += v
pop = dict(duckdb.sql(f"""select area_id, sum(value) from read_parquet('{ROOT}/public/fact.parquet') where indicator_id='population'
 and area_id like 'TR-{PLATE}-%-%' and year(period_start)=2025 group by 1""").fetchall())
kids = dict(duckdb.sql(f"""select area_id, sum(value) from read_parquet('{ROOT}/public/fact.parquet') where indicator_id='population'
 and area_id like 'TR-{PLATE}-%-%' and year(period_start)=2025 and dims='age=0-17' group by 1""").fetchall())
E = {}
for f in Path("C:/veri-ham/endeksa/demography").glob(f"TR-{PLATE}-*.json"):
    for code, v in json.loads(f.read_text(encoding="utf-8")).items():
        e = v.get("demography") or {}
        E[f"{f.stem}-{code}"] = [e.get(f"Age_{k}_Total") or 0 for k in EK]

nb = pl.read_csv(D / f"kent_{PLATE}_ikili.csv", infer_schema_length=0)


def expand(bands, dist):
    """14 Endeksa bands -> 19 TÜİK groups, 65+ split by the district's own old-age shape."""
    old = dist[13:]
    s = sum(old) or 1
    return bands[:13] + [bands[13] * o / s for o in old]


def med(c):
    h, acc = sum(c) / 2, 0
    for (a, b), n in zip(G, c):
        if n > 0 and acc + n >= h:
            return a + (h - acc) / n * (b - a)
        acc += n


def mean(c):
    return sum(n * (a + b) / 2 for (a, b), n in zip(G, c)) / sum(c)


def kids_of(c):  # 0-17 = 0-14 plus three fifths of 15-19
    return sum(c[:3]) + 0.6 * c[3]


rows = []
for did, dist in sorted(DIST.items()):
    sub = nb.filter(pl.col("area_id").str.starts_with(did + "-"))
    urban = [0.0] * len(G)
    good, fill = [], []
    for r in sub.filter(pl.col("kent_kir") == "kent").iter_rows(named=True):
        P, b = pop.get(r["area_id"]) or 0, E.get(r["area_id"])
        if P and b and abs(sum(b) - P) <= 0.1 * P:
            good.append((P, [x * P / sum(b) for x in expand(b, dist)]))
        elif P:
            fill.append(P)
    shape = [sum(c[i] for _, c in good) for i in range(len(G))]
    tot = sum(shape) or 1
    for P, c in good:
        urban = [u + x for u, x in zip(urban, c)]
    for P in fill:
        urban = [u + P * s / tot for u, s in zip(urban, shape)]
    rural = [d - u for d, u in zip(dist, urban)]
    neg = sum(-x for x in rural if x < 0)
    rural = [max(x, 0) for x in rural]
    rp = sub.filter(pl.col("kent_kir") == "kır")
    have = [a for a in rp["area_id"] if a in kids]
    name = sub["district"][0]
    rows.append(dict(ilce=name, area_id=did, dist=dist, urban=urban, rural=rural, neg=neg,
                     kids_tuik=sum(kids[a] for a in have), kids_pop=sum(pop.get(a) or 0 for a in have)))

out = []
agg = {k: [0.0] * len(G) for k in ("dist", "urban", "rural")}
for r in rows:
    for k in agg:
        agg[k] = [a + b for a, b in zip(agg[k], r[k])]
rows.append(dict(ilce="BURSA", area_id=f"TR-{PLATE}", neg=sum(r["neg"] for r in rows), kids_tuik=sum(r["kids_tuik"] for r in rows),
                 kids_pop=sum(r["kids_pop"] for r in rows), **agg))
for r in rows:
    u, k = r["urban"], r["rural"]
    rk = sum(k)
    out.append(dict(ilce=r["ilce"], kent_ortanca=round(med(u), 1), kir_ortanca=round(med(k), 1) if rk else None,
                    fark=round(med(k) - med(u), 1) if rk else None,
                    kent_ortalama=round(mean(u), 1), kir_ortalama=round(mean(k), 1) if rk else None,
                    kir_nufus=round(rk), kir_65_plus=round(sum(k[13:]) / rk * 100, 1) if rk else None,
                    kir_cocuk_artik=round(kids_of(k) / rk * 100, 1) if rk else None,
                    kir_cocuk_tuik=round(r["kids_tuik"] / r["kids_pop"] * 100, 1) if r["kids_pop"] else None,
                    negatif=round(r["neg"])))
t = pl.DataFrame(out).sort("kent_ortanca")
t.write_csv(D / f"yas_artik_{PLATE}.csv")
pl.Config.set_tbl_rows(30); pl.Config.set_tbl_width_chars(220); pl.Config.set_tbl_cols(12)
print(t)
