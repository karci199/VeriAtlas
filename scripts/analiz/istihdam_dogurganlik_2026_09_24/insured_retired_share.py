"""Insured plus old-age/invalidity pensioners as share of the 18+ population, by province and year.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import json

import duckdb

c = duckdb.connect()
f = r"C:\veri\public\fact.parquet"
names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
c.sql(rf"""create table pop as select area_id a, year(period_start) y, sum(value) p from '{f}'
 where indicator_id='population' and area_level='province' and dims like 'age=%;sex=%'
 and try_cast(regexp_extract(dims,'age=(\d+)',1) as int)>=18 group by 1,2""")
c.sql(f"""create table ins as select area_id a, year(period_start) y, sum(value) i from '{f}'
 where indicator_id='sgk_compulsory_insured' and area_level='province' and dims in
 ('scheme=4a;sex=female','scheme=4a;sex=male','scheme=4c;sex=female','scheme=4c;sex=male',
  'insured_type=self_employed;scheme=4b;sex=female','insured_type=self_employed;scheme=4b;sex=male',
  'insured_type=agriculture;scheme=4b;sex=female','insured_type=agriculture;scheme=4b;sex=male') group by 1,2""")
c.sql(f"""create table ret as select area_id a, year(period_start) y, sum(value) r from '{f}'
 where indicator_id='sgk_pension_recipients' and area_level='province' and
 regexp_extract(dims,'benefit=([a-z_]+)',1) in ('old_age','invalidity','duty_invalidity') and dims like '%recipient=%' group by 1,2""")
# check coverage counts
print(c.sql("select y, count(*) from ret group by 1 order by 1").fetchall())
print(c.sql("select y, count(*) from pop group by 1 order by 1").fetchall()[-14:])
c.sql(
    "create table t as select pop.a, pop.y, p, i, r, (i+r)/p*100 sh, i/p*100 ish, r/p*100 rsh from pop join ins using(a,y) join ret using(a,y) where pop.y between 2014 and 2025"
)
tr = c.sql(
    "select y, sum(p), sum(i), sum(r), sum(i+r)/sum(p)*100, sum(i)/sum(p)*100, sum(r)/sum(p)*100 from t group by 1 order by 1"
).fetchall()
for r in tr:
    print(r)
rows = c.sql(
    "select a, max(sh) filter (where y=2025), max(ish) filter (where y=2025), max(rsh) filter (where y=2025), max(sh) filter (where y=2014), max(p) filter (where y=2025) from t group by 1 order by 2 desc"
).fetchall()
json.dump(
    dict(tr=tr, rows=[[names[r[0]]] + list(r[1:]) for r in rows]),
    open(r"C:\veri-ham\analiz\2026_09_24\cov.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
for r in rows[:8] + rows[-8:]:
    print(names[r[0]], [round(x, 1) for x in r[1:5]])
