"""Districts by 2015-2025 localness change vs fertility, education, household size and votes.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import json

import duckdb
import numpy as np
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
f = "public/fact.parquet"
Y = (2015, 2025)
yer = duckdb.sql(f"""select area_id d, year(period_start) y, sum(value) filter (where split_part(dims,'=',2)=substr(area_id,1,5))/sum(value)*100 yerli, sum(value) pop
 from '{f}' where indicator_id='population_by_registry_province' and year(period_start) in {Y} group by 1,2""").pl()
G = "('age=15-19;sex=female','age=20-24;sex=female','age=25-29;sex=female','age=30-34;sex=female','age=35-39;sex=female','age=40-44;sex=female','age=45-49;sex=female')"
gfr = duckdb.sql(f"""with w as (select area_id d, year(period_start) y, sum(value) w from '{f}' where indicator_id='population' and area_level='district' and dims in {G} group by 1,2),
 b as (select area_id d, year(period_start) y, value b from '{f}' where indicator_id='births' and area_level='district' and dims='')
 select d,y,b/w*1000 gfr from w join b using(d,y) where y in {Y}""").pl()
edu = duckdb.sql(f"""select area_id d, year(period_start) y,
 sum(value) filter (where split_part(split_part(dims,'education_level=',2),';',1) in ('higher','masters','doctorate'))/sum(value) filter (where split_part(split_part(dims,'education_level=',2),';',1)<>'unknown')*100 uni
 from '{f}' where indicator_id='education_level_district' and split_part(split_part(dims,'age=',2),';',1) in ('25-29','30-34','35-39','40-44','45-49','50-54','55-59','60-64','65+') and year(period_start) in {Y} group by 1,2""").pl()
hh = duckdb.sql(
    f"select area_id d, year(period_start) y, value hh from '{f}' where indicator_id='household_size' and area_level='district' and dims='' and year(period_start) in {Y}"
).pl()


def el(fn, parties):
    t = json.load(open(fn, encoding="utf-8"))
    rows = []
    for k, v in t.items():
        r = {"d": k, "kat": v["o"] / v["k"] * 100 if v["k"] else None}
        for q, keys in parties.items():
            r[q] = sum(v["v"].get(x, 0) for x in keys) / v["g"] * 100
        rows.append(r)
    return pl.DataFrame(rows)


e15 = el(
    "public/tiles/secim-mv2015h-ilce.json",
    {"AKP": ["AK PARTİ"], "CHP": ["CHP"], "MHP": ["MHP"], "KURT": ["HDP"]},
).rename(lambda c: c if c == "d" else c + "_15")
e23 = el(
    "public/tiles/secim-mv2023-ilce.json",
    {
        "AKP": ["AK PARTİ"],
        "CHP": ["CHP"],
        "MHP": ["MHP"],
        "KURT": ["YEŞİL SOL PARTİ"],
        "İYİ": ["İYİ PARTİ"],
    },
).rename(lambda c: c if c == "d" else c + "_23")


def wide(df, col):
    return df.pivot(on="y", index="d", values=col).rename(
        {"2015": col + "_15", "2025": col + "_25"}
    )


D = (
    wide(yer, "yerli")
    .join(wide(yer, "pop"), on="d")
    .join(wide(gfr, "gfr"), on="d", how="left")
    .join(wide(edu, "uni"), on="d", how="left")
    .join(wide(hh, "hh"), on="d", how="left")
    .join(e15, on="d", how="left")
    .join(e23, on="d", how="left")
)
D = D.filter(
    pl.col("yerli_15").is_not_null() & pl.col("yerli_25").is_not_null()
).with_columns(
    (pl.col("yerli_25") - pl.col("yerli_15")).alias("dy"),
    ((pl.col("pop_25") / pl.col("pop_15") - 1) * 100).alias("buyume"),
    pl.col("d").replace_strict(names, default=None).alias("ilce"),
    pl.col("d").str.slice(0, 5).replace_strict(names, default=None).alias("il"),
)
print("ilçe", D.height)
D = D.sort("dy").with_columns(
    (pl.col("pop_25").cum_sum() / pl.col("pop_25").sum() * 5)
    .ceil()
    .clip(1, 5)
    .cast(pl.Int32)
    .alias("q")
)


def w(c, wt="pop_25"):
    return (
        (
            (pl.col(c) * pl.col(wt)).sum()
            / pl.col(wt).filter(pl.col(c).is_not_null()).sum()
        )
        .round(1)
        .alias(c)
    )


cols = [
    "dy",
    "yerli_15",
    "yerli_25",
    "buyume",
    "gfr_15",
    "gfr_25",
    "uni_15",
    "uni_25",
    "hh_15",
    "hh_25",
    "kat_15",
    "kat_23",
    "AKP_15",
    "AKP_23",
    "CHP_15",
    "CHP_23",
    "MHP_15",
    "MHP_23",
    "KURT_15",
    "KURT_23",
    "İYİ_23",
]
T = D.group_by("q").agg(pl.len().alias("ilce_n"), *[w(c) for c in cols]).sort("q")
pl.Config.set_tbl_cols(40)
pl.Config.set_tbl_width_chars(600)
pl.Config.set_tbl_hide_column_data_types(True)
pl.Config.set_tbl_hide_dataframe_shape(True)
print(T)
T.write_json(r"C:\veri-ham\analiz\2026_09_24\kt3.json")
# within-province correlations of change variables with dy (weighted), controlling growth
X = D.drop_nulls(
    [
        "gfr_15",
        "gfr_25",
        "uni_15",
        "uni_25",
        "hh_15",
        "hh_25",
        "AKP_15",
        "AKP_23",
        "CHP_15",
        "CHP_23",
        "KURT_15",
        "KURT_23",
    ]
).with_columns(
    (pl.col("gfr_25") / pl.col("gfr_15") * 100 - 100).alias("d_gfr"),
    (pl.col("uni_25") - pl.col("uni_15")).alias("d_uni"),
    (pl.col("hh_25") - pl.col("hh_15")).alias("d_hh"),
    (pl.col("AKP_23") - pl.col("AKP_15")).alias("d_akp"),
    (pl.col("CHP_23") - pl.col("CHP_15")).alias("d_chp"),
    (pl.col("KURT_23") - pl.col("KURT_15")).alias("d_kurt"),
    (pl.col("MHP_23") - pl.col("MHP_15")).alias("d_mhp"),
)


def demean(v, g):
    import collections

    s = collections.defaultdict(list)
    for a, b in zip(g, v):
        s[a].append(b)
    m = {k: np.mean(x) for k, x in s.items()}
    return np.array([b - m[a] for a, b in zip(g, v)])


g = X["il"].to_list()
dy = demean(X["dy"].to_numpy(), g)
gr = demean(np.log(X["pop_25"] / X["pop_15"]).to_numpy(), g)
for c in ["d_gfr", "d_uni", "d_hh", "d_akp", "d_chp", "d_mhp", "d_kurt"]:
    y = demean(X[c].to_numpy(), g)
    r = np.corrcoef(dy, y)[0, 1]
    Z = np.column_stack([dy, gr])
    b = np.linalg.lstsq(Z, y, rcond=None)[0]
    print(
        c,
        "il içi r=",
        round(r, 2),
        " | büyüme kontrolüyle yerli -10 puan etkisi:",
        round(-10 * b[0], 2),
    )
print(
    "EN ÇOK DÜŞEN 15:",
    [
        (r[0], r[1], round(r[2], 1), round(r[3], 1), round(r[4], 0))
        for r in D.filter(pl.col("pop_25") >= 20000)
        .sort("dy")
        .head(15)
        .select("ilce", "il", "yerli_15", "yerli_25", "buyume")
        .rows()
    ],
)
