"""Province-level link between female registered employment and fertility: levels, changes, two-way fixed effects.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import json

import duckdb
import numpy as np

c = duckdb.connect()
f = r"C:\veri\public\fact.parquet"
names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
G = "('age=15-19;sex=female','age=20-24;sex=female','age=25-29;sex=female','age=30-34;sex=female','age=35-39;sex=female','age=40-44;sex=female','age=45-49;sex=female')"
c.sql(
    f"create table w as select substr(area_id,1,5) a, year(period_start) y, sum(value) w from '{f}' where indicator_id='population' and area_level='district' and dims in {G} group by 1,2"
)
c.sql(
    f"create table b as select substr(area_id,1,5) a, year(period_start) y, sum(value) b from '{f}' where indicator_id='births' and area_level='district' and dims='' group by 1,2"
)
c.sql(f"""create table wp as select area_id a, year(period_start) y, sum(value) wp from '{f}' where indicator_id='population' and area_level='province' and dims like 'age=%;sex=female'
 and try_cast(regexp_extract(dims,'age=([0-9]+)',1) as int) between 18 and 60 and dims not like '%+%' group by 1,2""")
c.sql(f"""create table e as select area_id a, year(period_start) y, sum(value) e from '{f}' where indicator_id='sgk_compulsory_insured' and area_level='province' and dims in
 ('scheme=4a;sex=female','scheme=4c;sex=female','insured_type=self_employed;scheme=4b;sex=female','insured_type=agriculture;scheme=4b;sex=female') group by 1,2""")
rows = c.sql(
    "select a,y,b/w*1000 gfr, e/wp*100 emp from w join b using(a,y) join wp using(a,y) join e using(a,y) where y between 2014 and 2025 order by a,y"
).fetchall()
import collections

P = collections.defaultdict(dict)
for a, y, g, m in rows:
    P[a][y] = (g, m)
A = sorted(P)
print(len(A), len(rows))


def corr(x, y):
    x, y = np.array(x), np.array(y)
    r = np.corrcoef(x, y)[0, 1]
    rx = np.argsort(np.argsort(x))
    ry = np.argsort(np.argsort(y))
    s = np.corrcoef(rx, ry)[0, 1]
    b = np.polyfit(x, y, 1)[0]
    return round(r, 3), round(s, 3), round(b, 3)


g25 = [P[a][2025][0] for a in A]
m25 = [P[a][2025][1] for a in A]
g14 = [P[a][2014][0] for a in A]
m14 = [P[a][2014][1] for a in A]
print("level2025 r,rho,slope", corr(m25, g25))
print("level2014", corr(m14, g14))
dg = [(P[a][2025][0] / P[a][2014][0] - 1) * 100 for a in A]
dm = [P[a][2025][1] - P[a][2014][1] for a in A]
print("change: d_emp(pp) vs d_gfr(%)", corr(dm, dg))
# control for initial gfr: regress dg on dm and log g14
X = np.column_stack([np.ones(81), dm, np.log(g14), m14])
beta, res, _, _ = np.linalg.lstsq(X, np.array(dg), rcond=None)
yhat = X @ beta
r2 = 1 - ((np.array(dg) - yhat) ** 2).sum() / ((np.array(dg) - np.mean(dg)) ** 2).sum()
# se
n, k = X.shape
s2 = ((np.array(dg) - yhat) ** 2).sum() / (n - k)
se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
print(
    "OLS dg ~ dm + log g14 + m14:",
    [round(v, 3) for v in beta],
    "se",
    [round(v, 3) for v in se],
    "R2",
    round(r2, 3),
)
# excluding quake provinces
Q = {
    "TR-01",
    "TR-02",
    "TR-21",
    "TR-27",
    "TR-31",
    "TR-44",
    "TR-46",
    "TR-63",
    "TR-79",
    "TR-80",
    "TR-23",
}
idx = [i for i, a in enumerate(A) if a not in Q]
print("change ex-quake", corr([dm[i] for i in idx], [dg[i] for i in idx]))
X2 = X[idx]
y2 = np.array(dg)[idx]
b2 = np.linalg.lstsq(X2, y2, rcond=None)[0]
yh = X2 @ b2
s2 = ((y2 - yh) ** 2).sum() / (len(idx) - 4)
se2 = np.sqrt(np.diag(s2 * np.linalg.inv(X2.T @ X2)))
print("OLS ex-quake", [round(v, 3) for v in b2], [round(v, 3) for v in se2])
# panel two-way FE: log gfr on emp rate with province and year FE
yrs = list(range(2014, 2026))
Y = []
E = []
ai = []
yi = []
for i, a in enumerate(A):
    for y in yrs:
        if y in P[a]:
            Y.append(np.log(P[a][y][0]))
            E.append(P[a][y][1])
            ai.append(i)
            yi.append(yrs.index(y))
Y = np.array(Y)
E = np.array(E)


def demean(v):
    v = v.copy()
    for _ in range(50):
        for grp in (ai, yi):
            s = collections.defaultdict(list)
            for j, gv in enumerate(grp):
                s[gv].append(v[j])
            m = {gg: np.mean(vv) for gg, vv in s.items()}
            v = v - np.array([m[gv] for gv in grp])
    return v


Yd, Ed = demean(Y), demean(E)
bfe = (Ed @ Yd) / (Ed @ Ed)
res = Yd - bfe * Ed
# cluster-robust se by province
meat = 0
for i in range(len(A)):
    idxs = [j for j, g in enumerate(ai) if g == i]
    meat += (Ed[idxs] @ res[idxs]) ** 2
se_c = np.sqrt(meat) / (Ed @ Ed)
print(
    "TWFE log(gfr) on emp: beta",
    round(bfe, 4),
    "cluster se",
    round(se_c, 4),
    "=> 1pp emp ->",
    round((np.exp(bfe) - 1) * 100, 2),
    "% gfr",
)
out = [
    [names[a], P[a][2014][1], P[a][2025][1], P[a][2014][0], P[a][2025][0]] for a in A
]
json.dump(
    out,
    open(r"C:\veri-ham\analiz\2026_09_24\rel.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
print("TR emp 2014/2025", round(sum(1 for _ in [0]), 1))
