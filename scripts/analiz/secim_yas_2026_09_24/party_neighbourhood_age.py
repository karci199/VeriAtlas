"""Per-province vote-weighted neighbourhood age of each party relative to the province.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import glob
import json

import polars as pl

names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
P = {
    "AKP": "AK PARTİ",
    "CHP": "CHP",
    "MHP": "MHP",
    "İYİ": "İYİ PARTİ",
    "YSP": "YEŞİL SOL PARTİ",
    "YRP": "YENİDEN REFAH",
    "ZP": "ZAFER PARTİSİ",
    "TİP": "TİP",
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
                "yas": sum((x.get(f"Age_{b}_Total") or 0) * w * mm for b, mm, w in B)
                / ad,
            }
        )
E = pl.DataFrame(rows)
V = []
for t in glob.glob("public/tiles/secim-mv2023-mahalle-TR-*.json"):
    for k, v in json.load(open(t, encoding="utf-8")).items():
        V.append(
            {
                "mid": k.split("-")[-1],
                "il": k[:5],
                "g": v["g"],
                **{q: v["v"].get(n, 0) for q, n in P.items()},
            }
        )
V = pl.DataFrame(V)
D = V.join(E, on="mid", how="left")
cov = D.group_by("il").agg(
    (
        pl.col("g").filter(pl.col("yas").is_not_null()).sum() / pl.col("g").sum() * 100
    ).alias("kapsam")
)
A = D.filter(pl.col("yas").is_not_null())
agg = (
    A.group_by("il")
    .agg(
        ((pl.col("g") * pl.col("yas")).sum() / pl.col("g").sum()).alias("il_ort"),
        *[
            pl.when(pl.col(q).sum() > 0)
            .then((pl.col(q) * pl.col("yas")).sum() / pl.col(q).sum())
            .otherwise(None)
            .alias(q)
            for q in P
        ],
        *[(pl.col(q).sum() / pl.col("g").sum() * 100).alias("oy_" + q) for q in P],
    )
    .join(cov, on="il")
    .sort("il")
)
res = {}
for r in agg.iter_rows(named=True):
    res[r["il"]] = {
        "ad": names[r["il"]],
        "il_ort": r["il_ort"],
        "kapsam": r["kapsam"],
        **{q: (r[q], r["oy_" + q]) for q in P},
    }
tr = A.select(
    ((pl.col("g") * pl.col("yas")).sum() / pl.col("g").sum()).alias("x"),
    *[((pl.col(q) * pl.col("yas")).sum() / pl.col(q).sum()).alias(q) for q in P],
).row(0, named=True)
res["TR"] = {
    "ad": "Türkiye",
    "il_ort": tr["x"],
    "kapsam": None,
    **{q: (tr[q], None) for q in P},
}
json.dump(
    res,
    open(r"C:\veri-ham\analiz\2026_09_24\age_vw.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
f = lambda x: f"{x:+.1f}".replace(".", ",") if x is not None else "–"
print("TR", round(tr["x"], 1), {q: round(tr[q] - tr["x"], 2) for q in P})
for il, r in sorted(res.items(), key=lambda kv: kv[1]["ad"] if kv[0] != "TR" else ""):
    if il == "TR":
        continue
    cells = []
    for q in P:
        a, share = r[q]
        cells.append(
            f(a - r["il_ort"]) if a is not None and share and share >= 0.5 else "–"
        )
    print(
        f"| {r['ad']} | {r['il_ort']:.1f} | {r['kapsam']:.0f} | "
        + " | ".join(cells)
        + " |"
    )
