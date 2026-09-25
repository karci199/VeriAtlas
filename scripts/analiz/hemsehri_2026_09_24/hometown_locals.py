"""Local share per neighbourhood/district/province and single-origin neighbourhoods.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import glob
import json

import polars as pl

names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
dn = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr_districts.csv", encoding="utf-8")
    )
}
pop = []
for fp in glob.glob(r"C:\veri-ham\endeksa\demography\*.json"):
    for mid, m in json.load(open(fp, encoding="utf-8")).items():
        d = m.get("demography") or {}
        pop.append((mid, d.get("PopulationTotal") or 0))
P = pl.DataFrame(pop, schema=["mid", "pop"], orient="row")
df = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem.parquet").join(
    P, on="mid", how="left"
)
df = df.with_columns(
    pl.col("host").replace_strict(names, default=None).alias("hostn"),
    pl.col("orig").replace_strict(names, default=None).alias("orign"),
    pl.col("did").replace_strict(dn, default=None).alias("dname"),
)
m = df.group_by("mid", "did", "dname", "host", "hostn", "mname").agg(
    pl.col("pop").first(),
    pl.col("n").sum().alias("listed"),
    pl.col("n").filter(pl.col("orig") == pl.col("host")).sum().alias("local"),
)
m = m.with_columns(pl.max_horizontal("pop", "listed").alias("den")).with_columns(
    (pl.col("local") / pl.col("den") * 100).alias("locsh")
)
m.write_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_m.parquet")
df.write_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_df.parquet")
print("coverage listed/pop:", (m["listed"].sum() / m["pop"].sum()))
# province local share (population-weighted)
pv = (
    m.group_by("hostn")
    .agg(
        (pl.col("local").sum() / pl.col("den").sum() * 100).alias("loc"),
        pl.col("den").sum(),
    )
    .sort("loc")
)
print(
    "least local provinces:", [(r[0], round(r[1], 1)) for r in pv.head(10).iter_rows()]
)
print("most local:", [(r[0], round(r[1], 1)) for r in pv.tail(8).iter_rows()])
# districts least local (den>=20000)
dv = (
    m.group_by("hostn", "dname")
    .agg(
        (pl.col("local").sum() / pl.col("den").sum() * 100).alias("loc"),
        pl.col("den").sum(),
    )
    .filter(pl.col("den") >= 20000)
    .sort("loc")
)
print(
    "least local districts:",
    [(r[1], r[0], round(r[2], 1)) for r in dv.head(12).iter_rows()],
)
# mahalles dominated by one outside province (share>=50, pop>=1000)
big = (
    df.join(m.select("mid", "den"), on="mid")
    .filter((pl.col("orig") != pl.col("host")) & (pl.col("den") >= 1000))
    .with_columns((pl.col("n") / pl.col("den") * 100).alias("sh"))
)
top = big.sort("sh", descending=True).head(25)
print("little-hometowns:")
for r in top.select("mname", "dname", "hostn", "orign", "sh", "den").iter_rows():
    print("  ", r[0], "/", r[1], r[2], "<-", r[3], round(r[4], 1), r[5])
# count of mahalles where top origin is non-local
tops = (
    df.sort("n", descending=True)
    .group_by("mid")
    .first()
    .join(m.select("mid", "den"), on="mid")
)
nl = tops.filter((pl.col("orig") != pl.col("host")) & (pl.col("den") >= 500))
print(
    "mahalles where top origin non-local (pop>=500):",
    nl.height,
    "of",
    tops.filter(pl.col("den") >= 500).height,
)
print(nl.group_by("hostn").len().sort("len", descending=True).head(10).rows())
print(nl.group_by("orign").len().sort("len", descending=True).head(12).rows())
