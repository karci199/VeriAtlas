import csv

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

S = "C:/veri-ham/analiz/2026-09-24/"
A = "read_csv('C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/areas_tr.csv')"
c = duckdb.connect("C:/veri/warehouse.duckdb", read_only=True)
q = lambda s: c.sql(s).fetchall()
SCH = "split_part(split_part(dims,'scheme=',2),';',1)"
# compulsory insured (active) by scheme; 4/b split into self-employed / agriculture / muhtar
ins = q(f"""select a.name_tr, year(period_start), {SCH},
  case when dims like '%agriculture%' then 'tarim' when dims like '%self_employed%' then 'esnaf' when dims like '%muhtar%' then 'muhtar' else '' end,
  sum(value) from fact f join {A} a on a.area_id=f.area_id where indicator_id='sgk_compulsory_insured' and f.area_level='province' group by all""")
pen = q(f"""select a.name_tr, year(period_start), {SCH}, sum(value) from fact f join {A} a on a.area_id=f.area_id
  where indicator_id='sgk_social_security_coverage' and f.area_level='province' and dims like 'coverage_component=pensioners%' group by all""")
pop = {(n, y): v for n, y, v in q(f"""select a.name_tr, year(period_start), sum(value) from fact f join {A} a on a.area_id=f.area_id
  where indicator_id='population' and f.area_level='province' group by 1,2""")}
D, P = {}, {}
for n, y, s, sub, v in ins:
    D.setdefault((n, y), {}).setdefault(s, 0)
    D[(n, y)][s] += v
    if sub:
        D[(n, y)][sub] = D[(n, y)].get(sub, 0) + v
for n, y, s, v in pen:
    P.setdefault((n, y), {})[s] = v
years = sorted({y for _, y in D if all(k in D[(_, y)] for k in ("4a", "4b", "4c"))})
provs = sorted({n for n, _ in D})
tr = lambda y, k: sum(D[(n, y)].get(k, 0) for n in provs if (n, y) in D)
trp = lambda y, k: sum(P[(n, y)].get(k, 0) for n in provs if (n, y) in P)
trpop = lambda y: sum(pop.get((n, y), 0) for n in provs)
print("yil  4a  4b(esnaf,tarim)  4c  | pay%  | 100 kisiye aktif | aktif/emekli 4a 4b 4c")
rows = []
for y in years:
    a, b, cc = tr(y, "4a"), tr(y, "4b"), tr(y, "4c")
    t = a + b + cc
    pa, pb, pc = trp(y, "4a"), trp(y, "4b"), trp(y, "4c")
    r = [y, a, b, tr(y, "esnaf"), tr(y, "tarim"), cc, a / t * 100, b / t * 100, cc / t * 100, t / trpop(y) * 100 if trpop(y) else None,
         a / pa if pa else None, b / pb if pb else None, cc / pc if pc else None, pa, pb, pc]
    rows.append(r)
    print(y, f"{a/1e6:.2f} {b/1e6:.2f} ({r[3]/1e6:.2f},{r[4]/1e6:.2f}) {cc/1e6:.2f} | {r[6]:.1f} {r[7]:.1f} {r[8]:.1f} | {r[9] or 0:.1f} |",
          " ".join(f"{x:.2f}" if x else "-" for x in r[10:13]), f"emekli {pa/1e6:.2f} {pb/1e6:.2f} {pc/1e6:.2f}")
with open(S + "sgk_4abc_turkiye.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["yil", "4a", "4b", "4b_esnaf", "4b_tarim", "4c", "4a_pay", "4b_pay", "4c_pay", "aktif_100_kisiye", "aktif_emekli_4a", "aktif_emekli_4b", "aktif_emekli_4c", "emekli_4a", "emekli_4b", "emekli_4c"])
    for r in rows:
        w.writerow([r[0]] + [("" if x is None else f"{x:.2f}".replace(".", ",")) for x in r[1:]])
Y = years[-1]
pr = []
for n in provs:
    d = D[(n, Y)]
    t = d["4a"] + d["4b"] + d["4c"]
    pp = P.get((n, Y), {})
    pr.append({"il": n, "4a": d["4a"], "4b": d["4b"], "4c": d["4c"], "esnaf": d.get("esnaf", 0), "tarim": d.get("tarim", 0), "t": t,
               "a%": d["4a"] / t * 100, "b%": d["4b"] / t * 100, "c%": d["4c"] / t * 100, "tarim%": d.get("tarim", 0) / t * 100,
               "per100": t / pop[(n, Y)] * 100, "ae": t / sum(pp.values()) if pp else None, "ae_c": d["4c"] / pp["4c"] if pp.get("4c") else None,
               "ae_b": d["4b"] / pp["4b"] if pp.get("4b") else None})
with open(S + "sgk_4abc_iller_2025.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    k = ["il", "4a", "4b", "esnaf", "tarim", "4c", "t", "a%", "b%", "c%", "tarim%", "per100", "ae", "ae_b", "ae_c"]
    w.writerow(k)
    for r in sorted(pr, key=lambda r: -r["t"]):
        w.writerow([r["il"]] + [("" if r[x] is None else f"{r[x]:.2f}".replace(".", ",")) for x in k[1:]])
top = lambda key, n=6, rev=True: [(r["il"], round(r[key], 1)) for r in sorted(pr, key=lambda r: r[key] or 0, reverse=rev)[:n]]
print("4c payı en yüksek", top("c%"), "en düşük", top("c%", rev=False))
print("4b payı en yüksek", top("b%"), "tarım payı", top("tarim%"))
print("4a payı en yüksek", top("a%"), "en düşük", top("a%", rev=False))
print("100 kişiye aktif sigortalı en yüksek", top("per100"), "en düşük", top("per100", rev=False))
print("aktif/emekli en düşük", top("ae", rev=False), "en yüksek", top("ae"))
print("4b aktif/emekli en düşük", top("ae_b", rev=False))
# change 2012->2025 by province in 4c and 4b
ch = sorted(((n, D[(n, Y)]["4b"] / D[(n, 2012)]["4b"], D[(n, Y)]["4c"] / D[(n, 2012)]["4c"], D[(n, Y)]["4a"] / D[(n, 2012)]["4a"]) for n in provs), key=lambda t: t[1])
print("4b 2012->2025 en çok düşen", [(n, round(b, 2)) for n, b, _, _ in ch[:6]], "en çok artan", [(n, round(b, 2)) for n, b, _, _ in ch[-5:]])
ch = sorted(ch, key=lambda t: -t[3])
print("4a en çok artan", [(n, round(a, 2)) for n, _, _, a in ch[:6]], "en az", [(n, round(a, 2)) for n, _, _, a in ch[-6:]])

# charts
BLUE, ORANGE, AQUA, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 6), facecolor="white")
for i, (lab, col) in enumerate([("4/a (işçi)", BLUE), ("4/b (esnaf, çiftçi)", ORANGE), ("4/c (memur)", AQUA)]):
    ys = [r[1 + [0, 1, 4][i]] / 1e6 for r in rows]
    a1.plot(years, ys, color=col, lw=2.2, marker="o", ms=3.5)
    a1.annotate(f"{lab} {ys[-1]:.2f} mn".replace(".", ","), (years[-1], ys[-1]), xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
    ae = [r[10 + i] for r in rows]
    a2.plot(years, ae, color=col, lw=2.2, marker="o", ms=3.5)
    a2.annotate(f"{lab} {ae[-1]:.2f}".replace(".", ","), (years[-1], ae[-1]), xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
a1.set_title("Aktif zorunlu sigortalı sayısı (milyon)", loc="left", fontsize=11.5, color=INK)
a2.set_title("Aktif sigortalı / emekli (aylık alan) oranı", loc="left", fontsize=11.5, color=INK)
a2.axhline(1, color=MUTED, lw=1, ls="--")
for a in (a1, a2):
    a.set_xlim(years[0] - 0.5, years[-1] + 4.5)
    a.grid(axis="y", color=GRID)
    for s in ("top", "right", "left"):
        a.spines[s].set_visible(False)
    a.tick_params(colors=MUTED)
    a.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(range(years[0], years[-1] + 1, 2)))
    a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
fig.text(0.01, 0.01, "Kaynak: SGK istatistik yıllıkları (yıl sonu). Aktif: zorunlu sigortalı; emekli: sosyal güvenlik kapsamındaki aylık/gelir alanlar. "
         "4/b: esnaf, tarım ve muhtar.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(S + "sgk_4abc_yillar.png", dpi=150)
plt.close(fig)

pr_s = sorted(pr, key=lambda r: r["a%"])
fig, ax = plt.subplots(figsize=(11, 17), facecolor="white")
ys = range(len(pr_s))
ax.barh(ys, [r["a%"] for r in pr_s], color=BLUE, height=0.75, label="4/a işçi")
ax.barh(ys, [r["b%"] for r in pr_s], left=[r["a%"] for r in pr_s], color=ORANGE, height=0.75, label="4/b esnaf, çiftçi")
ax.barh(ys, [r["c%"] for r in pr_s], left=[r["a%"] + r["b%"] for r in pr_s], color=AQUA, height=0.75, label="4/c memur")
ax.set_yticks(list(ys), [f"{r['il']}  ({r['t']/1000:,.0f} bin)".replace(",", ".") for r in pr_s], fontsize=8.5)
ax.set_xlim(0, 100)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"%{v:.0f}"))
for i, r in enumerate(pr_s):
    ax.text(r["a%"] + r["b%"] + r["c%"] / 2, i, f"{r['c%']:.0f}", va="center", ha="center", fontsize=7, color="white")
    ax.text(r["a%"] / 2, i, f"{r['a%']:.0f}", va="center", ha="center", fontsize=7, color="white")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False)
ax.set_title(f"İllere göre aktif sigortalıların dağılımı, {Y} (4/a işçi payına göre sıralı)", loc="left", fontsize=12, color=INK, pad=28)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(colors=INK)
fig.text(0.01, 0.005, "Kaynak: SGK. Parantez içinde toplam aktif zorunlu sigortalı. İl, sigortalının kayıtlı olduğu iş yeri/SGK il müdürlüğüdür, ikamet değil "
         "(genel müdürlükler Ankara ve İstanbul'u büyütür).", fontsize=7.5, color=MUTED)
fig.tight_layout(rect=(0, 0.01, 1, 1))
fig.savefig(S + "sgk_4abc_iller.png", dpi=130)
