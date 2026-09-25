"""Neighbourhood profile by localness decile (education, age, tenure, prices) and least-local neighbourhoods.

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
m = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_m.parquet").select(
    "mid", "host", "hostn", "dname", "mname", "den", "locsh"
)
df = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_df.parquet")
ma = pl.read_parquet(r"C:\veri-ham\analiz\mahalle\mahalle.parquet").with_columns(
    pl.col("id").cast(pl.Utf8).alias("mid")
)
cols = [
    "uni_share",
    "low_edu_share",
    "divorced_share",
    "never_married_share",
    "ses_ab_share",
    "child_share",
    "elder_share",
    "hh_size",
    "owner_share",
    "renter_share",
    "car_ratio",
    "ecom_ratio",
    "house_price",
    "house_rent",
    "income",
]
# number of distinct origins listed and top-origin share (diversity)
dv = df.group_by("mid").agg(pl.len().alias("n_orig"))
D = (
    m.join(ma.select(["mid"] + cols), on="mid", how="left")
    .join(dv, on="mid", how="left")
    .filter(pl.col("den") > 0)
)
D = D.sort("locsh").with_columns(
    (pl.col("den").cum_sum() / pl.col("den").sum() * 10)
    .ceil()
    .clip(1, 10)
    .cast(pl.Int32)
    .alias("dec")
)


def w(c):
    return (
        (
            (pl.col(c) * pl.col("den")).sum()
            / pl.col("den").filter(pl.col(c).is_not_null()).sum()
        )
        .round(2)
        .alias(c)
    )


T = (
    D.group_by("dec")
    .agg(pl.len().alias("mah"), w("locsh"), *[w(c) for c in cols])
    .sort("dec")
)
pl.Config.set_tbl_cols(30)
pl.Config.set_tbl_width_chars(500)
pl.Config.set_tbl_hide_column_data_types(True)
pl.Config.set_tbl_hide_dataframe_shape(True)
print(T)
# house price relative within province (median ratio) to avoid level effects
D2 = D.filter(pl.col("house_price").is_not_null()).with_columns(
    (pl.col("house_price") / pl.col("house_price").median().over("host")).alias(
        "hp_rel"
    )
)
print(
    D2.group_by("dec")
    .agg(
        ((pl.col("hp_rel") * pl.col("den")).sum() / pl.col("den").sum())
        .round(2)
        .alias("konut_fiyati_il_medyanina_orani")
    )
    .sort("dec")
)
# least local mahalles pop>=5000
top = D.filter(pl.col("den") >= 5000).sort("locsh").head(20)
tops = (
    df.sort("n", descending=True)
    .group_by("mid")
    .first()
    .select(
        "mid", pl.col("orig").replace_strict(names, default=None).alias("ilk_kok"), "n"
    )
)
print(
    top.join(tops, on="mid", how="left")
    .select(
        "mname",
        "dname",
        "hostn",
        "den",
        "locsh",
        "ilk_kok",
        (pl.col("n") / pl.col("den") * 100).round(1).alias("ilk_kok_pay"),
        "uni_share",
        "child_share",
        "renter_share",
    )
    .with_columns(
        pl.col("locsh").round(1),
        pl.col("uni_share").round(1),
        pl.col("child_share").round(1),
        pl.col("renter_share").round(1),
    )
)
