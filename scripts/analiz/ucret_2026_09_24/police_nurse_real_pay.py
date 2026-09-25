"""Police (robot net, overtime included) and nurse (robot 2024+, plus duty pay) real pay, semiannual.

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


def s(p):
    return dict(
        c.sql(
            f"select period_start, value from '{f}' where indicator_id='civil_servant_salary' and dims='civil_servant_profile={p};salary_item=net'"
        ).fetchall()
    )


pol, hem = s("polis"), s("hemsire")
kat = dict(
    c.sql(
        f"select period_start, value from '{f}' where indicator_id='civil_servant_pay_coefficient' and dims='pay_coefficient=monthly'"
    ).fetchall()
)
ogr = json.load(open(r"C:\veri-ham\analiz\2026_09_24\ogretmen.json"))
ref = cpi[dt.date(2026, 8, 1)]
out = []
for i, p in enumerate(sorted(pol)):
    pay = dt.date(p.year, p.month + 1, 1)
    d = ref / cpi[pay]
    k = kat[pay]
    r = dict(
        p=f"{p.year}-{1 if p.month == 1 else 2}",
        pol=round(pol[p]),
        r_pol=round(pol[p] * d),
        r_ogr=ogr[i]["r_top"],
    )
    if p in hem:
        saat = 90 * k
        nob = saat * 60 * (1 - 0.00759)
        r.update(
            hem=round(hem[p]),
            saat=round(saat, 2),
            nob=round(nob),
            htop=round(hem[p] + nob),
            r_hem=round(hem[p] * d),
            r_htop=round((hem[p] + nob) * d),
        )
    out.append(r)
for r in out:
    print(r)
json.dump(out, open(r"C:\veri-ham\analiz\2026_09_24\polhem.json", "w"))
