"""Internal consistency of public/nufus_birimler.json (the ranking page's data).

usage: check_population_table.py

  1. province = sum of its districts, against the warehouse's own province rows
  2. district = sum of its neighbourhoods and villages (coverage), per year
  3. under-18s: district estimate from 5-year bands against the sum of its quarters' 0-17 rows
  4. belde never above its district; year-on-year jumps of beldes and districts
  5. gaps inside a unit's series
Reads only.
"""
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
FACT = "C:/veri/public/fact.parquet"
d = json.loads((ROOT / "public/nufus_birimler.json").read_text(encoding="utf-8"))
Y = d["years"]


def at(u, yi, idx=4, first=3):
    s = u[idx] if idx == 4 else u[idx]
    if idx != 4:
        if not s:
            return None
        first_, vals = s
    else:
        first_, vals = u[first], s
    i = yi - first_
    return vals[i] if 0 <= i < len(vals) else None


units = d["units"]
by = {lv: [u for u in units if u[0] == lv] for lv in ("il", "ilce", "belde", "mahalle", "koy")}

# 1
prov = {(r[0], r[1]): r[2] for r in duckdb.sql(f"""select area_id, year(period_start), sum(value) from read_parquet('{FACT}')
   where indicator_id='population' and area_level='province' group by 1,2""").fetchall()}
worst = []
for u in by["il"]:
    pid = d["provinces"][-1 - u[2]][0]
    for yi in range(len(Y)):
        v, o = at(u, yi), prov.get((pid, Y[yi]))
        if v is not None and o:
            worst.append((abs(v - o) / o * 100, u[1], Y[yi], v, o))
worst.sort(reverse=True)
print(f"1. il = ilçeler toplamı, depodaki il satırıyla: {len(worst)} il-yıl, en büyük fark %{worst[0][0]:.3f} ({worst[0][1]} {worst[0][2]}); "
      f"%0,1'i aşan: {sum(1 for w in worst if w[0] > 0.1)}")

# 2
cov = {}
for lv in ("mahalle", "koy"):
    for u in by[lv]:
        for yi in range(len(Y)):
            v = at(u, yi)
            if v is not None:
                cov[(u[2], yi)] = cov.get((u[2], yi), 0) + v
rows = []
for u in by["ilce"]:
    for yi in range(len(Y)):
        v = at(u, yi)
        if v:
            rows.append((cov.get((u[2], yi), 0) / v * 100, u[1], Y[yi]))
bad = [r for r in rows if abs(r[0] - 100) > 1]
print(f"2. ilçe = mahalle+köy toplamı: {len(rows)} ilçe-yıl; ±%1 dışında {len(bad)} ({len(bad) / len(rows) * 100:.1f}%)")
for y in (2007, 2012, 2013, 2025):
    ry = [r for r in rows if r[2] == y]
    by_ = [r for r in ry if abs(r[0] - 100) > 1]
    print(f"   {y}: {len(by_)}/{len(ry)} ilçe ±%1 dışında; en uç {sorted(by_)[:2] + sorted(by_)[-2:] if by_ else '-'}")

# 3
q17 = {}
for u in by["mahalle"]:
    for yi in range(len(Y)):
        c = at(u, yi, 6)
        if c is not None:
            q17[(u[2], yi)] = q17.get((u[2], yi), 0) + c
diff = []
for u in by["ilce"]:
    for yi in range(len(Y)):
        est, tot = at(u, yi, 6), at(u, yi)
        vil = sum(1 for k in by["koy"] if k[2] == u[2] and at(k, yi) is not None) if yi == len(Y) - 1 else None
        if est and (u[2], yi) in q17 and Y[yi] == 2025 and vil == 0:
            diff.append(((q17[(u[2], yi)] - est) / est * 100, u[1]))
diff.sort()
import statistics  # noqa: E402
print(f"3. 0-17: ilçe tahmini (5'li gruplar) vs mahalle 0-17 toplamı, 2025, köysüz {len(diff)} ilçe: ortanca fark %{statistics.median([x for x, _ in diff]):.1f}, "
      f"uçlar {diff[:2]} … {diff[-2:]}")

# 4
over = []
for b in by["belde"]:
    dist = next(u for u in by["ilce"] if u[2] == b[2])
    for yi in range(len(Y)):
        v, t = at(b, yi), at(dist, yi)
        if v is not None and t and v > t:
            over.append((b[1], Y[yi], v, t))
print(f"4. belde > ilçe: {len(over)} durum {over[:3]}")
for lv in ("belde", "ilce"):
    jumps = []
    for u in by[lv]:
        for yi in range(1, len(Y)):
            a, b_ = at(u, yi - 1), at(u, yi)
            if a and b_ and a >= 1000 and abs(b_ / a - 1) > 0.3:
                jumps.append((round((b_ / a - 1) * 100), u[1], Y[yi]))
    jumps.sort()
    print(f"   {lv} yıllık ±%30 sıçrama (1.000+ kişi): {len(jumps)}; örnek {jumps[:3] + jumps[-3:]}")

# 5
gaps = [(u[0], u[1]) for u in units if any(v is None for v in u[4])]
print(f"5. seri içinde boşluk: {len(gaps)} birim; türe göre", {k: sum(1 for g in gaps if g[0] == k) for k in by})
