"""Istanbul bloc-concentrated neighbourhood groups across 13 elections (2010-2024).

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
BL = {
    "TR90": "Doğu Karadeniz",
    "TR83": "Samsun-Tokat-Çorum-Amasya",
    "TR82": "Kastamonu-Çankırı-Sinop",
    "TR72": "Sivas-Kayseri-Yozgat",
    "TRA1": "Erzurum-Erzincan-Bayburt",
    "TRA2": "Kars-Ağrı-Iğdır-Ardahan",
    "TRB2": "Van-Muş-Bitlis-Hakkari",
    "TRC3": "Mardin-Batman-Şırnak-Siirt",
    "TRB1": "Malatya-Elazığ-Bingöl-Tunceli",
    "TRC1": "Gaziantep-Adıyaman-Kilis",
    "TRC2": "Şanlıurfa-Diyarbakır",
}
m = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_m.parquet").filter(
    pl.col("host") == "TR-34"
)
df = pl.read_parquet(r"C:\veri-ham\analiz\2026_09_24\hem_df.parquet").filter(
    pl.col("host") == "TR-34"
)
d = df.join(m.select("mid", "den"), on="mid").with_columns(
    pl.col("orig").replace_strict(n2).alias("b")
)
B = (
    d.filter(pl.col("b").is_in(list(BL)))
    .group_by("mid", "b")
    .agg(pl.col("n").sum())
    .join(m.select("mid", "den"), on="mid")
    .with_columns((pl.col("n") / pl.col("den")).alias("s"))
)
avg = (
    B.group_by("b")
    .agg(pl.col("n").sum())
    .with_columns((pl.col("n") / m["den"].sum()).alias("avg"))
)
B = B.join(avg.select("b", "avg"), on="b").with_columns(
    (pl.col("s") / pl.col("avg")).alias("lq")
)
groups = {
    BL[b]: set(
        B.filter((pl.col("b") == b) & (pl.col("lq") >= 2.5) & (pl.col("den") >= 1000))[
            "mid"
        ].to_list()
    )
    for b in BL
}
groups["Yerli İstanbullu (≥%40)"] = set(
    m.filter((pl.col("locsh") >= 40) & (pl.col("den") >= 1000))["mid"].to_list()
)
for k, v in groups.items():
    print(
        k,
        len(v),
        "mahalle, nüfus",
        int(m.filter(pl.col("mid").is_in(list(v)))["den"].sum()),
    )
FAM = {
    "AKP": ["AK PARTİ"],
    "CHP": ["CHP"],
    "MHP": ["MHP"],
    "İYİ": ["İYİ PARTİ"],
    "KÜRT": ["BĞMZ", "HDP", "YEŞİL SOL PARTİ", "DEM PARTİ"],
    "İSLAMCI": ["SAADET PARTİSİ", "YENİDEN REFAH"],
    "ZAFER": ["ZAFER PARTİSİ", "ZAFER"],
    "ERDOĞAN": ["RECEP TAYYİP ERDOĞAN"],
    "DEMİRTAŞ": ["SELAHATTİN DEMİRTAŞ"],
    "İMAMOĞLU": [],
    "EVET": ["Evet", "Evet oyları"],
}
E = [
    ("mv2011", "MV 2011", ["AKP", "CHP", "MHP", "KÜRT", "İSLAMCI"]),
    ("ho2010", "Halkoylaması 2010", ["EVET"]),
    ("yerel_bsb_2014", "İBB 2014", ["AKP", "CHP", "KÜRT"]),
    ("cb2014", "CB 2014", ["ERDOĞAN", "DEMİRTAŞ"]),
    ("mv2015h", "MV Haz 2015", ["AKP", "CHP", "MHP", "KÜRT", "İSLAMCI"]),
    ("mv2015k", "MV Kas 2015", ["AKP", "CHP", "MHP", "KÜRT"]),
    ("ho2017", "Halkoylaması 2017", ["EVET"]),
    ("cb2018", "CB 2018", ["ERDOĞAN", "DEMİRTAŞ"]),
    ("mv2018", "MV 2018", ["AKP", "CHP", "MHP", "İYİ", "KÜRT", "İSLAMCI"]),
    ("yerel_bsb_2019", "İBB 2019 (yenileme)", ["CHP", "AKP"]),
    ("mv2023", "MV 2023", ["AKP", "CHP", "MHP", "İYİ", "KÜRT", "İSLAMCI", "ZAFER"]),
    ("cb2023t2", "CB 2023 2. tur", ["ERDOĞAN"]),
    ("yerel_bsb_2024", "İBB 2024", ["CHP", "AKP", "KÜRT", "İSLAMCI", "ZAFER"]),
]
OUT = {}
for e, lab, fams in E:
    t = json.load(open(f"public/tiles/secim-{e}-mahalle-TR-34.json", encoding="utf-8"))
    rows = [
        {
            "mid": k.split("-")[-1],
            "g": v["g"],
            **{f: sum(v["v"].get(x, 0) for x in FAM[f]) for f in fams},
        }
        for k, v in t.items()
    ]
    T = pl.DataFrame(rows)
    res = {"İstanbul": {f: round(T[f].sum() / T["g"].sum() * 100, 1) for f in fams}}
    for gname, ids in groups.items():
        X = T.filter(pl.col("mid").is_in(list(ids)))
        res[gname] = {
            f: round(X[f].sum() / X["g"].sum() * 100, 1) if X["g"].sum() > 0 else None
            for f in fams
        }
    OUT[lab] = res
json.dump(
    OUT,
    open(r"C:\veri-ham\analiz\2026_09_24\ist_groups.json", "w", encoding="utf-8"),
    ensure_ascii=False,
)
for lab, res in OUT.items():
    print("==" + lab)
    for g, v in res.items():
        print("  ", g, v)
