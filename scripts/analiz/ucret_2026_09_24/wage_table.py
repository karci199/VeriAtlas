"""Yearly table: teacher/police/civil-servant net pay, minimum wage, highest salary, severance ceiling, coefficient.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import json

import duckdb

c = duckdb.connect()
f = r"C:\veri\public\fact.parquet"


def s(ind, dims):
    return dict(
        c.sql(
            f"select year(period_start), value from '{f}' where indicator_id='{ind}' and dims='{dims}' and month(period_start)=1 and area_id='TR'"
        ).fetchall()
    )


ogr = s("civil_servant_salary", "civil_servant_profile=ogretmen;salary_item=net")
mem = s("civil_servant_salary", "civil_servant_profile=memur;salary_item=net")
pol = s("civil_servant_salary", "civil_servant_profile=polis;salary_item=net")
asg = s("minimum_wage", "wage_measure=net")
yuk = s("highest_civil_servant_salary", "")
kid = s("severance_pay_ceiling", "")
kat = s("civil_servant_pay_coefficient", "pay_coefficient=monthly")
ort = dict(
    c.sql(
        f"select year(period_start), value from '{f}' where indicator_id='average_wage_by_sector' and dims='wage_measure=net;employee_group=civil_servant'"
    ).fetchall()
)
rows = []
for y in range(2000, 2027):
    rows.append(
        dict(
            y=y,
            ogr=ogr.get(y),
            mem=mem.get(y),
            pol=pol.get(y),
            asg=asg.get(y),
            yuk=yuk.get(y),
            kid=kid.get(y),
            kat=kat.get(y),
            ort=ort.get(y),
        )
    )
json.dump(rows, open(r"C:\veri-ham\analiz\2026_09_24\wage_rows.json", "w"))
for r in rows:
    print(r)
print(
    c.sql(
        f"select distinct split_part(split_part(dims,';',1),'=',2) p, min(year(period_start)), max(year(period_start)), count(*)//2 from '{f}' where indicator_id='civil_servant_salary' group by 1 order by 1"
    ).fetchall()
)
