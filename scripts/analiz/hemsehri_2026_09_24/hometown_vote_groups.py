"""Grouped (NUTS-1) hometown vote model with district and neighbourhood expectations.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import json

import numpy as np
import polars as pl
from scipy.optimize import lsq_linear

names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
dn = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr_districts.csv", encoding="utf-8")
    )
}
code = {v: k for k, v in names.items() if k.startswith("TR-") and len(k) == 5}
n1 = {
    code[r["province_name"]]: r["nuts1_name"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\nuts_tr.csv", encoding="utf-8")
    )
}
METRO = ["TR-34", "TR-06", "TR-35", "TR-16", "TR-41", "TR-07", "TR-59", "TR-33"]
PROVS = sorted(n1)


def grp(p):
    if p in METRO:
        return names[p] + " kayıtlı"
    if p == "TR-58":
        return "Sivas"
    return n1[p] + " (diğer iller)"


G = sorted({grp(p) for p in PROVS})
df = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_df.parquet")
m = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_m.parquet")
ELEC = {
    "mv2015h": {"AKP": ["AK PARTİ"], "CHP": ["CHP"], "MHP": ["MHP"], "HDP": ["HDP"]},
    "mv2023": {
        "AKP": ["AK PARTİ"],
        "CHP": ["CHP"],
        "MHP": ["MHP"],
        "İYİ": ["İYİ PARTİ"],
        "YSP": ["YEŞİL SOL PARTİ"],
    },
}
comp = (
    df.filter(pl.col("host").is_in(METRO))
    .join(m.select("mid", "den", "dname"), on="mid")
    .with_columns(
        (pl.col("n") / pl.col("den")).alias("s"),
        pl.col("orig").replace_strict({p: grp(p) for p in PROVS}).alias("grp"),
    )
)
W = comp.pivot(on="grp", index="mid", values="s", aggregate_function="sum").fill_null(0)
for gname in G:
    if gname not in W.columns:
        W = W.with_columns(pl.lit(0.0).alias(gname))
W = W.with_columns((1 - pl.sum_horizontal(G)).clip(0, 1).alias("Listede yok"))
COLS = G + ["Listede yok"]
OUT = {}
for el, parties in ELEC.items():
    il = json.load(open(f"public/tiles/secim-{el}-ilce.json", encoding="utf-8"))
    hg = {}  # home by group
    for k, v in il.items():
        gname = grp(k[:5])
        h = hg.setdefault(gname, {"g": 0, **{q: 0 for q in parties}})
        h["g"] += v["g"]
        for q, keys in parties.items():
            h[q] += sum(v["v"].get(x, 0) for x in keys)
    rows = []
    for p in METRO:
        t = json.load(
            open(f"public/tiles/secim-{el}-mahalle-{p}.json", encoding="utf-8")
        )
        for key, v in t.items():
            if v["g"] < 300:
                continue
            r = {
                "mid": key.split("-")[-1],
                "did": "-".join(key.split("-")[:3]),
                "g": v["g"],
                "ad": v.get("ad"),
            }
            for q, keys in parties.items():
                r[q] = sum(v["v"].get(x, 0) for x in keys) / v["g"]
            rows.append(r)
    J = (
        pl.DataFrame(rows)
        .join(W, on="mid")
        .join(m.select("mid", "den"), on="mid")
        .filter(pl.col("den") >= 500)
    )
    X = J.select(COLS).to_numpy()
    g = J["g"].to_numpy()
    w = np.sqrt(g)
    popg = (X * J["den"].to_numpy()[:, None]).sum(0)
    res = {"n": J.height, "groups": {}, "r2": {}}
    preds = {}
    for q in parties:
        y = J[q].to_numpy()
        b = lsq_linear(X * w[:, None], y * w, bounds=(0, 1)).x
        yh = X @ b
        preds[q] = yh
        res["r2"][q] = round(
            1
            - np.sum(g * (y - yh) ** 2)
            / np.sum(g * (y - np.average(y, weights=g)) ** 2),
            3,
        )
        for i, c in enumerate(COLS):
            home = hg.get(c, {})
            res["groups"].setdefault(c, {"pop": int(popg[i])})[q] = (
                round(b[i] * 100, 1),
                round(home[q] / home["g"] * 100, 1) if home else None,
            )
    # district and mahalle residuals
    J2 = J.with_columns([pl.Series("p_" + q, preds[q]) for q in parties])
    D = J2.group_by("did").agg(
        [pl.col("g").sum()]
        + [
            ((pl.col(q) * pl.col("g")).sum() / pl.col("g").sum()).alias(q)
            for q in parties
        ]
        + [
            ((pl.col("p_" + q) * pl.col("g")).sum() / pl.col("g").sum()).alias("p_" + q)
            for q in parties
        ]
    )
    D = D.with_columns(
        pl.col("did").replace_strict(dn, default=None).alias("ilce"),
        pl.col("did").str.slice(0, 5).replace_strict(names, default=None).alias("il"),
    )
    res["districts"] = D.to_dicts()
    res["mahalle"] = (
        J2.select(
            ["mid", "did", "ad", "g"] + list(parties) + ["p_" + q for q in parties]
        )
        .with_columns(pl.col("did").replace_strict(dn, default=None).alias("ilce"))
        .to_dicts()
    )
    OUT[el] = res
    print(el, res["n"], res["r2"])
    for c in COLS:
        print("  ", c, res["groups"][c])
json.dump(
    OUT,
    open(r"C:\veri-ham\analiz\2026_09_24\hem_grp.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
