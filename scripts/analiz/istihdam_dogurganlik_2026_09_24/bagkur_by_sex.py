"""4B (self-employed, agriculture, muhtar) insured by sex, Türkiye and provinces.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv

import duckdb

c = duckdb.connect()
f = r"C:\veri\public\fact.parquet"
names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
q = f"""select year(period_start) y, area_id a, split_part(split_part(dims,'insured_type=',2),';',1) t, split_part(dims,'sex=',2) s, value v
from '{f}' where indicator_id='sgk_compulsory_insured' and dims like '%scheme=4b%' and area_level='province'"""
c.sql(f"create table d as {q}")
print(
    c.sql(
        "select y, t, sum(v) filter (where s='female') k, sum(v) tot, round(100*sum(v) filter (where s='female')/sum(v),1) pay from d group by 1,2 order by 2,1"
    ).fetchall()
)
print(
    c.sql(
        "select y, sum(v) filter (where s='female') k, sum(v) tot, round(100*sum(v) filter (where s='female')/sum(v),1) from d where t in ('self_employed','agriculture') group by 1 order by 1"
    ).fetchall()
)
for t in ["self_employed", "agriculture"]:
    r = c.sql(
        f"select a, sum(v) filter (where s='female') k, sum(v) tot, 100*sum(v) filter (where s='female')/sum(v) p from d where y=2025 and t='{t}' group by 1 order by p desc"
    ).fetchall()
    print(t, "TOP", [(names[x[0]], int(x[1]), round(x[3], 1)) for x in r[:7]])
    print(t, "BOTTOM", [(names[x[0]], int(x[1]), round(x[3], 1)) for x in r[-7:]])
