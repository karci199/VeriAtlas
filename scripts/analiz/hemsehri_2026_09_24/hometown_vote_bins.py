"""Dose-response tables (eastern, Karadeniz, Sivas, local shares) and expected-vs-actual by district and neighbourhood.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import json

import numpy as np
import polars as pl

exec(
    open(
        r"scripts/analiz/hemsehri_2026_09_24/hometown_vote_groups.py", encoding="utf-8"
    )
    .read()
    .split("OUT={}")[0]
)
EAST = {
    p
    for p in PROVS
    if n1[p] in ("Kuzeydoğu Anadolu", "Ortadoğu Anadolu", "Güneydoğu Anadolu")
}
KAR = {p for p in PROVS if n1[p] in ("Batı Karadeniz", "Doğu Karadeniz")}
sh = comp.with_columns(
    pl.col("orig").is_in(list(EAST)).alias("e"),
    pl.col("orig").is_in(list(KAR)).alias("k"),
    (pl.col("orig") == "TR-58").alias("sv"),
    (pl.col("orig") == pl.col("host")).alias("yer"),
)
S = sh.group_by("mid").agg(
    (pl.col("s") * pl.col("e")).sum().alias("east"),
    (pl.col("s") * pl.col("k")).sum().alias("kar"),
    (pl.col("s") * pl.col("sv")).sum().alias("sivas"),
    (pl.col("s") * pl.col("yer")).sum().alias("yerli"),
)
R = {}
for el, parties in ELEC.items():
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
                r[q] = sum(v["v"].get(x, 0) for x in keys)
            rows.append(r)
    J = (
        pl.DataFrame(rows)
        .join(S, on="mid")
        .join(W, on="mid")
        .join(m.select("mid", "den"), on="mid")
        .filter(pl.col("den") >= 500)
    )
    out = {}
    for var, bins in (
        ("east", [0, 0.05, 0.1, 0.2, 0.3, 0.45, 1.01]),
        ("sivas", [0, 0.02, 0.05, 0.1, 0.15, 1.01]),
        ("kar", [0, 0.1, 0.2, 0.3, 0.4, 1.01]),
        ("yerli", [0, 0.1, 0.2, 0.4, 0.6, 1.01]),
    ):
        tab = []
        for a, b in zip(bins, bins[1:]):
            x = J.filter((pl.col(var) >= a) & (pl.col(var) < b))
            if x.height == 0:
                continue
            tab.append(
                [f"%{int(a * 100)}–{int(min(b, 1) * 100)}", x.height, int(x["g"].sum())]
                + [round(x[q].sum() / x["g"].sum() * 100, 1) for q in parties]
            )
        out[var] = tab
    # OLS expected on group shares
    X = np.column_stack([np.ones(J.height), J.select(G).to_numpy()])
    g = J["g"].to_numpy()
    w = np.sqrt(g)
    D = []
    for q in parties:
        y = (J[q] / J["g"]).to_numpy()
        b = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)[0]
        J = J.with_columns(pl.Series("e_" + q, X @ b * J["g"].to_numpy()))
    agg = J.group_by("did").agg(
        [pl.col("g").sum()]
        + [pl.col(q).sum() for q in parties]
        + [pl.col("e_" + q).sum() for q in parties]
    )
    agg = agg.with_columns(
        pl.col("did").replace_strict(dn, default=None).alias("ilce"),
        pl.col("did").str.slice(0, 5).replace_strict(names, default=None).alias("il"),
    )
    out["dist"] = agg.to_dicts()
    out["mah"] = (
        J.select(
            ["mid", "did", "ad", "g"] + list(parties) + ["e_" + q for q in parties]
        )
        .with_columns(pl.col("did").replace_strict(dn, default=None).alias("ilce"))
        .to_dicts()
    )
    R[el] = out
    print("==", el)
    for var in ("east", "sivas", "kar", "yerli"):
        print(var, list(parties))
        [print("  ", r) for r in out[var]]
json.dump(
    R,
    open(r"C:\veri-ham\analiz\2026_09_24\hem_bins.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
