"""New teacher: net salary plus 20 weekly extra lessons (140 x coefficient), real, semiannual 2014-2026.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import datetime as dt
import json

import duckdb

c = duckdb.connect()
f = r"C:\veri\public\fact.parquet"
cpi = dict(
    c.sql(
        f"select period_start, value from '{f}' where indicator_id='cpi_2003' and area_id='TR'"
    ).fetchall()
)
sal = dict(
    c.sql(
        f"select period_start, value from '{f}' where indicator_id='civil_servant_salary' and dims='civil_servant_profile=ogretmen;salary_item=net'"
    ).fetchall()
)
kat = dict(
    c.sql(
        f"select period_start, value from '{f}' where indicator_id='civil_servant_pay_coefficient' and dims='pay_coefficient=monthly'"
    ).fetchall()
)
asg = dict(
    c.sql(
        f"select period_start, value from '{f}' where indicator_id='minimum_wage' and dims='wage_measure=net'"
    ).fetchall()
)
ref = cpi[dt.date(2026, 8, 1)]
rows = []
for p in sorted(sal):
    pay = dt.date(p.year, p.month + 1, 1)  # Feb / Aug payslip
    k = kat[pay]
    hour = 140 * k
    net_hour = hour * (1 - 0.15 - 0.00759)
    ek = net_hour * 20 * 4
    defl = ref / cpi[pay]
    rows.append(
        dict(
            p=f"{p.year}-{'1' if p.month == 1 else '2'}",
            maas=round(sal[p]),
            saat=round(hour, 2),
            ek=round(ek),
            top=round(sal[p] + ek),
            r_maas=round(sal[p] * defl),
            r_top=round((sal[p] + ek) * defl),
            r_asg=round(asg[pay] * defl),
        )
    )
for r in rows:
    print(r)
json.dump(rows, open(r"C:\veri-ham\analiz\2026_09_24\ogretmen.json", "w"))
