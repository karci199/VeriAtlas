import csv

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

S = "C:/veri-ham/analiz/2026-09-24/"
A = "read_csv('C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/areas_tr.csv')"
c = duckdb.connect("C:/veri/warehouse.duckdb", read_only=True)
q = lambda s: c.sql(s).fetchall()
SEX = "split_part(split_part(dims,'sex=',2),';',1)"
pop = {(n, y, s): v for n, y, s, v in q(f"""select a.name_tr, year(period_start), {SEX}, sum(value) from fact f join {A} a on a.area_id=f.area_id
 where indicator_id='population' and f.area_level='province'
 and try_cast(regexp_extract(dims, 'age=(\\d+)', 1) as int) between 18 and 60 group by all""")}
ins = {(n, y, s, sch): v for n, y, s, sch, v in q(f"""select a.name_tr, year(period_start), {SEX}, split_part(split_part(dims,'scheme=',2),';',1), sum(value)
 from fact f join {A} a on a.area_id=f.area_id where indicator_id='sgk_compulsory_insured' and f.area_level='province' and year(period_start)>=2012 group by all""")}
provs = sorted({k[0] for k in ins})
years = sorted({k[1] for k in ins})
I = lambda n, y, s, sch=None: sum(v for (a, b, c_, d), v in ins.items() if a == n and b == y and c_ == s and (sch is None or d == sch))
tr = {}
print("yil  erkek%  kadin%  (4a erkek, 4a kadin)  kadin/erkek")
rows = []
for y in years:
    r = {"yil": y}
    for s in ("male", "female"):
        num = sum(I(n, y, s) for n in provs)
        den = sum(pop.get((n, y, s), 0) for n in provs)
        r[s] = num / den * 100
        r[s + "_4a"] = sum(I(n, y, s, "4a") for n in provs) / den * 100
        r[s + "_4b"] = sum(I(n, y, s, "4b") for n in provs) / den * 100
        r[s + "_4c"] = sum(I(n, y, s, "4c") for n in provs) / den * 100
        r[s + "_n"] = num
        r[s + "_pop"] = den
    rows.append(r)
    print(y, f"{r['male']:.1f} {r['female']:.1f} ({r['male_4a']:.1f}, {r['female_4a']:.1f}) {r['female'] / r['male']:.2f}  sayı E {r['male_n']/1e6:.2f} K {r['female_n']/1e6:.2f}")
with open(S + "istihdam_oran_turkiye.csv", "w", newline="", encoding="utf-8-sig") as f:
    k = ["yil", "male", "female", "male_4a", "female_4a", "male_4b", "female_4b", "male_4c", "female_4c", "male_n", "female_n", "male_pop", "female_pop"]
    w = csv.writer(f, delimiter=";")
    w.writerow(["yil", "erkek_pct", "kadin_pct", "erkek_4a_pct", "kadin_4a_pct", "erkek_4b_pct", "kadin_4b_pct", "erkek_4c_pct", "kadin_4c_pct",
                "erkek_sigortali", "kadin_sigortali", "erkek_nufus_18_60", "kadin_nufus_18_60"])
    for r in rows:
        w.writerow([r["yil"]] + [f"{r[x]:.2f}".replace(".", ",") for x in k[1:]])
Y = years[-1]
pr = []
for n in provs:
    e = I(n, Y, "male") / pop[(n, Y, "male")] * 100
    k_ = I(n, Y, "female") / pop[(n, Y, "female")] * 100
    e0 = I(n, 2012, "male") / pop[(n, 2012, "male")] * 100
    k0 = I(n, 2012, "female") / pop[(n, 2012, "female")] * 100
    pr.append((n, e, k_, k_ / e, e0, k0))
with open(S + "istihdam_oran_iller.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["il", f"erkek_{Y}", f"kadin_{Y}", "kadin_erkek_orani", "erkek_2012", "kadin_2012"])
    for r in sorted(pr, key=lambda r: -r[2]):
        w.writerow([r[0]] + [f"{x:.2f}".replace(".", ",") for x in r[1:]])
srt = lambda i, rev=True, n=6: [(r[0], round(r[i], 1)) for r in sorted(pr, key=lambda r: r[i], reverse=rev)[:n]]
print("kadın en yüksek", srt(2), "en düşük", srt(2, False))
print("erkek en yüksek", srt(1), "en düşük", srt(1, False))
print("kadın/erkek en düşük", srt(3, False), "en yüksek", srt(3))
print("kadın 2012->2025 artış (puan) en çok", sorted(((r[0], round(r[2] - r[5], 1)) for r in pr), key=lambda t: -t[1])[:6])

BLUE, PINK, INK, MUTED, GRID = "#2a78d6", "#e87ba4", "#0b0b0b", "#898781", "#e1e0d9"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, ax = plt.subplots(figsize=(11, 6), facecolor="white")
for s, col, lab in (("male", BLUE, "Erkek"), ("female", PINK, "Kadın")):
    ys = [r[s] for r in rows]
    ax.plot(years, ys, color=col, lw=2.4, marker="o", ms=4)
    for i in (0, len(years) - 1):
        ax.annotate(f"%{ys[i]:.1f}".replace(".", ","), (years[i], ys[i]), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9, color=INK)
    ax.annotate(lab, (years[-1], ys[-1]), xytext=(30, 0), textcoords="offset points", va="center", fontsize=10, color=INK)
ax.set_ylim(0, 80)
ax.set_xlim(years[0] - 0.5, years[-1] + 1.5)
ax.set_title("Kayıtlı (SGK'lı) çalışanların 18–60 yaş nüfusuna oranı", loc="left", fontsize=12.5, color=INK)
ax.grid(axis="y", color=GRID)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"%{v:.0f}"))
ax.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(range(years[0], years[-1] + 1, 2)))
for s_ in ("top", "right", "left"):
    ax.spines[s_].set_visible(False)
ax.tick_params(colors=MUTED)
fig.text(0.01, 0.01, "Pay: 4/a + 4/b + 4/c zorunlu sigortalı (yıl sonu, SGK). Payda: 18–60 yaş nüfus (TÜİK ADNKS). Payda yaş aralığının dışında çalışanlar "
         "da var; oran yaklaşıktır.\nKayıt dışı çalışanlar dahil değildir; il: sigortalının kayıtlı olduğu iş yeri ili.", fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(S + "istihdam_oran_turkiye.png", dpi=150)
plt.close(fig)

ps = sorted(pr, key=lambda r: r[2])
fig, ax = plt.subplots(figsize=(10, 17), facecolor="white")
for i, (n, e, k_, *_rest) in enumerate(ps):
    ax.plot([k_, e], [i, i], color=GRID, lw=2, zorder=1)
    ax.scatter([e], [i], color=BLUE, s=28, zorder=2)
    ax.scatter([k_], [i], color=PINK, s=28, zorder=2)
ax.set_yticks(range(len(ps)), [f"{r[0]}  (K %{r[2]:.0f} / E %{r[1]:.0f})" for r in ps], fontsize=8.5)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"%{v:.0f}"))
ax.grid(axis="x", color=GRID)
ax.scatter([], [], color=BLUE, label="Erkek")
ax.scatter([], [], color=PINK, label="Kadın")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False)
ax.set_title(f"Kayıtlı çalışanların 18–60 yaş nüfusuna oranı, illere göre, {Y} (kadın oranına göre sıralı)", loc="left", fontsize=11.5, color=INK, pad=24)
for s_ in ("top", "right", "left"):
    ax.spines[s_].set_visible(False)
fig.text(0.01, 0.004, "Kaynak: SGK zorunlu sigortalı (4/a+4/b+4/c), TÜİK ADNKS. İl, iş yeri kaydının ilidir; Ankara ve İstanbul genel müdürlükler yüzünden şişik olabilir.", fontsize=7.5, color=MUTED)
fig.tight_layout(rect=(0, 0.01, 1, 1))
fig.savefig(S + "istihdam_oran_iller.png", dpi=130)

# ---- yearly by province
R = {}
for n in provs:
    for y in years:
        if (n, y, "female") in pop:
            R[(n, y)] = (I(n, y, "male") / pop[(n, y, "male")] * 100, I(n, y, "female") / pop[(n, y, "female")] * 100)
with open(S + "istihdam_oran_iller_yillik.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["il"] + [f"kadin_{y}" for y in years] + [f"erkek_{y}" for y in years])
    for n in sorted(provs, key=lambda n: -R[(n, Y)][1]):
        w.writerow([n] + [f"{R[(n, y)][1]:.1f}".replace(".", ",") for y in years] + [f"{R[(n, y)][0]:.1f}".replace(".", ",") for y in years])
chg = sorted(((n, R[(n, Y)][1] - R[(n, 2012)][1], R[(n, 2012)][1], R[(n, Y)][1], R[(n, Y)][0] - R[(n, 2012)][0]) for n in provs), key=lambda t: -t[1])
print("kadın artış puan 2012->2025 en çok", [(n, round(d, 1), round(a, 1), round(b, 1)) for n, d, a, b, _ in chg[:10]])
print("en az", [(n, round(d, 1), round(a, 1), round(b, 1)) for n, d, a, b, _ in chg[-8:]])
rel = sorted(((n, R[(n, Y)][1] / R[(n, 2012)][1]) for n in provs), key=lambda t: -t[1])
print("kadın oran kat artış en çok", [(n, round(k, 2)) for n, k in rel[:8]])
c20 = sorted(((n, R[(n, Y)][1] - R[(n, 2020)][1]) for n in provs), key=lambda t: -t[1])
print("2020->2025 en çok", [(n, round(d, 1)) for n, d in c20[:8]], "en az", [(n, round(d, 1)) for n, d in c20[-5:]])
gapc = sorted(((n, (R[(n, Y)][1] / R[(n, Y)][0]) - (R[(n, 2012)][1] / R[(n, 2012)][0])) for n in provs), key=lambda t: -t[1])
print("kadın/erkek oranı en çok iyileşen", [(n, round(d, 2)) for n, d in gapc[:6]])
print("erkek artış puan en çok", sorted(((n, round(e, 1)) for n, *_r, e in chg), key=lambda t: -t[1])[:5], "en çok düşen", sorted(((n, round(e, 1)) for n, *_r, e in chg), key=lambda t: t[1])[:5])

cs = sorted(chg, key=lambda t: t[1])
fig, ax = plt.subplots(figsize=(10, 17), facecolor="white")
for i, (n, d, a, b, _) in enumerate(cs):
    ax.plot([a, b], [i, i], color=GRID, lw=2.2, zorder=1)
    ax.scatter([a], [i], color="#c3c2b7", s=22, zorder=2)
    ax.scatter([b], [i], color=PINK, s=30, zorder=3)
ax.set_yticks(range(len(cs)), [f"{n}  +{d:.1f} puan".replace(".", ",") for n, d, *_ in cs], fontsize=8.5)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"%{v:.0f}"))
ax.grid(axis="x", color=GRID)
ax.scatter([], [], color="#c3c2b7", label="2012")
ax.scatter([], [], color=PINK, label=str(Y))
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False)
ax.set_title(f"Kadın kayıtlı istihdam oranı (18–60 yaş kadın nüfusuna), 2012 → {Y}, artışa göre sıralı", loc="left", fontsize=11.5, color=INK, pad=24)
for s_ in ("top", "right", "left"):
    ax.spines[s_].set_visible(False)
fig.text(0.01, 0.004, "Kaynak: SGK zorunlu sigortalı kadın (4/a+4/b+4/c), TÜİK ADNKS. İl, iş yeri kaydının ilidir.", fontsize=7.5, color=MUTED)
fig.tight_layout(rect=(0, 0.01, 1, 1))
fig.savefig(S + "kadin_istihdam_artis_iller.png", dpi=130)
