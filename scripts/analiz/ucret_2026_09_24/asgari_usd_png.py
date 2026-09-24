import csv
import datetime as dt
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

H = "C:/veri-ham/ucret/"
S = "C:/veri-ham/analiz/2026-09-24/"
rows = json.load(open(H + "asgari/asgari_ucret_donemler.json", encoding="utf-8"))
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


usd = {}
for it in json.load(open(H + "kur/evds_usd_aylik.json"))["items"]:
    y, m = it["Tarih"].split("-")
    if it["TP_DK_USD_A_YTL"]:
        usd[dt.date(int(y), int(m), 1)] = float(it["TP_DK_USD_A_YTL"])
cpi = {}
for r in csv.DictReader(open(H + "kur/fred_CPIAUCSL.csv")):
    if r["CPIAUCSL"].strip() not in ("", "."):
        cpi[dt.date.fromisoformat(r["observation_date"])] = float(r["CPIAUCSL"])
# October 2025 was never published (US government shutdown): midpoint of Sep and Nov.
o = dt.date(2025, 10, 1)
if o not in cpi:
    cpi[o] = (cpi[dt.date(2025, 9, 1)] + cpi[dt.date(2025, 11, 1)]) / 2
b25 = sum(v for k, v in cpi.items() if k.year == 2025) / 12

out = []
d = dt.date(1996, 8, 1)
while d <= dt.date(2026, 8, 1):
    n = net(d)
    out.append((d, usd[d], n, n / usd[d], n / usd[d] * b25 / cpi[d]))
    d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)

with open(S + "asgari_ucret_usd_aylik.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["ay", "usd_kuru_aylik_ort", "net_asgari_tl", "net_asgari_usd", "net_asgari_usd_reel_2025"])
    for d, k, n, u, r in out:
        w.writerow([d.strftime("%Y-%m"), f"{k:.4f}".replace(".", ","), f"{n:.2f}".replace(".", ","), f"{u:.1f}".replace(".", ","), f"{r:.1f}".replace(".", ",")])

BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED})
fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 8.5), height_ratios=[3, 1.4], sharex=True, facecolor="white")
xs = [t[0] for t in out]
a1.plot(xs, [t[4] for t in out], color=BLUE, lw=2, label="Reel (2025 doları, ABD TÜFE ile)")
a1.plot(xs, [t[3] for t in out], color=ORANGE, lw=1.5, label="Cari dolar")
AY = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
pick = lambda a, b, f: f((t for t in out if a <= t[0] <= b), key=lambda t: t[4])
marks = [(pick(dt.date(1996, 1, 1), dt.date(2003, 1, 1), min), -38), (pick(dt.date(2003, 1, 1), dt.date(2017, 1, 1), max), 14),
         (pick(dt.date(2018, 1, 1), dt.date(2023, 1, 1), min), -38), (pick(dt.date(2023, 1, 1), dt.date(2026, 8, 1), max), 14),
         (out[-1], -38)]
for t, dy in marks:
    d, v = t[0], t[4]
    a1.plot([d], [v], "o", color=BLUE, ms=6, mec="white", mew=1.5, zorder=5)
    a1.annotate(f"{AY[d.month - 1]} {d.year}: {v:.0f} $", (d, v), xytext=(0, dy), textcoords="offset points", ha="center", fontsize=9, color=INK)
a1.set_title("Net asgari ücret, dolar (aylık, Ağu 1996 – Ağu 2026)", loc="left", fontsize=13, color=INK, pad=12)
a1.set_ylabel("$ / ay", color=MUTED)
a1.grid(axis="y", color=GRID, lw=1)
a1.set_ylim(0, max(t[4] for t in out) * 1.18)
a1.legend(loc="upper left", frameon=False)
a2.plot(xs, [t[1] for t in out], color=BLUE, lw=2)
a2.set_yscale("log")
a2.set_title("Aylık ortalama USD/TL kuru (log ölçek)", loc="left", fontsize=11, color=INK)
a2.grid(axis="y", color=GRID, lw=1)
a2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
a2.xaxis.set_major_locator(mdates.YearLocator(2))
a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
for a in (a1, a2):
    for s in ("top", "right", "left"):
        a.spines[s].set_visible(False)
    a.tick_params(colors=MUTED)
fig.text(0.01, 0.005, "Kaynak: ÇSGB (net asgari ücret, 16 yaş üstü), TCMB EVDS (TP.DK.USD.A.YTL aylık ortalama), FRED CPIAUCSL. "
         "Ekim 2025 ABD TÜFE'si yayımlanmadı, Eylül–Kasım ortalaması kullanıldı.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.02, 1, 1))
fig.savefig(S + "asgari_ucret_usd.png", dpi=150)
print(len(out), out[0], out[-1])
