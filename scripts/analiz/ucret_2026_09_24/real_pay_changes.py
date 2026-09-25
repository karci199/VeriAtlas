"""CPI-deflated changes 2005/2014 -> 2026 for titles and pay parameters; semiannual civil-servant real pay.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import duckdb

c = duckdb.connect()
f = r"C:\veri\public\fact.parquet"
cpi = dict(
    c.sql(
        f"select period_start, value from '{f}' where indicator_id='cpi_2003' and area_id='TR'"
    ).fetchall()
)
import datetime as dt


def v(ind, dims, d):
    r = c.sql(
        f"select value from '{f}' where indicator_id='{ind}' and dims='{dims}' and period_start='{d}' and area_id='TR'"
    ).fetchall()
    return r[0][0] if r else None


def real(ind, dims, a, b, ca=None, cb=None):
    x, y = v(ind, dims, a), v(ind, dims, b)
    pa = cpi[dt.date.fromisoformat(ca or a)]
    pb = cpi[dt.date.fromisoformat(cb or b)]
    return round(x, 2), round(y, 2), round((y / pb) / (x / pa) * 100 - 100, 1)


print("cpi last", max(cpi), cpi[max(cpi)])
L = [
    (
        "memur 9/1",
        "civil_servant_salary",
        "civil_servant_profile=memur;salary_item=net",
        "2014-01-01",
        "2026-07-01",
    ),
    (
        "ogretmen",
        "civil_servant_salary",
        "civil_servant_profile=ogretmen;salary_item=net",
        "2014-01-01",
        "2026-07-01",
    ),
    (
        "hizmetli",
        "civil_servant_salary",
        "civil_servant_profile=hizmetli;salary_item=net",
        "2014-01-01",
        "2026-07-01",
    ),
    (
        "uzman hekim kidemli",
        "civil_servant_salary",
        "civil_servant_profile=tabip_uzman_kidemli;salary_item=net",
        "2014-01-01",
        "2026-07-01",
    ),
    (
        "profesor kidemli",
        "civil_servant_salary",
        "civil_servant_profile=profesor_kidemli;salary_item=net",
        "2014-01-01",
        "2026-07-01",
    ),
    (
        "hakim kidemli",
        "civil_servant_salary",
        "civil_servant_profile=hakim_kidemli;salary_item=net",
        "2014-01-01",
        "2026-07-01",
    ),
    ("asgari net", "minimum_wage", "wage_measure=net", "2014-01-01", "2026-07-01"),
    ("asgari net 2005", "minimum_wage", "wage_measure=net", "2005-01-01", "2026-07-01"),
    ("en yuksek memur", "highest_civil_servant_salary", "", "2005-01-01", "2026-07-01"),
    ("kidem tavani", "severance_pay_ceiling", "", "2005-01-01", "2026-07-01"),
    (
        "es yardimi",
        "civil_servant_family_allowance",
        "family_member=spouse",
        "2005-01-01",
        "2026-07-01",
    ),
    (
        "cocuk yardimi",
        "civil_servant_family_allowance",
        "family_member=child",
        "2005-01-01",
        "2026-07-01",
    ),
    (
        "399 tavan",
        "contract_staff_pay_ceiling",
        "contract_staff_type=soe_decree_399",
        "2005-01-01",
        "2026-07-01",
    ),
]
for n, i, d, a, b in L:
    print(n, real(i, d, a, b, cb="2026-07-01"))
# 2022 dip
for n, i, d in [
    ("memur", "civil_servant_salary", "civil_servant_profile=memur;salary_item=net"),
    ("asgari", "minimum_wage", "wage_measure=net"),
]:
    for yr in [
        "2014-01-01",
        "2018-01-01",
        "2021-07-01",
        "2022-01-01",
        "2022-07-01",
        "2023-01-01",
        "2023-07-01",
        "2024-01-01",
        "2025-01-01",
        "2026-01-01",
        "2026-07-01",
    ]:
        x = v(i, d, yr)
        print(
            n,
            yr,
            round(x),
            round(x / cpi[dt.date.fromisoformat(yr)] * cpi[dt.date(2026, 7, 1)]),
        )
# SBB real 2003-2017 annual avg cpi
acpi = dict(
    c.sql(
        f"select year(period_start), avg(value) from '{f}' where indicator_id='cpi_2003' and area_id='TR' group by 1"
    ).fetchall()
)
for g in ["civil_servant", "public_worker", "private_worker", "minimum_wage"]:
    r = dict(
        c.sql(
            f"select year(period_start), value from '{f}' where indicator_id='average_wage_by_sector' and dims='wage_measure=net;employee_group={g}'"
        ).fetchall()
    )
    last = max(r)
    print(
        "SBB",
        g,
        round(r[2003]),
        round(r[last]),
        last,
        round((r[last] / acpi[last]) / (r[2003] / acpi[2003]) * 100 - 100, 1),
    )
