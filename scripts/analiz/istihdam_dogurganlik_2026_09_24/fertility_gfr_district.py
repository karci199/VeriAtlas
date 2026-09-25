"""General fertility rate (births per 1000 women 15-49) by district, province and year, 2014-2025.

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
for r in csv.DictReader(
    open(r"C:\veri\src\veriatlas\data\areas_tr_districts.csv", encoding="utf-8")
):
    names[r["area_id"]] = r.get("name_tr") or r.get("name")
G = "('age=15-19;sex=female','age=20-24;sex=female','age=25-29;sex=female','age=30-34;sex=female','age=35-39;sex=female','age=40-44;sex=female','age=45-49;sex=female')"
c.sql(
    f"create table w as select area_id a, year(period_start) y, sum(value) w from '{f}' where indicator_id='population' and area_level='district' and dims in {G} group by 1,2"
)
c.sql(
    f"create table b as select area_id a, year(period_start) y, value b from '{f}' where indicator_id='births' and area_level='district' and dims=''"
)
c.sql("create table d as select a, y, w, b, b/w*1000 g from w join b using(a,y)")
print(
    c.sql(
        "select y, count(*), sum(b), sum(w), sum(b)/sum(w)*1000 from d group by 1 order by 1"
    ).fetchall()
)
# check vs province births
print(
    c.sql(
        f"select year(period_start), sum(value) from '{f}' where indicator_id='births' and area_level='province' and dims='' group by 1 order by 1"
    ).fetchall()[-3:]
)
c.sql(
    "create table p as select substr(a,1,5) pa, y, sum(w) w, sum(b) b, sum(b)/sum(w)*1000 g from d group by 1,2"
)
prov = c.sql(
    "select pa, max(g) filter (where y=2014), max(g) filter (where y=2019), max(g) filter (where y=2025), max(b) filter (where y=2014), max(b) filter (where y=2025), max(w) filter (where y=2014), max(w) filter (where y=2025) from p group by 1 order by 4 desc"
).fetchall()
dist = c.sql(
    "select a, max(g) filter (where y=2014), max(g) filter (where y=2019), max(g) filter (where y=2025), max(b) filter (where y=2014), max(b) filter (where y=2025), max(w) filter (where y=2014), max(w) filter (where y=2025) from d group by 1"
).fetchall()
json.dump(
    dict(
        prov=[[names.get(r[0], r[0])] + list(r[1:]) for r in prov],
        dist=[
            [r[0], names.get(r[0], r[0]), names.get(r[0][:5])] + list(r[1:])
            for r in dist
        ],
    ),
    open(r"C:\veri-ham\analiz\2026_09_24\gfr.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
print(len(dist), prov[:3], prov[-3:])
