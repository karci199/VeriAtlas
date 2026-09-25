"""District-level changes of registry-province communities 2015-2025, earthquake provinces, Ordu example.

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
for r in csv.DictReader(
    open(r"C:\veri\src\veriatlas\data\areas_tr_districts.csv", encoding="utf-8")
):
    names[r["area_id"]] = r["name_tr"]
R = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\kutuk.parquet")
N = lambda c: pl.col(c).replace_strict(names, default=None)
T = R.group_by("d", "y").agg(pl.col("n").sum().alias("tot"))
X = R.join(T, on=["d", "y"]).with_columns(
    (pl.col("n") / pl.col("tot") * 100).alias("sh")
)
W = (
    X.filter(pl.col("y").is_in([2015, 2025]))
    .pivot(on="y", index=["d", "o", "h"], values=["n", "sh", "tot"])
    .fill_null(0)
)
W = W.with_columns(
    (pl.col("sh_2025") - pl.col("sh_2015")).alias("dsh"),
    (pl.col("n_2025") - pl.col("n_2015")).alias("dn"),
    N("d").alias("ilce"),
    N("h").alias("il"),
    N("o").alias("kok"),
)
out = W.filter((pl.col("o") != pl.col("h")) & (pl.col("tot_2025") >= 20000))
print("PAY ARTIŞI (dış il, puan):")
for r in (
    out.sort("dsh", descending=True)
    .head(25)
    .select("ilce", "il", "kok", "sh_2015", "sh_2025", "n_2015", "n_2025")
    .rows()
):
    print(
        "  ",
        r[0],
        r[1],
        "<-",
        r[2],
        round(r[3], 1),
        "→",
        round(r[4], 1),
        int(r[5]),
        "→",
        int(r[6]),
    )
print("SAYI ARTIŞI:")
for r in (
    out.sort("dn", descending=True)
    .head(20)
    .select("ilce", "il", "kok", "n_2015", "n_2025")
    .rows()
):
    print("  ", r[0], r[1], "<-", r[2], int(r[3]), "→", int(r[4]))
print("PAY DÜŞÜŞÜ (dış il):")
for r in (
    out.sort("dsh")
    .head(15)
    .select("ilce", "il", "kok", "sh_2015", "sh_2025", "n_2015", "n_2025")
    .rows()
):
    print(
        "  ",
        r[0],
        r[1],
        "<-",
        r[2],
        round(r[3], 1),
        "→",
        round(r[4], 1),
        int(r[5]),
        "→",
        int(r[6]),
    )
# yerli share decline in districts
y = W.filter((pl.col("o") == pl.col("h")) & (pl.col("tot_2025") >= 20000)).sort("dsh")
print(
    "YERLİ PAYI EN ÇOK DÜŞEN:",
    [
        (r[0], r[1], round(r[2], 1), round(r[3], 1))
        for r in y.head(15).select("ilce", "il", "sh_2015", "sh_2025").rows()
    ],
)
print(
    "YERLİ PAYI ARTAN:",
    [
        (r[0], r[1], round(r[2], 1), round(r[3], 1))
        for r in y.tail(8).select("ilce", "il", "sh_2015", "sh_2025").rows()
    ],
)
# Ordu-registered destinations
o = W.filter((pl.col("o") == "TR-52") & (pl.col("h") != "TR-52")).sort(
    "n_2025", descending=True
)
print(
    "ORDULU 2025 top:",
    [
        (r[0], r[1], int(r[2]), int(r[3]), round(r[4], 1))
        for r in o.head(15).select("ilce", "il", "n_2015", "n_2025", "sh_2025").rows()
    ],
)
print(
    "ORDULU artış top:",
    [
        (r[0], r[1], int(r[2]), int(r[3]))
        for r in o.sort("dn", descending=True)
        .head(10)
        .select("ilce", "il", "n_2015", "n_2025")
        .rows()
    ],
)
oi = (
    R.filter(pl.col("o") == "TR-52")
    .group_by("y", "h")
    .agg(pl.col("n").sum())
    .with_columns(N("h").alias("il"))
    .sort("n", descending=True)
)
for yy in (2007, 2015, 2025):
    print(
        "ORDULU il",
        yy,
        [
            (r[0], int(r[1]))
            for r in oi.filter(pl.col("y") == yy).head(8).select("il", "n").rows()
        ],
    )
# quake provinces: where did they go (outside home) 2015->2025 absolute growth
for q in [
    "TR-31",
    "TR-46",
    "TR-02",
    "TR-44",
    "TR-27",
    "TR-01",
    "TR-80",
    "TR-21",
    "TR-79",
    "TR-63",
    "TR-23",
]:
    z = (
        W.filter((pl.col("o") == q) & (pl.col("h") != q))
        .sort("dn", descending=True)
        .head(5)
    )
    print(
        "DEPREM",
        names[q],
        [
            (r[0], r[1], int(r[2]), int(r[3]))
            for r in z.select("ilce", "il", "n_2015", "n_2025").rows()
        ],
    )
