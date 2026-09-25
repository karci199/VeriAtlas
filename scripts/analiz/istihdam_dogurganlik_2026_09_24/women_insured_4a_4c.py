"""Female share of 4A and 4C compulsory insured by province and year.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import json

import duckdb

c = duckdb.connect()
f = r"C:\veri\public\fact.parquet"
names = {}
for r in csv.DictReader(
    open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
):
    names[r.get("area_id") or r.get("id")] = (
        r.get("name_tr") or r.get("name") or r.get("label_tr")
    )
q = f"""select area_id, year(period_start) y, dims, value from '{f}' where indicator_id='sgk_compulsory_insured' and dims in ('scheme=4a;sex=female','scheme=4a;sex=male','scheme=4c;sex=female','scheme=4c;sex=male')"""
d = {}
for a, y, dm, v in c.sql(q).fetchall():
    d[(a, y, dm)] = v
print(
    c.sql(
        f"select distinct area_level, month(period_start), frequency from '{f}' where indicator_id='sgk_compulsory_insured'"
    ).fetchall()
)
areas = sorted({a for a, _, _ in d if a.startswith("TR-") and a.count("-") == 1})
print(len(areas))
Y = range(2010, 2026)
tr = []
for y in Y:
    s = lambda dm: sum(d.get((a, y, dm), 0) for a in areas)
    af, am, cf, cm = (
        s("scheme=4a;sex=female"),
        s("scheme=4a;sex=male"),
        s("scheme=4c;sex=female"),
        s("scheme=4c;sex=male"),
    )
    trv = {
        k: d.get(("TR", y, k)) for k in ["scheme=4a;sex=female", "scheme=4c;sex=female"]
    }
    tr.append(dict(y=y, af=af, at=af + am, cf=cf, ct=cf + cm, chk=trv))
for r in tr:
    print(r)
prov = []
for a in areas:
    g = lambda y, dm: d.get((a, y, dm))
    af, am, cf, cm = (
        g(2025, "scheme=4a;sex=female"),
        g(2025, "scheme=4a;sex=male"),
        g(2025, "scheme=4c;sex=female"),
        g(2025, "scheme=4c;sex=male"),
    )
    af0, am0 = g(2010, "scheme=4a;sex=female"), g(2010, "scheme=4a;sex=male")
    cf0, cm0 = g(2012, "scheme=4c;sex=female"), g(2012, "scheme=4c;sex=male")
    prov.append(
        dict(
            a=a,
            n=names.get(a, a),
            af=af,
            ash=af / (af + am) * 100,
            cf=cf,
            csh=cf / (cf + cm) * 100,
            ash0=af0 / (af0 + am0) * 100,
            csh0=cf0 / (cf0 + cm0) * 100,
        )
    )
json.dump(
    dict(tr=tr, prov=prov),
    open(r"C:\veri-ham\analiz\2026_09_24\women.json", "w"),
    ensure_ascii=False,
    default=str,
)
for p in (
    sorted(prov, key=lambda p: -p["ash"])[:5] + sorted(prov, key=lambda p: p["ash"])[:5]
):
    print(p)
