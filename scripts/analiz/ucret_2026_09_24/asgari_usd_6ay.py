import csv, datetime as dt, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
S = "./"
rows = list(csv.reader(open("asgari_ucret_usd_aylik.csv", encoding="utf-8-sig"), delimiter=";"))[1:]
f = lambda s: float(s.replace(",", "."))
g = collections.OrderedDict()
for ay, kur, tl, u, r in rows:
    y, m = int(ay[:4]), int(ay[5:])
    k = (y, 1 if m <= 6 else 2)
    g.setdefault(k, []).append((f(kur), f(tl), f(u), f(r)))
out = []
for (y, h), v in g.items():
    n = len(v)
    out.append((f"{y}-{'I' if h == 1 else 'II'}", n, sum(x[0] for x in v) / n, v[0][1], v[-1][1], sum(x[2] for x in v) / n, sum(x[3] for x in v) / n))
with open("asgari_ucret_usd_6ay.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh, delimiter=";")
    w.writerow(["donem", "ay_sayisi", "usd_kuru_ort", "net_asgari_tl_donem_basi", "net_asgari_tl_donem_sonu", "net_asgari_usd_ort", "net_asgari_usd_reel_2025_ort"])
    for p, n, k, a, b, u, r in out:
        w.writerow([p, n] + [f"{x:.2f}".replace(".", ",") for x in (k, a, b, u, r)])
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, ax = plt.subplots(figsize=(13, 6.5), facecolor="white")
x = range(len(out))
ax.bar(x, [t[6] for t in out], width=0.8, color=BLUE, label="Reel (2025 doları, 6 aylık ortalama)", zorder=2)
ax.plot(x, [t[5] for t in out], color=ORANGE, lw=1.8, marker="o", ms=3, label="Cari dolar (6 aylık ortalama)", zorder=3)
for i, t in enumerate(out):
    if t[6] in (max(o[6] for o in out),) or t[0] in ("2001-II", "2008-II", "2013-I", "2016-I", "2022-I", "2024-I", "2026-I", "2026-II"):
        ax.annotate(f"{t[6]:.0f}", (i, t[6]), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=8.5, color=INK)
ax.set_xticks(list(x)[1::2], [t[0][:4] for t in out][1::2], rotation=90, fontsize=8.5, color=MUTED)
ax.set_ylabel("$ / ay", color=MUTED)
ax.grid(axis="y", color=GRID, lw=1, zorder=0)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(colors=MUTED)
ax.legend(loc="upper left", frameon=False)
ax.set_title("Net asgari ücret, dolar – 6 aylık dönemler (1996-II – 2026-II)", loc="left", fontsize=13, color=INK, pad=12)
fig.text(0.01, 0.01, "Her çubuk bir yarıyıl (Oca–Haz, Tem–Ara); etiketler her yılın ilk yarısı. 1996-II yalnız Ağu–Ara, 2026-II yalnız Tem–Ağu. "
         "Kaynak: ÇSGB, TCMB EVDS aylık ort. USD kuru, FRED CPIAUCSL.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig("asgari_ucret_usd_6ay.png", dpi=150)
for t in out: print(t[0], t[1], round(t[2], 3), round(t[5]), round(t[6]))
