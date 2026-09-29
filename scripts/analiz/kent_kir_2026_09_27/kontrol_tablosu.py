"""Data of the urban/rural review page (web/kentkir.html).

usage: kontrol_tablosu.py

One row per neighbourhood/village of 2025: identity, population (TÜİK 2013/2025), age, sex
and housing (Endeksa 2024), buildings, the 2023 general election, what every source says
(TÜİK status, AATOPLU 2015, DEGURBA, the building analysis) with each source's urban/rural
reading, the level of disagreement between them, the merged suggestion and an automatic note
spelling out the telling signals. The user's decisions are not here: the page saves them to
kullanici_karar.json next to this script (scripts/serve.py, POST /karar).

Settlement: outside metropolitan provinces the official status of today (district centre,
belde, villages); in the 30 metropolitan provinces the status of 2012, before they became
all-neighbourhood (eski_statu of the urban/rural list).
"""
import json
import math
import re
import sys
from pathlib import Path

import duckdb
import polars as pl
import shapely

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
OUT = HERE.parents[2] / "public/kentkir_kontrol.json"
sys.argv = [sys.argv[0], "06"]
from il import wh  # noqa: E402

_src = (HERE / "aatoplu_onay.py").read_text(encoding="utf-8").split("\nplates = ")[0]
A = {"__file__": str(HERE / "aatoplu_onay.py")}
exec(compile(_src, "aatoplu_onay.py", "exec"), A)
BASE, label, prov, IL_ALIAS, fold = A["BASE"], A["label"], A["prov"], A["IL_ALIAS"], A["fold"]
ROOT = HERE.parents[2]
FACT = "C:/veri/public/fact.parquet"
NAME_SUFFIX = re.compile(r"\s+(Köyü|Mahallesi|Mah\.?)$")
TILES = Path("C:/veri/public/tiles")
METRO = {"01", "06", "07", "09", "10", "16", "20", "21", "25", "26", "27", "31", "33", "34", "35", "38", "41", "42",
         "44", "45", "46", "47", "48", "52", "54", "55", "59", "61", "63", "65"}

# population 2013 and 2025 (neighbourhoods: 0-17 + 18+), 0-17 of 2025; ids are stable since 2013
POP = {}
for y, aid, v in duckdb.sql(f"""select year(period_start), area_id, sum(value) from read_parquet('{FACT}') where indicator_id='population'
  and area_level in ('neighbourhood','village') and year(period_start) in (2013, 2025) group by 1,2""").fetchall():
    POP[(y, aid)] = v
kid = {r[0]: r[1] for r in duckdb.sql(f"""select area_id, sum(value) from read_parquet('{FACT}') where indicator_id='population'
  and area_level='neighbourhood' and dims='age=0-17' and year(period_start)=2025 group by 1""").fetchall()}

# Endeksa 2024: sex, households, dwellings, summer houses, age bands, education
END = {}
for fn in Path("C:/veri-ham/endeksa/demography").glob("TR-*.json"):
    for k, v in json.loads(fn.read_text(encoding="utf-8")).items():
        e = v.get("demography") or {}
        if e.get("PopulationTotal"):
            END[f"{fn.stem}-{k}"] = e


def endx(aid):
    e = END.get(aid)
    if e is None:
        did, code = aid.rsplit("-", 1)
        e = END.get(f"{did}-{int(code) + 2000000}") if code.isdigit() else None
    return e or {}


BANDS = [f"Age_{a}_{a + 4}_Total" for a in range(0, 65, 5)] + ["Age_65_Total"]

# ages of 2024 (Monte Carlo median)
MC = {}
for f in BASE.glob("[0-9][0-9]/yas_mc_*_mahalle.csv"):
    for r in pl.read_csv(f, infer_schema_length=0).iter_rows(named=True):
        if r["ortanca"]:
            MC[wh(r["area_id"])] = float(r["ortanca"])
# area in km2 from the neighbourhood polygons (equal-area enough at this scale)
AREA = {}
for fn in Path("C:/veri/public/geo/neighbourhoods").glob("*.geojson"):
    for ft in json.loads(fn.read_text(encoding="utf-8"))["features"]:
        g = shapely.from_geojson(json.dumps(ft["geometry"]))
        lat = shapely.centroid(g).y
        AREA[wh(ft["properties"]["area_id"])] = g.area * 111.32 * 111.32 * math.cos(math.radians(lat))
# 2023 general election per place
PARTIES = [("AK PARTİ", "AK PARTİ", "FFFF00", "000000"), ("CHP", "CHP", "FF0000", "FFFFFF"),
           ("MHP", "MHP", "2F75B5", "FFFFFF"), ("İYİ PARTİ", "İYİ", "00B0F0", "000000"),
           ("YEŞİL SOL PARTİ", "YSP", "7030A0", "FFFFFF"), ("YENİDEN REFAH", "YRP", "00B050", "FFFFFF")]
PCOL = {p: (fill, font) for p, _, fill, font in PARTIES}
VOTE, VOTE_BY_NAME = {}, {}
for f in TILES.glob("secim-mv2023-mahalle-TR-*.json"):
    for key, v in json.loads(f.read_text(encoding="utf-8")).items():
        if "~" not in key:
            VOTE[wh(key)] = v
            # outside metropolitan provinces the warehouse ids differ from the tiles': by name within the district
            VOTE_BY_NAME.setdefault((key.rsplit("-", 1)[0], fold(v.get("ad") or "")), []).append(v)
# institutions (prisons, barracks, dormitories) flagged nationwide
KURUM = {}
kp = BASE / "_kurum_tespit.csv"
if kp.exists():
    for r in pl.read_csv(kp, infer_schema_length=0).iter_rows(named=True):
        if r["tip"]:
            KURUM[wh(r["area_id"])] = r["tip"] + (f" ({r['cezaevi']})" if r["cezaevi"] and "cezaevi (" not in r["tip"] else "")

# official status today: belde quarters (registry municipality not the district's own)
reg = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0).filter(pl.col("last_seen") == "2025")
MUN = {r["area_id"]: (r["municipality"] or "").removesuffix(" Bel.").strip() for r in reg.iter_rows(named=True)}
VIL = set(pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_villages.csv", infer_schema_length=0)["area_id"])


def centre_name(il, ilce):
    return f"{il} Merkez" if fold(ilce) in (fold(il), "merkez") else f"{ilce} İlçe Merkezi"


def status_and_settlement(p, il, ilce, aid, wid, eski):
    """(TÜİK status, settlement): today outside metropolitan provinces, 2012 inside"""
    if p in METRO:
        if eski.startswith("belde:"):
            return "Belde (2012)", eski[6:]
        if eski == "koy":
            return "Köy (2012)", f"{ilce} Köyleri"
        if eski == "ilce_mahalle":
            return "İlçe merkezi mahallesi (2012)", centre_name(il, ilce)
        return "Mahalle (2013 sonrası kuruldu)", centre_name(il, ilce)
    if wid in VIL or aid in VIL:
        return "Köy", f"{ilce} Köyleri"
    mun = MUN.get(wid) or MUN.get(aid) or ""
    if mun and fold(mun) != fold(ilce) and fold(mun) != fold(il):
        return "Belde", mun
    return ("İl merkezi mahallesi" if fold(ilce) == fold(il) else "İlçe merkezi mahallesi"), centre_name(il, ilce)


CLASS_TR = {"merkez": "Merkez (kent)", "kentsel_belde": "Kentsel belde (kent)", "kasaba": "Kasaba (kır)",
            "kirsal_belde": "Kırsal belde (kır)", "kir": "Köy (kır)", "osb": "OSB"}
DEG = {"YOĞUN KENT": "Yoğun kent", "ORTA YOĞUN KENT": "Orta yoğun kent", "KIR": "Kır"}
URBAN_CLASS = {"merkez", "kentsel_belde"}


def readings(stat, aat, deg, bsin):
    """each source's urban (K) / rural (R) reading; a belde is neither until looked at"""
    t = "K" if ("merkezi mahallesi" in stat or "sonrası" in stat) else "R" if stat.startswith("Köy") else None
    a = "K" if aat == "Mahalle" else "R" if aat == "Köy" else None
    d = "K" if deg in ("Yoğun kent", "Orta yoğun kent") else "R" if deg == "Kır" else None
    b = "K" if bsin in URBAN_CLASS else "R" if bsin else None
    return {"TÜİK": t, "AATOPLU": a, "DEGURBA": d, "bina": b}


def dispute(oy):
    """uyumlu: every source agrees; hafif: one dissents out of 3+; cok: an even split; az: under two sources"""
    k = [x for x in oy.values() if x]
    if len(k) < 2:
        return "az"
    m = min(k.count("K"), k.count("R"))
    return "uyumlu" if m == 0 else "hafif" if m == 1 and len(k) >= 3 else "cok"


def suggested_class(son, yer):
    return {"merkez": "İl Merkezi" if yer.endswith(" Merkez") else "İlçe Merkezi", "kentsel_belde": "Kentsel Belde",
            "kasaba": "Kasaba", "kirsal_belde": "Kırsal Belde", "kir": "Köy"}.get(son, "")


def tr(x, nd=0):
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def auto_note(v):
    """the signals worth a look, most telling first"""
    out = []
    if v["kurum"]:
        out.append(f"KURUM: {v['kurum']}")
    known = {k: s for k, s in v["oy"].items() if s is not None}
    kent = [k for k, s in known.items() if s == "K"]
    if kent and len(kent) < len(known):
        out.append("çelişki: " + ", ".join(kent) + " kent; " + ", ".join(k for k in known if k not in kent) + " kır")
    if v["g"] is not None:
        if v["g"] >= 100:
            out.append(f"2013'ten beri {tr(1 + v['g'] / 100, 1)} katı (yeni yapılaşma)")
        elif v["g"] >= 40:
            out.append(f"hızlı büyüme +%{tr(v['g'])}")
        elif v["g"] <= -30:
            out.append(f"boşalıyor %{tr(v['g'])}")
    if v["kpb"] is not None:
        if v["kpb"] >= 3:
            out.append(f"apartman dokusu (bina başına {tr(v['kpb'], 1)} konut)")
        elif v["kpb"] <= 1.1 and v["n"] < 5000:
            out.append("müstakil/köy dokusu")
    if v["yaz"] is not None and v["yaz"] >= 30:
        out.append(f"yazlık ağırlıklı (konutların %{tr(v['yaz'])}'i)")
    if v["o65"] is not None and v["o65"] >= 25:
        out.append(f"yaşlı (%{tr(v['o65'])} 65+)")
    if v["uni"] is not None and v["uni"] >= 30:
        out.append(f"üniversiteli %{tr(v['uni'])}")
    if v["dens"] is not None and v["dens"] >= 10000:
        out.append("çok yoğun")
    if v["leke"] is not None and 20 <= v["leke"] < 50:
        out.append(f"binaların %{tr(v['leke'])}'i merkez lekesinde (bitişik ama ayrı)")
    if v["n"] >= 5000 and v["sinif"] not in URBAN_CLASS:
        out.append("5.000+ ama kır sayılmış")
    if v["bnote"] and v["bnote"] not in ("köy",):
        out.append("bina: " + v["bnote"])
    return " · ".join(out)


# semt: one per neighbourhood (semt.py; PTT 2022 in split districts, former belde, "<ilçe> Köyleri")
SEMT = {}
for f in BASE.glob("[0-9][0-9]/semt_*_mahalle.csv"):
    for r in pl.read_csv(f, infer_schema_length=0).iter_rows(named=True):
        SEMT[r["area_id"]] = r["semt"]

rows = []
plates = sorted(p.name for p in BASE.iterdir() if (p / f"kent_{p.name}_son.csv").exists())
for p in plates:
    il = prov[p]
    d = pl.read_csv(BASE / p / f"kent_{p}_son.csv", infer_schema_length=0)
    for r in d.filter(pl.col("son_sinif") != "osb").iter_rows(named=True):
        aid, wid = r["area_id"], wh(r["area_id"])
        n = POP.get((2025, wid)) or POP.get((2025, aid))
        if not n:
            continue
        n0 = POP.get((2013, wid)) or POP.get((2013, aid))
        e = endx(aid) or endx(wid)
        en, em = e.get("PopulationTotal") or 0, e.get("PopulationMale") or 0
        bands = sum(e.get(b) or 0 for b in BANDS)
        hh, dw, bl = e.get("HouseholdCount") or None, e.get("HousingCount") or None, int(float(r["buildings"])) if r["buildings"] else None
        et = e.get("EducationTotal") or 0
        uni = sum(e.get(x) or 0 for x in ("EduLicenseDegree", "EduGraduate", "EduDoctorate"))
        k = kid.get(wid)
        stat, settle = status_and_settlement(p, il, r["district"], aid, wid, r["eski_statu"] or "")
        area = AREA.get(wid)
        vt = VOTE.get(wid) or VOTE.get(aid)
        if vt is None:
            cand = VOTE_BY_NAME.get((aid.rsplit("-", 1)[0], fold(NAME_SUFFIX.sub("", r["name"]))), [])
            vt = cand[0] if len(cand) == 1 else None  # two places of one name in a district: leave empty
        v = dict(
            il=il, ilce=r["district"], yer=settle, ad=r["name"], tur="Köy" if (wid in VIL or aid in VIL) else "Mahalle",
            n=int(n), n0=int(n0) if n0 else None, g=round((n / n0 - 1) * 100, 1) if n0 else None,
            area=round(area, 2) if area else None, dens=round(n / area) if area and area > 0.01 else None,
            er=round(em / en * 100, 2) if en else None, u17=round(k / n * 100, 2) if k is not None else None,
            o65=round((e.get("Age_65_Total") or 0) / en * 100, 1) if en and bands >= 0.9 * en else None,
            med=MC.get(wid), hh=hh, hs=round(n / hh, 2) if hh else None, dw=dw, bl=bl,
            kpb=round(dw / bl, 2) if dw and bl else None, kpbl=round(n / bl, 1) if bl else None,
            hpb=round(hh / bl, 2) if hh and bl else None,
            prs=int(float(r["parsel"])) if r.get("parsel") else None, yaz=round((e.get("SummerResortCount") or 0) / dw * 100, 1) if dw else None,
            uni=round(uni / et * 100, 1) if et >= 50 else None,
            leke=round(float(r["share"]) * 100) if r["share"] not in (None, "") else None,
            kur=r["first_seen"] if r["first_seen"] and r["first_seen"] > "2013" else None,
            stat=stat, aat=label(IL_ALIAS.get(il, il), r["district"], r["name"], r["eski_statu"]) or "—",
            deg=DEG.get(r["degurba"] or "", r["degurba"] or "—"), sinif=r["son_sinif"],
            bina=CLASS_TR.get(r["sinif"], r["sinif"] or "—"), oneri=CLASS_TR.get(r["son_sinif"], r["son_sinif"]),
            kurum=KURUM.get(wid, ""), bnote=r["note"] or "",
        )
        v["oy"] = readings(stat, v["aat"], v["deg"], r["sinif"])
        v["ih"] = dispute(v["oy"])
        v["os"] = suggested_class(r["son_sinif"], settle)
        v["id"] = aid
        v["semt"] = SEMT.get(aid) or SEMT.get(wid)
        if vt:
            g_ = vt.get("g") or 0
            v.update(k23=vt.get("k"), g23=g_, kn=round(vt["k"] / n * 100, 1) if vt.get("k") else None)
            for pn, _, _, _ in PARTIES:
                v[pn] = round(vt["v"].get(pn, 0) / g_ * 100, 2) if g_ else None
            v["win"] = max(vt["v"], key=vt["v"].get) if vt.get("v") else None
        v["not"] = auto_note(v)
        rows.append(v)
rows.sort(key=lambda x: (x["il"], x["ilce"], x["yer"], x["ad"]))
print("satır", len(rows), "| seçim eşleşen", sum(1 for v in rows if v.get("k23")))


# uncertainty 0-10: a weighted urban probability over every signal, 0 when they all point one
# way, 10 at an even split; at least 5 when the merged suggestion sits on the other side of
# the probability, +2 for an institution. Under 2 the page places the row provisionally.
BINA_P = {"Merkez (kent)": 1, "Kentsel belde (kent)": 1, "Kasaba (kır)": .25, "Kırsal belde (kır)": .2, "Köy (kır)": 0}
DEG_P = {"Yoğun kent": 1, "Orta yoğun kent": .8, "Kır": 0}
URBAN_TR = {"İl Merkezi", "İlçe Merkezi", "Kentsel Belde"}


def uncertainty(v):
    sig = [(1 if v["oy"][k] == "K" else 0, w) for k, w in (("TÜİK", 1), ("AATOPLU", 1.5)) if v["oy"][k]]
    if v["deg"] in DEG_P:
        sig.append((DEG_P[v["deg"]], 1))
    if v["bina"] in BINA_P:
        sig.append((BINA_P[v["bina"]], 2))
    if v["kpb"] is not None:
        sig.append((min(1, max(0, (v["kpb"] - 1) / 2)), .75))  # 1 dwelling per building rural, 3+ urban
    if v["dens"]:
        sig.append((min(1, max(0, (math.log10(max(v["dens"], 1)) - 2) / 1.7)), .75))  # 100/km2 rural, 5,000 urban
    if v["n"] >= 10000:
        sig.append((1, 1))
    if v["uni"] is not None:
        sig.append((min(1, max(0, (v["uni"] - 5) / 15)), .5))  # university graduates 5 % rural, 20 %+ urban
    if v["o65"] is not None:
        sig.append((min(1, max(0, (25 - v["o65"]) / 15)), .5))  # 65+ at 25 %+ rural, 10 % urban
    pk = sum(x * w for x, w in sig) / sum(w for _, w in sig)
    u = 10 * (1 - abs(2 * pk - 1))
    if (pk >= .5) != (v["os"] in URBAN_TR):
        u = max(u, 5)
    if v["kurum"]:
        u = min(10, u + 2)
    return round(pk, 2), round(u, 1)


for v in rows:
    v["pk"], v["bs"] = uncertainty(v)

# compact: a column list and one array per row
KEYS = ["id", "il", "ilce", "yer", "semt", "ad", "tur", "n", "n0", "g", "area", "dens", "er", "u17", "o65", "med", "uni",
        "hh", "hs", "dw", "bl", "kpb", "kpbl", "hpb", "prs", "yaz", "leke", "kur", "k23", "g23", "kn", *[p for p, _, _, _ in PARTIES], "win",
        "stat", "aat", "deg", "bina", "oneri", "os", "ih", "bs", "pk", "oy", "kurum", "not"]
for v in rows:
    v["oy"] = "".join(v["oy"][k] or "-" for k in ("TÜİK", "AATOPLU", "DEGURBA", "bina"))
out = {"keys": KEYS, "parties": [[p, short, fill] for p, short, fill, _ in PARTIES],
       "rows": [[v.get(k) for k in KEYS] for v in rows]}
OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("yazıldı", OUT, round(OUT.stat().st_size / 1e6, 1), "MB |", {k: sum(1 for v in rows if v["ih"] == k) for k in ("uyumlu", "hafif", "cok", "az")})
