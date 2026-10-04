"""Binary urban/rural per neighbourhood and district from birlestir.py output; no row left open.

kent = merkez, kentsel_belde (and OSB, which has no residents); kır = kasaba, kirsal_belde,
kir (and lakes/islands without residents). Umurbey-type kasabas are rural (user, 2026-09-27).

usage: ikili.py 16 <dir with kent_16_son.csv>
"""

import sys
from pathlib import Path
import polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG  # noqa: E402

KENT = {"merkez", "kentsel_belde", "osb"}
KIR = {"kasaba", "kirsal_belde", "kir"}
d = pl.read_csv(D / f"kent_{PLATE}_son.csv", infer_schema_length=0)
open_ = set(d["son_sinif"]) - KENT - KIR
assert not open_, f"sınıfsız: {open_}"
d = d.with_columns(pl.when(pl.col("son_sinif").is_in(list(KENT))).then(pl.lit("kent")).otherwise(pl.lit("kır")).alias("kent_kir_kalip"),
                   pl.col("pop").cast(pl.Float64).fill_null(0).cast(pl.Int64).alias("nufus"))
# outside the 30 metropolitan provinces the legal split (şehir = il/ilçe merkezi) is taken as is
# (user, 2026-09-29); the building rule stays beside it as the check
if "resmi" not in d.columns:
    d = d.with_columns(pl.lit("bsb").alias("resmi"))
METRO = (d["resmi"] == "bsb").all()
d = d.with_columns((pl.col("kent_kir_kalip") if METRO else pl.when(pl.col("resmi") == "sehir").then(pl.lit("kent")).otherwise(pl.lit("kır"))).alias("kent_kir"))
d.select("district", "area_id", "name", "nufus", "kent_kir", "kent_kir_kalip", "resmi", "son_sinif", "degurba", "note", "arada").write_csv(D / f"kent_{PLATE}_ikili.csv")
print("resmi/kalıp uyuşmayan:", d.filter(pl.col("kent_kir") != pl.col("kent_kir_kalip")).height, "mahalle")
s = d.group_by("district").agg(
    pl.len().alias("mahalle"),
    (pl.col("kent_kir") == "kent").sum().alias("kent_mah"),
    pl.col("nufus").filter(pl.col("kent_kir_kalip") == "kent").sum().alias("kent_kalip"),
    pl.col("nufus").filter(pl.col("kent_kir") == "kent").sum().alias("kent"),
    pl.col("nufus").filter(pl.col("kent_kir") == "kır").sum().alias("kir"),
    pl.col("nufus").sum().alias("toplam"))
s = pl.concat([s, s.select(pl.lit(IL_UP).alias("district"), pl.exclude("district").sum())])
s = s.with_columns((pl.col("kent") / pl.col("toplam") * 100).round(1).alias("kent%"), (pl.col("kent_kalip") / pl.col("toplam") * 100).round(1).alias("kent%_kalip")).sort("kent%")
s.write_csv(D / f"kent_{PLATE}_ikili_ilce.csv")
pl.Config.set_tbl_rows(30)
print(s)
print("sınıfsız mahalle: 0 /", d.height)
