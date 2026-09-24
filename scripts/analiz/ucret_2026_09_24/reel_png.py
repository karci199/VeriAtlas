import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
d = json.load(open("reel_analizler.json"))
BLUE, INK, MUTED, GRID = "#2a78d6", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, axs = plt.subplots(2, 2, figsize=(13, 9), facecolor="white")
tr = lambda v: f"{v:,.0f}".replace(",", ".")
def panel(ax, title, xs, ys, note_idx=(), fmt=tr, unit=""):
    ax.plot(xs, ys, color=BLUE, lw=2, marker="o", ms=4)
    for i in note_idx:
        ax.annotate(fmt(ys[i]) + unit, (xs[i], ys[i]), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9, color=INK)
    ax.set_title(title, loc="left", fontsize=11.5, color=INK)
    ax.grid(axis="y", color=GRID); ax.set_ylim(0, max(ys) * 1.18)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: tr(v)))
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED); ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2)); ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v)}"))
k = d["konut"]; xs = sorted(int(y) for y in k)
ys = [k[str(y)][0] for y in xs]; panel(axs[0][0], "Konut m² değeri, reel (2025 TL)", xs, ys, [0, xs.index(2019), xs.index(2023), len(xs) - 1])
ys = [k[str(y)][1] for y in xs]; panel(axs[0][1], "100 m² konut = kaç aylık net asgari ücret", xs, ys, [0, xs.index(2019), xs.index(2022), len(xs) - 1], unit=" ay")
m = d["mevduat"]; xs = sorted(int(y) for y in m); ys = [m[str(y)][0] for y in xs]
panel(axs[1][0], "Kişi başı banka mevduatı, reel (2025 TL)", xs, ys, [0, xs.index(2019), xs.index(2023), len(xs) - 1])
v = d["vergi"]; xs = sorted(int(y) for y in v); ys = [v[str(y)] for y in xs]
panel(axs[1][1], "Kişi başı vergi tahsilatı, reel (2025 TL)", xs, ys, [0, xs.index(2019), len(xs) - 1])
fig.suptitle("Nominalde görünmeyen: yıllara göre reel değerler", x=0.01, ha="left", fontsize=14, color=INK)
fig.text(0.01, 0.01, "Hepsi TÜİK TÜFE yıllık ortalamasıyla 2025 fiyatlarına çevrildi. Konut: TCMB değerleme m² fiyatı (satış değil; 2026 = ilk iki çeyrek). "
         "Mevduat: TBB, bankalar arası hariç, döviz TL karşılığıyla.\nVergi: Muhasebat genel bütçe vergi tahsilatı. Nüfus: TÜİK ADNKS. Asgari ücret: ÇSGB net, yıllık ortalama.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.04, 1, 0.96)); fig.savefig("reel_analizler.png", dpi=150)
