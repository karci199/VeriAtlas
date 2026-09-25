"""Istanbul regional (NUTS-2) hometown blocs by neighbourhood and district.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv

import polars as pl

names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
code = {v: k for k, v in names.items() if k.startswith("TR-") and len(k) == 5}
nuts = list(
    csv.DictReader(open(r"C:\veri\src\veriatlas\data\nuts_tr.csv", encoding="utf-8"))
)
n2 = {code[r["province_name"]]: r["nuts2_id"] for r in nuts}
n2name = {}
for r in nuts:
    n2name.setdefault(r["nuts2_id"], []).append(r["province_name"])
lab = {k: "-".join(v) for k, v in n2name.items()}
m = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_m.parquet").filter(
    pl.col("host") == "TR-34"
)
df = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_df.parquet").filter(
    pl.col("host") == "TR-34"
)
# upper bound for İstanbul share where outside top 10
z = m.filter(pl.col("local") == 0).select("mid", "mname", "dname", "den")
tenth = (
    df.join(z, on="mid")
    .group_by("mid")
    .agg(pl.col("n").min().alias("min_n"), pl.len().alias("k"))
)
zz = z.join(tenth, on="mid").with_columns(
    (pl.col("min_n") / pl.col("den") * 100).round(1).alias("ust_sinir")
)
print(
    "İLK10 DIŞI üst sınır:",
    zz.sort("den", descending=True)
    .head(8)
    .select("mname", "dname", "k", "ust_sinir")
    .rows(),
)
d = (
    df.join(m.select("mid", "den", "dname", "mname"), on="mid")
    .filter(pl.col("orig") != "TR-34")
    .with_columns(pl.col("orig").replace_strict(n2).alias("b"))
)
B = (
    d.group_by("mid", "mname", "dname", "den", "b")
    .agg(pl.col("n").sum())
    .with_columns((pl.col("n") / pl.col("den") * 100).alias("sh"))
)
tot = m["den"].sum()
ist = (
    B.group_by("b")
    .agg(pl.col("n").sum())
    .with_columns((pl.col("n") / tot * 100).alias("ist_sh"))
)
print(
    "İstanbul geneli blok payları:",
    [
        (lab[r[0]], round(r[1], 1))
        for r in ist.sort("ist_sh", descending=True)
        .select("b", "ist_sh")
        .head(12)
        .rows()
    ],
)
# mahalles with strongest bloc concentration (pop>=2000)
top = (
    B.filter(pl.col("den") >= 2000)
    .join(ist.select("b", "ist_sh"), on="b")
    .with_columns((pl.col("sh") / pl.col("ist_sh")).alias("lq"))
    .sort("sh", descending=True)
)
print("MAHALLE en yoğun blok (pay):")
for r in top.head(30).select("mname", "dname", "den", "b", "sh", "lq").rows():
    print(
        "  ",
        r[0],
        "/",
        r[1],
        int(r[2]),
        lab[r[3]],
        round(r[4], 1),
        "x" + str(round(r[5], 1)),
    )
# per bloc: districts with highest concentration and count of mahalles >= 3x average
Dd = (
    B.group_by("dname", "b")
    .agg(pl.col("n").sum())
    .join(m.group_by("dname").agg(pl.col("den").sum().alias("dpop")), on="dname")
    .with_columns((pl.col("n") / pl.col("dpop") * 100).alias("sh"))
    .join(ist.select("b", "ist_sh"), on="b")
    .with_columns((pl.col("sh") / pl.col("ist_sh")).alias("lq"))
)
for b in ist.sort("ist_sh", descending=True)["b"].to_list()[:14]:
    t = Dd.filter(pl.col("b") == b).sort("lq", descending=True).head(4)
    mm = top.filter(pl.col("b") == b).head(4)
    print(
        "BLOK",
        lab[b],
        "ist %",
        round(ist.filter(pl.col("b") == b)["ist_sh"][0], 1),
        "| ilçeler:",
        [(r[0], round(r[1], 1)) for r in t.select("dname", "sh").rows()],
        "| mahalleler:",
        [
            (r[0] + "/" + r[1], round(r[2], 1))
            for r in mm.select("mname", "dname", "sh").rows()
        ],
    )
