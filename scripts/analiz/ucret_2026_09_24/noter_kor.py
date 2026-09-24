import sys

import numpy as np
import polars as pl
from scipy import stats

S = sys.argv[1]
p = pl.read_parquet(f"{S}/prov.parquet")
p = p.with_columns(
    noter_100k=pl.col("noter") / pl.col("nufus") * 1e5,
    kisi_basina_noter=pl.col("nufus") / pl.col("noter"),
    n1_pay=pl.col("n1") / pl.col("noter") * 100,
    arac_devir_kb=pl.col("arac_devir") / pl.col("nufus") * 1000,
    konut_satis_kb=pl.col("konut_satis") / pl.col("nufus") * 1000,
    sirket_kb=pl.col("sirket_kurulus") / pl.col("nufus") * 1e5,
    mevduat_kb=pl.col("mevduat") / pl.col("nufus"),
    kredi_kb=pl.col("kredi") / pl.col("nufus"),
    sube_100k=pl.col("banka_sube") / pl.col("nufus") * 1e5,
    eczane_100k=pl.col("eczane") / pl.col("nufus") * 1e5,
    net_goc_kb=pl.col("net_goc") / pl.col("nufus") * 1000,
    bosanma_kb=pl.col("bosanma") / pl.col("nufus") * 1000,
    evlilik_kb=pl.col("evlilik") / pl.col("nufus") * 1000,
    ihracat_kb=pl.col("ihracat") / pl.col("nufus"),
    zincir_100k=pl.col("zincir_magaza") / pl.col("nufus") * 1e5,
    noter_arac=pl.col("arac_devir") / pl.col("noter"),
    noter_konut=pl.col("konut_satis") / pl.col("noter"),
)
p.write_parquet(f"{S}/prov2.parquet")

print("== TOPLAM ==", p["noter"].sum(), p[["n1", "n2", "n3"]].sum())
print("Türkiye 100 bin kişiye", p["noter"].sum() / p["nufus"].sum() * 1e5)
cols = ["il", "noter", "n1", "n2", "n3", "nufus", "noter_100k", "kisi_basina_noter", "noter_arac"]
print(p.sort("noter", descending=True).select(cols).head(12))
print(p.sort("noter_100k", descending=True).select(cols).head(12))
print(p.sort("noter_100k").select(cols).head(12))
print("n1 olan il sayısı", (p["n1"] > 0).sum(), "n2", (p["n2"] > 0).sum(), "n3", (p["n3"] > 0).sum())


def cor(x, y):
    m = np.isfinite(x) & np.isfinite(y)
    return stats.pearsonr(x[m], y[m])[0], stats.spearmanr(x[m], y[m])[0], m.sum()


# 1) level (counts) correlations
print("\n== SAYI ~ SAYI (log-log pearson, spearman) ==")
for v in ["nufus", "gsyh", "arac_devir", "konut_satis", "sirket_kurulus", "mevduat", "kredi", "banka_sube", "eczane", "bosanma", "evlilik", "ihracat", "zincir_magaza", "tasinmaz_satis_ay"]:
    x = np.log(p[v].to_numpy().astype(float))
    y = np.log(p["noter"].to_numpy().astype(float))
    r, rs, n = cor(x, y)
    print(f"{v:20s} r_log={r:.3f} rho={rs:.3f}  raw_r={stats.pearsonr(p[v], p['noter'])[0]:.3f}")

# elasticity
x = np.log(p["nufus"].to_numpy())
y = np.log(p["noter"].to_numpy())
lr = stats.linregress(x, y)
print(f"\nesneklik noter~nüfus^b: b={lr.slope:.3f} ±{lr.stderr:.3f} R2={lr.rvalue**2:.3f}")

# 2) per-capita correlations
print("\n== NOTER/100K ~ KİŞİ BAŞI GÖSTERGE ==")
res = []
for v in ["gsyh_kb", "ort_gunluk_kazanc", "yuksekogretim_pct", "yogunluk", "medyan_yas", "net_goc_kb", "arac_devir_kb", "konut_satis_kb", "sirket_kb", "mevduat_kb", "kredi_kb", "sube_100k", "eczane_100k", "bosanma_kb", "evlilik_kb", "ihracat_kb", "zincir_100k", "nufus"]:
    xv = p[v].to_numpy().astype(float)
    if v in ("yogunluk", "nufus", "gsyh_kb", "mevduat_kb", "kredi_kb", "ihracat_kb"):
        xv = np.log(xv)
    r, rs, n = cor(xv, p["noter_100k"].to_numpy())
    pv = stats.pearsonr(xv, p["noter_100k"].to_numpy())[1]
    res.append((v, r, rs, pv))
for v, r, rs, pv in sorted(res, key=lambda t: -abs(t[2])):
    print(f"{v:20s} r={r:+.3f} rho={rs:+.3f} p={pv:.3g}")

# 3) regression: log noter on log pop + log X
print("\n== log(noter) = a + b·log(nüfus) + c·log(X/nüfus) ==")
import numpy.linalg as la

for v in ["arac_devir", "konut_satis", "sirket_kurulus", "mevduat", "gsyh", "banka_sube", "eczane", "ihracat"]:
    X = np.column_stack([np.ones(81), np.log(p["nufus"]), np.log(p[v] / p["nufus"])])
    beta, *_ = la.lstsq(X, y, rcond=None)
    yh = X @ beta
    r2 = 1 - ((y - yh) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"{v:16s} b_nüfus={beta[1]:.3f} c={beta[2]:+.3f} R2={r2:.3f}")

# residuals vs population: which provinces have more/less than expected
p = p.with_columns(beklenen=np.exp(lr.intercept + lr.slope * x))
p = p.with_columns(fark=pl.col("noter") - pl.col("beklenen"), oran=pl.col("noter") / pl.col("beklenen"))
print(p.sort("oran", descending=True).select("il", "noter", "beklenen", "oran", "nufus").head(10))
print(p.sort("oran").select("il", "noter", "beklenen", "oran", "nufus").head(10))
p.write_parquet(f"{S}/prov2.parquet")

# class structure
print("\n== sınıf payı ==")
print(p.select(pl.corr("n1_pay", pl.col("nufus").log(), method="spearman").alias("a"), pl.corr("n1_pay", pl.col("gsyh_kb").log(), method="spearman").alias("b")))
print(p.sort("n1_pay", descending=True).select("il", "noter", "n1", "n2", "n3", "n1_pay").head(10))

# workload
print("\n== noter başına iş ==")
print(p.select(pl.col("noter_arac").median(), pl.col("noter_konut").median(), pl.col("kisi_basina_noter").median()))
print(p.sort("noter_arac", descending=True).select("il", "noter", "arac_devir", "noter_arac", "kisi_basina_noter").head(8))
print(p.sort("noter_arac").select("il", "noter", "arac_devir", "noter_arac", "kisi_basina_noter").head(8))

# 4) residual (beyond population) vs per-capita
print("\n== NÜFUSTAN ARINDIRILMIŞ: log(oran) ~ gösterge ==")
d = pl.read_csv(r"C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/areas_tr_districts.csv", infer_schema_length=0)
d = d.filter(pl.col("valid_to").is_null() | (pl.col("valid_to") == "")).group_by(pl.col("parent_id").alias("area_id")).agg(ilce_say=pl.len())
p = p.join(d, on="area_id", how="left")
print("ilçe sayısı toplam", p["ilce_say"].sum())
lo = np.log(p["oran"].to_numpy())
res = []
for v in ["gsyh_kb", "ort_gunluk_kazanc", "yuksekogretim_pct", "yogunluk", "medyan_yas", "net_goc_kb", "arac_devir_kb", "konut_satis_kb", "sirket_kb", "mevduat_kb", "kredi_kb", "sube_100k", "eczane_100k", "bosanma_kb", "evlilik_kb", "ihracat_kb", "zincir_100k", "ilce_say"]:
    xv = p[v].to_numpy().astype(float)
    if v in ("yogunluk", "gsyh_kb", "mevduat_kb", "kredi_kb", "ihracat_kb", "ilce_say"):
        xv = np.log(xv)
    r, pv = stats.pearsonr(xv, lo)
    rs = stats.spearmanr(xv, lo)[0]
    res.append((v, r, rs, pv))
for v, r, rs, pv in sorted(res, key=lambda t: -abs(t[1])):
    print(f"{v:20s} r={r:+.3f} rho={rs:+.3f} p={pv:.3g}")
X = np.column_stack([np.ones(81), np.log(p["nufus"]), np.log(p["ilce_say"])])
beta, *_ = la.lstsq(X, y, rcond=None); yh = X @ beta
print("log noter ~ log nüfus + log ilçe:", beta, 1 - ((y - yh) ** 2).sum() / ((y - y.mean()) ** 2).sum())
X = np.column_stack([np.ones(81), np.log(p["nufus"]), np.log(p["ilce_say"]), np.log(p["gsyh_kb"]), p["medyan_yas"]])
beta, *_ = la.lstsq(X, y, rcond=None); yh = X @ beta
print("+gsyh_kb +medyan yaş:", beta, 1 - ((y - yh) ** 2).sum() / ((y - y.mean()) ** 2).sum())
print(p.select(pl.corr(pl.col("noter"), pl.col("ilce_say")).alias("r_noter_ilce"), (pl.col("noter")/pl.col("ilce_say")).median().alias("med_noter_per_ilce")))
p.write_parquet(f"{S}/prov2.parquet")
