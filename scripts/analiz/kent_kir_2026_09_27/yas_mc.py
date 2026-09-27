"""Median age per neighbourhood, semt, district x urban/rural -- with uncertainty.

Seed shape of every neighbourhood (20 age columns, 15-19 split 15-17 / 18-19):
  A. Endeksa 2024 bands where they add up to the TÜİK population (+-10%): 558 places, 95% of people
  B. else, if Endeksa marital counts exist: median predicted by a regression fitted on A
     (median ~ widow share + never-married share + TÜİK 0-17 share; R2 0.94, RMSE 1.9 on A),
     then the mean shape of A-places of the same class province-wide whose own median lies
     within 1.5 years of the prediction (widened until >= 5 donors)
  C. else: mean shape of the district's A-places of the same class
Then iterative proportional fitting to the exact TÜİK margins: district 5-year groups,
neighbourhood population, neighbourhood 0-17 where given.

Monte Carlo (N draws): Endeksa bands x lognormal(0, 0.10); regression refitted on a bootstrap
of A and prediction + N(0, RMSE); 65+ split ~ Dirichlet around the district's old-age shape;
15-17 share of 15-19 ~ U(0.55, 0.65). Median and 5-95 percentile of the draws are reported.
Hold-out: 30% of A hidden and predicted through B, five repeats, fitted on the rest.
Sensitivity: every borderline ("arada") neighbourhood moved to the other class.

usage: yas_mc.py 16 <dir> [draws]
"""

import json, sys, time
from pathlib import Path
import duckdb, numpy as np, polars as pl

PLATE, D = sys.argv[1], Path(sys.argv[2])
N = int(sys.argv[3]) if len(sys.argv) > 3 else 200
ROOT = Path("C:/veri")
rng = np.random.default_rng(20260928)
EDGES = np.array([0, 5, 10, 15, 18, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 100], float)
TLAB = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64",
        "65-69", "70-74", "75-79", "80-84", "85-89", "90+"]
COL2T = np.array([0, 1, 2, 3, 3] + list(range(4, 19)))
CHILD = np.array([1, 1, 1, 1] + [0] * 16, bool)
EK = ["0_4", "5_9", "10_14", "15_19", "20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54", "55_59", "60_64", "65"]

q = lambda s: duckdb.sql(s.replace("FACT", f"read_parquet('{ROOT}/public/fact.parquet')")).fetchall()
DIST = {}
for aid, g, v in q(f"""select area_id, regexp_extract(dims,'age=([^;]+)',1), sum(value) from FACT where indicator_id='population'
 and area_id like 'TR-{PLATE}-___' and year(period_start)=2025 and dims like 'age=%sex=%' group by 1,2"""):
    DIST.setdefault(aid, np.zeros(19))[TLAB.index(g)] += v
POP = dict(q(f"""select area_id, sum(value) from FACT where indicator_id='population' and area_id like 'TR-{PLATE}-%-%'
 and year(period_start)=2025 group by 1"""))
KID = dict(q(f"""select area_id, sum(value) from FACT where indicator_id='population' and area_id like 'TR-{PLATE}-%-%'
 and year(period_start)=2025 and dims='age=0-17' group by 1"""))
E, MAR = {}, {}
for f in Path("C:/veri-ham/endeksa/demography").glob(f"TR-{PLATE}-*.json"):
    for code, v in json.loads(f.read_text(encoding="utf-8")).items():
        e = v.get("demography") or {}
        a = f"{f.stem}-{code}"
        E[a] = np.array([e.get(f"Age_{k}_Total") or 0 for k in EK], float)
        ms = sum(e.get(k) or 0 for k in ("MarriedNever", "Married", "Divorced", "Widow"))
        if ms >= 20:
            MAR[a] = ((e.get("Widow") or 0) / ms, (e.get("MarriedNever") or 0) / ms)
nb = pl.read_csv(D / f"kent_{PLATE}_ikili.csv", infer_schema_length=0)
nb = nb.filter(pl.col("area_id").is_in([a for a in nb["area_id"] if (POP.get(a) or 0) > 0]))
SEMT = dict(pl.read_csv(D / f"semt_{PLATE}_mahalle.csv").select("area_id", "semt").iter_rows())
ARADA = set(nb.filter(pl.col("arada").is_not_null() & (pl.col("arada") != ""))["area_id"])
IDS = nb["area_id"].to_list(); KK = np.array(nb["kent_kir"].to_list()); DID = np.array([a.rsplit("-", 1)[0] for a in IDS])
NAME = dict(zip(nb["area_id"], nb["district"]))
P = np.array([POP[a] for a in IDS], float)
HASK = np.array([a in KID for a in IDS]); K = np.array([KID.get(a, 0) for a in IDS], float)
# registered voters (2024 local: no prison boxes) ~ 18+ residents x 1.02 in villages (p10-p90
# 0.97-1.09); where TÜİK gives no 0-17, children = population - voters / 1.02, clipped at 0
VOT = {a: v["k"] for a, v in json.loads((ROOT / f"public/tiles/secim-yerel_bsb_2024-mahalle-TR-{PLATE}.json").read_text(encoding="utf-8")).items()}
HASV = np.array([(not HASK[i]) and a in VOT for i, a in enumerate(IDS)])
KV = np.array([VOT.get(a, 0) for a in IDS], float)


def child_margin(noise):
    """(K, hasK) for this draw: TÜİK 0-17 where given, voter-based estimate elsewhere."""
    r = rng.lognormal(np.log(1.02), 0.04, len(IDS)) if noise else np.full(len(IDS), 1.02)
    Kx = np.where(HASK, K, np.clip(P - KV / r, 0, P))
    return Kx, HASK | HASV


USABLE = np.array([a in E and abs(E[a].sum() - P[i]) <= 0.1 * P[i] for i, a in enumerate(IDS)])
HASM = np.array([a in MAR for a in IDS])


def medians(X):
    c = np.cumsum(X, 1); h = X.sum(1, keepdims=True) / 2
    i = np.clip((c < h).sum(1), 0, 19)
    prev = np.where(i > 0, c[np.arange(len(X)), np.maximum(i - 1, 0)], 0)
    n = X[np.arange(len(X)), i]
    return EDGES[i] + np.where(n > 0, (h[:, 0] - prev) / np.maximum(n, 1e-12), 0) * (EDGES[i + 1] - EDGES[i])


def to20(b, old, s1517):
    return np.concatenate([b[:3], [b[3] * s1517, b[3] * (1 - s1517)], b[4:13], b[13] * old])


def shapes_A(noise, mask):
    """Normalised 20-column shape of every A-place (nan rows elsewhere)."""
    S = np.full((len(IDS), 20), np.nan)
    s1517 = rng.uniform(0.55, 0.65) if noise else 0.6
    for did, dist in DIST.items():
        old = dist[13:] / max(dist[13:].sum(), 1)
        if noise:
            old = rng.dirichlet(old * 200 + 0.5)
        for i in np.where(USABLE & ~mask & (DID == did))[0]:
            b = E[IDS[i]] * (rng.lognormal(0, 0.10, 14) if noise else 1)
            v = to20(b, old, s1517); S[i] = v / v.sum()
    return S


def regression(train, noise):
    """median ~ 1 + widow + never_married + child share, fitted on train rows."""
    idx = np.where(train)[0]
    if noise:
        idx = rng.choice(idx, len(idx))
    X = np.column_stack([np.ones(len(idx)), [MAR[IDS[i]][0] for i in idx], [MAR[IDS[i]][1] for i in idx],
                         np.where(HASK[idx], K[idx] / P[idx], np.nan)])
    X[:, 3] = np.where(np.isnan(X[:, 3]), np.nanmedian(X[:, 3]), X[:, 3])
    y = MED_A[idx]
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    rmse = float(np.sqrt(((X @ beta - y) ** 2).mean()))
    return beta, rmse, float(np.nanmedian(X[:, 3]))


def build(noise=False, mask=None):
    mask = np.zeros(len(IDS), bool) if mask is None else mask
    S = shapes_A(noise, mask)
    medA = medians(np.nan_to_num(S))
    train = USABLE & ~mask & HASM
    beta, rmse, cmed = regression(train, noise)
    seed = np.zeros((len(IDS), 20)); src = np.full(len(IDS), "C", dtype="<U1")
    src[USABLE & ~mask] = "A"
    for i in np.where(~(USABLE & ~mask))[0]:
        cls = KK[i]
        pool = np.where(train & (KK == cls))[0]
        if HASM[i] and len(pool) >= 5:
            x = np.array([1, MAR[IDS[i]][0], MAR[IDS[i]][1], K[i] / P[i] if HASK[i] else cmed])
            pred = float(x @ beta) + (rng.normal(0, rmse) if noise else 0)
            w = 1.5
            while True:
                near = pool[np.abs(medA[pool] - pred) <= w]
                if len(near) >= 5 or w > 20:
                    break
                w += 1
            S[i] = S[near].mean(0); src[i] = "B"
        else:
            pool = np.where(train & (DID == DID[i]) & (KK == cls))[0]
            if not len(pool):
                pool = np.where(train & (DID == DID[i]))[0]
            S[i] = S[pool].mean(0)
    seed = S / S.sum(1, keepdims=True) * P[:, None]
    return seed, src, (beta, rmse)


def fit(seed, Kx=None, hkx=None, iters=400):
    if Kx is None:
        Kx, hkx = child_margin(False)
    X = seed.copy()
    for did, dist in DIST.items():
        m = DID == did
        Xd = X[m] + 1e-6; Pd, Kd, hk = P[m], Kx[m], hkx[m]
        for _ in range(iters):
            cs = np.zeros(19); np.add.at(cs, COL2T, Xd.sum(0))
            Xd *= (dist / np.maximum(cs, 1e-9))[COL2T]
            c, ad = Xd[:, CHILD].sum(1), Xd[:, ~CHILD].sum(1)
            Xd[np.ix_(hk, CHILD)] *= (Kd[hk] / np.maximum(c[hk], 1e-9))[:, None]
            Xd[np.ix_(hk, ~CHILD)] *= ((Pd[hk] - Kd[hk]) / np.maximum(ad[hk], 1e-9))[:, None]
            Xd[~hk] *= (Pd[~hk] / np.maximum(Xd[~hk].sum(1), 1e-9))[:, None]
            cs = np.zeros(19); np.add.at(cs, COL2T, Xd.sum(0))
            if np.abs(cs - dist).max() < 0.5:
                break
        X[m] = Xd
    return X


# central run
S0 = shapes_A(False, np.zeros(len(IDS), bool)); MED_A = medians(np.nan_to_num(S0))
seed0, src0, (beta0, rmse0) = build()
X0 = fit(seed0)
print(f"regresyon: sabit {beta0[0]:.1f}, dul {beta0[1]:.1f}, bekâr {beta0[2]:.1f}, çocuk {beta0[3]:.1f}; RMSE {rmse0:.2f}")
print("kaynak:", {s: (int((src0 == s).sum()), int(P[src0 == s].sum())) for s in "ABC"})
print("çocuk kısıtı: TÜİK", int(HASK.sum()), "| seçmenden", int(HASV.sum()), f"({int(P[HASV].sum())} kişi) | yok", int((~HASK & ~HASV).sum()))

t0 = time.time()
GROUPS = {}  # key -> boolean mask over IDS
for did in DIST:
    for cls in ("kent", "kır"):
        m = (DID == did) & (KK == cls)
        if m.any():
            GROUPS[("ilce", NAME[IDS[np.where(m)[0][0]]], cls)] = m
for cls in ("kent", "kır"):
    GROUPS[("ilce", "BURSA", cls)] = KK == cls
for s in set(SEMT.values()):
    m = np.array([SEMT.get(a) == s for a in IDS])
    if m.any():
        GROUPS[("semt", NAME[IDS[np.where(m)[0][0]]], s)] = m
draws = {k: [] for k in GROUPS}; nbd = []
for r in range(N):
    X = fit(build(True)[0], *child_margin(True))
    for k, m in GROUPS.items():
        draws[k].append(X[m].sum(0))
    nbd.append(medians(X))
    if r % 25 == 0:
        print(f"tur {r} ({time.time() - t0:.0f} sn)", flush=True)
nbd = np.array(nbd)

def summ(arr):
    md = medians(np.array(arr)); return float(np.median(md)), float(np.percentile(md, 5)), float(np.percentile(md, 95))

rows = {}
for (kind, ilce, key), v in draws.items():
    if kind != "ilce":
        continue
    o, lo, hi = summ(v); rows.setdefault(ilce, {"ilce": ilce}) | {}
    rows[ilce] |= {f"{key}_ortanca": o, f"{key}_p5": lo, f"{key}_p95": hi, f"{key}_merkezi": float(medians(X0[GROUPS[(kind, ilce, key)]].sum(0, keepdims=True))[0])}
for ilce, r in rows.items():
    if ("ilce", ilce, "kır") in draws and ("ilce", ilce, "kent") in draws:
        f = medians(np.array(draws[("ilce", ilce, "kır")])) - medians(np.array(draws[("ilce", ilce, "kent")]))
        r |= {"fark": float(np.median(f)), "fark_p5": float(np.percentile(f, 5)), "fark_p95": float(np.percentile(f, 95))}
rnd = lambda df: df.with_columns(pl.col(pl.Float64).round(1))
out = rnd(pl.DataFrame(list(rows.values()))).sort("kent_ortanca")
out.write_csv(D / f"yas_mc_{PLATE}_ilce.csv")
rnd(pl.DataFrame([dict(ilce=i, semt=s, nufus=int(P[GROUPS[k]].sum()), **dict(zip(("ortanca", "p5", "p95"), summ(v))))
                  for k, v in draws.items() if k[0] == "semt" for _, i, s in [k]])).sort("ilce", "nufus", descending=[False, True]).write_csv(D / f"yas_mc_{PLATE}_semt.csv")
rnd(pl.DataFrame(dict(area_id=IDS, ilce=[NAME[a] for a in IDS], kent_kir=KK, nufus=P, kaynak=src0, ortanca=np.median(nbd, 0),
                      p5=np.percentile(nbd, 5, 0), p95=np.percentile(nbd, 95, 0)))).write_csv(D / f"yas_mc_{PLATE}_mahalle.csv")

# hold-out
hold = []
base = medians(X0)
for rep in range(5):
    mask = USABLE & (rng.random(len(IDS)) < 0.3)
    est = medians(fit(build(False, mask)[0]))
    for i in np.where(mask)[0]:
        hold.append(dict(kent_kir=KK[i], nufus=P[i], yol="B" if HASM[i] else "C", gercek=base[i], tahmin=est[i]))
h = pl.DataFrame(hold).with_columns((pl.col("tahmin") - pl.col("gercek")).alias("hata"),
                                    pl.when(pl.col("nufus") < 500).then(pl.lit("<500")).when(pl.col("nufus") < 2000).then(pl.lit("500-2000")).otherwise(pl.lit("2000+")).alias("boy"))
h.write_csv(D / f"yas_mc_{PLATE}_holdout.csv")
print(h.group_by("kent_kir", "boy").agg(pl.len(), pl.col("hata").mean().round(2).alias("sapma"), pl.col("hata").abs().mean().round(2).alias("ort_mutlak"),
                                         pl.col("hata").abs().quantile(0.9).round(2).alias("p90_mutlak")).sort("kent_kir", "boy"))

# sensitivity
KK2 = np.array([("kır" if k == "kent" else "kent") if a in ARADA else k for a, k in zip(IDS, KK)])
sens = []
for did in list(DIST) + ["BURSA"]:
    dm = np.ones(len(IDS), bool) if did == "BURSA" else DID == did
    r = dict(ilce="BURSA" if did == "BURSA" else NAME[IDS[np.where(dm)[0][0]]])
    for cls in ("kent", "kır"):
        for lab, arr in (("", KK), ("_ters", KK2)):
            m = dm & (arr == cls)
            r[f"{cls}{lab}"] = float(medians(X0[m].sum(0, keepdims=True))[0]) if m.any() else None
    sens.append(r)
rnd(pl.DataFrame(sens)).write_csv(D / f"yas_mc_{PLATE}_duyarlilik.csv")
pl.Config.set_tbl_rows(40); pl.Config.set_tbl_width_chars(250); pl.Config.set_tbl_cols(20)
print(out.select("ilce", "kent_ortanca", "kent_p5", "kent_p95", "kır_ortanca", "kır_p5", "kır_p95", "fark", "fark_p5", "fark_p95"))
print(rnd(pl.DataFrame(sens)))
print("bitti", round(time.time() - t0), "sn")
