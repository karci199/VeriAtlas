"""TÜİK registry (2007, 2015, 2025): share of each province's registered population living elsewhere.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv

import duckdb
import polars as pl

names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
for r in csv.DictReader(
    open(r"C:\veri\src\veriatlas\data\areas_tr_districts.csv", encoding="utf-8")
):
    names[r["area_id"]] = r["name_tr"]
R = duckdb.sql(
    """select area_id d, year(period_start) y, split_part(dims,'=',2) o, value n from 'public/fact.parquet' where indicator_id='population_by_registry_province'"""
).pl()
R = R.with_columns(pl.col("d").str.slice(0, 5).alias("h"))
print(R.group_by("y").agg(pl.col("d").n_unique(), pl.col("n").sum()).sort("y").rows())
R.write_parquet(r"C:\veri-ham\analiz\2026_09_24\kutuk.parquet")
# 1) diaspora share by origin
P = R.group_by("y", "o").agg(
    pl.col("n").sum().alias("tot"),
    pl.col("n").filter(pl.col("h") == pl.col("o")).sum().alias("home"),
)
P = P.with_columns(((1 - pl.col("home") / pl.col("tot")) * 100).alias("disari"))
W = P.filter(pl.col("y").is_in([2007, 2025])).pivot(
    on="y", index="o", values=["disari", "tot"]
)
W = (
    W.with_columns(
        (pl.col("disari_2025") - pl.col("disari_2007")).alias("deg"),
        ((pl.col("tot_2025") / pl.col("tot_2007") - 1) * 100).alias("buyume"),
    )
    .with_columns(pl.col("o").replace_strict(names).alias("il"))
    .sort("disari_2025", descending=True)
)
for r in W.select(
    "il", "tot_2007", "tot_2025", "buyume", "disari_2007", "disari_2025", "deg"
).rows():
    print(
        "DIAS",
        r[0],
        int(r[1]),
        int(r[2]),
        round(r[3], 1),
        round(r[4], 1),
        round(r[5], 1),
        round(r[6], 1),
    )
