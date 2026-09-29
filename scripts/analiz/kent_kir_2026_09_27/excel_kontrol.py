"""Review workbook for the user's own urban/rural decisions, in the look of AATOPLU 7H.xlsx.

usage: excel_kontrol.py [output.xlsx]

One row per neighbourhood/village of 2025: identity, settlement, population facts, what every
source says about it, and three empty yellow columns for the user (KENT/KIR, own settlement,
note). The İLÇE and İL sheets add the user's KENT/KIR column up with SUMIFS, so the summaries
fill in as the user types.

Settlement: outside metropolitan provinces the official status of today (district centre,
belde, villages); in the 30 metropolitan provinces the status of 2012, before they became
all-neighbourhood (eski_statu of the urban/rural list).
"""
import json
import math
import sys
from pathlib import Path

import duckdb
import openpyxl
import polars as pl
import shapely
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

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
METRO = {"01", "06", "07", "09", "10", "16", "20", "21", "25", "26", "27", "31", "33", "34", "35", "38", "41", "42",
         "44", "45", "46", "47", "48", "52", "54", "55", "59", "61", "63", "65"}

# 2025 population and 0-17, all neighbourhoods and villages
pop = {r[0]: r[1] for r in duckdb.sql(f"""select area_id, sum(value) from read_parquet('{FACT}') where indicator_id='population'
  and area_level in ('neighbourhood','village') and year(period_start)=2025 group by 1""").fetchall()}
kid = {r[0]: r[1] for r in duckdb.sql(f"""select area_id, sum(value) from read_parquet('{FACT}') where indicator_id='population'
  and area_level='neighbourhood' and dims='age=0-17' and year(period_start)=2025 group by 1""").fetchall()}
# Endeksa 2024: sex, households, dwellings, age bands
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


# ages of 2024 (Monte Carlo median; mean from Endeksa bands at TÜİK's 0-17)
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
# official status today: belde quarters (registry municipality not the district's own)
reg = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0).filter(pl.col("last_seen") == "2025")
dname = {r["area_id"]: r["name_tr"] for r in pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_districts.csv", infer_schema_length=0).iter_rows(named=True)}
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

rows = []
plates = sorted(p.name for p in BASE.iterdir() if (p / f"kent_{p.name}_son.csv").exists())
for p in plates:
    il = prov[p]
    d = pl.read_csv(BASE / p / f"kent_{p}_son.csv", infer_schema_length=0)
    for r in d.filter(pl.col("son_sinif") != "osb").iter_rows(named=True):
        aid, wid = r["area_id"], wh(r["area_id"])
        n = pop.get(wid) or pop.get(aid)
        if not n:
            continue
        e = endx(aid) or endx(wid)
        en, em = e.get("PopulationTotal") or 0, e.get("PopulationMale") or 0
        k = kid.get(wid)
        stat, settle = status_and_settlement(p, il, r["district"], aid, wid, r["eski_statu"] or "")
        lab = label(IL_ALIAS.get(il, il), r["district"], r["name"], r["eski_statu"])
        rows.append([
            il, r["district"], settle, r["name"], "Köy" if (wid in VIL or aid in VIL) else "Mahalle",
            int(n), round(em / en * 100, 2) if en else None, round(k / n * 100, 2) if k is not None else None,
            MC.get(wid), round(AREA[wid], 2) if wid in AREA else None,
            e.get("HouseholdCount") or None, e.get("HousingCount") or None, int(float(r["buildings"])) if r["buildings"] else None,
            stat, lab or "—", DEG.get(r["degurba"] or "", r["degurba"] or "—"),
            CLASS_TR.get(r["sinif"], r["sinif"] or "—"), CLASS_TR.get(r["son_sinif"], r["son_sinif"]),
        ])
rows.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
print("satır", len(rows))

# --- workbook, AATOPLU look: Calibri 11, bold centred headers, thin spacer columns
F = "Calibri"
HEAD = Font(name=F, size=11, bold=True)
BODY = Font(name=F, size=11)
YEL = PatternFill("solid", fgColor="FFFF00")
GROUP = {"id": PatternFill("solid", fgColor="D9E1F2"), "data": PatternFill("solid", fgColor="E2EFDA"),
         "src": PatternFill("solid", fgColor="FCE4D6")}
THIN = Border(bottom=Side(style="thin", color="999999"))
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "MAHALLE-KÖY"
cols = [  # (header, width, group, number format)
    ("İL", 15.5, "id", None), ("İLÇE", 19.7, "id", None), ("YERLEŞİM", 26, "id", None), ("MAHALLE / KÖY", 28, "id", None),
    ("TÜR", 9, "id", None), None,
    ("Nüfus 2025", 11, "data", "#,##0"), ("Erkek %", 9, "data", "0.00"), ("0-17 %", 9, "data", "0.00"),
    ("Ortanca yaş", 10, "data", "0.0"), ("Yüzölçümü km²", 12, "data", "#,##0.00"), ("Hane", 9, "data", "#,##0"),
    ("Konut", 9, "data", "#,##0"), ("Bina", 9, "data", "#,##0"), None,
    ("TÜİK statü", 26, "src", None), ("AATOPLU 2015", 13, "src", None), ("DEGURBA", 15, "src", None),
    ("Microsoft bina analizi", 22, "src", None), ("Analiz önerisi", 22, "src", None), None,
    ("KENT / KIR", 11, "you", None), ("YERLEŞİM (senin)", 24, "you", None), ("NOT", 30, "you", None),
]
ci, colmap = 1, {}
for c in cols:
    letter = get_column_letter(ci)
    if c is None:
        ws.column_dimensions[letter].width = 2.5
        ci += 1
        continue
    h, w, g, fmt = c
    cell = ws.cell(row=1, column=ci, value=h)
    cell.font = HEAD
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.fill = YEL if g == "you" else GROUP[g]
    cell.border = THIN
    ws.column_dimensions[letter].width = w
    colmap[h] = (ci, fmt, g)
    ci += 1
ws.row_dimensions[1].height = 30
data_cols = [c for c in cols if c is not None]
for ri, row in enumerate(rows, start=2):
    for (h, _, g, fmt), v in zip(data_cols, row + [None, None, None]):
        c = ws.cell(row=ri, column=colmap[h][0], value=v)
        c.font = BODY
        if fmt:
            c.number_format = fmt
        if g == "you":
            c.fill = PatternFill("solid", fgColor="FFF9C4")
last = len(rows) + 1
ws.freeze_panes = "F2"
ws.auto_filter.ref = f"A1:{get_column_letter(ci - 1)}{last}"
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402
dv = DataValidation(type="list", formula1='"KENT,KIR"', allow_blank=True)
ws.add_data_validation(dv)
kc = get_column_letter(colmap["KENT / KIR"][0])
dv.add(f"{kc}2:{kc}{last}")

# İLÇE and İL: totals from the user's column, live
M = "'MAHALLE-KÖY'"
colA, colB = "$A$2:$A$" + str(last), "$B$2:$B$" + str(last)
colN = f"${get_column_letter(colmap['Nüfus 2025'][0])}$2:${get_column_letter(colmap['Nüfus 2025'][0])}${last}"
colK = f"${kc}$2:${kc}${last}"
for title, keys in (("İLÇE", sorted({(r[0], r[1]) for r in rows})), ("İL", sorted({(r[0],) for r in rows}))):
    s = wb.create_sheet(title)
    heads = (["İL", "İLÇE"] if title == "İLÇE" else ["İL"]) + ["Nüfus 2025", "KENT nüfus", "KIR nüfus", "Karar bekleyen", "Kent %"]
    for i, h in enumerate(heads, 1):
        c = s.cell(row=1, column=i, value=h)
        c.font, c.alignment, c.border = HEAD, Alignment(horizontal="center"), THIN
        c.fill = GROUP["data"] if i > len(heads) - 5 else GROUP["id"]
        s.column_dimensions[get_column_letter(i)].width = 19 if i <= 2 else 13
    for ri, key in enumerate(keys, 2):
        for i, v in enumerate(key, 1):
            s.cell(row=ri, column=i, value=v).font = BODY
        crit = f"{M}!{colA},$A{ri}" + (f",{M}!{colB},$B{ri}" if title == "İLÇE" else "")
        o = len(key)
        L = lambda k: get_column_letter(o + k)  # noqa: E731
        s.cell(row=ri, column=o + 1, value=f"=SUMIFS({M}!{colN},{crit})").number_format = "#,##0"
        s.cell(row=ri, column=o + 2, value=f'=SUMIFS({M}!{colN},{crit},{M}!{colK},"KENT")').number_format = "#,##0"
        s.cell(row=ri, column=o + 3, value=f'=SUMIFS({M}!{colN},{crit},{M}!{colK},"KIR")').number_format = "#,##0"
        s.cell(row=ri, column=o + 4, value=f"={L(1)}{ri}-{L(2)}{ri}-{L(3)}{ri}").number_format = "#,##0"
        s.cell(row=ri, column=o + 5, value=f'=IF({L(2)}{ri}+{L(3)}{ri}=0,"",{L(2)}{ri}/({L(2)}{ri}+{L(3)}{ri})*100)').number_format = "0.00"
        for i in range(o + 1, o + 6):
            s.cell(row=ri, column=i).font = BODY
    s.freeze_panes = "A2" if title == "İL" else "C2"
    s.auto_filter.ref = f"A1:{get_column_letter(len(heads))}{len(keys) + 1}"

# AÇIKLAMA
a = wb.create_sheet("AÇIKLAMA", 0)
notes = [
    ("Ne doldurulacak", "MAHALLE-KÖY sayfasındaki sarı sütunlar: KENT / KIR (listeden KENT ya da KIR), YERLEŞİM (senin; boşsa YERLEŞİM geçerli), NOT. İLÇE ve İL sayfaları bu sütundan kendiliğinden hesaplanır; 'Karar bekleyen' henüz işaretlenmemiş nüfustur."),
    ("Örnek satır", "Bursa | İznik | İznik İlçe Merkezi | Mustafakemalpaşa | Mahalle | … | KENT | İznik Merkez | sur içi"),
    ("YERLEŞİM", "Büyükşehir dışı: bugünkü resmî statü (İl/İlçe merkezi, belde adı, '<ilçe> Köyleri'). 30 büyükşehirde 2012 statüsü (mahalleye dönüşmeden önce)."),
    ("Nüfus 2025, 0-17 %", "TÜİK ADNKS 2025. 0-17 yalnız mahallelerde; TÜİK'in gizlediği çok küçük mahallelerde boş."),
    ("Erkek %, Hane, Konut", "Endeksa 2024 (ADNKS ile %85 birebir)."),
    ("Ortanca yaş", "2024; Endeksa yaş grupları TÜİK toplamlarıyla Monte Carlo (200 çekiliş)."),
    ("Yüzölçümü km²", "Mahalle sınırı çokgeninden; yaklaşık."),
    ("Bina", "Microsoft bina ayak izleri (Şubat 2026), mahalle sınırı içinde."),
    ("TÜİK statü", "Resmî statü: büyükşehir dışında bugün, büyükşehirde 2012."),
    ("AATOPLU 2015", "Senin 7 Haziran 2015 tablon: Mahalle / Belde / Köy."),
    ("DEGURBA", "AB kentleşme derecesi 2025 (Yoğun kent / Orta yoğun kent / Kır)."),
    ("Microsoft bina analizi", "Bina lekesi kuralı: merkez, kentsel belde (ayrı leke ≥5.000), kasaba (2.000-5.000), kırsal belde, köy."),
    ("Analiz önerisi", "Bütün kaynaklar ve senin önceki kararlarınla birleştirilmiş sınıf (Bursa/Ankara elle, diğer iller kurallarla)."),
]
a.column_dimensions["A"].width = 24
a.column_dimensions["B"].width = 120
for i, (k, v) in enumerate(notes, 1):
    a.cell(row=i, column=1, value=k).font = HEAD
    c = a.cell(row=i, column=2, value=v)
    c.font, c.alignment = BODY, Alignment(wrap_text=True, vertical="top")
wb.active = 1
OUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT)
print("yazıldı", OUT)
