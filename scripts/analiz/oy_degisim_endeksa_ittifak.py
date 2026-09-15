import glob
import json
import re
import sys

import numpy as np

sys.path.insert(0,"scripts")
from parse_secim import fold

T="public/tiles/"
def load(v):
    out={}
    for f in glob.glob(T+f"secim-{v}-mahalle-TR-*.json"): out.update(json.load(open(f,encoding="utf-8")))
    return out
a=load("mv2015k"); b=load("mv2023")
B={"cumhur":r"^(AK PART|MHP$|BBP$|B[ÜU]Y[ÜU]K B[İI]RL|YEN[İI]DEN REFAH|CUMHUR)",
   "millet":r"^(CHP$|[İI]Y[İI]|SAADET|SP$|DEMOKRAT PART|DP$|M[İI]LLET [İI]TT)",
   "emek":r"^(HDP$|YE[ŞS][İI]L SOL|T[İI]P$|EMEK VE [ÖO]ZG)"}
def sh(r,p): return 100*sum(n for c,n in r["v"].items() if re.search(p,c,re.IGNORECASE))/r["g"] if r.get("g") else None
# endeksa by (district, folded name)
E={}
for f in glob.glob("C:/veri-ham/endeksa/demography/TR-*.json"):
    dist=f.split("\\")[-1].split("/")[-1][:-5]
    for code,rec in json.load(open(f,encoding="utf-8")).items():
        E.setdefault((dist,fold(rec["name_tr"])),rec["demography"])
rows=[]
for k in a:
    if k not in b or "~" in k: continue
    ra,rb=a[k],b[k]
    if (ra.get("k") or 0)<300 or (rb.get("k") or 0)<300: continue
    d=E.get((k[:9],fold(rb.get("ad",""))))
    if not d or not d.get("PopulationTotal"): continue
    edu=d.get("EducationTotal") or 0
    pop=d["PopulationTotal"]
    mar=(d.get("MarriedNever") or 0)+(d.get("Married") or 0)+(d.get("Divorced") or 0)+(d.get("Widow") or 0)
    uni=((d.get("EduLicenseDegree") or 0)+(d.get("EduGraduate") or 0)+(d.get("EduDoctorate") or 0))/edu*100 if edu else np.nan
    low=((d.get("EduNonLiterated") or 0)+(d.get("EduLiteratedUntutored") or 0)+(d.get("EduPrimarySchool") or 0))/edu*100 if edu else np.nan
    rows.append(dict(id=k, ad=rb["ad"], il=k[:5], secmen=rb["k"],
        d_cumhur=sh(rb,B["cumhur"])-sh(ra,B["cumhur"]), d_millet=sh(rb,B["millet"])-sh(ra,B["millet"]), d_emek=sh(rb,B["emek"])-sh(ra,B["emek"]),
        cumhur15=sh(ra,B["cumhur"]),
        nufus=pop, universite=uni, dusuk_egitim=low,
        yasli=d.get("PopulationElderRatio"), genc=d.get("PopulationYoungRatio"),
        evli=(d.get("Married") or 0)/mar*100 if mar else np.nan, bekar=(d.get("MarriedNever") or 0)/mar*100 if mar else np.nan,
        boşanmış=(d.get("Divorced") or 0)/mar*100 if mar else np.nan,
        ses_ab=d.get("SesGroupABRatio"), gelir=d.get("HouseIncome"), kira=d.get("RentedShare"),
        konut_m2=d.get("HouseUnitPriceForSale"), belediye=1 if d.get("IsMunicipality") else 0,
        koy=1 if "KÖY" in (d.get("DistrictType") or "") else 0))
print("eslesen mahalle:",len(rows), "/ ortak", sum(1 for k in a if k in b))
import polars as pl

df=pl.DataFrame(rows).fill_nan(None)
df.write_csv("C:/veri-ham/analiz_oy_degisim_mahalle.csv")
pl.Config.set_tbl_rows(40); pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(250)
def wm(c): return ((pl.col(c)*pl.col("secmen")).sum()/pl.col("secmen").filter(pl.col(c).is_not_null()).sum()).round(2).alias(c)
print(df.select(wm("d_cumhur"),wm("d_millet"),wm("d_emek")))
for var in ["nufus","universite","dusuk_egitim","yasli","genc","evli","bekar","ses_ab","gelir","kira","konut_m2","cumhur15"]:
    x=df.filter(pl.col(var).is_not_null()).with_columns(((pl.col(var).rank("ordinal")-1)*10/pl.len()).floor().cast(pl.Int32).alias("dilim")+1)
    print(f"## {var} (1=en dusuk)")
    print(x.group_by("dilim").agg(pl.col(var).min().round(1).alias("alt"),pl.col(var).max().round(1).alias("ust"),wm("d_cumhur"),wm("d_millet"),wm("d_emek"),pl.len().alias("n")).sort("dilim"))
feats=["universite","yasli","genc","evli","ses_ab","kira","nufus","cumhur15"]
X=df.drop_nulls(feats)
Z=np.column_stack([np.log(X["nufus"].to_numpy()) if f=="nufus" else X[f].to_numpy() for f in feats]).astype(float)
Z=(Z-Z.mean(0))/Z.std(0)
rng=np.random.default_rng(0); best=None
for s in range(5):
    C=Z[rng.choice(len(Z),10,replace=False)]
    for _ in range(100):
        lab=((Z[:,None,:]-C[None])**2).sum(2).argmin(1)
        C2=np.array([Z[lab==i].mean(0) if (lab==i).any() else C[i] for i in range(10)])
        if np.allclose(C,C2): break
        C=C2
    inertia=((Z-C[lab])**2).sum()
    if best is None or inertia<best[0]: best=(inertia,lab)
X=X.with_columns(pl.Series("kume",best[1]))
print("## 10 kume")
print(X.group_by("kume").agg(pl.len().alias("mah"),pl.col("secmen").sum(),pl.col("nufus").median().alias("nufus_med"),wm("universite"),wm("yasli"),wm("genc"),wm("evli"),wm("ses_ab"),wm("kira"),wm("cumhur15"),wm("d_cumhur"),wm("d_millet"),wm("d_emek")).sort("d_cumhur"))
print("## korelasyon")
for t in ["d_cumhur","d_millet","d_emek"]:
    print(t, {v: round(df.select(pl.corr(t,v)).item(),2) for v in ["universite","dusuk_egitim","yasli","genc","evli","bekar","ses_ab","gelir","kira","cumhur15"]})
