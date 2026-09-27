"""Semt layer of one province: every neighbourhood gets exactly one semt, then population
and election results per semt.

Semt rule (2026-09-28):
- urban neighbourhood (merkez) in a district PTT splits (Osmangazi, Nilüfer, Yıldırım):
  its PTT 2022 semt; in an unsplit district: "<district> Merkez"
- kentsel belde and kasaba: a semt of its own, named after the former belde when haritatr
  groups several neighbourhoods under it (Güzelyalı), else after the neighbourhood
- kırsal belde and village: "<district> Köyleri"
- OSB: "<district> OSB" (no residents)

usage: semt.py 16 BURSA <dir with kent_16_son.csv>
"""

import json, sys
from pathlib import Path
import duckdb, polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG  # noqa: E402
IL = PTT_IL



def fold(t):
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalpha())


def title(t):
    return " ".join(w[:1] + w[1:].replace("I", "ı").replace("İ", "i").lower() for w in t.split())


nb = pl.read_csv(D / f"kent_{PLATE}_son.csv", infer_schema_length=0)

# PTT 2022: (district, neighbourhood) -> semt
ptt = pl.read_excel("C:/veri-ham/ptt/pk_20220810.xlsx").with_columns(pl.all().str.strip_chars()).filter(pl.col("il") == IL)
PTT, split = {}, set()
for (d,), g in ptt.group_by(["ilçe"]):
    if g["semt_bucak_belde"].n_unique() > 1:
        split.add(fold(d))
    for r in g.iter_rows(named=True):
        m = r["Mahalle"].split("(")[0].removesuffix(" MAH").removesuffix(" MAH.").strip()
        PTT[(fold(d), fold(m).removesuffix("mah"))] = title(r["semt_bucak_belde"])

# former beldes absorbed into a town (İnegöl Alanyurt, closed 2008): the municipality a
# neighbourhood code was listed under in its first ADNKS year. The registry keeps only the
# newest municipality, and haritatr mixes same-named quarters (Cumhuriyet -> Kurşunlu).
sys.path.insert(0, str(ROOT / "src"))
from veriatlas.adapters.tuik_neighbourhoods import DOWNLOADS, read_export  # noqa: E402

FIRST = {}
for f in DOWNLOADS.glob(f"nufus-mahalle-{IL_UP}*.csv"):
    for cell in read_export(f):
        if cell.year <= 2012 and (cell.code not in FIRST or cell.year < FIRST[cell.code][0]):
            FIRST[cell.code] = (cell.year, cell.municipality.removesuffix(" Bel."))

# haritatr: belde groups with more than one neighbourhood
ht = pl.read_csv(f"C:/veri-ham/haritatr/{PLATE}/semt_mahalle.csv", infer_schema_length=0)
HT = {(fold(r["district"]), fold(r["neighbourhood"].removesuffix(" Köyü"))): r["semt"] for r in ht.iter_rows(named=True)}


import shapely

CENT = {}
for f in (ROOT / "public/geo/neighbourhoods").glob(f"TR-{PLATE}-*.geojson"):
    for ft in json.loads(f.read_text(encoding="utf-8"))["features"]:
        CENT[ft["properties"]["area_id"]] = shapely.centroid(shapely.from_geojson(json.dumps(ft["geometry"])))
NAME = {r["area_id"]: r["name"] for r in nb.iter_rows(named=True)}


def nearest_semt(aid, fd):
    did = aid.rsplit("-", 1)[0]
    best = min(((shapely.distance(CENT[aid], CENT[o]), PTT[(fd, fold(NAME[o]))]) for o in CENT
                if o != aid and o.startswith(did + "-") and (fd, fold(NAME.get(o, ""))) in PTT), key=lambda x: x[0])
    print("yakın komşu semti:", NAME[aid], "->", best[1])
    return best[1]


# kentsel belde neighbourhoods sharing one separate built-up cluster (same "lekesi N kişi"
# note) form one semt named after them: İnegöl Akhisar + Huzur
GROUP = {}
_kb = nb.filter((pl.col("son_sinif") == "kentsel_belde") & pl.col("note").str.contains("lekesi"))
_kb = _kb.with_columns(pl.col("note").str.extract(r"lekesi (\d+)").alias("leke"))
for (dist, leke), g in _kb.group_by(["district", "leke"]):
    if g.height > 1 and fold(dist) not in split:
        names = g.sort(pl.col("pop").cast(pl.Float64), descending=True)["name"].to_list()
        for aid in g["area_id"]:
            GROUP[aid] = "-".join(names) if len(names) <= 3 else names[0] + " ve çevresi"


def semt(r):
    d, fd, c = r["district"], fold(r["district"]), r["son_sinif"]
    if c == "osb":
        return f"{d} OSB"
    if c in ("kir", "kirsal_belde"):
        return f"{d} Köyleri"
    if c == "merkez":
        if fd in split:
            # a neighbourhood split after 2022 (Yıldırım Sakarya) takes its nearest neighbour's semt
            return PTT.get((fd, fold(r["name"]))) or nearest_semt(r["area_id"], fd)
        m = FIRST.get(r["area_id"].rsplit("-", 1)[1], (0, d))[1]
        if fold(m) not in (fd, fold(IL)):
            return m  # a former belde, now part of the town
        return f"{d} Merkez"
    # kentsel belde / kasaba: former belde group from haritatr, else PTT semt in a split
    # district (Görükle), else the neighbourhood itself
    if c == "kasaba":
        return r["name"]
    if r["area_id"] in GROUP:
        return GROUP[r["area_id"]]
    h = HT.get((fd, fold(r["name"])), "")
    if h and not h.endswith(("Merkez", "Köyleri")) and fd not in split:
        return h
    if fd in split and (fd, fold(r["name"])) in PTT and not PTT[(fd, fold(r["name"]))].endswith("köy"):
        return PTT[(fd, fold(r["name"]))]
    return r["name"]


nb = nb.with_columns(pl.struct("district", "name", "son_sinif", "area_id", "pop").map_elements(semt, return_dtype=pl.Utf8).alias("semt"))
assert nb["semt"].null_count() == 0

# population, children
pop = duckdb.sql(f"""select area_id, sum(value) filter (where dims='age=0-17') c, sum(value) v
 from read_parquet('{ROOT}/public/fact.parquet') where indicator_id='population' and area_id like 'TR-{PLATE}-%-%'
 and year(period_start)={YEAR} group by 1""").pl()
nb = nb.join(pop, on="area_id", how="left")

# elections
EL = {"mv2023": ["AK PARTİ", "CHP", "İYİ PARTİ", "MHP", "YEŞİL SOL PARTİ", "YENİDEN REFAH", "ZAFER PARTİSİ"],
      "cb2023t2": ["RECEP TAYYİP ERDOĞAN"], "yerel_bsb_2024": ["CHP", "AK PARTİ"]}
vrows = []
for e, parties in EL.items():
    for aid, v in json.loads((ROOT / f"public/tiles/secim-{e}-mahalle-TR-{PLATE}.json").read_text(encoding="utf-8")).items():
        if v["o"] >= v["k"] + 20:
            continue
        vrows.append(dict(area_id=aid, key=f"{e}:k", n=v["k"]))
        vrows.append(dict(area_id=aid, key=f"{e}:o", n=v["o"]))
        vrows.append(dict(area_id=aid, key=f"{e}:g", n=v["g"]))
        for p in parties:
            vrows.append(dict(area_id=aid, key=f"{e}:{p}", n=v["v"].get(p, 0)))
votes = pl.DataFrame(vrows).join(nb.select("area_id", "semt"), on="area_id", how="inner")
vs = votes.group_by("semt", "key").agg(pl.col("n").sum()).pivot(on="key", index="semt", values="n")

s = nb.group_by("district", "semt").agg(
    pl.len().alias("mahalle"),
    pl.col("son_sinif").unique().sort().str.join("+").alias("sinif"),
    pl.col("v").sum().cast(pl.Int64).alias("nufus"),
    (pl.col("c").sum() / pl.col("v").filter(pl.col("c").is_not_null()).sum() * 100).round(1).alias("cocuk%"))
s = s.join(vs, on="semt", how="left")
pct = lambda e, p, nm: (pl.col(f"{e}:{p}") / pl.col(f"{e}:g") * 100).round(1).alias(nm)
s = s.with_columns(
    (pl.col("mv2023:o") / pl.col("mv2023:k") * 100).round(1).alias("katilim23"),
    pct("mv2023", "AK PARTİ", "AKP23"), pct("mv2023", "CHP", "CHP23"), pct("mv2023", "İYİ PARTİ", "IYI23"),
    pct("mv2023", "MHP", "MHP23"), pct("mv2023", "YEŞİL SOL PARTİ", "YSP23"), pct("mv2023", "YENİDEN REFAH", "YRP23"),
    pct("mv2023", "ZAFER PARTİSİ", "ZAF23"), pct("cb2023t2", "RECEP TAYYİP ERDOĞAN", "ERD23"),
    pct("yerel_bsb_2024", "CHP", "CHP24"), pct("yerel_bsb_2024", "AK PARTİ", "AKP24"),
).select("district", "semt", "mahalle", "sinif", "nufus", "cocuk%", pl.col("mv2023:k").alias("secmen23"), "katilim23",
         "AKP23", "CHP23", "IYI23", "MHP23", "YSP23", "YRP23", "ZAF23", "ERD23", "CHP24", "AKP24").sort("district", "nufus", descending=[False, True])
nb.select("district", "area_id", "name", "son_sinif", "semt").write_csv(D / f"semt_{PLATE}_mahalle.csv")
s.write_csv(D / f"semt_{PLATE}.csv")
print("semt:", s.height, "| mahalle:", nb.height, "| semtsiz: 0 | nüfus", s["nufus"].sum())
