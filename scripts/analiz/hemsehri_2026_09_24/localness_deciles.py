"""Equal-population deciles of localness, 2023 MV and presidential run-off results; Türkiye, metros, within-province.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import glob
import json

import polars as pl

m = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_m.parquet").select(
    "mid", "host", "den", "locsh"
)
dem = pl.read_parquet(r"C:\veri-ham\analiz\mahalle\mahalle.parquet").select(
    pl.col("id").cast(pl.Utf8).alias("mid"),
    "uni_share",
    "elder_share",
    "child_share",
    "ses_ab_share",
    "owner_share",
    "divorced_share",
)
MV = {
    "AKP": ["AK PARTİ"],
    "CHP": ["CHP"],
    "MHP": ["MHP"],
    "İYİ": ["İYİ PARTİ"],
    "YSP": ["YEŞİL SOL PARTİ"],
    "YRP": ["YENİDEN REFAH"],
    "ZP": ["ZAFER PARTİSİ"],
    "TİP": ["TİP"],
}
rows = []
for fp in glob.glob("public/tiles/secim-mv2023-mahalle-TR-*.json"):
    for key, v in json.load(open(fp, encoding="utf-8")).items():
        r = {"mid": key.split("-")[-1], "k": v["k"], "o": v["o"], "g": v["g"]}
        for q, ks in MV.items():
            r[q] = sum(v["v"].get(x, 0) for x in ks)
        rows.append(r)
A = pl.DataFrame(rows)
rows = []
for fp in glob.glob("public/tiles/secim-cb2023t2-mahalle-TR-*.json"):
    for key, v in json.load(open(fp, encoding="utf-8")).items():
        rows.append(
            {
                "mid": key.split("-")[-1],
                "cg": v["g"],
                "RTE": v["v"].get("RECEP TAYYİP ERDOĞAN", 0),
            }
        )
B = pl.DataFrame(rows)
D = (
    m.join(A, on="mid", how="inner")
    .join(B, on="mid", how="left")
    .join(dem, on="mid", how="left")
    .filter((pl.col("den") > 0) & (pl.col("g") > 0))
)
print("mahalle", D.height, "nufus", int(D["den"].sum()))
METRO = ["TR-34", "TR-06", "TR-35", "TR-16", "TR-41", "TR-07", "TR-59", "TR-33"]


def deciles(X, label):
    X = (
        X.sort("locsh")
        .with_columns((pl.col("den").cum_sum() / pl.col("den").sum()).alias("cp"))
        .with_columns(
            ((pl.col("cp") * 10).ceil().clip(1, 10)).cast(pl.Int32).alias("dec")
        )
    )
    wavg = lambda c, wt="den": (
        (pl.col(c) * pl.col(wt)).sum()
        / pl.col(wt).filter(pl.col(c).is_not_null()).sum()
    )
    T = (
        X.group_by("dec")
        .agg(
            pl.len().alias("mah"),
            pl.col("den").sum().alias("nufus"),
            pl.col("locsh").min().alias("ymin"),
            pl.col("locsh").max().alias("ymax"),
            (
                (pl.col("local") * 0 + pl.col("locsh") * pl.col("den")).sum()
                / pl.col("den").sum()
            ).alias("yort")
            if False
            else wavg("locsh").alias("yort"),
            (pl.col("o").sum() / pl.col("k").sum() * 100).alias("katilim"),
            *[(pl.col(q).sum() / pl.col("g").sum() * 100).alias(q) for q in MV],
            (pl.col("RTE").sum() / pl.col("cg").sum() * 100).alias("RTE"),
            wavg("uni_share").alias("uni"),
            wavg("elder_share").alias("yasli"),
            wavg("child_share").alias("cocuk"),
            wavg("ses_ab_share").alias("sesab"),
            wavg("owner_share").alias("evsahibi"),
        )
        .sort("dec")
    )
    print("=====", label)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(400)
    pl.Config.set_tbl_hide_column_data_types(True)
    pl.Config.set_tbl_hide_dataframe_shape(True)
    print(
        T.with_columns(
            [pl.col(c).round(1) for c in T.columns if c not in ("dec", "mah", "nufus")]
        )
    )
    return T


T1 = deciles(D, "Türkiye")
T2 = deciles(D.filter(pl.col("host").is_in(METRO)), "8 büyükşehir")
# within-province relative: rank by locsh - province weighted mean
pm = D.group_by("host").agg(
    ((pl.col("locsh") * pl.col("den")).sum() / pl.col("den").sum()).alias("pmean")
)
D3 = D.join(pm, on="host").with_columns(
    (pl.col("locsh") - pl.col("pmean")).alias("locsh")
)
T3 = deciles(D3, "il içi göreli (il ortalamasından sapma)")
json.dump(
    {"tr": T1.to_dicts(), "metro": T2.to_dicts(), "rel": T3.to_dicts()},
    open(r"C:\veri-ham\analiz\2026_09_24\dec.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
