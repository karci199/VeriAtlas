"""Neighbourhood x age matrix by iterative proportional fitting, then urban/rural median and mean.

The residual method (yas_artik.py) dumps every urban error on the rural remainder -- in a
district that is 97% urban a 1% urban error is a 30% rural one (Yıldırım went negative).
Here every cell is fitted at once to three exact TÜİK margins:
  1. district 5-year groups (ADNKS 2025),
  2. neighbourhood population,
  3. neighbourhood 0-17 / 18+ split where TÜİK gives it.
Seed: Endeksa 2024 bands where they add up to the TÜİK population (+-10%), otherwise the
district's mean shape of usable neighbourhoods of the same class (urban / rural). Endeksa's
65+ is split with the district's own old-age shape. 15-19 is split 15-17 / 18-19 (3:2) so
the child margin can be applied.

usage: yas_ipf.py 16 <dir with kent_16_ikili.csv>
"""

import json, sys
from pathlib import Path
import duckdb, numpy as np, polars as pl

PLATE, D = sys.argv[1], Path(sys.argv[2])
ROOT = Path("C:/veri")
# 20 working columns; 3 = 15-17, 4 = 18-19 (both inside TÜİK's 15-19)
EDGES = [0, 5, 10, 15, 18, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 100]
TLAB = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64",
        "65-69", "70-74", "75-79", "80-84", "85-89", "90+"]
COL2T = [0, 1, 2, 3, 3] + list(range(4, 19))  # working column -> TÜİK group
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
E = {}
for f in Path("C:/veri-ham/endeksa/demography").glob(f"TR-{PLATE}-*.json"):
    for code, v in json.loads(f.read_text(encoding="utf-8")).items():
        e = v.get("demography") or {}
        E[f"{f.stem}-{code}"] = np.array([e.get(f"Age_{k}_Total") or 0 for k in EK], float)
nb = pl.read_csv(D / f"kent_{PLATE}_ikili.csv", infer_schema_length=0)


def to20(b, dist):
    old = dist[13:] / max(dist[13:].sum(), 1)
    return np.concatenate([b[:3], [b[3] * 0.6, b[3] * 0.4], b[4:13], b[13] * old])


def med(c):
    h, acc = c.sum() / 2, 0
    for i, n in enumerate(c):
        if n > 0 and acc + n >= h:
            return EDGES[i] + (h - acc) / n * (EDGES[i + 1] - EDGES[i])
        acc += n


MID = np.array([(EDGES[i] + EDGES[i + 1]) / 2 for i in range(20)])
MID[-1] = 93  # 90+
mean = lambda c: float((c * MID).sum() / c.sum())

res, cells = [], []
for did, dist in sorted(DIST.items()):
    sub = nb.filter(pl.col("area_id").str.starts_with(did + "-") & pl.col("area_id").map_elements(lambda a: (POP.get(a) or 0) > 0, return_dtype=pl.Boolean))
    ids, kk = sub["area_id"].to_list(), sub["kent_kir"].to_list()
    P = np.array([POP[a] for a in ids], float)
    seed = np.zeros((len(ids), 20))
    usable = np.zeros(len(ids), bool)
    for i, a in enumerate(ids):
        b = E.get(a)
        if b is not None and abs(b.sum() - P[i]) <= 0.1 * P[i]:
            seed[i] = to20(b, dist) / b.sum() * P[i]; usable[i] = True
    for cls in ("kent", "kır"):
        m = np.array([k == cls for k in kk])
        src = usable & m if (usable & m).any() else usable
        shape = seed[src].sum(0); shape = shape / shape.sum()
        seed[m & ~usable] = np.outer(P[m & ~usable], shape)
    seed += 1e-6
    hasK = np.array([a in KID for a in ids])
    K = np.array([KID.get(a, 0) for a in ids], float)
    X = seed.copy()
    for it in range(500):
        # district margin (15-17 and 18-19 share TÜİK's 15-19)
        colsum = np.zeros(19)
        np.add.at(colsum, COL2T, X.sum(0))
        X *= (dist / np.maximum(colsum, 1e-9))[COL2T]
        # neighbourhood margins: child / adult where known, total otherwise
        c, ad = X[:, CHILD].sum(1), X[:, ~CHILD].sum(1)
        X[hasK][:, CHILD]  # noqa
        X[np.ix_(hasK, CHILD)] *= (K[hasK] / np.maximum(c[hasK], 1e-9))[:, None]
        X[np.ix_(hasK, ~CHILD)] *= ((P[hasK] - K[hasK]) / np.maximum(ad[hasK], 1e-9))[:, None]
        X[~hasK] *= (P[~hasK] / np.maximum(X[~hasK].sum(1), 1e-9))[:, None]
        colsum = np.zeros(19); np.add.at(colsum, COL2T, X.sum(0))
        if np.abs(colsum - dist).max() < 0.5:
            break
    err = float(np.abs(colsum - dist).sum() / dist.sum() * 100)
    name = sub["district"][0]
    for cls in ("kent", "kır"):
        m = np.array([k == cls for k in kk])
        if m.any():
            u = X[m].sum(0)
            s0 = seed[m].sum(0)
            res.append(dict(ilce=name, sinif=cls, nufus=round(u.sum()), ortanca=round(med(u), 1), ortalama=round(mean(u), 1),
                            tohum_ortanca=round(med(s0), 1), cocuk=round(u[CHILD].sum() / u.sum() * 100, 1),
                            yasli65=round(u[15:].sum() / u.sum() * 100, 1), olcum_payi=round(P[m & usable].sum() / P[m].sum() * 100),
                            uyum_hatasi=round(err, 2), tur=it + 1, _c=u))
    for a, row in zip(ids, X):
        cells.append(dict(area_id=a, ortanca=round(med(row), 1), ortalama=round(mean(row), 1)))

# province
for cls in ("kent", "kır"):
    u = sum(r["_c"] for r in res if r["sinif"] == cls)
    res.append(dict(ilce="BURSA", sinif=cls, nufus=round(u.sum()), ortanca=round(med(u), 1), ortalama=round(mean(u), 1),
                    tohum_ortanca=None, cocuk=round(u[CHILD].sum() / u.sum() * 100, 1), yasli65=round(u[15:].sum() / u.sum() * 100, 1),
                    olcum_payi=None, uyum_hatasi=None, tur=None, _c=u))
r = pl.DataFrame([{k: v for k, v in x.items() if k != "_c"} for x in res])
r.write_csv(D / f"yas_ipf_{PLATE}.csv")
pl.DataFrame(cells).write_csv(D / f"yas_ipf_{PLATE}_mahalle.csv")
w = r.pivot(on="sinif", index="ilce", values=["ortanca", "ortalama", "cocuk", "yasli65", "olcum_payi"])
w = w.with_columns((pl.col("ortanca_kır") - pl.col("ortanca_kent")).round(1).alias("fark_ortanca"),
                   (pl.col("ortalama_kır") - pl.col("ortalama_kent")).round(1).alias("fark_ortalama")).sort("ortanca_kent")
w.write_csv(D / f"yas_ipf_{PLATE}_ozet.csv")
pl.Config.set_tbl_rows(30); pl.Config.set_tbl_width_chars(250); pl.Config.set_tbl_cols(20)
print(w.select("ilce", "ortanca_kent", "ortanca_kır", "fark_ortanca", "ortalama_kent", "ortalama_kır", "fark_ortalama", "cocuk_kır", "yasli65_kır", "olcum_payi_kır"))
print(r.filter(pl.col("sinif") == "kır").select("ilce", "uyum_hatasi", "tur", "tohum_ortanca", "ortanca"))
