"""Party voter age: vote-weighted neighbourhood age and ecological regression, with YSP-share filters.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import glob
import json
import sys

import numpy as np
import polars as pl
from scipy.optimize import lsq_linear

PROV = sys.argv[1]  # "TR-45" or "ALL"
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
GR = {
    "18-29": ([("15_19", 0.4), ("20_24", 1), ("25_29", 1)], 23.5),
    "30-44": ([("30_34", 1), ("35_39", 1), ("40_44", 1)], 37),
    "45-59": ([("45_49", 1), ("50_54", 1), ("55_59", 1)], 52),
    "60+": ([("60_64", 1), ("65", 1)], 70.5),
}
B = (
    [("15_19", 18.5, 0.4)]
    + [(f"{a}_{a + 4}", a + 2.5, 1) for a in range(20, 65, 5)]
    + [("65", 73.0, 1)]
)
pat = "TR-45-*.json" if PROV != "ALL" else "TR-*.json"
rows = []
for f in glob.glob(r"C:\veri-ham\endeksa\demography\\" + pat):
    for mid, m in json.load(open(f, encoding="utf-8")).items():
        x = m.get("demography") or {}
        if (x.get("HouseholdCount") or 0) <= 0:
            continue
        ad = sum((x.get(f"Age_{b}_Total") or 0) * w for b, _, w in B)
        if ad <= 0:
            continue
        r = {
            "mid": mid,
            "a18": ad,
            "yas": sum((x.get(f"Age_{b}_Total") or 0) * w * mm for b, mm, w in B) / ad,
        }
        for gname, (bands, _) in GR.items():
            r[gname] = sum((x.get(f"Age_{b}_Total") or 0) * w for b, w in bands) / ad
        rows.append(r)
E = pl.DataFrame(rows)
tiles = (
    [f"public/tiles/secim-mv2023-mahalle-{PROV}.json"]
    if PROV != "ALL"
    else glob.glob("public/tiles/secim-mv2023-mahalle-TR-*.json")
)
V = []
for t in tiles:
    for k, v in json.load(open(t, encoding="utf-8")).items():
        V.append(
            {
                "mid": k.split("-")[-1],
                "g": v["g"],
                **{q: v["v"].get(n, 0) for q, n in P.items()},
            }
        )
D = (
    E.join(pl.DataFrame(V), on="mid")
    .filter(pl.col("g") >= 50)
    .with_columns((pl.col("YSP") / pl.col("g") * 100).alias("ysp_pct"))
)
PARTS = [q for q in P if D[q].sum() > 0]
print(PROV, "mahalle", D.height)


def vw(X, label):
    out = {
        q: round(float((X[q] * X["yas"]).sum() / X[q].sum()), 2)
        for q in PARTS
        if X[q].sum() > 0
    }
    print(
        f"  [{label}] n={X.height} ort18+yaş={round(float((X['a18'] * X['yas']).sum() / X['a18'].sum()), 2)} | oy-ağırlıklı mahalle yaşı:",
        out,
    )
    return out


res = {"vw": {}, "reg": {}}
for th, label in ((None, "hepsi"), (5, "YSP<%5"), (2, "YSP<%2"), (1, "YSP<%1")):
    X = D if th is None else D.filter(pl.col("ysp_pct") < th)
    res["vw"][label] = vw(X, label)
# ecological regression on age-group shares
G = list(GR)
mids = np.array([GR[g][1] for g in G])
for th, label in ((None, "hepsi"), (2, "YSP<%2")):
    X = D if th is None else D.filter(pl.col("ysp_pct") < th)
    A = X.select(G).to_numpy()
    w = np.sqrt(X["g"].to_numpy())
    N = (A * X["a18"].to_numpy()[:, None]).sum(0)
    est = {}
    for q in PARTS:
        y = (X[q] / X["g"]).to_numpy()
        b = lsq_linear(A * w[:, None], y * w, bounds=(0, 1)).x
        votes = b * N
        mage = float((votes * mids).sum() / votes.sum()) if votes.sum() > 0 else None
        est[q] = {
            "yas_gruplari_oy%": [round(v * 100, 1) for v in b],
            "ort_secmen_yasi": round(mage, 1) if mage else None,
        }
    print(
        f"  REG [{label}] gruplar {G} pay(%):",
        [round(v, 1) for v in (N / N.sum() * 100)],
    )
    for q, e in est.items():
        print("     ", q, e)
    res["reg"][label] = est
json.dump(
    res,
    open(rf"C:\veri-ham\analiz\2026_09_24\age_{PROV}.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
