import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
f = lambda s: float(s.replace(",", "."))
rows = [(r[0], f(r[6])) for r in list(csv.reader(open("asgari_ucret_usd_6ay.csv", encoding="utf-8-sig"), delimiter=";"))[1:]]
BLUE, RED, INK, MUTED, GRID = "#2a78d6", "#e34948", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
note = "1996-II yalnız Ağu–Ara, 2026-II yalnız Tem–Ağu. Kaynak: ÇSGB net asgari ücret, TCMB EVDS aylık ort. USD kuru, FRED CPIAUCSL (2025 dolarına)."
def axis(ax, labels):
    idx = [i for i, p in enumerate(labels) if p.endswith("-I")]
    ax.set_xticks(idx, [labels[i][:4] for i in idx], rotation=90, fontsize=8.5, color=MUTED)
    ax.grid(axis="y", color=GRID, lw=1, zorder=0)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED)
# 1) level
fig, ax = plt.subplots(figsize=(13, 6.2), facecolor="white")
v = [r[1] for r in rows]
ax.bar(range(len(rows)), v, width=0.8, color=BLUE, zorder=2)
for i, (p, x) in enumerate(rows):
    if p in ("2001-II", "2008-I", "2013-I", "2016-I", "2018-II", "2022-I", "2026-I", "2026-II"):
        ax.annotate(f"{x:.0f}", (i, x), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=8.5, color=INK)
axis(ax, [r[0] for r in rows]); ax.set_ylabel("$ / ay (2025 doları)", color=MUTED)
ax.set_title("Net asgari ücret, reel dolar – 6 aylık ortalama (2025 doları)", loc="left", fontsize=13, color=INK, pad=12)
fig.text(0.01, 0.01, "Her çubuk bir yarıyıl (Oca–Haz, Tem–Ara); etiketler yılın ilk yarısı. " + note, fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig("asgari_usd_reel_6ay.png", dpi=150); plt.close(fig)
# 2) change vs previous half
ch = [(rows[i][0], (rows[i][1] / rows[i - 1][1] - 1) * 100) for i in range(1, len(rows))]
fig, ax = plt.subplots(figsize=(13, 6.2), facecolor="white")
ax.bar(range(len(ch)), [c for _, c in ch], width=0.8, color=[BLUE if c >= 0 else RED for _, c in ch], zorder=2)
ax.axhline(0, color=MUTED, lw=1)
for i, (p, c) in enumerate(ch):
    if abs(c) >= 15:
        ax.annotate(f"{c:+.0f}%", (i, c), xytext=(0, 4 if c > 0 else -12), textcoords="offset points", ha="center", fontsize=8.5, color=INK)
axis(ax, [p for p, _ in ch]); ax.set_ylabel("Önceki yarıyıla göre %", color=MUTED)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:+.0f}%"))
ax.set_title("Net asgari ücret, reel dolar – bir önceki 6 aylık döneme göre değişim", loc="left", fontsize=13, color=INK, pad=12)
fig.text(0.01, 0.01, "Mavi artış, kırmızı düşüş; ±%15'i aşanlar etiketli. " + note, fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig("asgari_usd_reel_degisim_6ay.png", dpi=150)
for p, c in ch: print(p, round(c, 1))
