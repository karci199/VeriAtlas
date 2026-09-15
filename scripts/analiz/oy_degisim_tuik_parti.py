import csv
import glob
import json
import re
import sys

import duckdb
import polars as pl

sys.path.insert(0,"scripts")
from parse_secim import fold

pl.Config.set_tbl_rows(40); pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(250)
T="public/tiles/"
def load(v):
    out={}
    for f in glob.glob(T+f"secim-{v}-mahalle-TR-*.json"): out.update(json.load(open(f,encoding="utf-8")))
    return out
a=load("mv2015k"); b=load("mv2023")
B={"akp":(r"^AK PART",r"^AK PART"),"chp":(r"^CHP$",r"^CHP$"),"mhp":(r"^MHP$",r"^MHP$"),"hdp":(r"^HDP$",r"^YE[ŞS][İI]L SOL")}
def sh(r,p): return 100*sum(n for c,n in r["v"].items() if re.search(p,c,re.IGNORECASE))/r["g"] if r.get("g") else None
def swings(ra,rb): return {f"d_{p}":sh(rb,y)-sh(ra,x) for p,(x,y) in B.items()} | {"cumhur15":sh(ra,B["akp"][0])}
F="public/fact.parquet"
# TÜİK neighbourhood population by (district, folded name)
names={r["area_id"]:(r["parent_id"],fold(r["name_tr"])) for r in csv.DictReader(open("src/veriatlas/data/areas_tr_neighbourhoods.csv",encoding="utf-8"))}
for r in csv.DictReader(open("src/veriatlas/data/areas_tr_villages.csv",encoding="utf-8")): names[r["area_id"]]=(r["parent_id"],fold(r["name_tr"]))
pop=duckdb.sql(f"""select area_id, year(period_start) y, dims, value from '{F}' where indicator_id='population' and area_level in ('neighbourhood','village') and year(period_start) in (2015,2023)""").pl()
P={}
for aid,y,d,v in pop.iter_rows():
    key=names.get(aid)
    if key: P.setdefault(key,{})[(y,d)]=v
med={}
for r in csv.DictReader(open("C:/veri-ham/medeni_durum_mahalle.csv",encoding="utf-8")):
    med.setdefault((fold(r["il"]),fold(r["ilce"]),fold(r["mahalle"])),r)
il_ad={k:fold(v) for k,v in json.load(open(T+"il-adlari.json",encoding="utf-8")).items()}
ilce_ad={k:fold(v["ad"]) for k,v in json.load(open(T+"secim-cb2023t1-ilce.json",encoding="utf-8")).items()}
rows=[]
for k in a:
    if k not in b or "~" in k or (a[k].get("k") or 0)<300 or (b[k].get("k") or 0)<300: continue
    p=P.get((k[:9],fold(b[k].get("ad",""))))
    if not p: continue
    c15=p.get((2015,"age=0-17"),0); a15=p.get((2015,"age=18+"),0); c23=p.get((2023,"age=0-17"),0); a23=p.get((2023,"age=18+"),0)
    if not (c15+a15) or not (c23+a23): continue
    m=med.get((il_ad.get(k[:5],""),ilce_ad.get(k[:9],""),fold(b[k].get("ad",""))))
    rows.append(dict(id=k, secmen=b[k]["k"], **swings(a[k],b[k]),
        nufus=c23+a23, buyume=100*((c23+a23)/(c15+a15)-1), cocuk=100*c23/(c23+a23),
        cocuk_degisim=100*c23/(c23+a23)-100*c15/(c15+a15),
        secmen_artis=100*(b[k]["k"]/a[k]["k"]-1),
        katilim_degisim=100*(b[k]["o"]/b[k]["k"]-a[k]["o"]/a[k]["k"]),
        bekar=float(m["hic_evlenmemis_oran"]) if m else None, bosanmis=float(m["bosanmis_oran"]) if m else None,
        dul=float(m["dul_oran"]) if m else None))
df=pl.DataFrame(rows)
print("mahalle:",df.height, " medeni eslesen:", df.filter(pl.col("bekar").is_not_null()).height)
def wm(c): return ((pl.col(c)*pl.col("secmen")).filter(pl.col(c).is_not_null()).sum()/pl.col("secmen").filter(pl.col(c).is_not_null()).sum()).round(2).alias(c)
for var in ["buyume","cocuk","katilim_degisim","cumhur15"]:
    x=df.filter(pl.col(var).is_not_null()).with_columns((((pl.col(var).rank("ordinal")-1)*10/pl.len()).floor().cast(pl.Int32)+1).alias("dilim"))
    print(f"## {var}")
    print(x.group_by("dilim").agg(pl.col(var).min().round(1).alias("alt"),pl.col(var).max().round(1).alias("ust"),wm("d_akp"),wm("d_chp"),wm("d_mhp"),wm("d_hdp"),pl.len().alias("n")).sort("dilim"))
print("## korelasyon")
for t in ["d_akp","d_chp","d_mhp","d_hdp"]:
    print(t,{v:round(df.drop_nulls([t,v]).select(pl.corr(t,v)).item(),2) for v in ["nufus","buyume","cocuk","cocuk_degisim","secmen_artis","katilim_degisim","bekar","bosanmis","dul","cumhur15"]})

# ---- ilce level with TÜİK district indicators
ia=json.load(open(T+"secim-mv2015k-ilce.json",encoding="utf-8")); ib=json.load(open(T+"secim-mv2023-ilce.json",encoding="utf-8"))
edu=duckdb.sql(f"""
 with e as (select area_id, year(period_start) y, dims, value from '{F}' where indicator_id='education_level_district' and year(period_start)=2023)
 select area_id,
  100*sum(case when dims like '%education_level=higher%' or dims like '%masters%' or dims like '%doctorate%' then value end)/sum(case when dims not like '%unknown%' then value end) uni,
  100*sum(case when dims like '%illiterate%' or dims like '%literate_no_school%' or dims like '%education_level=primary%' then value end)/sum(case when dims not like '%unknown%' then value end) dusuk
 from e where dims like '%age=%' group by 1""").pl()
print("edu dims ornek", duckdb.sql(f"select dims from '{F}' where indicator_id='education_level_district' limit 2").fetchall())
E={r[0]:(r[1],r[2]) for r in edu.iter_rows()}
ir=[]
for k in ia:
    if k in ib and "-x" not in k and k in E and not ib[k].get("eski") and not ia[k].get("eski"):
        ir.append(dict(id=k, ad=ib[k]["ad"], secmen=ib[k]["k"], **swings(ia[k],ib[k]), uni=E[k][0], dusuk=E[k][1]))
idf=pl.DataFrame(ir)
print("ilce:",idf.height)
for var in ["uni"]:
    x=idf.with_columns((((pl.col(var).rank("ordinal")-1)*10/pl.len()).floor().cast(pl.Int32)+1).alias("dilim"))
    print(f"## ILCE {var}")
    print(x.group_by("dilim").agg(pl.col(var).min().round(1).alias("alt"),pl.col(var).max().round(1).alias("ust"),wm("d_akp"),wm("d_chp"),wm("d_mhp"),wm("d_hdp"),pl.len().alias("n")).sort("dilim"))
print("ILCE korelasyon", {t:{v:round(idf.select(pl.corr(t,v)).item(),2) for v in ["uni","dusuk","cumhur15"]} for t in ["d_akp","d_chp","d_mhp","d_hdp"]})
