"""Teacher, police and nurse real totals on one table after the AGI double-count fix.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import datetime as dt
import json

import duckdb

c = duckdb.connect()
f = r"C:\veri\public\fact.parquet"


def ser(ind, dims):
    return dict(
        c.sql(
            f"select period_start, value from '{f}' where indicator_id='{ind}' and dims='{dims}'"
        ).fetchall()
    )


cpi = ser("cpi_2003", "")
k = ser("civil_servant_pay_coefficient", "pay_coefficient=monthly")
ogr = ser("civil_servant_salary", "civil_servant_profile=ogretmen;salary_item=net")
pol = ser("civil_servant_salary", "civil_servant_profile=polis;salary_item=net")
nur = json.load(open(r"C:\veri-ham\analiz\2026_09_24\nurse.json"))
ref = cpi[dt.date(2026, 8, 1)]
rows = []
for i, p in enumerate(sorted(ogr)):
    pay = dt.date(p.year, p.month + 1, 1)
    d = ref / cpi[pay]
    ek = 140 * k[pay] * (1 - 0.15 - 0.00759) * 80
    rows.append(
        dict(
            p=p.strftime("%Y") + ("/1" if p.month == 1 else "/2"),
            o=round(ogr[p]),
            ek=round(ek),
            ot=round(ogr[p] + ek),
            r_ot=round((ogr[p] + ek) * d),
            pol=round(pol[p]),
            r_pol=round(pol[p] * d),
            h=nur[i]["net"],
            nob=nur[i]["nob"],
            ht=nur[i]["top"],
            r_ht=nur[i]["r_top"],
        )
    )
for r in rows:
    print(r)
b = rows[0]
e = rows[-1]
for key in ["r_ot", "r_pol", "r_ht"]:
    print(key, round((e[key] / b[key] - 1) * 100, 1))
json.dump(rows, open(r"C:\veri-ham\analiz\2026_09_24\three.json", "w"))
