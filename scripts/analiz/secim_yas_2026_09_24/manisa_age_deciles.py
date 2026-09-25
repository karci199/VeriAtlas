"""Manisa neighbourhoods by mean adult age (equal adult-population deciles) and 2023 votes.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import glob
import json

import polars as pl

B = (
    [("15_19", 18.5, 0.4)]
    + [(f"{a}_{a + 4}", a + 2.5, 1) for a in range(20, 65, 5)]
    + [("65", 73.0, 1)]
)
rows = []
for f in glob.glob(r"C:\veri-ham\endeksa\demography\TR-45-*.json"):
    for mid, m in json.load(open(f, encoding="utf-8")).items():
        x = m.get("demography") or {}
        ad = sum((x.get(f"Age_{b}_Total") or 0) * w for b, _, w in B)
        ok = (x.get("HouseholdCount") or 0) > 0 and ad > 0
        mean = (
            sum((x.get(f"Age_{b}_Total") or 0) * w * mid_ for b, mid_, w in B) / ad
            if ok
            else None
        )
        rows.append(
            {
                "mid": mid,
                "ad": x.get("CountyName"),
                "mah": x.get("DistrictName"),
                "pop": x.get("PopulationTotal") or 0,
                "a18": ad if ok else None,
                "yas": mean,
                "uni": (
                    (x.get("EduLicenseDegree") or 0)
                    + (x.get("EduGraduate") or 0)
                    + (x.get("EduDoctorate") or 0)
                )
                if ok
                else None,
            }
        )
E = pl.DataFrame(rows)
P = {
    "AKP": "AK PARTİ",
    "MHP": "MHP",
    "CHP": "CHP",
    "YSP": "YEŞİL SOL PARTİ",
    "İYİ": "İYİ PARTİ",
    "ZP": "ZAFER PARTİSİ",
    "TİP": "TİP",
    "YRP": "YENİDEN REFAH",
    "BBP": "BÜYÜK BİRLİK",
}
t = json.load(open("public/tiles/secim-mv2023-mahalle-TR-45.json", encoding="utf-8"))
c = json.load(open("public/tiles/secim-cb2023t2-mahalle-TR-45.json", encoding="utf-8"))
V = pl.DataFrame(
    [
        {
            "mid": k.split("-")[-1],
            "k": v["k"],
            "o": v["o"],
            "g": v["g"],
            **{q: v["v"].get(n, 0) for q, n in P.items()},
            "cg": c.get(k, {}).get("g", 0),
            "RTE": c.get(k, {}).get("v", {}).get("RECEP TAYYİP ERDOĞAN", 0),
        }
        for k, v in t.items()
    ]
)
D = E.join(V, on="mid", how="inner")
print(
    "eşleşen",
    D.height,
    "of",
    E.height,
    V.height,
    "seçmen",
    D["k"].sum(),
    "il toplam seçmen",
    sum(v["k"] for v in t.values()),
)
A = (
    D.filter(pl.col("yas").is_not_null())
    .sort("yas")
    .with_columns((pl.col("a18").cum_sum() / pl.col("a18").sum()).alias("cp"))
    .with_columns((pl.col("cp") * 10).ceil().clip(1, 10).cast(pl.Int32).alias("dilim"))
)
N = D.filter(pl.col("yas").is_null()).with_columns(pl.lit(11).alias("dilim"))


def agg(X):
    return (
        X.group_by("dilim")
        .agg(
            pl.len().alias("mah"),
            pl.col("a18").sum().round(0).alias("n18"),
            pl.col("k").sum().alias("secmen"),
            pl.col("yas").min().round(1).alias("ymin"),
            pl.col("yas").max().round(1).alias("ymax"),
            ((pl.col("yas") * pl.col("a18")).sum() / pl.col("a18").sum())
            .round(1)
            .alias("yas"),
            (pl.col("o").sum() / pl.col("k").sum() * 100).round(1).alias("katilim"),
            *[(pl.col(q).sum() / pl.col("g").sum() * 100).round(2).alias(q) for q in P],
            (pl.col("RTE").sum() / pl.col("cg").sum() * 100).round(1).alias("RTE"),
            (pl.col("uni").sum() / pl.col("pop").sum() * 100).round(1).alias("uni_pop"),
        )
        .sort("dilim")
    )


T = pl.concat([agg(A), agg(N)], how="diagonal")
pl.Config.set_tbl_cols(30)
pl.Config.set_tbl_width_chars(400)
pl.Config.set_tbl_hide_column_data_types(True)
pl.Config.set_tbl_hide_dataframe_shape(True)
print(T)
tot = D.select(
    [(pl.col(q).sum() / pl.col("g").sum() * 100).round(2).alias(q) for q in P]
    + [(pl.col("RTE").sum() / pl.col("cg").sum() * 100).round(1).alias("RTE")]
)
print("Manisa toplam", tot)
import numpy as np

x = A["yas"].to_numpy()
w = A["g"].to_numpy()
for q in list(P) + ["RTE"]:
    y = (A[q] / A["cg" if q == "RTE" else "g"]).to_numpy() * 100
    b = np.polyfit(x, y, 1, w=np.sqrt(w))
    print(q, "her +1 yaş:", round(b[0], 2), "puan")
# json.dump(T.to_dicts(),open(r"C:\veri-ham\analiz\2026_09_24\manisa.json","w",encoding="utf-8"),ensure_ascii=False)

for d in (1, 2):
    X = (
        A.filter(pl.col("dilim") == d)
        .with_columns(
            (pl.col("YSP") / pl.col("g") * 100).round(1).alias("ysp%"),
            (pl.col("BBP") / pl.col("g") * 100).round(1).alias("bbp%"),
            (pl.col("CHP") / pl.col("g") * 100).round(1).alias("chp%"),
        )
        .sort("g", descending=True)
    )
    print(
        "DİLİM",
        d,
        X.select("ad", "mah", "yas", "g", "ysp%", "bbp%", "chp%").head(14).rows(),
    )
