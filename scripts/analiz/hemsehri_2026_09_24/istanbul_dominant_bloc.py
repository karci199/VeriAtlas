"""Istanbul: every neighbourhood in its dominant bloc, no threshold, across elections.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import json

import polars as pl

names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
code = {v: k for k, v in names.items() if k.startswith("TR-") and len(k) == 5}
nuts = list(
    csv.DictReader(open(r"C:\veri\src\veriatlas\data\nuts_tr.csv", encoding="utf-8"))
)
n2 = {code[r["province_name"]]: r["nuts2_id"] for r in nuts}
lab = {}
for r in nuts:
    lab.setdefault(r["nuts2_id"], []).append(r["province_name"])
lab = {k: "–".join(v) for k, v in lab.items()}
lab["TR10"] = "İstanbul kayıtlı"
m = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_m.parquet").filter(
    pl.col("host") == "TR-34"
)
df = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_df.parquet").filter(
    pl.col("host") == "TR-34"
)
B = (
    df.with_columns(pl.col("orig").replace_strict(n2).alias("b"))
    .group_by("mid", "b")
    .agg(pl.col("n").sum())
)
dom = (
    B.sort("n", descending=True)
    .group_by("mid")
    .first()
    .join(m.select("mid", "den"), on="mid")
    .with_columns((pl.col("n") / pl.col("den") * 100).alias("pay"))
)
G = (
    dom.group_by("b")
    .agg(
        pl.len().alias("mah"),
        pl.col("den").sum().alias("nufus"),
        ((pl.col("pay") * pl.col("den")).sum() / pl.col("den").sum())
        .round(1)
        .alias("ort_pay"),
    )
    .sort("nufus", descending=True)
)
print([(lab[r[0]], r[1], int(r[2]), r[3]) for r in G.rows()])
print("toplam mahalle", dom.height, "of", m.height)
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
COLS = [
    ("cb2014", "ERDOĞAN", "Erd14"),
    ("cb2018", "ERDOĞAN", "Erd18"),
    ("cb2023t2", "ERDOĞAN", "Erd23"),
    ("mv2011", "AKP", "AKP11"),
    ("mv2015h", "AKP", "AKP15H"),
    ("mv2023", "AKP", "AKP23"),
    ("mv2011", "CHP", "CHP11"),
    ("mv2023", "CHP", "CHP23"),
    ("mv2011", "KÜRT", "Kürt11"),
    ("mv2015h", "KÜRT", "HDP15H"),
    ("mv2023", "KÜRT", "YSP23"),
    ("mv2015h", "MHP", "MHP15H"),
    ("mv2023", "MHPİYİ", "MHP+İYİ23"),
    ("yerel_bsb_2019", "CHP", "İmam19"),
    ("yerel_bsb_2024", "CHP", "İmam24"),
    ("ho2010", "EVET", "Evet10"),
    ("ho2017", "EVET", "Evet17"),
    ("mv2023", "İSLAMCI", "YRP+SP23"),
]
res = {}
tiles = {}
for e, f, l in COLS:
    t = tiles.setdefault(
        e,
        json.load(open(f"public/tiles/secim-{e}-mahalle-TR-34.json", encoding="utf-8")),
    )
    T = (
        pl.DataFrame(
            [
                {
                    "mid": k.split("-")[-1],
                    "g": v["g"],
                    "x": sum(v["v"].get(x, 0) for x in FAM[f]),
                }
                for k, v in t.items()
            ]
        )
        .join(dom.select("mid", "b"), on="mid", how="left")
        .with_columns(pl.col("b").fill_null("?"))
    )
    res.setdefault("İstanbul", {})[l] = round(T["x"].sum() / T["g"].sum() * 100, 1)
    for b, x, g in T.group_by("b").agg(pl.col("x").sum(), pl.col("g").sum()).rows():
        res.setdefault(b, {})[l] = round(x / g * 100, 1) if g else None
order = ["İstanbul"] + G["b"].to_list()
labs = [c[2] for c in COLS]
print("| Baskın blok | Mah. | Nüfus | Blok payı | " + " | ".join(labs) + " |")
for b in order:
    if b == "İstanbul":
        pre = "| **İstanbul geneli** | 960 | 15,7 mn | – |"
    else:
        r = G.filter(pl.col("b") == b).row(0)
        pre = f"| {lab[b]} | {r[1]} | {r[2] / 1e6:.2f} mn | %{r[3]} |".replace(".", ",")
    print(
        pre
        + " "
        + " | ".join(str(res[b].get(l)).replace(".", ",") for l in labs)
        + " |"
    )
