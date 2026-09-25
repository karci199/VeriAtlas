"""Men aged 18-60 outside registered employment (4A+4B+4C male), by province and year.

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
c.sql(f"""create table pop as select area_id a, year(period_start) y, sum(value) p from '{f}'
 where indicator_id='population' and area_level='province' and dims like 'age=%;sex=male'
 and try_cast(regexp_extract(dims,'age=([0-9]+)',1) as int) between 18 and 60 and dims not like '%+%' group by 1,2""")
c.sql(f"""create table emp as select area_id a, year(period_start) y, sum(value) e,
 sum(value) filter (where dims like 'scheme=4a%') e4a, sum(value) filter (where dims like '%scheme=4b%') e4b, sum(value) filter (where dims like 'scheme=4c%') e4c
 from '{f}' where indicator_id='sgk_compulsory_insured' and area_level='province' and dims in
 ('scheme=4a;sex=male','scheme=4c;sex=male','insured_type=self_employed;scheme=4b;sex=male','insured_type=agriculture;scheme=4b;sex=male') group by 1,2""")
c.sql(
    "create table t as select a,y,p,e,e4a,e4b,e4c,(1-e/p)*100 dis from pop join emp using(a,y) where y>=2012"
)
print(c.sql("select y,count(*) from t group by 1 order by 1").fetchall())
tr = c.sql(
    "select y, sum(p), sum(e), sum(e4a), sum(e4b), sum(e4c), (1-sum(e)/sum(p))*100 from t group by 1 order by 1"
).fetchall()
for r in tr:
    print(r)
rows = c.sql("""select a, max(dis) filter (where y=2025) o25, max(dis) filter (where y=2012) o12, max(dis) filter (where y=2019) o19,
 max(p) filter (where y=2025), max(e) filter (where y=2025) from t group by 1 order by o25 desc""").fetchall()
json.dump(
    dict(tr=tr, rows=[[names[r[0]]] + list(r[1:]) for r in rows]),
    open(r"C:\veri-ham\analiz\2026_09_24\men.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
