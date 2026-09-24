import csv
import datetime as dt
import json

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

S = "C:/veri-ham/analiz/2026-09-24/"
LABEL = {
    "memur": "Memur (lisans, 9/1)", "memur_lise": "Memur (lise, 13/1)", "ogretmen": "Öğretmen", "polis": "Polis",
    "hemsire": "Hemşire", "ebe": "Ebe", "tabip_pratisyen": "Pratisyen hekim", "muhendis": "Mühendis", "avukat": "Avukat (kamu)",
    "imam": "İmam-hatip", "hakim": "Hâkim (aday sonrası)", "arastirma_gorevlisi": "Araştırma görevlisi", "veteriner": "Veteriner hekim",
    "eczaci": "Eczacı", "zabita": "Zabıta", "itfaiyeci": "İtfaiyeci", "infaz_koruma": "İnfaz koruma memuru", "hizmetli": "Hizmetli",
    "sofor": "Şoför", "teknisyen": "Teknisyen", "memur_kidemli": "Memur", "ogretmen_kidemli": "Öğretmen", "polis_kidemli": "Polis",
    "hemsire_kidemli": "Hemşire", "tabip_uzman_kidemli": "Uzman hekim (döner sermaye hariç)", "muhendis_kidemli": "Mühendis",
    "imam_kidemli": "İmam-hatip", "sube_muduru_kidemli": "Şube müdürü", "profesor_kidemli": "Profesör", "hakim_kidemli": "Hâkim (1. sınıf)",
}
rows = [json.loads(l) for l in open("C:/veri-ham/ucret/memur/memurlarnet/salaries.jsonl", encoding="utf-8")]
c = duckdb.connect("C:/veri/warehouse.duckdb", read_only=True)
cpi = {r[0]: r[1] for r in c.sql("select period_start, value from fact where indicator_id='cpi_2003'").fetchall()}
BASE = sum(v for k, v in cpi.items() if k.year == 2025) / 12
aw = json.load(open("C:/veri-ham/ucret/asgari/asgari_ucret_donemler.json", encoding="utf-8"))
aw.append({"start": "01.01.2026", "end": "31.12.2026", "net": 28075.5})


def P(s):
    y, m, d = int(s[6:]), int(s[3:5]), int(s[:2])
    while True:
        try:
            return dt.date(y, m, d)
        except ValueError:
            d -= 1


def asg(d):
    return next(r["net"] for r in aw if P(r["start"]) <= d <= P(r["end"]))


tab = {}
for r in rows:
    it = {a: v for a, _, v in r["items"]}
    net = r["net"] + (it.get("Asgari Geçim İndirimi") or 0)  # AGİ was paid on top until 2021
    d = dt.date.fromisoformat(r["date"])
    m = d.replace(day=1)
    tab.setdefault(r["profile"], {})[r["date"][:7]] = {
        "net": net, "reel": net * BASE / cpi[m], "kat": net / asg(d),
        "seyyanen": it.get("İlave Seyyanen Ödenek") or 0,
    }
periods = sorted({p for v in tab.values() for p in v})
with open(S + "memur_maaslari_6ay.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["profil", "unvan", "donem", "net_tl_agi_dahil", "net_reel_2025_tl", "net_asgari_ucret_kati"])
    for k in LABEL:
        for p in periods:
            if p in tab.get(k, {}):
                x = tab[k][p]
                w.writerow([k, LABEL[k], p] + [f"{v:.2f}".replace(".", ",") for v in (x["net"], x["reel"], x["kat"])])
first, last = periods[0], periods[-1]
print("dönemler", first, last, len(periods))
for k in LABEL:
    v = tab.get(k)
    if not v:
        print("EKSIK", k)
        continue
    peak = max(v, key=lambda p: v[p]["reel"])
    first, last = min(v), max(v)
    print(f"{LABEL[k]:34s} {'kıdemli' if 'kidemli' in k else 'giriş':7s} {first} net {v[first]['net']:9.0f} -> {v[last]['net']:9.0f} | reel {v[first]['reel']:7.0f} -> {v[last]['reel']:7.0f} ({(v[last]['reel'] / v[first]['reel'] - 1) * 100:+.0f}%) zirve {peak} {v[peak]['reel']:.0f} | asgari katı {v[first]['kat']:.2f} -> {v[last]['kat']:.2f}")
json.dump(tab, open(S + "memur_tab.json", "w"), ensure_ascii=False)

# charts
BLUE, INK, MUTED, GRID = "#2a78d6", "#0b0b0b", "#898781", "#e1e0d9"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
xs = [dt.date(int(p[:4]), int(p[5:]), 15) for p in periods]


def chart(keys, field, title, ylabel, fname, fmt, note):
    fig, ax = plt.subplots(figsize=(13, 6.8), facecolor="white")
    ends = []
    for i, k in enumerate(keys):
        ys = [tab[k][p][field] if p in tab[k] else None for p in periods]
        ax.plot(xs, ys, color=CAT[i], lw=2, marker="o", ms=3.5)
        ends.append([ys[-1], ys[-1], f"{LABEL[k]}  {fmt(ys[-1])}", CAT[i]])
    allv = [e[0] for e in ends]
    gap = (max(allv) - min(allv)) * 0.06 or 1
    ends.sort(key=lambda e: e[0])
    for j in range(1, len(ends)):  # push labels apart, keep order
        ends[j][1] = max(ends[j][1], ends[j - 1][1] + gap)
    for v, ypos, lab, col in ends:
        ax.annotate(lab, (xs[-1], v), xytext=(xs[-1] + dt.timedelta(days=120), ypos), textcoords="data", va="center", fontsize=9, color=INK,
                    arrowprops=dict(arrowstyle="-", color=col, lw=0.8))
    ax.set_title(title, loc="left", fontsize=13, color=INK, pad=12)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.grid(axis="y", color=GRID)
    ax.set_xlim(xs[0], dt.date(xs[-1].year + 3, 6, 1))
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt(v)))
    fig.text(0.01, 0.01, note, fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(S + fname, dpi=150)
    plt.close(fig)


tl = lambda v: f"{v:,.0f}".replace(",", ".")
kat = lambda v: f"{v:.2f}".replace(".", ",")
NOTE = ("Şubat ve Ağustos maaşları; bekâr, çocuksuz, sendikasız, BES yok, Ankara. 2014–2021 AGİ net maaşa eklendi. Kaynak: memurlar.net maaş robotu "
        "(resmî katsayılarla), TÜFE: TÜİK, asgari ücret: ÇSGB.\nEk ders, nöbet, döner sermaye, toplu sözleşme ikramiyesi ve aile yardımı dahil değil.")
entry = ["memur", "ogretmen", "polis", "imam", "eczaci", "memur_lise", "hizmetli"]
senior = ["memur_kidemli", "ogretmen_kidemli", "polis_kidemli", "muhendis_kidemli", "tabip_uzman_kidemli", "sube_muduru_kidemli", "profesor_kidemli", "hakim_kidemli"]
chart(entry, "reel", "Yeni başlayan kamu görevlisi net maaşı, reel (2025 TL)", "TL / ay (2025 fiyatları)", "memur_giris_reel.png", tl, NOTE)
chart(senior, "reel", "Kıdemli (1/4, 25 yıl) kamu görevlisi net maaşı, reel (2025 TL)", "TL / ay (2025 fiyatları)", "memur_kidemli_reel.png", tl, NOTE)
chart(entry, "kat", "Yeni başlayan kamu görevlisi: net maaş, net asgari ücretin kaç katı", "kat", "memur_giris_asgari_kati.png", kat, NOTE)
chart(senior, "kat", "Kıdemli kamu görevlisi: net maaş, net asgari ücretin kaç katı", "kat", "memur_kidemli_asgari_kati.png", kat, NOTE)
