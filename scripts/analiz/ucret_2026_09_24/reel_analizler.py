import json

import duckdb

S = "C:/veri-ham/analiz/2026-09-24/"
AREAS = "C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/areas_tr.csv"
c = duckdb.connect("C:/veri/warehouse.duckdb", read_only=True)
q = lambda s: c.sql(s).fetchall()
cpi = {y: v for y, v in q("select year(period_start), avg(value) from fact where indicator_id='cpi_2003' group by 1")}
R = lambda v, y: v * cpi[2025] / cpi[y]  # to 2025 TL
pop = {y: v for y, v in q("select year(period_start), sum(value) from fact where indicator_id='population' and area_level='country' group by 1")}
aw = json.load(open("C:/veri-ham/ucret/asgari/asgari_ucret_donemler.json", encoding="utf-8"))
out = {}

# 1) housing m2 (valuation) - yearly mean of quarters, real; m2 per yearly-avg net min wage
hp = {y: v for y, v in q("select year(period_start), avg(value) from fact where indicator_id='housing_unit_price' and area_level='country' group by 1")}
netavg = {}
import datetime as dt


def P(s):
    y, m, d = int(s[6:]), int(s[3:5]), int(s[:2])
    while True:
        try:
            return dt.date(y, m, d)
        except ValueError:
            d -= 1


aw.append({"start": "01.01.2026", "end": "31.12.2026", "net": 28075.5})
for y in range(2003, 2027):
    ms = [dt.date(y, m, 15) for m in range(1, 13)]
    vals = [next(r["net"] for r in aw if P(r["start"]) <= d <= P(r["end"])) for d in ms]
    netavg[y] = sum(vals) / 12
print("== KONUT m2 (değerleme) ==")
for y in sorted(hp):
    if y in cpi:
        print(y, round(hp[y]), "reel", round(R(hp[y], y)), "m2/asgari", round(netavg[y] / hp[y], 3), "asgari kaç ayda 100m2", round(100 * hp[y] / netavg[y]))
out["konut"] = {y: [R(hp[y], y), 100 * hp[y] / netavg[y]] for y in hp if y in cpi}
# province real change 2010 -> 2025
pr = q(f"""select a.name_tr, year(period_start) y, avg(value) from fact f join read_csv('{AREAS}') a on a.area_id=f.area_id
 where indicator_id='housing_unit_price' and f.area_level='province' and year(period_start) in (2013,2025) group by 1,2""")
d = {}
for n, y, v in pr:
    d.setdefault(n, {})[y] = R(v, y)
ch = sorted(((n, v[2025] / v[2013]) for n, v in d.items() if 2013 in v and 2025 in v), key=lambda t: -t[1])
print("il reel kat 2013->2025 en yüksek", [(n, round(x, 2)) for n, x in ch[:6]], "en düşük", [(n, round(x, 2)) for n, x in ch[-6:]])

# 2) new company average capital (real)
cap = {y: v for y, v in q("select year(period_start), sum(value) from fact where indicator_id='companies_opened_capital' and dims='company_capital_item=ac2_top_s' group by 1")}
cnt = {y: v for y, v in q("select year(period_start), sum(value) from fact where indicator_id='companies_opened_closed' and dims='company_count_item=ac2_top_a' group by 1")}
print("== YENİ ŞİRKET ORT. SERMAYE ==")
for y in sorted(cap):
    if y in cpi and y in cnt:
        print(y, int(cnt[y]), "ort nominal", round(cap[y] / cnt[y]), "reel 2025", round(R(cap[y] / cnt[y], y)), "toplam reel mlyr", round(R(cap[y], y) / 1e9, 1))
out["sermaye"] = {y: R(cap[y] / cnt[y], y) for y in cap if y in cpi and y in cnt and y <= 2025}

# 3) deposits per capita real (excluding interbank), fx share
dep = q("""select year(period_start), sum(value) filter (where dims<>'deposit_type=interbank'), sum(value) filter (where dims in ('deposit_type=foreign_currency','deposit_type=gold'))
 from fact where indicator_id='bank_deposits' group by 1 order by 1""")
print("== MEVDUAT ==")
out["mevduat"] = {}
for y, t, fx in dep:
    if y in cpi and y in pop:
        print(y, "kişi başı reel", round(R(t, y) / pop[y]), "döviz+altın payı %", round(fx / t * 100, 1))
        out["mevduat"][y] = [R(t, y) / pop[y], fx / t * 100]

# 4) budget tax revenue per capita real
bt = q("select year(period_start), sum(value) from fact where indicator_id='budget_revenue_by_province' and dims='budget_measure=collected;revenue_line=tax' group by 1 order by 1")
print("== VERGİ ==")
out["vergi"] = {}
for y, v in bt:
    if y in cpi and y in pop:
        print(y, "kişi başı reel vergi", round(R(v * 1000, y) / pop[y]))
        out["vergi"][y] = R(v * 1000, y) / pop[y]
# 5) province GDP per capita TRY real, 2004->2024 growth
g = q(f"""select a.name_tr, year(period_start), value from fact f join read_csv('{AREAS}') a on a.area_id=f.area_id
 where indicator_id='province_gdp_per_capita' and dims='gdp_currency=try;gdp_price=current' and f.area_level='province' and year(period_start) in (2004,2024)""")
d = {}
for n, y, v in g:
    d.setdefault(n, {})[y] = R(v, y)
ch = sorted(((n, v[2024] / v[2004], v[2024]) for n, v in d.items() if len(v) == 2), key=lambda t: -t[1])
print("== İL GSYH kişi başı reel kat 2004->2024 ==", [(n, round(x, 2)) for n, x, _ in ch[:8]], [(n, round(x, 2)) for n, x, _ in ch[-8:]])
tr = {y: v for y, v in q("select year(period_start), value from fact where indicator_id='province_gdp_per_capita' and dims='gdp_currency=try;gdp_price=current' and area_level='country'")}
print("TR kişi başı GSYH reel", {y: round(R(tr[y], y)) for y in sorted(tr) if y in cpi})
out["gsyh"] = {y: R(tr[y], y) for y in tr if y in cpi}
json.dump({k: {str(a): b for a, b in v.items()} for k, v in out.items()}, open(S + "reel_analizler.json", "w"))
