import csv
import datetime as dt
import json

import duckdb

S = "C:/veri-ham/analiz/2026-09-24/"
c = duckdb.connect("C:/veri/warehouse.duckdb", read_only=True)
# TÜİK average-price item -> (label, unit, 5-digit CPI (2025=100) item used after 2022-04)
ITEMS = {
    "0111301": ("Ekmek", "kg", "01113"),
    "0111101": ("Pirinç", "kg", "01111"),
    "0111501": ("Makarna", "kg", "01115"),
    "0112201": ("Dana eti", "kg", "01122"),
    "0114101": ("Süt", "lt", "01141"),
    "0114401": ("Beyaz peynir", "kg", "01145"),
    "0114501": ("Yumurta", "adet", "01148"),
    "0115302": ("Ayçiçek yağı", "lt", "01151"),
    "0117122": ("Domates", "kg", "01172"),
    "0117201": ("Patates", "kg", "01175"),
    "0117146": ("Kuru soğan", "kg", "01174"),
    "0118101": ("Toz şeker", "kg", "01181"),
    "0121201": ("Çay", "kg", "01230"),
    "0722001": ("Benzin", "lt", "07222"),
    "0452201": ("Tüp gaz", "tüp", "04522"),
    "1110106": ("Döner", "porsiyon", "11112"),
    "0411101": ("Ortalama kira", "ay", "04110"),
}
q = lambda s: c.sql(s).fetchall()
price = {}
for k, (lab, unit, new) in ITEMS.items():
    p = {r[0]: r[1] for r in q(f"select period_start, value from fact where indicator_id='average_item_price' and dims='cpi_item={k}'")}
    idx = {r[0]: r[1] for r in q(f"select period_start, value from fact where indicator_id='cpi_2025_items' and dims='cpi_2025_item=tukfiy2025_{new}'")}
    last = dt.date(2022, 4, 1)
    for m, v in idx.items():
        if m > last:
            p[m] = p[last] * v / idx[last]
    price[k] = p
cpi = {r[0]: r[1] for r in q("select period_start, value from fact where indicator_id='cpi_2003'")}

rows = json.load(open("C:/veri-ham/ucret/asgari/asgari_ucret_donemler.json", encoding="utf-8"))
rows.append({"start": "01.01.2026", "end": "31.12.2026", "net": 28075.5})


def P(s):
    y, m, d = int(s[6:]), int(s[3:5]), int(s[:2])
    while True:
        try:
            return dt.date(y, m, d)
        except ValueError:
            d -= 1


def net(d):
    x = d.replace(day=15)
    for r in rows:
        if P(r["start"]) <= x <= P(r["end"]):
            return r["net"]


months = []
d = dt.date(2003, 1, 1)
while d <= dt.date(2026, 8, 1):
    months.append(d)
    d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
# yearly averages of monthly quantities (2026: Jan-Aug)
out = {}
for y in range(2003, 2027):
    ms = [m for m in months if m.year == y]
    rec = {"net_tl": sum(net(m) for m in ms) / len(ms),
           "reel_2026ag": sum(net(m) * cpi[dt.date(2026, 8, 1)] / cpi[m] for m in ms) / len(ms)}
    for k in ITEMS:
        rec[k] = sum(net(m) / price[k][m] for m in ms) / len(ms)
    out[y] = rec
json.dump({str(y): v for y, v in out.items()}, open(S + "alim_gucu_yillik.json", "w"))
with open(S + "asgari_ucret_alim_gucu_yillik.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["yil", "net_asgari_tl_ort", "net_asgari_reel_2026ag_tl"] + [f"{ITEMS[k][0]} ({ITEMS[k][1]})" for k in ITEMS])
    for y, r in out.items():
        w.writerow([y] + [f"{r[x]:.1f}".replace(".", ",") for x in ["net_tl", "reel_2026ag"] + list(ITEMS)])
base = out[2003]
print("yil reel_endeks " + " ".join(ITEMS[k][0] for k in ITEMS))
for y in (2003, 2008, 2013, 2016, 2018, 2021, 2022, 2023, 2024, 2025, 2026):
    r = out[y]
    print(y, round(r["reel_2026ag"]), " | ".join(f"{ITEMS[k][0]} {r[k]:.1f}" for k in ITEMS))
print("\nkat 2003->2025 ve genele göre (reel ücret katı ile oran)")
g = out[2025]["reel_2026ag"] / base["reel_2026ag"]
print("genel reel kat", round(g, 2))
for k in sorted(ITEMS, key=lambda k: out[2025][k] / base[k]):
    kk = out[2025][k] / base[k]
    print(f"{ITEMS[k][0]:14s} 2003 {base[k]:8.1f}  2025 {out[2025][k]:8.1f}  kat {kk:5.2f}  genele göre {kk / g:5.2f}  2026 {out[2026][k]:8.1f}")
