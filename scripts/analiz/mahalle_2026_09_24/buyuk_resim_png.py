"""Charts for buyuk_resim.py. Needs matplotlib: uv run --no-project --with matplotlib --with polars python ..."""

import matplotlib
import polars as pl

matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = "C:/veri-ham/analiz/mahalle/"
L = pl.read_csv(D + "gelir_merdiveni.csv", separator=";")
P = pl.read_csv(D + "iller.csv", separator=";")
R = pl.read_csv(D + "faiz_satis.csv", separator=";")
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#898781", "#e1e0d9"
Q = ["#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#0d366b"]  # sequential blue, poorest -> richest
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
tr = lambda v, d=1: f"{v:.{d}f}".replace(".", ",")


def clean(a):
    a.grid(axis="y", color=GRID)
    for s in ("top", "right", "left"):
        a.spines[s].set_visible(False)
    a.tick_params(colors=MUTED)


# 1) income ladder
panels = [("universite", "Üniversite mezunu payı (%)"), ("cocuk_0_14", "0–14 yaş payı (%)"), ("hane", "Ortalama hane büyüklüğü (kişi)"),
          ("bosanmis", "Boşanmışların payı (%)"), ("kiraci", "Kiracı hane payı (%)"), ("gida_payi", "Harcamada gıdanın payı (%)")]
fig, axs = plt.subplots(2, 3, figsize=(15, 8.5), facecolor="white")
x = L["decile"].to_list()
for a, (col, t) in zip(axs.flat, panels):
    ys = L[col].to_list()
    a.bar(x, ys, color=BLUE, width=0.7)
    for xi, yi in zip(x, ys):
        if xi in (1, 10):
            a.annotate(tr(yi), (xi, yi), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9, color=INK)
    a.set_title(t, loc="left", fontsize=11, color=INK)
    a.set_xticks(x, [str(i) for i in x])
    a.set_ylim(0, max(ys) * 1.18)
    clean(a)
for a in axs[1]:
    a.set_xlabel("Mahalle gelir dilimi (1 = en yoksul %10 nüfus, 10 = en zengin %10)", color=MUTED, fontsize=9)
fig.suptitle("Gelir merdiveni: Türkiye'nin 40 bin mahallesi, nüfus ağırlıklı on dilim", x=0.01, ha="left", fontsize=14, color=INK)
fig.text(0.01, 0.01, "Mahalleler Endeksa hane geliri tahminine göre sıralandı; her dilimde ~8,4 milyon kişi. Eğitim, yaş, medeni hal: 2024 ADNKS (Endeksa aracılığıyla). "
         "Gelir, kiracı payı ve harcama: Endeksa modeli.\nEn zengin dilimin ortalama hane geliri en yoksulun 10,4 katı. Endeksa verisi araştırma kopyasıdır.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.05, 1, 0.95))
fig.savefig(D + "buyuk_resim_1_gelir_merdiveni.png", dpi=140)
plt.close(fig)

# 2) rates, inequality, SGK
fig = plt.figure(figsize=(16, 10), facecolor="white")
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.15])
a1 = fig.add_subplot(gs[0, 0])
a1.plot(R["yil"], R["konut_faizi"], color=INK, lw=2.2, marker="o", ms=4)
for y in (2020, 2024):
    v = R.filter(pl.col("yil") == y)["konut_faizi"][0]
    a1.annotate(f"%{tr(v)}", (y, v), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=9)
a1.set_title("Konut kredisi faizi, yıllık ortalama (%) — EVDS", loc="left", fontsize=11, color=INK)
clean(a1)
a2 = fig.add_subplot(gs[0, 1])
lab = ["En yoksul %20", "2.", "3.", "4.", "En zengin %20"]
for i in range(5):
    d = R  # 2019 is null: the line breaks there instead of bridging 2018-2020
    a2.plot(d["yil"], d[f"ipotek_q{i+1}"], color=Q[i], lw=2.2 if i in (0, 4) else 1.4, marker="o", ms=3.5)
    if i in (0, 4):
        a2.annotate(lab[i], (d["yil"][-1], d[f"ipotek_q{i+1}"][-1]), xytext=(6, -6 if i == 0 else 6), textcoords="offset points", va="center", fontsize=8.5, color=INK)
a2.set_xlim(2009.5, 2027)
a2.set_title("İpotekli satış payı (%), mahalle gelir dilimine göre (beşte bir; 2019 yok)", loc="left", fontsize=11, color=INK)
clean(a2)
a3 = fig.add_subplot(gs[1, 0])
a3.scatter(P["gelir_ort"] / 1000, P["gini"], s=P["nufus"] / 60000 + 12, color=BLUE, alpha=0.75, edgecolor="white", lw=0.8)
lab_set = {"İSTANBUL", "ŞANLIURFA", "DİYARBAKIR", "ANKARA", "İZMİR", "YALOVA", "BİLECİK", "BAYBURT"}
for r in P.iter_rows(named=True):
    if r["il"] in lab_set:
        a3.annotate(r["il"].title(), (r["gelir_ort"] / 1000, r["gini"]), xytext=(5, 3), textcoords="offset points", fontsize=8.5, color=INK)
a3.set_xlabel("İl ortalama mahalle hane geliri (Endeksa, bin TL)", color=MUTED)
a3.set_title("Şehir içi uçurum: mahalleler arası gelir Gini'si (daire = nüfus)", loc="left", fontsize=11, color=INK)
clean(a3)
a4 = fig.add_subplot(gs[1, 1])
a4.scatter(P["sgk"], P["gelir_ort"] / 1000, s=40, color=ORANGE, alpha=0.8, edgecolor="white", lw=0.8)
import numpy as np

x, y = np.log(P["sgk"].to_numpy()), np.log(P["gelir_ort"].to_numpy())
b = np.polyfit(x, y, 1)
res = y - (b[0] * x + b[1])
order = np.argsort(res)
for i in [j for j in list(order[:6]) + list(order[-5:]) if P["il"][int(j)] in ("AĞRI", "HAKKARİ", "İSTANBUL", "ANKARA", "EDİRNE", "SİNOP", "BURDUR")]:
    a4.annotate(P["il"][int(i)].title(), (P["sgk"][int(i)], P["gelir_ort"][int(i)] / 1000), xytext=(5, 3), textcoords="offset points", fontsize=8.5, color=INK)
xs = np.linspace(x.min(), x.max(), 50)
a4.plot(np.exp(xs), np.exp(b[0] * xs + b[1]) / 1000, color=MUTED, lw=1, ls="--")
a4.set_xlabel("SGK'ya bildirilen ortalama günlük kazanç, 2024 (TL)", color=MUTED)
a4.set_title("Mahalle geliri ile kayıtlı ücret: çizginin üstü, ücretine göre daha varlıklı iller", loc="left", fontsize=11, color=INK)
clean(a4)
fig.suptitle("Büyük resim: mahalleden il ve makroya", x=0.01, ha="left", fontsize=14, color=INK)
fig.text(0.01, 0.008, "Kaynak: Endeksa mahalle demografisi (araştırma kopyası; konut satışları tapu kökenli, ipotek tanımı TÜİK'inkinden geniş, 2019 ipotek sütunu yok), "
         "TCMB EVDS konut kredisi faizi (akım), SGK il yıllığı. Gini: mahalle ortalamaları arası, hane içi eşitsizliği içermez.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.03, 1, 0.96))
fig.savefig(D + "buyuk_resim_2_makro.png", dpi=140)
