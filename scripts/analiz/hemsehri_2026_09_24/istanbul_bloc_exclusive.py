"""Istanbul: each neighbourhood in its largest bloc if that bloc is at least 15%.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import json

import polars as pl

exec(
    open(
        r"scripts/analiz/hemsehri_2026_09_24/istanbul_bloc_elections.py",
        encoding="utf-8",
    )
    .read()
    .split("groups={")[0]
)
top = B.sort("s", descending=True).group_by("mid").first().filter(pl.col("s") >= 0.15)
top = top.join(m.select("mid", "den"), on="mid").filter(pl.col("den") >= 1000)
groups = {}
for b in BL:
    groups[BL[b]] = set(top.filter(pl.col("b") == b)["mid"].to_list())
groups["Yerli İstanbullu (≥%40)"] = set(
    m.filter((pl.col("locsh") >= 40) & (pl.col("den") >= 1000))["mid"].to_list()
)
mixed = set(m.filter(pl.col("den") >= 1000)["mid"].to_list()) - set().union(
    *groups.values()
)
groups["Karışık (baskın blok yok)"] = mixed
for k, v in groups.items():
    print(k, len(v), int(m.filter(pl.col("mid").is_in(list(v)))["den"].sum()))
COLS = [
    ("cb2014", "ERDOĞAN", "Erdoğan 2014"),
    ("cb2018", "ERDOĞAN", "Erdoğan 2018"),
    ("cb2023t2", "ERDOĞAN", "Erdoğan 2023-2"),
    ("mv2011", "AKP", "AKP 2011"),
    ("mv2015h", "AKP", "AKP H2015"),
    ("mv2018", "AKP", "AKP 2018"),
    ("mv2023", "AKP", "AKP 2023"),
    ("mv2011", "CHP", "CHP 2011"),
    ("mv2015h", "CHP", "CHP H2015"),
    ("mv2023", "CHP", "CHP 2023"),
    ("mv2015h", "MHP", "MHP H2015"),
    ("mv2023", "MHPİYİ", "MHP+İYİ 2023"),
    ("mv2011", "KÜRT", "Kürt 2011"),
    ("mv2015h", "KÜRT", "HDP H2015"),
    ("mv2015k", "KÜRT", "HDP K2015"),
    ("mv2023", "KÜRT", "YSP 2023"),
    ("yerel_bsb_2019", "CHP", "İmamoğlu 2019"),
    ("yerel_bsb_2024", "CHP", "İmamoğlu 2024"),
    ("ho2010", "EVET", "Evet 2010"),
    ("ho2017", "EVET", "Evet 2017"),
    ("mv2023", "İSLAMCI", "YRP+SP 2023"),
    ("mv2023", "ZAFER", "Zafer 2023"),
]
FAM = {
    "AKP": ["AK PARTİ"],
    "CHP": ["CHP"],
    "MHP": ["MHP"],
    "KÜRT": ["BĞMZ", "HDP", "YEŞİL SOL PARTİ", "DEM PARTİ"],
    "İSLAMCI": ["SAADET PARTİSİ", "YENİDEN REFAH"],
    "ZAFER": ["ZAFER PARTİSİ", "ZAFER"],
    "ERDOĞAN": ["RECEP TAYYİP ERDOĞAN"],
    "EVET": ["Evet", "Evet oyları"],
    "MHPİYİ": ["MHP", "İYİ PARTİ"],
}
groups = {k: v for k, v in groups.items() if v}
cache = {}
res = {g: {} for g in ["İstanbul"] + list(groups)}
for e, f, lab in COLS:
    if e not in cache:
        cache[e] = json.load(
            open(f"public/tiles/secim-{e}-mahalle-TR-34.json", encoding="utf-8")
        )
    t = cache[e]
    T = pl.DataFrame(
        [
            {
                "mid": k.split("-")[-1],
                "g": v["g"],
                "x": sum(v["v"].get(x, 0) for x in FAM[f]),
            }
            for k, v in t.items()
        ]
    )
    res["İstanbul"][lab] = round(T["x"].sum() / T["g"].sum() * 100, 1)
    for g, ids in groups.items():
        X = T.filter(pl.col("mid").is_in(list(ids)))
        res[g][lab] = (
            round(X["x"].sum() / X["g"].sum() * 100, 1) if X["g"].sum() > 0 else None
        )
json.dump(
    {
        "groups": {k: len(v) for k, v in groups.items()},
        "res": res,
        "cols": [c[2] for c in COLS],
    },
    open(r"C:\veri-ham\analiz\2026_09_24\ist3.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
labs = [c[2] for c in COLS]
print("| Grup | " + " | ".join(labs) + " |")
for g, v in res.items():
    print(
        "| " + g + " | " + " | ".join(str(v[l]).replace(".", ",") for l in labs) + " |"
    )
