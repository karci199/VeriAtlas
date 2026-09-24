import sys

import duckdb
import numpy as np
import polars as pl
from scipy import stats

S = sys.argv[1]
AREAS = r"C:/veri/.claude/worktrees/noter-analysis-correlation-bbc643/src/veriatlas/data/"
c = duckdb.connect(r"C:/veri/warehouse.duckdb", read_only=True)
c.execute("create temp view nt as select * from read_parquet('" + S + "/notaries.parquet')")


def latest(ind, level, where="true"):
    return f"""(select area_id, sum(value) v from fact where indicator_id='{ind}' and area_level='{level}'
      and period_start=(select max(period_start) from fact where indicator_id='{ind}' and area_level='{level}')
      and {where} group by 1)"""


d = c.sql(f"""
with n as (select area_id, sum(value) noter,
   sum(value) filter (where dims='notary_class=first') n1,
   sum(value) filter (where dims='notary_class=second') n2,
   sum(value) filter (where dims='notary_class=third') n3
 from nt where area_level='district' group by 1),
a as (select * from read_csv('{AREAS}areas_tr_districts.csv', all_varchar=true) where valid_to is null or valid_to='')
select a.area_id, a.name_tr ilce, pr.name_tr il, coalesce(noter,0) noter, coalesce(n1,0) n1, coalesce(n2,0) n2, coalesce(n3,0) n3,
  p.v nufus, hs.v konut_satis, ph.v eczane, bb.v banka_sube, dv.v bosanma, hz.v hane_buyuklugu, ur.v kentlesme_2015,
  hi.v / ed.v * 100 yuksekogretim_pct, cs.v zincir_magaza, bi.v dogum
from a
left join (select area_id pid, name_tr from read_csv('{AREAS}areas_tr.csv')) pr on pr.pid=a.parent_id
left join n using(area_id)
left join {latest('population', 'district')} p using(area_id)
left join {latest('housing_sales_district', 'district')} hs using(area_id)
left join {latest('pharmacies', 'district')} ph using(area_id)
left join {latest('bank_branch_locations', 'district')} bb using(area_id)
left join {latest('divorces_district', 'district')} dv using(area_id)
left join {latest('household_size', 'district')} hz using(area_id)
left join {latest('district_urbanization', 'district')} ur using(area_id)
left join {latest('education_level_district', 'district', "dims similar to '.*education_level=(higher|masters|doctorate).*' and dims not similar to '.*age=(6-13|14-17|18-21);.*'")} hi using(area_id)
left join {latest('education_level_district', 'district', "dims not like '%unknown%' and dims not similar to '.*age=(6-13|14-17|18-21);.*'")} ed using(area_id)
left join {latest('chain_stores', 'district')} cs using(area_id)
left join {latest('births', 'district')} bi using(area_id)
""").pl()
for col in ["konut_satis", "eczane", "banka_sube", "zincir_magaza"]:
    d = d.with_columns(pl.col(col).fill_null(0))
d.write_parquet(f"{S}/ilce.parquet")
print(d.shape, d.null_count())
print("toplam noter", d["noter"].sum(), "noterli ilçe", (d["noter"] > 0).sum(), "/", len(d))

# the office's own city: most offices per province sit in central districts
d = d.with_columns(
    noter_100k=pl.col("noter") / pl.col("nufus") * 1e5,
    var=(pl.col("noter") > 0).cast(pl.Int8),
)
print(d.sort("noter", descending=True).select("il", "ilce", "noter", "n1", "n2", "n3", "nufus", "noter_100k").head(20))
print("sıfır noterli ilçeler en kalabalık:")
print(d.filter(pl.col("noter") == 0).sort("nufus", descending=True).select("il", "ilce", "nufus", "eczane", "banka_sube").head(15))
print("birden fazla noter ama küçük:")
print(d.filter(pl.col("noter") > 0).sort("noter_100k", descending=True).select("il", "ilce", "noter", "nufus", "noter_100k").head(12))

# threshold: share with a notary by population bin
bins = [0, 5000, 10000, 20000, 30000, 50000, 100000, 200000, 400000, 1e9]
d = d.with_columns(bin=pl.col("nufus").cut(bins[1:-1]))
print(d.group_by("bin").agg(ilce=pl.len(), noterli_pct=pl.col("var").mean() * 100, ort_noter=pl.col("noter").mean(), noter_100k=(pl.col("noter").sum() / pl.col("nufus").sum() * 1e5)).sort("bin"))

# correlations
print("\n== İLÇE KORELASYONLARI ==")
w = d.filter(pl.col("nufus") > 0)
for v in ["nufus", "konut_satis", "eczane", "banka_sube", "bosanma", "zincir_magaza", "dogum"]:
    x, y = w[v].to_numpy().astype(float), w["noter"].to_numpy().astype(float)
    m = np.isfinite(x)
    print(f"{v:15s} r={stats.pearsonr(x[m], y[m])[0]:+.3f} rho={stats.spearmanr(x[m], y[m])[0]:+.3f} n={m.sum()}")

# among notary-holding districts: log-log elasticity and residual correlates
h = w.filter(pl.col("noter") > 0)
lx, ly = np.log(h["nufus"].to_numpy()), np.log(h["noter"].to_numpy())
lr = stats.linregress(lx, ly)
print(f"noterli ilçelerde esneklik b={lr.slope:.3f} R2={lr.rvalue**2:.3f} n={len(h)}")
res = ly - (lr.intercept + lr.slope * lx)
h = h.with_columns(art=res)
print("nüfustan arındırılmış fazla (noterli ilçeler):")
for v in ["yuksekogretim_pct", "hane_buyuklugu", "kentlesme_2015", "konut_satis", "banka_sube", "eczane", "bosanma", "zincir_magaza", "dogum"]:
    x = h[v].to_numpy().astype(float)
    if v in ("konut_satis", "banka_sube", "eczane", "bosanma", "zincir_magaza", "dogum"):
        x = x / h["nufus"].to_numpy()
    m = np.isfinite(x)
    r, pv = stats.pearsonr(x[m], res[m])
    print(f"{v:18s} r={r:+.3f} rho={stats.spearmanr(x[m], res[m])[0]:+.3f} p={pv:.3g} n={m.sum()}")

# logistic-free view: does having a notary depend on more than size? within pop 10k-40k band
b = w.filter((pl.col("nufus") >= 10000) & (pl.col("nufus") < 40000))
print("\n10-40 bin nüfuslu ilçeler:", len(b), "noterli", b["var"].sum())
for v in ["nufus", "yuksekogretim_pct", "hane_buyuklugu", "kentlesme_2015", "banka_sube", "eczane"]:
    x = b[v].to_numpy().astype(float)
    m = np.isfinite(x)
    print(f"{v:18s} noterli ort={np.nanmean(x[b['var'].to_numpy()==1]):.2f} noterSİZ ort={np.nanmean(x[b['var'].to_numpy()==0]):.2f}  rho={stats.spearmanr(x[m], b['var'].to_numpy()[m])[0]:+.3f}")

# province concentration: share of province notaries in its top district
top = d.group_by("il").agg(top_pay=(pl.col("noter").max() / pl.col("noter").sum() * 100), nufus_top=(pl.col("nufus").max() / pl.col("nufus").sum() * 100))
print(top.sort("top_pay", descending=True).head(10))
print("il noterinin en büyük ilçedeki payı medyan", top["top_pay"].median(), "nüfus payı medyan", top["nufus_top"].median())
d.write_parquet(f"{S}/ilce.parquet")
