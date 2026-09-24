import polars as pl
from scipy import stats

AREAS = r"C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/"
S = r"C:/veri-ham/analiz/2026-09-24/"
d = pl.read_parquet(f"{S}/sirket_il.parquet")
nuts = pl.read_csv(f"{AREAS}nuts_tr.csv", infer_schema_length=0).select(pl.col("province_name").alias("il"), "nuts1_name")
d = d.join(nuts, on="il", how="left")
assert d["nuts1_name"].null_count() == 0


def agg(g):
    return g.agg(
        pl.col("kur", "tasf", "kap", "kur_s", "tasf_s", "kap_s", "kur_g", "kap_g").sum(),
        pl.col("nufus").first(),
    ).with_columns(
        oran=(pl.col("tasf") + pl.col("kap")) / pl.col("kur") * 100,
        oran_s=(pl.col("tasf_s") + pl.col("kap_s")) / pl.col("kur_s") * 100,
        kap_oran=pl.col("kap") / pl.col("kur") * 100,
        net=pl.col("kur") - pl.col("kap"),
    )


# 1) 2025 snapshot
s = agg(d.filter(pl.col("y") == 2025).group_by("il", "deprem", "nuts1_name")).with_columns(
    net_100k=pl.col("net") / pl.col("nufus") * 1e5, kur_100k=pl.col("kur") / pl.col("nufus") * 1e5
)
cols = ["il", "kur", "tasf", "kap", "net", "oran", "oran_s", "net_100k", "kur_100k"]
print("== 2025 oran_s en yüksek (şirket, kur_s>=200) ==")
print(s.filter(pl.col("kur_s") >= 200).sort("oran_s", descending=True).select(cols).head(12))
print(s.filter(pl.col("kur_s") >= 200).sort("oran_s").select(cols).head(10))
print("küçük iller (kur_s<200):", s.filter(pl.col("kur_s") < 200)["il"].to_list())
print("== net / 100 bin ==")
print(s.sort("net_100k", descending=True).select(cols).head(10))
print(s.sort("net_100k").select(cols).head(10))

# 2) periods 2018-22 vs 2023-25
a = agg(d.filter(pl.col("y").is_between(2018, 2022)).group_by("il", "deprem", "nuts1_name")).select("il", "deprem", "nuts1_name", pl.col("oran_s").alias("s_a"), pl.col("oran").alias("t_a"), (pl.col("kur") / 5).alias("kur_a"), pl.col("kur_s").alias("kur_s_a"), (pl.col("kur_g") - pl.col("kap_g")).alias("g_net_a"))
b = agg(d.filter(pl.col("y").is_between(2023, 2025)).group_by("il")).select("il", pl.col("oran_s").alias("s_b"), pl.col("oran").alias("t_b"), (pl.col("kur") / 3).alias("kur_b"), pl.col("kur_s").alias("kur_s_b"), (pl.col("kur_g") - pl.col("kap_g")).alias("g_net_b"), "nufus")
p = a.join(b, on="il").with_columns(deg=pl.col("s_b") - pl.col("s_a"), kur_deg=(pl.col("kur_b") / pl.col("kur_a") - 1) * 100)
p.write_parquet(f"{S}/sirket_donem.parquet")
pc = ["il", "deprem", "s_a", "s_b", "deg", "t_a", "t_b", "kur_deg"]
print("== şirket oranı değişimi 2018-22 -> 2023-25 ==")
print(p.sort("deg", descending=True).select(pc).head(15))
print(p.sort("deg").select(pc).head(10))
print("oranı düşen il sayısı", (p["deg"] < 0).sum(), "medyan artış", p["deg"].median())
print("kuruluşu artan il", (p["kur_deg"] > 0).sum())
print(p.select(pl.corr("deg", "kur_deg", method="spearman").alias("rho_deg_kurdeg")))

# 3) quake vs rest by year (company ratio)
print("== deprem bölgesi / diğer, yıllara göre şirket oranı ==")
q = agg(d.group_by("y", "deprem")).select("y", "deprem", "oran_s", "oran", "kur", "kap", "tasf").sort("y", "deprem")
print(q.pivot(on="deprem", index="y", values=["oran_s", "kur"]).sort("y"))
qd = d.filter(pl.col("y").is_between(2021, 2025))
print(agg(qd.group_by("y", "il")).filter(pl.col("il").is_in(["Hatay", "Kahramanmaraş", "Adıyaman", "Malatya", "Gaziantep", "Osmaniye"])).pivot(on="y", index="il", values="oran_s").sort("il"))
print(agg(qd.group_by("y", "il")).filter(pl.col("il").is_in(["Hatay", "Kahramanmaraş", "Adıyaman", "Malatya", "Gaziantep", "Osmaniye"])).pivot(on="y", index="il", values="kur").sort("il"))
# Mann-Whitney on deg
print("MWU deg deprem vs diğer", stats.mannwhitneyu(p.filter(pl.col("deprem"))["deg"], p.filter(~pl.col("deprem"))["deg"]), p.group_by("deprem").agg(pl.col("deg").median()))

# 4) NUTS1
print("== bölge (NUTS1) ==")
r1 = agg(d.filter(pl.col("y").is_between(2018, 2022)).group_by("nuts1_name")).select("nuts1_name", pl.col("oran_s").alias("s_a"))
r2 = agg(d.filter(pl.col("y").is_between(2023, 2025)).group_by("nuts1_name")).select("nuts1_name", pl.col("oran_s").alias("s_b"), pl.col("kur_s"))
r3 = agg(d.filter(pl.col("y") == 2025).group_by("nuts1_name")).select("nuts1_name", pl.col("oran_s").alias("s_2025"), "net", "nufus").with_columns(net_100k=pl.col("net") / pl.col("nufus") * 1e5)
print(r1.join(r2, on="nuts1_name").join(r3, on="nuts1_name").with_columns(deg=pl.col("s_b") - pl.col("s_a")).sort("deg", descending=True))

# 5) Istanbul share
print("== İstanbul payı ==")
tot = d.group_by("y").agg(pl.col("kur_s", "kap_s", "tasf_s").sum())
ist = d.filter(pl.col("il") == "İstanbul").select("y", pl.col("kur_s").alias("i_kur"), pl.col("kap_s").alias("i_kap"), pl.col("tasf_s").alias("i_tasf"))
big3 = d.filter(pl.col("il").is_in(["İstanbul", "Ankara", "İzmir"])).group_by("y").agg(pl.col("kur_s").sum().alias("b3"))
print(tot.join(ist, on="y").join(big3, on="y").with_columns(ist_kur_pay=pl.col("i_kur") / pl.col("kur_s") * 100, ist_cikis_pay=(pl.col("i_kap") + pl.col("i_tasf")) / (pl.col("kap_s") + pl.col("tasf_s")) * 100, b3_pay=pl.col("b3") / pl.col("kur_s") * 100, ist_oran=(pl.col("i_kap") + pl.col("i_tasf")) / pl.col("i_kur") * 100).sort("y").select("y", "ist_kur_pay", "ist_cikis_pay", "b3_pay", "ist_oran"))

# 6) sole traders
print("== gerçek kişi net (kur_g-kap_g) 2023-25 toplam, en negatif ==")
print(p.with_columns(g_net_b_100k=pl.col("g_net_b") / pl.col("nufus") * 1e5).sort("g_net_b").select("il", "g_net_a", "g_net_b", "g_net_b_100k").head(10))
print("gerçek kişi net negatif il sayısı 2023-25:", (p["g_net_b"] < 0).sum(), " 2018-22:", (p["g_net_a"] < 0).sum())

# 7) all-provinces 2025 table for appendix
s.sort("oran_s", descending=True).select("il", "nuts1_name", "deprem", "kur", "tasf", "kap", "net", "oran", "oran_s", "net_100k").write_csv(f"{S}/il_2025.csv")
