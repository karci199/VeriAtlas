import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
d = json.load(open("alim_gucu_yillik.json"))
L = {"0111301": "Ekmek", "0111101": "Pirinç", "0111501": "Makarna", "0112201": "Dana eti", "0114101": "Süt", "0114401": "Beyaz peynir",
     "0114501": "Yumurta", "0115302": "Ayçiçek yağı", "0117122": "Domates", "0117201": "Patates", "0117146": "Kuru soğan",
     "0118101": "Toz şeker", "0121201": "Çay", "0722001": "Benzin", "0452201": "Tüp gaz", "1110106": "Döner", "0411101": "Kira (TÜİK ort.)"}
U = {"0111301": "kg", "0111101": "kg", "0111501": "kg", "0112201": "kg", "0114101": "lt", "0114401": "kg", "0114501": "adet", "0115302": "lt",
     "0117122": "kg", "0117201": "kg", "0117146": "kg", "0118101": "kg", "0121201": "kg", "0722001": "lt", "0452201": "tüp", "1110106": "porsiyon", "0411101": "ay"}
g = d["2025"]["reel_2026ag"] / d["2003"]["reel_2026ag"]
items = sorted(L, key=lambda k: d["2025"][k] / d["2003"][k])
BLUE, RED, INK, MUTED, GRID = "#2a78d6", "#e34948", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, ax = plt.subplots(figsize=(12, 8), facecolor="white")
for i, k in enumerate(items):
    kat = d["2025"][k] / d["2003"][k]
    ax.barh(i, kat, color=BLUE if kat >= g else RED, height=0.7, zorder=2)
    fmt = (lambda v: f"{v:,.0f}".replace(",", ".")) if d["2025"][k] >= 10 else (lambda v: f"{v:.1f}".replace(".", ","))
    ax.text(kat + 0.05, i, f"{kat:.1f}".replace(".", ",") + f" kat   ({fmt(d['2003'][k])} → {fmt(d['2025'][k])} {U[k]})", va="center", fontsize=9, color=INK, zorder=4, bbox=dict(fc="white", ec="none", pad=1))
ax.axvline(g, color=INK, lw=1.2, ls="--", zorder=1)
ax.text(g, len(items) - 0.2, f" Genel alım gücü (TÜFE ile reel ücret): {g:.1f} kat".replace(".", ","), fontsize=9, color=INK, va="bottom")
ax.set_yticks(range(len(items)), [L[k] for k in items], fontsize=10, color=INK)
ax.set_xlim(0, max(d["2025"][k] / d["2003"][k] for k in items) * 1.55)
ax.grid(axis="x", color=GRID, lw=1, zorder=0)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.tick_params(colors=MUTED)
ax.set_xlabel("Net asgari ücretle alınabilen miktar, 2025 / 2003 (kat)", color=MUTED)
ax.set_title("Asgari ücretin alım gücü: 2003'e göre 2025'te kaç kat fazla alıyor?", loc="left", fontsize=13, color=INK, pad=12)
fig.text(0.01, 0.012, "Kırmızı: genel alım gücünden az artan (göreli pahalanan) ürünler. Yıllık ortalamalar. Fiyatlar: TÜİK madde ortalama fiyatları (2003–Nis 2022), "
         "sonrası aynı ürünün TÜFE alt endeksiyle taşındı (tahmin).\nNet asgari ücret: ÇSGB. Kira TÜİK'in kiracı ortalamasıdır, piyasa ilanı değildir.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig("asgari_alim_gucu_2003_2025.png", dpi=150)
