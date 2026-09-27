"""Registered voters, votes cast, 18+ residents and total population per neighbourhood and year.

Panel: elections 2015 Nov, 2018, 2023 (general), 2023 (pres. 2nd round), 2024 local, each joined
to ADNKS of the same year. Ratios: kayit = registered / 18+, katilim = cast / registered,
oy_18 = cast / 18+, cocuk = 0-17 / total. Types from the pattern over the years:
  kurum_sandigi   cast > registered + 20 in a general election (people vote there but are not
                  residents of the list: prison, barracks); absent in the 2024 local election
  secmen_disi_surekli / _yeni  registered / 18+ < 0.85 in every year / only in 2024 -> non-citizens, students, care homes,
                  workers registered elsewhere
  kayitli_gurbetci registered / 18+ > 1.10 in every year -> registered in the village, living away
  yabanci_akisi   18+ grew >= 15% 2018-2024 while registered grew less than half as much
  normal          otherwise

usage: secmen_iliski.py 16 <dir>
"""

import json, sys
from pathlib import Path
import duckdb, polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG  # noqa: E402

EL = [("mv2015k", 2015, "genel"), ("mv2018", 2018, "genel"), ("mv2023", 2023, "genel"), ("cb2023t2", 2023, "cb2"), ("yerel_bsb_2024", 2024, "yerel")]
p = duckdb.sql(f"""select area_id, year(period_start) y, sum(value) filter (where dims='age=18+') a18,
 sum(value) filter (where dims='age=0-17') c, sum(value) tot from read_parquet('{ROOT}/public/fact.parquet')
 where indicator_id='population' and area_id like 'TR-{PLATE}-%-%' and year(period_start) in (2015,2018,2023,2024) group by 1,2""").pl()
rows = []
for e, y, kind in EL:
    for a, v in json.loads((ROOT / f"public/tiles/secim-{e}-mahalle-TR-{PLATE}.json").read_text(encoding="utf-8")).items():
        rows.append(dict(area_id=a, e=e, y=y, kind=kind, k=v["k"], o=v["o"], g=v["g"]))
s = pl.DataFrame(rows).join(p, on=["area_id", "y"], how="inner")
cls = pl.read_csv(D / f"kent_{PLATE}_ikili.csv", infer_schema_length=0).select("area_id", "district", "name", "kent_kir", "son_sinif")
semt = pl.read_csv(D / f"semt_{PLATE}_mahalle.csv").select("area_id", "semt")
s = s.join(cls, on="area_id").join(semt, on="area_id", how="left").with_columns(
    (pl.col("k") / pl.col("a18")).alias("kayit"), (pl.col("o") / pl.col("k")).alias("katilim"), (pl.col("o") / pl.col("a18")).alias("oy_18"),
    (pl.col("c") / pl.col("tot")).alias("cocuk"), (pl.col("o") - pl.col("k")).alias("fazla_oy"))
s.write_csv(D / f"secmen_iliski_{PLATE}_panel.csv")

# province and class totals per election
tot = s.group_by("e", "y", "kind", "kent_kir").agg(pl.col("tot").sum().cast(pl.Int64), pl.col("a18").sum().cast(pl.Int64), pl.col("k").sum(), pl.col("o").sum()).with_columns(
    (pl.col("k") / pl.col("a18")).round(3).alias("kayit"), (pl.col("o") / pl.col("k")).round(3).alias("katilim"), (pl.col("o") / pl.col("a18")).round(3).alias("oy_18"),
    (pl.col("a18") - pl.col("k")).alias("secmen_disi_yetiskin")).sort("y", "e", "kent_kir")
tot.write_csv(D / f"secmen_iliski_{PLATE}_toplam.csv")

# typology per neighbourhood
w = s.pivot(on="e", index=["area_id", "district", "semt", "name", "kent_kir", "son_sinif"], values=["kayit", "fazla_oy", "k", "a18", "tot"])
gen = ["mv2015k", "mv2018", "mv2023"]
w = w.with_columns(
    pl.max_horizontal([pl.col(f"fazla_oy_{e}") for e in gen]).alias("fazla_oy_genel_max"),
    pl.col("fazla_oy_yerel_bsb_2024").alias("fazla_oy_yerel"),
    pl.min_horizontal([pl.col(f"kayit_{e}") for e in gen + ["yerel_bsb_2024"]]).alias("kayit_min"),
    pl.max_horizontal([pl.col(f"kayit_{e}") for e in gen + ["yerel_bsb_2024"]]).alias("kayit_max"),
    ((pl.col("a18_yerel_bsb_2024") / pl.col("a18_mv2018")) - 1).alias("a18_buyume"),
    ((pl.col("k_yerel_bsb_2024") / pl.col("k_mv2018")) - 1).alias("k_buyume"))
w = w.with_columns(
    pl.when((pl.col("fazla_oy_genel_max") >= 20) & (pl.col("fazla_oy_yerel").fill_null(0) < 20)).then(pl.lit("kurum_sandigi"))
    .when(pl.col("kayit_max") < 0.85).then(pl.lit("secmen_disi_surekli"))
    .when(pl.col("kayit_yerel_bsb_2024") < 0.85).then(pl.lit("secmen_disi_yeni"))
    .when(pl.col("kayit_min") > 1.05).then(pl.lit("kayitli_gurbetci"))
    .when((pl.col("a18_buyume") >= 0.15) & (pl.col("k_buyume") < pl.col("a18_buyume") / 2) & (pl.col("a18_mv2018") >= 300)).then(pl.lit("yabanci_akisi"))
    .otherwise(pl.lit("normal")).alias("tip"))
out = w.select("district", "semt", "name", "kent_kir", "son_sinif", "tip", pl.col("tot_yerel_bsb_2024").alias("nufus_2024"), pl.col("a18_yerel_bsb_2024").alias("a18_2024"),
               pl.col("k_yerel_bsb_2024").alias("secmen_2024"), *[pl.col(f"kayit_{e}").round(2).alias(f"kayit_{y}") for e, y, _ in EL if e != "cb2023t2"],
               "fazla_oy_genel_max", "fazla_oy_yerel", pl.col("a18_buyume").round(2), pl.col("k_buyume").round(2)).sort("tip", "nufus_2024", descending=[False, True])
out.write_csv(D / f"secmen_iliski_{PLATE}_tip.csv")
pl.Config.set_tbl_rows(60); pl.Config.set_tbl_width_chars(260); pl.Config.set_tbl_cols(20)
print(tot.select("e", "kent_kir", "tot", "a18", "k", "o", "kayit", "katilim", "oy_18", "secmen_disi_yetiskin"))
print(out.group_by("tip", "kent_kir").agg(pl.len(), pl.col("nufus_2024").sum().cast(pl.Int64), (pl.col("a18_2024") - pl.col("secmen_2024")).sum().cast(pl.Int64).alias("secmen_disi")).sort("tip", "kent_kir"))
for tip in ("kurum_sandigi", "secmen_disi_surekli", "secmen_disi_yeni", "yabanci_akisi", "kayitli_gurbetci"):
    print(f"== {tip}")
    print(out.filter(pl.col("tip") == tip).head(12).select("district", "name", "kent_kir", "nufus_2024", "a18_2024", "secmen_2024", "kayit_2015", "kayit_2018", "kayit_2023", "kayit_2024", "fazla_oy_genel_max", "a18_buyume", "k_buyume"))

# how tightly registered voters and votes follow the 18+ population (neighbourhood level)
import numpy as np
stat = []
for (e, kk), g in s.group_by(["e", "kent_kir"]):
    a, k, o = g["a18"].to_numpy(), g["k"].to_numpy(), g["o"].to_numpy()
    for lab, y_ in (("kayitli", k), ("oy", o)):
        b = np.linalg.lstsq(np.column_stack([np.ones(len(a)), a]), y_, rcond=None)[0]
        r2 = 1 - ((y_ - (b[0] + b[1] * a)) ** 2).sum() / ((y_ - y_.mean()) ** 2).sum()
        stat.append(dict(e=e, kent_kir=kk, y=lab, n=len(a), egim=round(float(b[1]), 3), sabit=round(float(b[0])), r2=round(float(r2), 4),
                         ortanca_oran=round(float(np.median(y_ / a)), 3)))
st = pl.DataFrame(stat).sort("e", "kent_kir", "y")
st.write_csv(D / f"secmen_iliski_{PLATE}_regresyon.csv")
print(st)
