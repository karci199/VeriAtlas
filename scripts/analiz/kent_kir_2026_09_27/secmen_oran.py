"""Registered voters / 18+ residents per neighbourhood and semt.

Voters from the web tiles (2023 general, 2024 local), 18+ from ADNKS of the same year.
Ratio ~1.02 in ordinary villages. Well below 1: non-citizens, students and workers
registered elsewhere, institutions (prison boxes vote but inmates are not residents in
the voter list of that place). Well above 1: people registered in the village but living
elsewhere.

usage: secmen_oran.py 16 <dir>
"""

import json, sys
from pathlib import Path
import duckdb, polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG, LOCAL24, wh, geo_code  # noqa: E402

p = duckdb.sql(f"""select area_id, year(period_start) y, sum(value) filter (where dims='age=18+') a18, sum(value) tot
 from read_parquet('{ROOT}/public/fact.parquet') where indicator_id='population' and area_id like 'TR-{PLATE}-%-%'
 and year(period_start) in (2023, 2024) group by 1,2""").pl()
rows = []
for e, y in (("mv2023", 2023), (LOCAL24, 2024)):
    for a, v in json.loads((ROOT / f"public/tiles/secim-{e}-mahalle-TR-{PLATE}.json").read_text(encoding="utf-8")).items():
        rows.append(dict(area_id=wh(a) if "~" not in a else a, y=y, e=e, secmen=v["k"], oy=v["o"]))
s = pl.DataFrame(rows).join(p, on=["area_id", "y"], how="inner")
cls = pl.read_csv(D / f"kent_{PLATE}_ikili.csv", infer_schema_length=0).select("area_id", "district", "name", "kent_kir", "son_sinif")
semt = pl.read_csv(D / f"semt_{PLATE}_mahalle.csv").select("area_id", "semt")
s = s.join(cls, on="area_id").join(semt, on="area_id", how="left").with_columns((pl.col("secmen") / pl.col("a18")).round(3).alias("oran"))
w = s.pivot(on="e", index=["district", "semt", "area_id", "name", "kent_kir", "son_sinif"], values=["tot", "a18", "secmen", "oran"])
w = w.rename({c: c.replace("_mv2023", "_2023").replace(f"_{LOCAL24}", "_2024") for c in w.columns}).sort("oran_2024")
w.write_csv(D / f"secmen_oran_{PLATE}_mahalle.csv")
g = s.filter(pl.col("e") == LOCAL24).group_by("district", "semt").agg(
    pl.col("tot").sum().cast(pl.Int64).alias("nufus"), pl.col("a18").sum().cast(pl.Int64), pl.col("secmen").sum(),
    (pl.col("secmen").sum() / pl.col("a18").sum()).round(3).alias("oran_2024"),
    (pl.col("a18").sum() - pl.col("secmen").sum()).cast(pl.Int64).alias("secmen_disi_yetiskin")).sort("oran_2024")
g.write_csv(D / f"secmen_oran_{PLATE}_semt.csv")
pl.Config.set_tbl_rows(30); pl.Config.set_tbl_width_chars(220)
print(s.filter(pl.col("e") == LOCAL24).group_by("kent_kir").agg((pl.col("secmen").sum() / pl.col("a18").sum()).round(3).alias("oran"),
      (pl.col("a18").sum() - pl.col("secmen").sum()).cast(pl.Int64).alias("secmen_disi_yetiskin")))
print(g.head(12)); print(g.tail(6))
print(w.filter(pl.col("a18_2024") > 1000).head(12).select("district", "name", "kent_kir", "tot_2024", "a18_2024", "secmen_2024", "oran_2024", "oran_2023"))
