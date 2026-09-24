import csv
import datetime as dt

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

S = "C:/veri-ham/analiz/2026-09-24/"
c = duckdb.connect("C:/veri/warehouse.duckdb", read_only=True)
q = lambda s: {r[0]: r[1] for r in c.sql(s).fetchall()}
ufe = q("select period_start, value from fact where indicator_id='ppi_domestic' and dims='ppi_domestic_item=tufe1yi_t1'")
t03 = q("select period_start, value from fact where indicator_id='cpi_2003'")
t94 = q("select period_start, value from fact where indicator_id='cpi_province_1994' and area_level='country'")


def yoy(s, d):
    p = d.replace(year=d.year - 1)
    return (s[d] / s[p] - 1) * 100 if d in s and p in s else None


rows = []
d = dt.date(1996, 1, 1)
while d <= dt.date(2026, 8, 1):
    t = yoy(t03, d) if d.year >= 2004 else yoy(t94, d)  # each year-on-year inside one base
    u = yoy(ufe, d)
    if t is not None and u is not None:
        rows.append((d, u, t, u - t))
    d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
with open(S + "ufe_tufe_aylik.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["ay", "ufe_yillik_pct", "tufe_yillik_pct", "fark_puan"])
    for d, u, t, g in rows:
        w.writerow([d.strftime("%Y-%m")] + [f"{x:.2f}".replace(".", ",") for x in (u, t, g)])
print(len(rows), rows[0][0], rows[-1][0])
for d, u, t, g in rows:
    if d.month in (1, 7) and d.year in (2003, 2004):
        print("base check", d, round(u, 1), round(t, 1))
mx = max(rows, key=lambda r: r[3]); mn = min(rows, key=lambda r: r[3])
print("max fark", mx, "min fark", mn)
print("son 12", [(d.strftime('%Y-%m'), round(u, 1), round(t, 1), round(g, 1)) for d, u, t, g in rows[-12:]])
pos = sum(1 for r in rows if r[3] > 0)
print("ÜFE>TÜFE ay sayısı", pos, "/", len(rows))
import collections
yr = collections.defaultdict(list)
for d, u, t, g in rows:
    yr[d.year].append(g)
print({y: round(sum(v) / len(v), 1) for y, v in yr.items()})
# cumulative since 2004-01: index ratio
u0, t0 = ufe[dt.date(2003, 12, 1)], t03[dt.date(2003, 12, 1)]
print("2003-12 -> 2026-08 kat: ÜFE", round(ufe[dt.date(2026, 8, 1)] / u0, 1), "TÜFE", round(t03[dt.date(2026, 8, 1)] / t0, 1))

BLUE, ORANGE, RED, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#e34948", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 9), height_ratios=[1.6, 1], sharex=True, facecolor="white")
xs = [r[0] for r in rows]
a1.plot(xs, [r[1] for r in rows], color=ORANGE, lw=1.8, label="Yİ-ÜFE (üretici), yıllık %")
a1.plot(xs, [r[2] for r in rows], color=BLUE, lw=1.8, label="TÜFE (tüketici), yıllık %")
a1.set_title("Üretici ve tüketici enflasyonu, yıllık % (aylık, 1996–2026)", loc="left", fontsize=13, color=INK, pad=10)
a1.legend(loc="upper center", frameon=False)
for d0, dy in [(mx[0], 8)]:
    r = next(r for r in rows if r[0] == d0)
    a1.annotate(f"{d0.strftime('%m/%Y')}: ÜFE %{r[1]:.0f}, TÜFE %{r[2]:.0f}", (d0, r[1]), xytext=(-10, -4), textcoords="offset points", ha="right", fontsize=9, color=INK)
a2.bar(xs, [r[3] for r in rows], width=25, color=[ORANGE if r[3] > 0 else BLUE for r in rows])
a2.axhline(0, color=MUTED, lw=1)
a2.set_title("Makas: ÜFE − TÜFE (yüzde puan). Turuncu: üretici maliyeti tüketiciden hızlı artıyor", loc="left", fontsize=11, color=INK)
for a in (a1, a2):
    a.grid(axis="y", color=GRID)
    for s in ("top", "right", "left"):
        a.spines[s].set_visible(False)
    a.tick_params(colors=MUTED)
a2.xaxis.set_major_locator(mdates.YearLocator(2))
a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.text(0.01, 0.005, "Kaynak: TÜİK via TCMB EVDS. Yİ-ÜFE genel (bie_tufe1yi). TÜFE 1996–2003: 1994=100, 2004'ten: 2003=100; her yıllık değişim tek bazın içinde hesaplandı.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.02, 1, 1))
fig.savefig(S + "ufe_tufe_makas.png", dpi=150)
