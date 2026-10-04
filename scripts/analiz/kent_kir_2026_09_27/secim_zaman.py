"""Neighbourhood-level election analysis over time with the fixed urban/rural list.

usage: secim_zaman.py 16

Every result tile key is resolved to today's class: a current neighbourhood id directly, a
2007-2012 id through tarihsel_<p>_sabit_satir.csv, a pre-2013 belde aggregate ("Görükle (B)")
through the current neighbourhoods carrying its name (population-weighted class). Party
results are folded into blocs so 1991 and 2024 compare. Institution boxes (votes >= registered
+ 20) are dropped as in secim_kentkir.py.

Writes secim_<p>_zaman_blok.csv (election x kent/kır x bloc), secim_<p>_zaman_mahalle.csv
(current neighbourhood x election x bloc share, for elections from 2011 on).
"""
import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
from il import PLATE, D, wh  # noqa: E402

TILES = Path("C:/veri/public/tiles")
ELECTIONS = ["mv1991", "mv1995", "mv1999", "mv2002", "mv2007", "mv2011", "mv2015h", "mv2015k", "mv2018",
             "mv2023", "cb2014", "cb2018", "cb2023t1", "cb2023t2", "ho2017",
             "yerel_bsb_2014", "yerel_bsb_2019", "yerel_bsb_2024"]
BLOC = {
    "AK PARTİ": "akp", "RECEP TAYYİP ERDOĞAN": "akp", "Evet oyları": "akp",
    "CHP": "chp", "SHP": "chp", "MUHARREM İNCE": "chp", "KEMAL KILIÇDAROĞLU": "chp", "Hayır oyları": "chp",
    "EKMELEDDİN MEHMET İHSANOĞLU": "chp",
    "MHP": "milliyetci", "İYİ PARTİ": "milliyetci", "BBP": "milliyetci", "ZAFER PARTİSİ": "milliyetci",
    "ZAFER": "milliyetci", "MERAL AKŞENER": "milliyetci", "SİNAN OĞAN": "milliyetci",
    "HADEP": "kurt", "DEHAP": "kurt", "HDP": "kurt", "YEŞİL SOL PARTİ": "kurt", "DEM PARTİ": "kurt",
    "SELAHATTİN DEMİRTAŞ": "kurt",
    "RP": "islamci", "FP": "islamci", "SAADET PARTİSİ": "islamci", "YENİDEN REFAH": "islamci",
    "TEMEL KARAMOLLAOĞLU": "islamci",
    "DYP": "merkez_sag", "ANAP": "merkez_sag", "DP": "merkez_sag", "GENÇ PARTİ": "merkez_sag",
    "DSP": "sol",
}


def fold(t):
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalpha())


ik = pl.read_csv(D / f"kent_{PLATE}_ikili.csv", infer_schema_length=0).with_columns(pl.col("nufus").cast(pl.Float64).fill_null(0))
CUR = {r["area_id"]: r for r in ik.iter_rows(named=True)}
OLD = {}
for r in pl.read_csv(D / f"tarihsel_{PLATE}_sabit_satir.csv", infer_schema_length=0).unique("area_id").iter_rows(named=True):
    if r["sabit"] != "eslesmedi":
        OLD[r["area_id"]] = "kent" if r["sabit"] in ("merkez", "kentsel_belde") else "kır"
BYNAME = {}
for r in ik.iter_rows(named=True):
    BYNAME.setdefault(r["area_id"].rsplit("-", 1)[0], []).append((fold(r["name"]), r))
URBAN_DISTRICT = {}
for did, rs in BYNAME.items():
    t = sum(r["nufus"] for _, r in rs)
    URBAN_DISTRICT[did] = sum(r["nufus"] for _, r in rs if r["kent_kir"] == "kent") / t if t else 0


OLD_DISTRICT = {"TR-52-x1552": "TR-52-002"}


def resolve(key, ad):
    """-> (kent/kır, current area_id or None)"""
    k = wh(key) if "~" not in key else key
    if k in CUR:
        return CUR[k]["kent_kir"], k
    if k in OLD:
        return OLD[k], None
    if "~" not in k:
        return None, None
    did, nm = k.split("~")
    # before 2013 Ordu's central district carried the code x1552 in the result tiles; it is
    # today's Altınordu (names such as Karşıyaka also exist elsewhere, so the province-wide
    # unique-name fallback below dropped those quarters)
    did = OLD_DISTRICT.get(did, did)
    if ad.endswith("(B)"):
        nm = nm.removesuffix("b")
    nm = nm.removesuffix("koyu").removesuffix("koy")
    hit = [r for n, r in BYNAME.get(did, []) if n == nm or n in (nm + "koy", nm + "koyu")]
    if not hit:
        # a belde's quarters kept its name as prefix (Emek Adnan Menderes, Emek Zafer ...)
        hit = [r for n, r in BYNAME.get(did, []) if len(nm) >= 4 and n.startswith(nm)]
    if not hit:
        # the 2008 redistricting moved quarters between districts (Ankara: Koru, Ümit,
        # Yaşamkent from Yenimahalle to Çankaya; Pursaklar split off Keçiören): a unique
        # exact name anywhere in the province
        hit = [r for rs in BYNAME.values() for n, r in rs if n == nm]
        if len({r["area_id"].rsplit("-", 1)[0] for r in hit}) != 1:
            hit = []
    if not hit:
        # a quarter renamed or merged in a district urban all through today (Altındağ's
        # renewal) is urban whatever it became
        return ("kent", None) if URBAN_DISTRICT.get(did, 0) >= 0.99 else (None, None)
    pop = {"kent": 0.0, "kır": 0.0}
    for r in hit:
        pop[r["kent_kir"]] += r["nufus"] or 1
    return max(pop, key=pop.get), (hit[0]["area_id"] if len(hit) == 1 else None)


rows, lost, inst = [], {}, 0
for e in ELECTIONS:
    f = TILES / f"secim-{e}-mahalle-TR-{PLATE}.json"
    if not f.exists():
        continue
    for key, v in json.loads(f.read_text(encoding="utf-8")).items():
        if v["o"] >= v["k"] + 20:
            inst += 1
            continue
        kk, aid = resolve(key, v["ad"])
        n = sum(v["v"].values())
        if kk is None:
            lost[e] = lost.get(e, 0) + n
            continue
        for p, c in v["v"].items():
            rows.append(dict(election=e, kent_kir=kk, area_id=aid, reg=v["k"], voted=v["o"], bloc=BLOC.get(p, "diger"), votes=c, key=key))
d = pl.DataFrame(rows)
tot = d.group_by("election").agg(pl.col("votes").sum())
print("sınıfsız kalan oy %:", {e: round(n / (n + tot.filter(pl.col('election') == e)['votes'][0]) * 100, 1) for e, n in lost.items()}, "| kurum sandığı dışlandı:", inst)

b = d.group_by("election", "kent_kir", "bloc").agg(pl.col("votes").sum())
b = b.with_columns((pl.col("votes") / pl.col("votes").sum().over("election", "kent_kir") * 100).round(1).alias("pay"))
b.write_csv(D / f"secim_{PLATE}_zaman_blok.csv")

m = d.filter(pl.col("area_id").is_not_null()).group_by("election", "area_id", "kent_kir", "bloc").agg(pl.col("votes").sum())
m = m.with_columns(pl.col("votes").sum().over("election", "area_id").alias("gecerli"))
m = m.with_columns((pl.col("votes") / pl.col("gecerli") * 100).round(2).alias("pay"))
m = m.join(ik.select("area_id", "district", "name"), on="area_id", how="left")
m.write_csv(D / f"secim_{PLATE}_zaman_mahalle.csv")
turn = d.unique(["election", "key"]).group_by("election", "kent_kir").agg((pl.col("voted").sum() / pl.col("reg").sum() * 100).round(1).alias("katilim"))
turn.write_csv(D / f"secim_{PLATE}_zaman_katilim.csv")
print("yazıldı", D)
