"""Big picture: Endeksa neighbourhoods x warehouse (SGK, TÜİK, EVDS).

Reads C:/veri-ham/analiz/mahalle/mahalle.parquet (mahalle_tablo.py) and a warehouse copy.
Prints the numbers and writes CSVs next to the parquet; charts in buyuk_resim_png.py.
"""

import sys

import duckdb
import numpy as np
import polars as pl

sys.stdout.reconfigure(encoding="utf-8")
D = "C:/veri-ham/analiz/mahalle/"
WH = "C:/veri-ham/yedek/2026-09-24b/warehouse.duckdb"  # copy: the live one is being reloaded
m = pl.read_parquet(D + "mahalle.parquet")
v = m.filter(pl.col("valid") & pl.col("income").is_not_null() & (pl.col("income") > 0))
print("gelirli mahalle", v.height, "nüfus", int(v["pop"].sum()))

# ---------------- A. income ladder: population-weighted deciles over Türkiye
v = v.sort("income").with_columns(cum=pl.col("pop").cum_sum() / pl.col("pop").sum())
v = v.with_columns(decile=(pl.col("cum") * 10).ceil().clip(1, 10).cast(pl.Int8))
W = lambda c: (pl.col(c) * pl.col("pop")).sum() / pl.col("pop").filter(pl.col(c).is_not_null()).sum()
ladder = v.group_by("decile").agg(
    pl.len().alias("mahalle"), pl.col("pop").sum().alias("nufus"),
    pl.col("income").min().alias("gelir_min"), W("income").alias("gelir"),
    W("uni_share").alias("universite"), W("low_edu_share").alias("okuryazar_degil_diplomasiz"),
    W("child_share").alias("cocuk_0_14"), W("elder_share").alias("yasli_60"),
    W("hh_size").alias("hane"), W("divorced_share").alias("bosanmis"), W("never_married_share").alias("hic_evlenmemis"),
    W("owner_share").alias("ev_sahibi"), W("renter_share").alias("kiraci"), W("car_ratio").alias("otomobil"),
W("density").alias("yogunluk"),
    ((pl.col("exp_food") * pl.col("pop")).sum() / (pl.col("expense") * pl.col("pop")).sum() * 100).alias("gida_payi"),
    ((pl.col("exp_education") * pl.col("pop")).sum() / (pl.col("expense") * pl.col("pop")).sum() * 100).alias("egitim_payi"),
    ((pl.col("exp_restaurant") * pl.col("pop")).sum() / (pl.col("expense") * pl.col("pop")).sum() * 100).alias("restoran_payi"),
    ((pl.col("saving") * pl.col("pop")).sum() / (pl.col("income") * pl.col("pop")).sum() * 100).alias("tasarruf_orani"),
).sort("decile")
pl.Config.set_tbl_cols(30); pl.Config.set_tbl_width_chars(260); pl.Config.set_tbl_formatting("ASCII_MARKDOWN")
print(ladder.with_columns(pl.exclude("decile", "mahalle", "nufus").round(1)))
ladder.write_csv(D + "gelir_merdiveni.csv", separator=";")
top, bot = ladder.row(9, named=True), ladder.row(0, named=True)
print("en zengin/en yoksul dilim gelir oranı", round(top["gelir"] / bot["gelir"], 2))

# correlations at neighbourhood level (population-weighted Spearman ~ plain Spearman on large n)
cols = ["income", "uni_share", "elder_share", "child_share", "hh_size", "divorced_share", "owner_share", "car_ratio", "ecom_ratio", "density"]
cc = v.select(cols).drop_nulls().to_pandas() if False else None
arr = v.select(cols).drop_nulls()
rk = arr.select([pl.col(c).rank() for c in cols]).to_numpy()
corr = np.corrcoef(rk.T)
print("gelir ile Spearman:", {c: round(corr[0, i], 2) for i, c in enumerate(cols)})

# ---------------- B. inequality inside provinces
def gini(x, w):
    o = np.argsort(x); x, w = x[o], w[o]
    cw = np.cumsum(w); cxw = np.cumsum(x * w)
    return 1 - np.sum((cxw[1:] + cxw[:-1]) * np.diff(cw)) / (cxw[-1] * cw[-1]) - (cxw[0] * cw[0]) / (cxw[-1] * cw[-1])


def share_ratio(x, w, q=0.1):
    o = np.argsort(x); x, w = x[o], w[o]
    c = np.cumsum(w) / w.sum()
    lo = (x[c <= q] * w[c <= q]).sum() / w[c <= q].sum() if (c <= q).any() else x[0]
    hi = (x[c > 1 - q] * w[c > 1 - q]).sum() / w[c > 1 - q].sum()
    return hi / lo


prov = []
for (p, name), g in v.group_by(["plate", "province"]):
    x, w = g["income"].to_numpy().astype(float), g["pop"].to_numpy().astype(float)
    prov.append({"plate": p, "il": name, "mahalle": g.height, "nufus": w.sum(), "gelir_ort": (x * w).sum() / w.sum(),
                 "gini": gini(x, w), "ust10_alt10": share_ratio(x, w), "ust_dilim_payi": g.filter(pl.col("decile") == 10)["pop"].sum() / w.sum() * 100,
                 "alt_dilim_payi": g.filter(pl.col("decile") == 1)["pop"].sum() / w.sum() * 100,
                 "universite": (g["uni_share"].fill_null(0) * g["pop"]).sum() / w.sum()})
P = pl.DataFrame(prov).sort("gini", descending=True)
print("TR mahalle Gini", round(gini(v["income"].to_numpy().astype(float), v["pop"].to_numpy().astype(float)), 3))
print(P.select("il", "mahalle", pl.col("gelir_ort").round(0), pl.col("gini").round(3), pl.col("ust10_alt10").round(2), pl.col("ust_dilim_payi").round(1), pl.col("alt_dilim_payi").round(1)).head(12))
print(P.select("il", "mahalle", pl.col("gelir_ort").round(0), pl.col("gini").round(3), pl.col("ust10_alt10").round(2)).tail(8))

# ---------------- C. against the warehouse (province level)
c = duckdb.connect(WH, read_only=True)
A = "read_csv('C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/areas_tr.csv')"
q = lambda s: dict(c.sql(s).fetchall())
key = lambda n: n
sgk = q(f"select cast(substr(f.area_id,4,2) as int), value from fact f where indicator_id='sgk_average_daily_earnings' and dims='earnings_segment=total' and year(period_start)=2024 and area_level='province'")
gdp = q(f"select cast(substr(f.area_id,4,2) as int), value from fact f where indicator_id='province_gdp_per_capita' and dims='gdp_currency=try;gdp_price=current' and year(period_start)=2024 and area_level='province'")
dep = q(f"select cast(substr(f.area_id,4,2) as int), sum(value) from fact f where indicator_id='bank_deposits' and year(period_start)=2024 and area_level='province' and dims<>'deposit_type=interbank' group by 1")
popi = q(f"select cast(substr(f.area_id,4,2) as int), sum(value) from fact f where indicator_id='population' and year(period_start)=2024 and area_level='province' group by 1")
P = P.with_columns(sgk=pl.col("plate").replace_strict(sgk, default=None), gsyh=pl.col("plate").replace_strict(gdp, default=None),
                   mevduat_kb=pl.col("plate").replace_strict({k: dep[k] / popi[k] for k in dep}, default=None))
for col in ("sgk", "gsyh", "mevduat_kb", "universite"):
    x = P.select("gelir_ort", col).drop_nulls()
    r = np.corrcoef(x["gelir_ort"].rank().to_numpy(), x[col].rank().to_numpy())[0, 1]
    print(f"il: Endeksa gelir ~ {col} Spearman {r:.2f}")
x = P.drop_nulls("sgk").with_columns(lr=np.log(pl.col("gelir_ort")), ls=np.log(pl.col("sgk")))
b = np.polyfit(x["ls"].to_numpy(), x["lr"].to_numpy(), 1)
x = x.with_columns(fark=(pl.col("lr") - (b[0] * pl.col("ls") + b[1])))
print("SGK kazancına göre Endeksa geliri yüksek iller", x.sort("fark", descending=True).select("il", pl.col("fark").round(2)).head(8).rows())
print("düşük iller", x.sort("fark").select("il", pl.col("fark").round(2)).head(8).rows())
P.write_csv(D + "iller.csv", separator=";")

# ---------------- D. who did the rates hit: sales by income quintile x EVDS mortgage rate
v = v.with_columns(quint=((pl.col("decile") + 1) // 2).cast(pl.Int8))
yrs = list(range(2010, 2025))
S = v.group_by("quint").agg([pl.col(f"sale_{y}").sum().alias(f"s{y}") for y in yrs] + [pl.col(f"mort_{y}").sum().alias(f"m{y}") for y in yrs]).sort("quint")
rate = q("select year(period_start), avg(value) from fact where indicator_id='loan_interest_rates_weekly' and dims='loan_rate_weekly_item=ktf12' group by 1")
tuik = q("select year(period_start), sum(value) from fact where indicator_id='housing_sales' and area_level='province' group by 1")
out = []
for y in yrs:
    row = {"yil": y, "konut_faizi": rate.get(y), "tuik_satis": tuik.get(y)}
    tot = sum(S[f"s{y}"])
    row["endeksa_satis"] = tot
    for i in range(5):
        s, mm = S[f"s{y}"][i], S[f"m{y}"][i]
        row[f"ipotek_q{i+1}"] = mm / s * 100 if s and mm is not None else None  # Endeksa has no 2019 mortgaged column
        row[f"satis_q{i+1}"] = s
    out.append(row)
R = pl.DataFrame(out)
R.write_csv(D + "faiz_satis.csv", separator=";")
print(R.select("yil", pl.col("konut_faizi").round(1), "tuik_satis", "endeksa_satis", *[pl.col(f"ipotek_q{i}").round(1) for i in range(1, 6)]))
b19 = {i: S[f"s2019"][i - 1] for i in range(1, 6)}
print("2024 satış / 2019 satış, beşte birlik dilimler:", {i: round(S[f"s2024"][i - 1] / b19[i], 2) for i in range(1, 6)})
print("2024 satış / 2021 satış:", {i: round(S[f"s2024"][i - 1] / S[f"s2021"][i - 1], 2) for i in range(1, 6)})
v.select("plate", "province", "district", "neighbourhood", "pop", "income", "decile").write_parquet(D + "mahalle_dilim.parquet")
