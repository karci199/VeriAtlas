"""Flag neighbourhoods whose residents are largely an institution's (prison, dormitory,
care home, barracks): from secmen_iliski types, written back as a `kurum` column into
kent_<p>_son.csv and kent_<p>_ikili.csv. Class is not changed; age and vote tables can
leave these out.

kurum = 1 when the neighbourhood is a kurum_sandigi (votes >= registered + 20 in a general
election, none in the local one) or registered / 18+ was below 0.6 in 2024.

usage: kurum_isaret.py 16
"""

import polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, D  # noqa: E402

t = pl.read_csv(D / f"secmen_iliski_{PLATE}_tip.csv", infer_schema_length=0)
flag = {}
for r in t.iter_rows(named=True):
    k24 = float(r["kayit_2024"]) if r["kayit_2024"] not in (None, "") else None
    flag[(r["district"], r["name"])] = int(r["tip"] == "kurum_sandigi" or (k24 is not None and k24 < 0.6))
for f in (f"kent_{PLATE}_son.csv", f"kent_{PLATE}_ikili.csv"):
    d = pl.read_csv(D / f, infer_schema_length=0)
    if "kurum" in d.columns:
        d = d.drop("kurum")
    d = d.with_columns(pl.struct("district", "name").map_elements(lambda s: flag.get((s["district"], s["name"]), 0), return_dtype=pl.Int64).alias("kurum"))
    d.write_csv(D / f)
k = d.filter(pl.col("kurum") == 1)
print("kurum nüfuslu mahalle:", k.height, k.select("district", "name", "nufus").to_dicts() if k.height <= 12 else "")
