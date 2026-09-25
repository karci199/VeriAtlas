"""Ecological regression of 2015-06 and 2023 votes on hometown shares in eight metros; fit comparison with SES. Per-group estimates proved unstable and were not reported.

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
df = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_df.parquet")
m = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_m.parquet")
METRO = ["TR-34", "TR-06", "TR-35", "TR-16", "TR-41", "TR-07", "TR-59", "TR-33"]
PROVS = sorted({k for k in names if k.startswith("TR-") and len(k) == 5})
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
ses = pl.read_parquet(r"C:\veri-ham\analiz\mahalle\mahalle.parquet").select(
    pl.col("id").cast(pl.Utf8).alias("mid"), "uni_share", "ses_ab_share", "elder_share"
)
SKIP = True
res = {}
for el, parties in ({} if SKIP else ELEC).items():
    # home vote per province
    il = json.load(open(f"public/tiles/secim-{el}-ilce.json", encoding="utf-8"))
    home = {}
    for k, v in il.items():
        p = k[:5]
        h = home.setdefault(p, {"g": 0, **{q: 0 for q in parties}})
        h["g"] += v["g"]
        for q, keys in parties.items():
            h[q] += sum(v["v"].get(x, 0) for x in keys)
    # mahalle results
    rows = []
    for p in METRO:
        t = json.load(
            open(f"public/tiles/secim-{el}-mahalle-{p}.json", encoding="utf-8")
        )
        for key, v in t.items():
            mid = key.split("-")[-1]
            if v["g"] < 300:
                continue
            r = {"mid": mid, "g": v["g"], "host": p}
            for q, keys in parties.items():
                r[q] = sum(v["v"].get(x, 0) for x in keys) / v["g"]
            rows.append(r)
    V = pl.DataFrame(rows)
    # composition matrix
    comp = (
        df.filter(pl.col("host").is_in(METRO))
        .join(m.select("mid", "den", "listed"), on="mid")
        .with_columns((pl.col("n") / pl.col("den")).alias("s"))
    )
    W = comp.pivot(
        on="orig", index="mid", values="s", aggregate_function="sum"
    ).fill_null(0)
    for p in PROVS:
        if p not in W.columns:
            W = W.with_columns(pl.lit(0.0).alias(p))
    W = W.with_columns((1 - pl.sum_horizontal(PROVS)).clip(0, 1).alias("OTHER"))
    J = (
        V.join(W, on="mid", how="inner")
        .join(m.select("mid", "den"), on="mid")
        .filter(pl.col("den") >= 500)
    )
    X = J.select(PROVS + ["OTHER"]).to_numpy()
    w = np.sqrt(J["g"].to_numpy())
    pop_by_orig = (X[:, :-1] * J["den"].to_numpy()[:, None]).sum(0)
    out = {"n": J.height, "parties": {}}
    Js = J.join(ses, on="mid", how="left").drop_nulls(
        ["uni_share", "ses_ab_share", "elder_share"]
    )
    Xs = Js.select(PROVS + ["OTHER"]).to_numpy()
    ws = np.sqrt(Js["g"].to_numpy())
    Z = np.column_stack(
        [
            np.ones(Js.height),
            Js["uni_share"].to_numpy(),
            Js["ses_ab_share"].to_numpy(),
            Js["elder_share"].to_numpy(),
        ]
    )
    for q in parties:
        y = J[q].to_numpy()
        fit = lsq_linear(X * w[:, None], y * w, bounds=(0, 1))
        b = fit.x
        yhat = X @ b
        r2 = 1 - np.sum(J["g"].to_numpy() * (y - yhat) ** 2) / np.sum(
            J["g"].to_numpy() * (y - np.average(y, weights=J["g"].to_numpy())) ** 2
        )
        ys = Js[q].to_numpy()

        def wr2(M):
            bb = np.linalg.lstsq(M * ws[:, None], ys * ws, rcond=None)[0]
            yh = M @ bb
            return 1 - np.sum(Js["g"].to_numpy() * (ys - yh) ** 2) / np.sum(
                Js["g"].to_numpy()
                * (ys - np.average(ys, weights=Js["g"].to_numpy())) ** 2
            )

        r2_ses = wr2(Z)
        r2_both = wr2(np.column_stack([Z, Xs[:, :-1]]))
        r2_orig_ols = wr2(np.column_stack([np.ones(Js.height), Xs[:, :-1]]))
        est = {
            names[p]: (
                round(b[i] * 100, 1),
                round(home[p][q] / home[p]["g"] * 100, 1),
                int(pop_by_orig[i]),
            )
            for i, p in enumerate(PROVS)
        }
        est["DİĞER"] = (round(b[-1] * 100, 1), None, None)
        out["parties"][q] = dict(
            r2_nnls=round(r2, 3),
            r2_ses=round(r2_ses, 3),
            r2_orig=round(r2_orig_ols, 3),
            r2_both=round(r2_both, 3),
            est=est,
        )
        print(
            el,
            q,
            "n",
            J.height,
            "R2 hemşehri(NNLS)",
            round(r2, 3),
            "| SES only",
            round(r2_ses, 3),
            "| hemşehri OLS",
            round(r2_orig_ols, 3),
            "| both",
            round(r2_both, 3),
        )
    res[el] = out
if not SKIP:
    json.dump(
        res,
        open(r"C:\veri-ham\analiz\2026_09_24\hem_vote.json", "w", encoding="utf-8"),
        ensure_ascii=False,
    )

# ---- ridge toward home vote, lambda by 5-fold CV ----
rng = np.random.default_rng(0)
res2 = {}
for el, parties in ELEC.items():
    il = json.load(open(f"public/tiles/secim-{el}-ilce.json", encoding="utf-8"))
    home = {}
    for k, v in il.items():
        p = k[:5]
        h = home.setdefault(p, {"g": 0, **{q: 0 for q in parties}})
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
            r = {"mid": key.split("-")[-1], "g": v["g"]}
            for q, keys in parties.items():
                r[q] = sum(v["v"].get(x, 0) for x in keys) / v["g"]
            rows.append(r)
    V = pl.DataFrame(rows)
    comp = (
        df.filter(pl.col("host").is_in(METRO))
        .join(m.select("mid", "den"), on="mid")
        .with_columns((pl.col("n") / pl.col("den")).alias("s"))
    )
    W = comp.pivot(
        on="orig", index="mid", values="s", aggregate_function="sum"
    ).fill_null(0)
    for p in PROVS:
        if p not in W.columns:
            W = W.with_columns(pl.lit(0.0).alias(p))
    W = W.with_columns((1 - pl.sum_horizontal(PROVS)).clip(0, 1).alias("OTHER"))
    J = (
        V.join(W, on="mid")
        .join(m.select("mid", "den"), on="mid")
        .filter(pl.col("den") >= 500)
    )
    X = J.select(PROVS + ["OTHER"]).to_numpy()
    g = J["g"].to_numpy()
    w = np.sqrt(g / g.mean())
    popo = (X[:, :-1] * J["den"].to_numpy()[:, None]).sum(0)
    folds = rng.integers(0, 5, J.height)
    out = {}
    for q in parties:
        y = J[q].to_numpy()
        tot = sum(home[p][q] for p in PROVS)
        totg = sum(home[p]["g"] for p in PROVS)
        prior = np.array([home[p][q] / home[p]["g"] for p in PROVS] + [tot / totg])

        def fit(idx, lam):
            A = np.vstack([X[idx] * w[idx, None], np.sqrt(lam) * np.eye(X.shape[1])])
            bvec = np.concatenate([y[idx] * w[idx], np.sqrt(lam) * prior])
            return lsq_linear(A, bvec, bounds=(0, 1)).x

        best = None
        for lam in [0.3, 1, 3, 10, 30, 100, 300]:
            err = 0
            for k in range(5):
                tr = folds != k
                te = ~tr
                b = fit(np.where(tr)[0], lam)
                err += np.sum(g[te] * (y[te] - X[te] @ b) ** 2)
            if best is None or err < best[1]:
                best = (lam, err)
        b = fit(np.arange(J.height), best[0])
        yh = X @ b
        r2 = 1 - np.sum(g * (y - yh) ** 2) / np.sum(
            g * (y - np.average(y, weights=g)) ** 2
        )
        out[q] = dict(
            lam=best[0],
            r2=round(r2, 3),
            est={
                names[p]: (round(b[i] * 100, 1), round(prior[i] * 100, 1), int(popo[i]))
                for i, p in enumerate(PROVS)
            },
        )
        print(el, q, "lambda", best[0], "R2", round(r2, 3))
    res2[el] = out
json.dump(
    res2,
    open(r"C:\veri-ham\analiz\2026_09_24\hem_vote_ridge.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
