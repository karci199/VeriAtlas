import csv
import json

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

S = "C:/veri-ham/analiz/2026-09-24/"
A = "read_csv('C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/areas_tr.csv')"
c = duckdb.connect("C:/veri/warehouse.duckdb", read_only=True)
q = lambda s: c.sql(s).fetchall()
cpi = {y: v for y, v in q("select year(period_start), avg(value) from fact where indicator_id='cpi_2003' group by 1")}
R = lambda v, y: v * cpi[2025] / cpi[y]
# weights: 4/a compulsory insured by province-year (both sexes)
W = """(select area_id, year(period_start) y, sum(value) w from fact where indicator_id='sgk_compulsory_insured'
 and area_level='province' and dims like 'scheme=4a%' group by 1,2)"""
SEG = ["total", "public", "private", "male", "female", "permanent", "temporary", "seasonal"]
nat = {}
for s in SEG:
    for y, v in q(f"""select year(e.period_start), sum(e.value*w.w)/sum(w.w) from fact e join {W} w on w.area_id=e.area_id and w.y=year(e.period_start)
      where e.indicator_id='sgk_average_daily_earnings' and e.dims='earnings_segment={s}' group by 1"""):
        nat.setdefault(s, {})[y] = v * 30  # daily -> monthly (SGK counts 30 days)
aw = json.load(open("C:/veri-ham/ucret/asgari/asgari_ucret_donemler.json", encoding="utf-8"))
import datetime as dt


def P(s):
    y, m, d = int(s[6:]), int(s[3:5]), int(s[:2])
    while True:
        try:
            return dt.date(y, m, d)
        except ValueError:
            d -= 1


brut = {y: sum(next(r["brut"] for r in aw if P(r["start"]) <= dt.date(y, m, 15) <= P(r["end"])) for m in range(1, 13)) / 12 for y in range(2010, 2026)}
years = sorted(nat["total"])
print("yil  aylik_brut_cari  reel2025  asgari_brut_kati  kamu/ozel  kadin/erkek  gecici/surekli")
for y in years:
    t = nat["total"][y]
    print(y, round(t), round(R(t, y)), round(t / brut[y], 2), round(nat["public"][y] / nat["private"][y], 2),
          round(nat["female"][y] / nat["male"][y], 3), round(nat["temporary"][y] / nat["permanent"][y], 2) if y in nat["temporary"] and y in nat["permanent"] else None)
for s in SEG:
    v = nat[s]
    y0, y1 = min(v), max(v); print(s, "reel", y0, round(R(v[y0], y0)), y1, round(R(v[y1], y1)), "kat", round(R(v[y1], y1) / R(v[y0], y0), 2))
# provinces
pr = q(f"""select a.name_tr, year(period_start) y, value*30 from fact f join {A} a on a.area_id=f.area_id
 where indicator_id='sgk_average_daily_earnings' and dims='earnings_segment=total' and year(period_start) in (2010,2025)""")
d = {}
for n, y, v in pr:
    d.setdefault(n, {})[y] = R(v, y)
lst = sorted(((n, v[2025], v[2025] / v[2010]) for n, v in d.items() if len(v) == 2), key=lambda t: -t[1])
print("il 2025 reel aylik en yuksek", [(n, round(a), round(k, 2)) for n, a, k in lst[:8]])
print("en dusuk", [(n, round(a), round(k, 2)) for n, a, k in lst[-8:]])
bym = sorted(lst, key=lambda t: -t[2])
print("reel artis en cok", [(n, round(k, 2)) for n, a, k in bym[:6]], "en az", [(n, round(k, 2)) for n, a, k in bym[-6:]])
gap = q(f"""select a.name_tr, max(value) filter (where dims='earnings_segment=female')/max(value) filter (where dims='earnings_segment=male')
 from fact f join {A} a on a.area_id=f.area_id where indicator_id='sgk_average_daily_earnings' and year(period_start)=2025 group by 1 order by 2""")
print("kadin/erkek il en dusuk", [(n, round(x, 2)) for n, x in gap[:6]], "en yuksek", [(n, round(x, 2)) for n, x in gap[-6:]])
with open(S + "sgk_ucret_yillik.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["yil"] + [f"{s}_aylik_cari" for s in SEG] + [f"{s}_aylik_reel_2025" for s in SEG] + ["brut_asgari_ucret_ort"])
    for y in years:
        w.writerow([y] + [f"{nat[s].get(y, 0):.0f}" for s in SEG] + [f"{R(nat[s][y], y):.0f}" if y in nat[s] else "" for s in SEG] + [f"{brut[y]:.0f}"])

CAT = {"total": ("#0b0b0b", "Toplam"), "public": ("#2a78d6", "Kamu"), "private": ("#eb6834", "Özel"), "male": ("#1baf7a", "Erkek"), "female": ("#e87ba4", "Kadın")}
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 6.3), facecolor="white")
for s, (col, lab) in CAT.items():
    ys = [R(nat[s][y], y) for y in years]
    a1.plot(years, ys, color=col, lw=2.4 if s == "total" else 1.8, marker="o", ms=3)
    a1.annotate(f"{lab} {ys[-1]:,.0f}".replace(",", "."), (years[-1], ys[-1]), xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
a1.set_title("SGK'ya bildirilen ortalama aylık brüt kazanç, reel (2025 TL)", loc="left", fontsize=11.5, color=INK)
a1.set_xlim(2009.5, 2028.3)
a2.plot(years, [nat["total"][y] / brut[y] for y in years], color="#2a78d6", lw=2.2, marker="o", ms=4)
for y in (2010, 2016, 2021, 2023, 2025):
    v = nat["total"][y] / brut[y]
    a2.annotate(f"{v:.2f}".replace(".", ","), (y, v), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=9, color=INK)
a2.set_title("Ortalama kazanç / brüt asgari ücret (kat)", loc="left", fontsize=11.5, color=INK)
a2.set_ylim(1, 2.4)
for a in (a1, a2):
    a.grid(axis="y", color=GRID)
    for s in ("top", "right", "left"):
        a.spines[s].set_visible(False)
    a.tick_params(colors=MUTED); a.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(range(2010, 2026, 2))); a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: str(int(v))))
    a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.2f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".") if v < 10 else f"{v:,.0f}".replace(",", ".")))
fig.text(0.01, 0.01, "Kaynak: SGK istatistik yıllıkları, 4/a zorunlu sigortalıların prime esas ortalama günlük kazancı × 30; il değerleri sigortalı sayısıyla ağırlıklandırıldı. "
         "Tavan–taban arası bildirilen kazançtır, gerçek ücret değildir.\nReel: TÜİK TÜFE yıllık ortalaması. Asgari ücret: ÇSGB brüt, yıllık ortalama.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(S + "sgk_ucret.png", dpi=150)
