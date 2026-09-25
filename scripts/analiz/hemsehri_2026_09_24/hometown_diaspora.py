"""Istanbul top origins, each origin's strongest neighbourhood outside its province, coastal settlers.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import polars as pl

df = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_df.parquet")
m = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_m.parquet")
d = df.join(m.select("mid", "den"), on="mid").with_columns(
    (pl.col("n") / pl.col("den") * 100).alias("sh")
)
tops = d.sort("n", descending=True).group_by("mid").first()
ist = tops.filter((pl.col("host") == "TR-34") & (pl.col("den") >= 1000))
print("Istanbul mahalles (pop>=1000):", ist.height)
print(ist.group_by("orign").len().sort("len", descending=True).head(12).rows())
# second-largest group in Istanbul when top is Istanbul: which provinces are #1 non-local
nl = (
    d.filter(
        (pl.col("host") == "TR-34")
        & (pl.col("orig") != "TR-34")
        & (pl.col("den") >= 1000)
    )
    .sort("n", descending=True)
    .group_by("mid")
    .first()
)
print(
    "Ist top non-local:",
    nl.group_by("orign").len().sort("len", descending=True).head(12).rows(),
)
# each origin's strongest mahalle outside home province
out = (
    d.filter((pl.col("orig") != pl.col("host")) & (pl.col("den") >= 1000))
    .sort("sh", descending=True)
    .group_by("orign")
    .first()
    .sort("sh", descending=True)
)
for r in out.select("orign", "mname", "dname", "hostn", "sh", "n").iter_rows():
    print("GURBET", r[0], "|", r[1], r[2], r[3], round(r[4], 1), r[5])
# Ankara/Istanbul-registered dominating outside
for o in ["TR-06", "TR-34"]:
    x = (
        d.filter((pl.col("orig") == o) & (pl.col("host") != o) & (pl.col("den") >= 500))
        .sort("sh", descending=True)
        .head(10)
    )
    print(
        o,
        [
            (r[0], r[1], r[2], round(r[3], 1))
            for r in x.select("mname", "dname", "hostn", "sh").iter_rows()
        ],
    )
# Syria? no. Where locals minority in non-metro provinces: mahalles pop>=2000 lowest local share outside big 5
lo = (
    m.filter(
        (pl.col("den") >= 2000)
        & (
            ~pl.col("host").is_in(
                ["TR-34", "TR-06", "TR-35", "TR-41", "TR-59", "TR-77", "TR-07", "TR-16"]
            )
        )
    )
    .sort("locsh")
    .head(15)
)
print(
    "LOWLOCAL",
    [
        (r[0], r[1], r[2], round(r[3], 1))
        for r in lo.select("mname", "dname", "hostn", "locsh").iter_rows()
    ],
)
