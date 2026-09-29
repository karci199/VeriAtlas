"""Review workbook for the user's own urban/rural decisions, in the look of AATOPLU 7H.xlsx.

usage: excel_kontrol.py [output.xlsx]

One row per neighbourhood/village of 2025, grouped like AATOPLU: identity, population, age and
sex, housing, the 2023 general election (party headers in party colours, the place's name
filled with the winner's colour), what every source says, an automatic note that spells out
the telling signals, and the user's yellow columns (class from a list, derived KENT/KIR, own
settlement, note). The İLÇE and İL sheets add the derived KENT/KIR up with SUMIFS, so the
summaries fill in as the user types.

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
import openpyxl
import polars as pl
import shapely
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("C:/Users/katan/OneDrive/Desktop/demografi/KENT_KIR_KONTROL_2025.xlsx")
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


def tr(x, nd=0):
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def auto_note(v):
    """the signals worth a look, most telling first"""
    out = []
    if v["kurum"]:
        out.append(f"KURUM: {v['kurum']}")
    says = {"bina": v["sinif"] in URBAN_CLASS, "DEGURBA": v["deg"] in ("Yoğun kent", "Orta yoğun kent"),
            "AATOPLU": v["aat"] in ("Mahalle",) or v["aat"].startswith("Belde")}
    known = {k: s for k, s in says.items() if not (k == "AATOPLU" and v["aat"] == "—") and not (k == "DEGURBA" and v["deg"] == "—")}
    kent = [k for k, s in known.items() if s]
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
            kpb=round(dw / bl, 2) if dw and bl else None, yaz=round((e.get("SummerResortCount") or 0) / dw * 100, 1) if dw else None,
            uni=round(uni / et * 100, 1) if et >= 50 else None,
            leke=round(float(r["share"]) * 100) if r["share"] not in (None, "") else None,
            kur=r["first_seen"] if r["first_seen"] and r["first_seen"] > "2013" else None,
            stat=stat, aat=label(IL_ALIAS.get(il, il), r["district"], r["name"], r["eski_statu"]) or "—",
            deg=DEG.get(r["degurba"] or "", r["degurba"] or "—"), sinif=r["son_sinif"],
            bina=CLASS_TR.get(r["sinif"], r["sinif"] or "—"), oneri=CLASS_TR.get(r["son_sinif"], r["son_sinif"]),
            kurum=KURUM.get(wid, ""), bnote=r["note"] or "",
        )
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

# --- workbook, AATOPLU look: Calibri 11, bold centred headers, party colours, thin spacers
F = "Calibri"
HEAD = Font(name=F, size=11, bold=True)
BODY = Font(name=F, size=11)
CENTER = Alignment(horizontal="center", vertical="center")
YEL = PatternFill("solid", fgColor="FFFF00")
LIGHT_YEL = PatternFill("solid", fgColor="FFF9C4")
GROUP = {"id": "D9E1F2", "pop": "E2EFDA", "age": "DDEBF7", "house": "FFF2CC", "vote": "EDEDED", "src": "FCE4D6", "note": "E7E6E6"}
THIN = Border(bottom=Side(style="thin", color="999999"))
# (key, header, width, group, number format)
COLS = [
    ("il", "İL", 13, "id", None), ("ilce", "İLÇE", 16, "id", None), ("yer", "YERLEŞİM", 24, "id", None),
    ("ad", "MAHALLE / KÖY", 24, "id", None), ("tur", "TÜR", 8, "id", None), None,
    ("n", "Nüfus 2025", 10, "pop", "#,##0"), ("n0", "Nüfus 2013", 10, "pop", "#,##0"), ("g", "Değişim 2013-25 %", 10, "pop", "0.0"),
    ("area", "Yüzölçümü km²", 10, "pop", "#,##0.00"), ("dens", "Yoğunluk kişi/km²", 10, "pop", "#,##0"), None,
    ("er", "Erkek %", 8, "age", "0.00"), ("u17", "0-17 %", 8, "age", "0.00"), ("o65", "65+ %", 8, "age", "0.0"),
    ("med", "Ortanca yaş", 8, "age", "0.0"), ("uni", "Üniversiteli %", 9, "age", "0.0"), None,
    ("hh", "Hane", 8, "house", "#,##0"), ("hs", "Hane büyüklüğü", 9, "house", "0.00"), ("dw", "Konut", 8, "house", "#,##0"),
    ("bl", "Bina", 8, "house", "#,##0"), ("kpb", "Konut / bina", 8, "house", "0.00"), ("yaz", "Yazlık %", 8, "house", "0.0"),
    ("leke", "Merkez lekesinde bina %", 10, "house", "0"), ("kur", "Kuruluş", 8, "house", None), None,
    ("k23", "Kayıtlı 2023", 9, "vote", "#,##0"), ("g23", "Geçerli", 9, "vote", "#,##0"), ("kn", "Kayıtlı / nüfus %", 9, "vote", "0.0"),
    *[(pn, short, 8, "party", "0.00") for pn, short, _, _ in PARTIES], None,
    ("stat", "TÜİK statü", 24, "src", None), ("aat", "AATOPLU 2015", 12, "src", None), ("deg", "DEGURBA", 14, "src", None),
    ("bina", "Microsoft bina analizi", 18, "src", None), ("oneri", "Analiz önerisi", 18, "src", None), None,
    ("not", "OTOMATİK NOT", 60, "note", None), None,
    ("u_sinif", "SINIF (senin)", 15, "you", None), ("u_kk", "KENT / KIR", 9, "you", None),
    ("u_yer", "YERLEŞİM (senin)", 22, "you", None), ("u_not", "NOT (senin)", 30, "you", None),
]
CHOICES = ["İl Merkezi", "İlçe Merkezi", "Kentsel Belde", "Kasaba", "Kırsal Belde", "Köy"]
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "MAHALLE-KÖY"
ci, col = 1, {}
for c in COLS:
    L = get_column_letter(ci)
    if c is None:
        ws.column_dimensions[L].width = 1.5
        ci += 1
        continue
    key, h, w, g, fmt = c
    cell = ws.cell(row=1, column=ci, value=h)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = THIN
    if g == "party":
        fill, font = PCOL[key]
        cell.fill, cell.font = PatternFill("solid", fgColor=fill), Font(name=F, size=11, bold=True, color=font)
    else:
        cell.fill, cell.font = (YEL if g == "you" else PatternFill("solid", fgColor=GROUP[g])), HEAD
    ws.column_dimensions[L].width = w
    col[key] = (ci, fmt, g)
    ci += 1
ws.row_dimensions[1].height = 45
WIN = {p: (PatternFill("solid", fgColor=fill), Font(name=F, size=11, bold=True, color=font)) for p, _, fill, font in PARTIES}
OTHER_WIN = (PatternFill("solid", fgColor="BFBFBF"), Font(name=F, size=11, bold=True))
sc, kc = get_column_letter(col["u_sinif"][0]), get_column_letter(col["u_kk"][0])
for ri, v in enumerate(rows, start=2):
    for key, (c, fmt, g) in col.items():
        if key == "u_kk":
            val = f'=IF({sc}{ri}="","",IF(OR({sc}{ri}="İl Merkezi",{sc}{ri}="İlçe Merkezi",{sc}{ri}="Kentsel Belde"),"KENT","KIR"))'
        else:
            val = v.get(key)
        cell = ws.cell(row=ri, column=c, value=val)
        cell.font = BODY
        if fmt:
            cell.number_format = fmt
        if g in ("pop", "age", "house", "vote", "party") or key in ("tur", "il"):
            cell.alignment = CENTER
        if g == "you":
            cell.fill = LIGHT_YEL
    if v.get("win"):
        fill, font = WIN.get(v["win"], OTHER_WIN)
        nc = ws.cell(row=ri, column=col["ad"][0])
        nc.fill, nc.font, nc.alignment = fill, font, CENTER
last = len(rows) + 1
ws.freeze_panes = ws.cell(row=2, column=col["tur"][0] + 1)
ws.auto_filter.ref = f"A1:{get_column_letter(ci - 1)}{last}"
dv = DataValidation(type="list", formula1='"' + ",".join(CHOICES) + '"', allow_blank=True)
ws.add_data_validation(dv)
dv.add(f"{sc}2:{sc}{last}")

# İLÇE and İL: totals from the derived KENT/KIR column, live
M = "'MAHALLE-KÖY'"
nl = get_column_letter(col["n"][0])
colA, colB, colN, colK = f"$A$2:$A${last}", f"$B$2:$B${last}", f"${nl}$2:${nl}${last}", f"${kc}$2:${kc}${last}"
for title, keys in (("İLÇE", sorted({(v["il"], v["ilce"]) for v in rows})), ("İL", sorted({(v["il"],) for v in rows}))):
    s = wb.create_sheet(title)
    heads = (["İL", "İLÇE"] if title == "İLÇE" else ["İL"]) + ["Nüfus 2025", "KENT nüfus", "KIR nüfus", "Karar bekleyen", "Kent %"]
    for i, h in enumerate(heads, 1):
        c = s.cell(row=1, column=i, value=h)
        c.font, c.alignment, c.border = HEAD, CENTER, THIN
        c.fill = PatternFill("solid", fgColor=GROUP["pop"] if i > len(heads) - 5 else GROUP["id"])
        s.column_dimensions[get_column_letter(i)].width = 19 if i <= 2 else 13
    for ri, key in enumerate(keys, 2):
        for i, x in enumerate(key, 1):
            s.cell(row=ri, column=i, value=x).font = BODY
        crit = f"{M}!{colA},$A{ri}" + (f",{M}!{colB},$B{ri}" if title == "İLÇE" else "")
        o = len(key)
        L = lambda k: get_column_letter(o + k)  # noqa: E731
        s.cell(row=ri, column=o + 1, value=f"=SUMIFS({M}!{colN},{crit})").number_format = "#,##0"
        s.cell(row=ri, column=o + 2, value=f'=SUMIFS({M}!{colN},{crit},{M}!{colK},"KENT")').number_format = "#,##0"
        s.cell(row=ri, column=o + 3, value=f'=SUMIFS({M}!{colN},{crit},{M}!{colK},"KIR")').number_format = "#,##0"
        s.cell(row=ri, column=o + 4, value=f"={L(1)}{ri}-{L(2)}{ri}-{L(3)}{ri}").number_format = "#,##0"
        s.cell(row=ri, column=o + 5, value=f'=IF({L(2)}{ri}+{L(3)}{ri}=0,"",{L(2)}{ri}/({L(2)}{ri}+{L(3)}{ri})*100)').number_format = "0.00"
        for i in range(o + 1, o + 6):
            s.cell(row=ri, column=i).font, s.cell(row=ri, column=i).alignment = BODY, CENTER
    s.freeze_panes = "B2" if title == "İL" else "C2"
    s.auto_filter.ref = f"A1:{get_column_letter(len(heads))}{len(keys) + 1}"

# AÇIKLAMA
a = wb.create_sheet("AÇIKLAMA", 0)
notes = [
    ("Ne doldurulacak", "MAHALLE-KÖY'deki sarı sütunlar: SINIF (listeden: " + ", ".join(CHOICES) + "), YERLEŞİM (senin; boşsa YERLEŞİM geçerli), NOT. "
     "KENT / KIR SINIF'tan kendiliğinden gelir (İl/İlçe Merkezi ve Kentsel Belde = KENT). İLÇE ve İL sayfaları bundan hesaplanır; 'Karar bekleyen' henüz sınıflanmamış nüfustur."),
    ("Örnek satır", "Bursa | İznik | İznik İlçe Merkezi | Mustafakemalpaşa | Mahalle | … | SINIF: İlçe Merkezi → KENT | YERLEŞİM: İznik Merkez | NOT: sur içi"),
    ("MAHALLE / KÖY rengi", "2023 milletvekili seçiminde birinci çıkan parti (AK PARTİ sarı, CHP kırmızı, MHP mavi, İYİ açık mavi, YSP mor, YRP yeşil, diğer gri)."),
    ("YERLEŞİM", "Büyükşehir dışı: bugünkü resmî statü (İl/İlçe merkezi, belde adı, '<ilçe> Köyleri'). 30 büyükşehirde 2012 statüsü (mahalleye dönüşmeden önce)."),
    ("Nüfus, 0-17 %", "TÜİK ADNKS 2013 ve 2025. 0-17 yalnız mahallelerde; TÜİK'in gizlediği çok küçük mahallelerde boş. 2013'te olmayan yerde değişim boş."),
    ("Yoğunluk", "Nüfus / mahalle çokgeninin alanı. Köylerde tarla ve orman da alana girdiği için düşük çıkar; mahalleler arasında karşılaştır."),
    ("Erkek %, 65+ %, Üniversiteli %, Hane, Konut, Yazlık %", "Endeksa 2024. 65+ yalnız yaş grupları gizlenmemişse; Üniversiteli % (lisans+yüksek lisans+doktora / eğitim toplamı) 50+ kişilik yerlerde."),
    ("Ortanca yaş", "2024; Endeksa yaş grupları TÜİK toplamlarıyla Monte Carlo (200 çekiliş)."),
    ("Bina, Konut / bina", "Microsoft bina ayak izleri (Şubat 2026). Konut / bina 3+ apartman, ~1 müstakil/köy dokusu."),
    ("Merkez lekesinde bina %", "Binalarının yüzde kaçı ilçe merkezinin kesintisiz yapılaşmasının içinde (100 = merkezin parçası, 0 = ayrı yerleşim)."),
    ("Kuruluş", "Mahalle 2013'ten sonra kurulduysa kuruluş yılı (bölünme ya da yeni yapılaşma)."),
    ("Seçim 2023", "14 Mayıs 2023 milletvekili, geçerli oya pay. Kayıtlı / nüfus: Türkiye ~%72; çok düşükse seçmen olmayan nüfus (cezaevi, kışla, yurt, yabancı), 100'ü aşarsa kurum sandığı ya da nüfusu başka yerde kayıtlı seçmen."),
    ("TÜİK statü", "Resmî statü: büyükşehir dışında bugün, büyükşehirde 2012."),
    ("AATOPLU 2015", "Senin 7 Haziran 2015 tablon: Mahalle / Belde / Köy."),
    ("DEGURBA", "AB kentleşme derecesi 2025 (Yoğun kent / Orta yoğun kent / Kır)."),
    ("Microsoft bina analizi", "Bina lekesi kuralı: merkez, kentsel belde (ayrı leke ≥5.000), kasaba (2.000-5.000), kırsal belde, köy."),
    ("Analiz önerisi", "Bütün kaynaklar ve senin önceki kararlarınla birleştirilmiş sınıf (Bursa/Ankara elle, diğer iller kurallarla)."),
    ("OTOMATİK NOT", "Göze çarpan işaretler: kurum (cezaevi/kışla/yurt), kaynak çelişkisi, 2013'ten beri hızlı büyüme ya da boşalma, apartman/müstakil doku, yazlık, yaşlı nüfus, merkeze bitişik ama ayrı yerleşim, 5.000+ olup kır sayılan yer, bina analizinin gerekçesi."),
]
a.column_dimensions["A"].width = 30
a.column_dimensions["B"].width = 130
for i, (k, x) in enumerate(notes, 1):
    a.cell(row=i, column=1, value=k).font = HEAD
    c = a.cell(row=i, column=2, value=x)
    c.font, c.alignment = BODY, Alignment(wrap_text=True, vertical="top")
wb.active = 1
OUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT)
print("yazıldı", OUT)
