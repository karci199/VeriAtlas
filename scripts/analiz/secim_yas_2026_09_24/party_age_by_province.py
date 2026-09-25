"""Per-province within-district age gradients of party votes (Endeksa age and TÜİK child share).

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import glob
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
B = (
    [("15_19", 18.5, 0.4)]
    + [(f"{a}_{a + 4}", a + 2.5, 1) for a in range(20, 65, 5)]
    + [("65", 73.0, 1)]
)
rows = []
for f in glob.glob(r"C:\veri-ham\endeksa\demography\TR-*.json"):
    for mid, m in json.load(open(f, encoding="utf-8")).items():
        x = m.get("demography") or {}
        if (x.get("HouseholdCount") or 0) <= 0:
            continue
        ad = sum((x.get(f"Age_{b}_Total") or 0) * w for b, _, w in B)
        if ad <= 0:
            continue
        rows.append(
            {
                "mid": mid,
                "a18": ad,
                "yas": sum((x.get(f"Age_{b}_Total") or 0) * w * mm for b, mm, w in B)
                / ad,
            }
        )
E = pl.DataFrame(rows)
T = (
    duckdb.sql("""select area_id, sum(value) filter (where dims='age=0-17') c, sum(value) filter (where dims='age=18+') a from 'public/fact.parquet'
 where indicator_id='population' and area_level='neighbourhood' and year(period_start)=2023 group by 1""")
    .pl()
    .with_columns(
        pl.col("area_id").str.split("-").list.last().alias("mid"),
        (pl.col("c") / (pl.col("c") + pl.col("a")) * 100).alias("cocuk"),
    )
)
V = []
for t in glob.glob("public/tiles/secim-mv2023-mahalle-TR-*.json"):
    for k, v in json.load(open(t, encoding="utf-8")).items():
        V.append(
            {
                "key": k,
                "mid": k.split("-")[-1],
                "did": "-".join(k.split("-")[:3]),
                "il": k[:5],
                "g": v["g"],
                **{q: v["v"].get(n, 0) for q, n in P.items()},
            }
        )
V = (
    pl.DataFrame(V)
    .filter(pl.col("g") >= 50)
    .with_columns((pl.col("YSP") / pl.col("g") * 100).alias("ysp"))
)
D = V.join(E, on="mid", how="left").join(
    T.select("mid", "cocuk", "a"), on="mid", how="left"
)
print(
    "seçim birimi",
    V.height,
    "Endeksa yaşlı",
    D.filter(pl.col("yas").is_not_null()).height,
    "TÜİK çocuk payı",
    D.filter(pl.col("cocuk").is_not_null()).height,
)
PARTS = list(P)


def slopes(X, xcol, scale):
    # within-district WLS slope of party share (pp) on x; returns per party slope*scale and n
    X = X.filter(pl.col(xcol).is_not_null())
    if X.height < 30:
        return None
    g = X["g"].to_numpy()
    did = X["did"].to_numpy()
    u, inv = np.unique(did, return_inverse=True)

    def dm(v):
        s = np.zeros(len(u))
        ws = np.zeros(len(u))
        np.add.at(s, inv, v * g)
        np.add.at(ws, inv, g)
        return v - (s / ws)[inv]

    x = dm(X[xcol].to_numpy().astype(float))
    out = {"n": X.height, "g": int(g.sum())}
    den = (g * x * x).sum()
    if den <= 0:
        return None
    for q in PARTS:
        y = dm((X[q] / X["g"]).to_numpy() * 100)
        b = (g * x * y).sum() / den
        # cluster-robust SE by district
        e = y - b * x
        sc = np.zeros(len(u))
        np.add.at(sc, inv, g * x * e)
        se = np.sqrt((sc**2).sum()) / den
        out[q] = (round(b * scale, 2), round(se * scale, 2))
    return out


res = {}
for il in sorted(D["il"].unique()):
    X = D.filter((pl.col("il") == il) & (pl.col("ysp") < 2))
    res[il] = {
        "ad": names[il],
        "yas": slopes(X, "yas", 10),
        "cocuk": slopes(X, "cocuk", -10),
        "all_yas": slopes(D.filter(pl.col("il") == il), "yas", 10),
    }
res["TR"] = {
    "ad": "Türkiye",
    "yas": slopes(D.filter(pl.col("ysp") < 2), "yas", 10),
    "cocuk": slopes(D.filter(pl.col("ysp") < 2), "cocuk", -10),
    "all_yas": slopes(D, "yas", 10),
}
json.dump(
    res,
    open(r"C:\veri-ham\analiz\2026_09_24\age_il.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
print("TR", res["TR"])
# agreement between two measures across provinces
for q in ["AKP", "CHP", "MHP", "İYİ", "ZP", "YRP"]:
    a = [
        res[i]["yas"][q][0]
        for i in res
        if i != "TR" and res[i]["yas"] and res[i]["cocuk"]
    ]
    b = [
        res[i]["cocuk"][q][0]
        for i in res
        if i != "TR" and res[i]["yas"] and res[i]["cocuk"]
    ]
    print(
        q, "iki ölçüt uyumu r=", round(np.corrcoef(a, b)[0, 1], 2), "il sayısı", len(a)
    )
