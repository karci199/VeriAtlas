"""Within-district relative age: deciles, vote-weighted relative age, district fixed-effect regression.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import glob
import json

import numpy as np
import polars as pl

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
GR = {
    "18-29": [("15_19", 0.4), ("20_24", 1), ("25_29", 1)],
    "30-44": [("30_34", 1), ("35_39", 1), ("40_44", 1)],
    "45-59": [("45_49", 1), ("50_54", 1), ("55_59", 1)],
    "60+": [("60_64", 1), ("65", 1)],
}
MID = {"18-29": 23.5, "30-44": 37, "45-59": 52, "60+": 70.5}
rows = []
for f in glob.glob(r"C:\veri-ham\endeksa\demography\TR-*.json"):
    did = f.split("\\")[-1][:-5]
    for mid, m in json.load(open(f, encoding="utf-8")).items():
        x = m.get("demography") or {}
        if (x.get("HouseholdCount") or 0) <= 0:
            continue
        ad = sum((x.get(f"Age_{b}_Total") or 0) * w for b, _, w in B)
        if ad <= 0:
            continue
        r = {
            "mid": mid,
            "did": did,
            "a18": ad,
            "yas": sum((x.get(f"Age_{b}_Total") or 0) * w * mm for b, mm, w in B) / ad,
        }
        for gname, bands in GR.items():
            r[gname] = sum((x.get(f"Age_{b}_Total") or 0) * w for b, w in bands) / ad
        rows.append(r)
E = pl.DataFrame(rows)
V = []
for t in glob.glob("public/tiles/secim-mv2023-mahalle-TR-*.json"):
    for k, v in json.load(open(t, encoding="utf-8")).items():
        V.append(
            {
                "mid": k.split("-")[-1],
                "g": v["g"],
                **{q: v["v"].get(n, 0) for q, n in P.items()},
            }
        )
D0 = (
    E.join(pl.DataFrame(V), on="mid")
    .filter(pl.col("g") >= 50)
    .with_columns((pl.col("YSP") / pl.col("g") * 100).alias("ysp_pct"))
)
PARTS = list(P)
out = {}
for th, label in ((None, "hepsi"), (2, "YSP<%2")):
    D = D0 if th is None else D0.filter(pl.col("ysp_pct") < th)
    # keep districts with >=3 mahalles
    D = D.join(
        D.group_by("did").len().filter(pl.col("len") >= 3).select("did"), on="did"
    )
    D = D.with_columns(
        (
            (pl.col("yas") * pl.col("a18")).sum().over("did")
            / pl.col("a18").sum().over("did")
        ).alias("dy")
    ).with_columns((pl.col("yas") - pl.col("dy")).alias("ry"))
    # (1) vote-weighted relative age
    rel = {q: round(float((D[q] * D["ry"]).sum() / D[q].sum()), 2) for q in PARTS}
    # (2) district-FE regression on age-group shares (drop 18-29 as reference) -> implied support per group
    G = list(GR)
    A = D.select(G).to_numpy()
    g = D["g"].to_numpy()
    w = np.sqrt(g)
    did = D["did"].to_numpy()
    u, inv = np.unique(did, return_inverse=True)

    def demean(M):
        M = M.astype(float)
        s = np.zeros((len(u), M.shape[1]))
        ws = np.zeros(len(u))
        np.add.at(s, inv, M * g[:, None])
        np.add.at(ws, inv, g)
        return M - (s / ws[:, None])[inv]

    Ad = demean(A[:, 1:])
    Nw = (A * D["a18"].to_numpy()[:, None]).sum(0)
    reg = {}
    for q in PARTS:
        y = (D[q] / D["g"]).to_numpy()
        yd = demean(y[:, None])[:, 0]
        b = np.linalg.lstsq(Ad * w[:, None], yd * w, rcond=None)[
            0
        ]  # differences vs 18-29
        diff = np.concatenate([[0], b])
        tot = D[q].sum() / D["g"].sum()
        base = (
            tot - (diff * Nw).sum() / Nw.sum()
        )  # level so weighted mean equals party share
        sup = base + diff
        votes = np.clip(sup, 0, None) * Nw
        mage = (votes * np.array([MID[k] for k in G])).sum() / votes.sum()
        reg[q] = {
            "oy%_by_age": [round(s * 100, 1) for s in sup],
            "ort_yas": round(float(mage), 1),
        }
    print("==", label, "mahalle", D.height, "ilçe", len(u))
    print("  oy-ağırlıklı ilçe-içi göreli yaş:", rel)
    for q in PARTS:
        print("  FE", q, reg[q])
    # (3) deciles of relative age
    X = D.sort("ry").with_columns(
        (pl.col("a18").cum_sum() / pl.col("a18").sum() * 10)
        .ceil()
        .clip(1, 10)
        .cast(pl.Int32)
        .alias("dec")
    )
    T = (
        X.group_by("dec")
        .agg(
            ((pl.col("ry") * pl.col("a18")).sum() / pl.col("a18").sum())
            .round(1)
            .alias("ry"),
            ((pl.col("yas") * pl.col("a18")).sum() / pl.col("a18").sum())
            .round(1)
            .alias("yas"),
            *[
                (pl.col(q).sum() / pl.col("g").sum() * 100).round(2).alias(q)
                for q in PARTS
            ],
        )
        .sort("dec")
    )
    out[label] = {"rel": rel, "reg": reg, "dec": T.to_dicts()}
    for r in T.rows():
        print("  ", r)
json.dump(
    out,
    open(r"C:\veri-ham\analiz\2026_09_24\age_fe.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
