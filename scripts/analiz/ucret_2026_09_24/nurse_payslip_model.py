"""Nurse 9/1 payslip rebuilt from official parameters (coefficients, 1550 side-payment points, 94% special service, 100% extra payment); validated against the salary robot 2024-2026; plus 60 hours of duty pay.

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


k = ser("civil_servant_pay_coefficient", "pay_coefficient=monthly")
t = ser("civil_servant_pay_coefficient", "pay_coefficient=base_salary")
y = ser("civil_servant_pay_coefficient", "pay_coefficient=side_payment")
asgb = ser("minimum_wage", "wage_measure=gross")
cpi = ser("cpi_2003", "")
# robot memur records for tax-rate calibration
rob = {}
for line in open(
    r"C:\veri-ham\ucret\memur\memurlarnet\salaries.jsonl", encoding="utf-8"
):
    r = json.loads(line)
    rob[(r["profile"], r["date"][:7])] = r


def item(r, name):
    for n, o, v in r["items"]:
        if n.startswith(name):
            return v


def nurse(pay, gosterge=620, E=100, Y=1550, O=94):
    K, T, YK = k[pay], t[pay], y[pay]
    H = 9500 * K
    g = gosterge * K
    tb = 1000 * T
    yan = Y * YK
    oz = O / 100 * H
    ek = E / 100 * H
    sey = 15965 * K if pay >= dt.date(2023, 7, 1) else 0
    gross = g + tb + yan + oz + ek + sey
    prim = 0.14 * (g + tb + oz)
    matrah = g + tb + yan - prim
    m = rob[("memur", pay.strftime("%Y-%m"))]
    agi = item(m, "Asgari Geçim") or 0
    gv_m = -(item(m, "Gelir Vergisi") or 0)
    mat_m = item(m, "Gelir Vergisi Matrahı")
    if pay < dt.date(2022, 1, 1):
        rate = (gv_m + agi) / mat_m
        gv = rate * matrah - agi
        damga = 0.00759 * gross
    else:
        gv = 0.0
        damga = 0.00759 * max(0, gross - asgb[pay])
    return gross - prim - gv - damga


# validate vs robot hemsire
for key, r in sorted(rob.items()):
    if key[0] == "hemsire":
        pay = dt.date(int(key[1][:4]), int(key[1][5:]), 1)
        print("valid", key[1], r["net"], round(nurse(pay), 2))
# 2019-07 anchor 8/1 (gosterge 740), published 4281 incl AGI
print(
    "anchor 2019-08 8/1:",
    round(nurse(dt.date(2019, 8, 1), gosterge=740), 2),
    "E90:",
    round(nurse(dt.date(2019, 8, 1), gosterge=740, E=90), 2),
)
ref = cpi[dt.date(2026, 8, 1)]
out = []
for yr in range(2014, 2027):
    for mo in (2, 8):
        pay = dt.date(yr, mo, 1)
        if pay > dt.date(2026, 8, 1):
            continue
        n = nurse(pay)
        saat = 90 * k[pay]
        nob = saat * 60 * (1 - 0.00759)
        out.append(
            dict(
                p=f"{yr}-{1 if mo == 2 else 2}",
                net=round(n),
                saat=round(saat, 2),
                nob=round(nob),
                top=round(n + nob),
                r_top=round((n + nob) * ref / cpi[pay]),
                r_net=round(n * ref / cpi[pay]),
            )
        )
for o in out:
    print(o)
json.dump(out, open(r"C:\veri-ham\analiz\2026_09_24\nurse.json", "w"))
