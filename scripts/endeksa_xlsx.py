"""Build a district workbook from an Endeksa dump plus TUIK neighbourhood series.

Usage:
    python scripts/endeksa_xlsx.py --district TR-16-006 [--dump endeksa-16-1420.json]
                                   [--raw C:/veri/raw/endeksa] [--out out.xlsx]

Without --dump the raw folder is expected to already hold the per-file layout
(county.json, <DistrictId>-<slug>.json, election.json, fellowcountryman.json,
geo.json). With --dump, a single endeksaFetch.download() file is unpacked into
that layout first.

Everything numeric that can be derived (shares, densities, turnout) is written
as a formula referencing count columns on the same row, so the workbook stays
live when a count is corrected. Raw JSON remains the source of truth.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

REPO = Path(__file__).resolve().parent.parent
FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
SUB_FILL = PatternFill("solid", fgColor="D9E1F2")
NOTE_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="BFBFBF")

AGE_BANDS = [
    "0_4", "5_9", "10_14", "15_19", "20_24", "25_29", "30_34", "35_39",
    "40_44", "45_49", "50_54", "55_59", "60_64", "65",
]
AGE_LABEL = {b: (b.replace("_", "-") if b != "65" else "65+") for b in AGE_BANDS}
EDU = [
    ("EduNonLiterated", "Okuma yazma bilmeyen"),
    ("EduLiteratedUntutored", "Bilen, okul bitirmemiş"),
    ("EduPrimarySchool", "İlkokul"),
    ("EduPrimaryEducation", "İlköğretim"),
    ("EduMiddleSchool", "Ortaokul"),
    ("EduHighSchool", "Lise"),
    ("EduLicenseDegree", "Lisans"),
    ("EduGraduate", "Yüksek lisans"),
    ("EduDoctorate", "Doktora"),
    ("EduUnknown", "Bilinmeyen"),
]
MARITAL = [
    ("MarriedNever", "Hiç evlenmedi"),
    ("Married", "Evli"),
    ("Divorced", "Boşanmış"),
    ("Widow", "Eşi ölmüş"),
]
SES = [("SesGroupAPlus", "A+"), ("SesGroupA", "A"), ("SesGroupB", "B"), ("SesGroupC", "C"), ("SesGroupD", "D")]
EXPENSE = [
    ("ExpenseFood", "Gıda"), ("ExpenseAlcoholAndSmoking", "Alkol-tütün"), ("ExpenseClothing", "Giyim"),
    ("ExpenseShelter", "Barınma"), ("ExpenseFurniture", "Mobilya"), ("ExpenseHealth", "Sağlık"),
    ("ExpenseTransportation", "Ulaşım"), ("ExpenseCommunication", "İletişim"),
    ("ExpenseEntertainment", "Eğlence"), ("ExpenseEducation", "Eğitim"),
    ("ExpenseRestaurant", "Restoran"), ("ExpenseOther", "Diğer"),
]
ELECTION_LABEL = {
    "2011genelsecim": "2011 Genel",
    "2014cumhurbaskani": "2014 Cumhurbaşkanı",
    "2014yerel": "2014 Yerel",
    "2015haziran": "2015 Haziran Genel",
    "2015kasim": "2015 Kasım Genel",
    "2017anayasa": "2017 Referandum",
    "2018cumhurbaskani": "2018 Cumhurbaşkanı",
    "2018genel": "2018 Genel",
    "2019yerelseçimilçebelediye": "2019 Yerel — İlçe Bld.",
    "2019yerelseçimbelediyemeclisi": "2019 Yerel — Bld. Meclisi",
    "2019yerelseçimbüyükşehir": "2019 Yerel — Büyükşehir",
    "2023genel": "2023 Genel",
    "2023CumhurTur1": "2023 Cumhurbaşkanı 1. tur",
    "2023CumhurTur2": "2023 Cumhurbaşkanı 2. tur",
    "2024yerelseçimbelediyebaşkanlığı": "2024 Yerel — İlçe Bld.",
    "2024yerelseçimbelediyemeclisüyeliği": "2024 Yerel — Bld. Meclisi",
    "2024yerelseçimbüyükşehirbelediyebaşkanlığı": "2024 Yerel — Büyükşehir",
}
FOCUS_ELECTION = "2024yerelseçimbelediyebaşkanlığı"


def slug(s: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    return re.sub(r"[^a-z0-9]+", "-", s.translate(tr).lower()).strip("-")


def norm_name(s: str) -> str:
    s = s.replace("I", "ı").replace("İ", "i").lower()
    return re.sub(r"\s*(mah\.|mahallesi|mah)$", "", s).strip()


# ---------------------------------------------------------------- loading


def unpack_dump(dump: Path, raw_dir: Path) -> None:
    d = json.loads(dump.read_text(encoding="utf-8"))
    raw_dir.mkdir(parents=True, exist_ok=True)
    meta = d["meta"]
    (raw_dir / "county.json").write_text(json.dumps({"_meta": meta, **d["county"]}, ensure_ascii=False), "utf-8")
    for did, q in d["quarters"].items():
        name = q["Demography"]["DistrictName"]
        q["_meta"] = {"fetched": meta["fetched"], "placeholder": q["Demography"]["HouseholdCount"] == 0}
        (raw_dir / f"{did}-{slug(name)}.json").write_text(json.dumps(q, ensure_ascii=False), "utf-8")
    (raw_dir / "election.json").write_text(json.dumps({"_meta": meta, **d["election"]}, ensure_ascii=False), "utf-8")
    (raw_dir / "fellowcountryman.json").write_text(json.dumps({"_meta": meta, **d["fellows"]}, ensure_ascii=False), "utf-8")
    if d.get("geo"):
        (raw_dir / "geo.json").write_text(json.dumps({"_meta": meta, **d["geo"]}, ensure_ascii=False), "utf-8")


def load_raw(raw_dir: Path) -> dict:
    county = json.loads((raw_dir / "county.json").read_text("utf-8"))
    quarters = {}
    for p in raw_dir.glob("*-*.json"):
        if p.name[0].isdigit():
            q = json.loads(p.read_text("utf-8"))
            quarters[str(q["Demography"]["DistrictId"])] = q["Demography"]
    election = json.loads((raw_dir / "election.json").read_text("utf-8"))
    fellows = json.loads((raw_dir / "fellowcountryman.json").read_text("utf-8"))
    return {"county": county, "quarters": quarters, "election": election, "fellows": fellows}


def load_tuik(district: str) -> tuple[dict[str, dict], dict[str, dict[int, dict]]]:
    """Return MEDAS areas (by normalised name) and yearly series per area_id."""
    areas = {}
    with open(REPO / "src/veriatlas/data/areas_tr_neighbourhoods.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["parent_id"] == district:
                areas[norm_name(r["name_tr"])] = r
    series: dict[str, dict[int, dict]] = {}
    with gzip.open(REPO / "public/population-neighbourhood.csv.gz", "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["area_id"].startswith(district + "-"):
                continue
            y = int(r["year"])
            cell = series.setdefault(r["area_id"], {}).setdefault(y, {})
            key = (r["age"] or "all") + "|" + (r["sex"] or "all")
            cell[key] = int(r["value"])
    return areas, series


# ---------------------------------------------------------------- styling


def style_header(ws, row: int, ncol: int, fill=HEAD_FILL, color="FFFFFF") -> None:
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name=FONT, bold=True, color=color, size=10)
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(bottom=THIN)
    ws.row_dimensions[row].height = 32


def finish(ws, header_row: int, widths: dict[int, float] | None = None, first_width: float = 22) -> None:
    ws.freeze_panes = ws.cell(row=header_row + 1, column=2)
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(ws.max_column)}{ws.max_row}"
    ws.column_dimensions["A"].width = first_width
    for c in range(2, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(c)].width = (widths or {}).get(c, 11)
    for row in ws.iter_rows(min_row=header_row + 1):
        for cell in row:
            cell.font = Font(name=FONT, size=10)
    ws.sheet_view.zoomScale = 90


def col_fmt(ws, col: int, fmt: str, first: int, last: int) -> None:
    for r in range(first, last + 1):
        ws.cell(row=r, column=col).number_format = fmt


def color_scale(ws, col: int, first: int, last: int) -> None:
    ref = f"{get_column_letter(col)}{first}:{get_column_letter(col)}{last}"
    ws.conditional_formatting.add(ref, ColorScaleRule(start_type="min", start_color="F8696B", mid_type="percentile", mid_value=50, mid_color="FFEB84", end_type="max", end_color="63BE7B"))


# ---------------------------------------------------------------- sheets


def build(district: str, raw: dict, areas: dict, series: dict, out: Path) -> None:
    county = raw["county"]["Demography"]
    subs = raw["county"]["SubRegionals"]
    quarters = raw["quarters"]
    # order: by Endeksa DistrictId (centre quarters first), then name
    order = sorted(subs, key=lambda s: (s["DistrictId"] >= 100000, s["RegionName"]))
    rows = []
    for s in order:
        did = str(s["DistrictId"])
        q = quarters.get(did)
        if not q:
            continue
        area = areas.get(norm_name(s["RegionName"]))
        rows.append({
            "did": did, "name": s["RegionName"], "q": q,
            "area_id": area["area_id"] if area else "",
            "kind": "merkez" if s["DistrictId"] < 100000 else "kır",
            "placeholder": q["HouseholdCount"] == 0,
            "tuik": series.get(area["area_id"], {}) if area else {},
        })
    n = len(rows)
    wb = Workbook()
    wb.calculation.fullCalcOnLoad = True

    # ---- Özet
    ws = wb.active
    ws.title = "Özet"
    title = f"{county['CityName'].title()} {county['CountyName'].title()} — mahalle özeti"
    ws["A1"] = title
    ws["A1"].font = Font(name=FONT, bold=True, size=14)
    ws["A2"] = "Endeksa 2024 kesiti + TÜİK ADNKS 2013-2025. Oran/yoğunluk sütunları formül; sayım sütunları kaynaktan. 'Veri' = hayır olan satırlarda Endeksa mahalle verisi yok (boş şablon), yalnız TÜİK ve seçim geçerli."
    ws["A2"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 4
    heads = [
        "Mahalle", "Tür", "Veri", "MEDAS kimlik", "Endeksa id",
        "Nüfus 2024 (TÜİK)", "Nüfus 2013 (TÜİK)", "Değişim 2013→24", "Nüfus 2025 (TÜİK)",
        "Erkek", "Kadın", "Kadın payı",
        "0-14", "15-64", "65+", "65+ payı", "0-14 payı",
        "Yüzölçümü km²", "Yoğunluk kişi/km²",
        "Hane", "Hane büyüklüğü", "Mülk sahibi %", "Kiracı %",
        "Lisans+ (kişi)", "Eğitim toplamı", "Lisans+ payı",
        "SES A+AB", "SES toplam", "AB payı", "Hane geliri ₺/ay", "Kişi başı gelir ₺/ay",
        "Konut", "Ticari birim",
        "2024 kayıtlı seçmen", "2024 kullanılan oy", "Katılım", "2024 1. parti", "1. parti oyu", "2024 geçerli oy", "1. parti payı",
        "Hemşehri 1. il (Bursa dışı)", "Kişi",
    ]
    ws.append([])
    for i, h in enumerate(heads, 1):
        ws.cell(row=H, column=i, value=h)
    style_header(ws, H, len(heads))
    el_q = raw["election"]["quarters"]
    fel_q = raw["fellows"]["quarters"]
    for i, r in enumerate(rows):
        q = r["q"]
        R = H + 1 + i
        t = r["tuik"]
        tot = lambda y: t.get(y, {}).get("all|all") or sum(v for k, v in t.get(y, {}).items() if k.endswith("|all") and not k.startswith("all")) or None
        e = next((x for x in el_q.get(r["did"], []) if x["Code"] == FOCUS_ELECTION), None)
        top = max(e["Secenekler"], key=lambda s: s["OySayisi"]) if e and e["Secenekler"] else None
        fel = [f for f in fel_q.get(r["did"], {}).get("FellowCountryman", []) if f["CitizenCity"] != county["CityName"]]
        ph = r["placeholder"]
        num = lambda k: None if ph else q[k]
        vals = [
            r["name"], r["kind"], "hayır" if ph else "evet", r["area_id"], int(r["did"]),
            tot(2024), tot(2013), f"=IF(AND(ISNUMBER(F{R}),ISNUMBER(G{R}),G{R}>0),F{R}/G{R}-1,\"\")", tot(2025),
            q["PopulationMale"], q["PopulationFemale"], f"=IF(J{R}+K{R}>0,K{R}/(J{R}+K{R}),\"\")",
            num("Age_Group_0_14"), (None if ph else q["PopulationTotal"] - q["Age_Group_0_14"] - q["Age_65_Total"]), num("Age_65_Total"),
            f"=IF(AND(ISNUMBER(O{R}),M{R}+N{R}+O{R}>0),O{R}/(M{R}+N{R}+O{R}),\"\")",
            f"=IF(AND(ISNUMBER(M{R}),M{R}+N{R}+O{R}>0),M{R}/(M{R}+N{R}+O{R}),\"\")",
            q["Area"], f"=IF(R{R}>0,(J{R}+K{R})/R{R},\"\")",
            num("HouseholdCount"), f"=IF(AND(ISNUMBER(T{R}),T{R}>0),(J{R}+K{R})/T{R},\"\")",
            None if ph else q["OwnerShare"] / 100, None if ph else q["RentedShare"] / 100,
            None if ph else q["EduLicenseDegree"] + q["EduGraduate"] + q["EduDoctorate"], num("EducationTotal"),
            f"=IF(AND(ISNUMBER(X{R}),Y{R}>0),X{R}/Y{R},\"\")",
            None if ph else q["SesGroupAPlus"] + q["SesGroupA"] + q["SesGroupB"],
            None if ph else sum(q[k] for k, _ in SES),
            f"=IF(AND(ISNUMBER(AA{R}),AB{R}>0),AA{R}/AB{R},\"\")",
            num("HouseIncomeTotal"), num("HouseIncome"),
            q["HousingCount"], q["CommercialCount"],
            e["KayitliSecmen"] if e else None, e["KullanilanOy"] if e else None,
            f"=IF(AND(ISNUMBER(AH{R}),AH{R}>0),AI{R}/AH{R},\"\")",
            top["Secenek"] if top else None, top["OySayisi"] if top else None, e["GecerliOy"] if e else None,
            f"=IF(AND(ISNUMBER(AL{R}),AM{R}>0),AL{R}/AM{R},\"\")",
            fel[0]["CitizenCity"].title() if fel else None, fel[0]["CountOf"] if fel else None,
        ]
        for c, v in enumerate(vals, 1):
            ws.cell(row=R, column=c, value=v)
    last = H + n
    # county row
    R = last + 1
    ws.cell(row=R, column=1, value="İLÇE TOPLAMI (Endeksa)").font = Font(name=FONT, bold=True)
    ws.cell(row=R, column=10, value=county["PopulationMale"])
    ws.cell(row=R, column=11, value=county["PopulationFemale"])
    ws.cell(row=R, column=12, value=f"=K{R}/(J{R}+K{R})")
    ws.cell(row=R, column=13, value=county["Age_Group_0_14"])
    ws.cell(row=R, column=14, value=county["PopulationTotal"] - county["Age_Group_0_14"] - county["Age_65_Total"])
    ws.cell(row=R, column=15, value=county["Age_65_Total"])
    ws.cell(row=R, column=16, value=f"=O{R}/(M{R}+N{R}+O{R})")
    ws.cell(row=R, column=18, value=county["Area"])
    ws.cell(row=R, column=19, value=f"=(J{R}+K{R})/R{R}")
    ws.cell(row=R, column=20, value=county["HouseholdCount"])
    ws.cell(row=R, column=30, value=county["HouseIncomeTotal"])
    ec = next((x for x in raw["election"]["county"] if x["Code"] == FOCUS_ELECTION), None)
    if ec:
        ws.cell(row=R, column=34, value=ec["KayitliSecmen"])
        ws.cell(row=R, column=35, value=ec["KullanilanOy"])
        ws.cell(row=R, column=36, value=f"=AI{R}/AH{R}")
    for c in range(1, len(heads) + 1):
        ws.cell(row=R, column=c).fill = SUB_FILL
    R2 = last + 2
    ws.cell(row=R2, column=1, value="Mahalleler toplamı (kontrol)").font = Font(name=FONT, italic=True)
    for c in (6, 7, 9, 10, 11, 13, 14, 15, 18, 20, 32, 33, 34, 35):
        L = get_column_letter(c)
        ws.cell(row=R2, column=c, value=f"=SUM({L}{H + 1}:{L}{last})")
    for c in range(1, len(heads) + 1):
        ws.cell(row=R2, column=c).font = Font(name=FONT, italic=True, size=9)
    pct_cols = [8, 12, 16, 17, 22, 23, 26, 29, 36, 40]
    for c in pct_cols:
        col_fmt(ws, c, "0.0%", H + 1, R2)
    for c in (6, 7, 9, 10, 11, 13, 14, 15, 20, 24, 25, 27, 28, 30, 31, 32, 33, 34, 35, 38, 39, 42):
        col_fmt(ws, c, "#,##0", H + 1, R2)
    col_fmt(ws, 18, "0.00", H + 1, R2)
    col_fmt(ws, 19, "#,##0", H + 1, R2)
    col_fmt(ws, 21, "0.00", H + 1, R2)
    for c in (8, 16, 26, 29, 36):
        color_scale(ws, c, H + 1, last)
    finish(ws, H, {4: 16, 37: 14, 41: 16})

    # ---- Yaş
    ws = wb.create_sheet("Yaş")
    ws["A1"] = "Yaş grupları (5'lik) × cinsiyet — Endeksa 2024. Satır toplamı ve payı formül."
    ws["A1"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 3
    heads = ["Mahalle", "Toplam"]
    for b in AGE_BANDS:
        heads += [f"{AGE_LABEL[b]} T", f"{AGE_LABEL[b]} E", f"{AGE_LABEL[b]} K"]
    heads += ["0-14 payı", "15-29 payı", "30-44 payı", "45-59 payı", "60+ payı", "Kadın/100 erkek (65+)"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=H, column=i, value=h)
    style_header(ws, H, len(heads))
    for i, r in enumerate(rows):
        q = r["q"]
        R = H + 1 + i
        if r["placeholder"]:
            ws.cell(row=R, column=1, value=r["name"] + " (veri yok)")
            continue
        ws.cell(row=R, column=1, value=r["name"])
        ws.cell(row=R, column=2, value=f"=SUMPRODUCT((MOD(COLUMN(C{R}:AR{R})-3,3)=0)*C{R}:AR{R})")
        c = 3
        for b in AGE_BANDS:
            for sfx in ("Total", "Male", "Female"):
                ws.cell(row=R, column=c, value=q[f"Age_{b}_{sfx}"])
                c += 1
        # shares: bands T columns: 0-4=C,5-9=F,10-14=I,15-19=L,20-24=O,25-29=R,30-34=U,35-39=X,40-44=AA,45-49=AD,50-54=AG,55-59=AJ,60-64=AM,65+=AP
        ws.cell(row=R, column=c, value=f"=IF(B{R}>0,(C{R}+F{R}+I{R})/B{R},\"\")")
        ws.cell(row=R, column=c + 1, value=f"=IF(B{R}>0,(L{R}+O{R}+R{R})/B{R},\"\")")
        ws.cell(row=R, column=c + 2, value=f"=IF(B{R}>0,(U{R}+X{R}+AA{R})/B{R},\"\")")
        ws.cell(row=R, column=c + 3, value=f"=IF(B{R}>0,(AD{R}+AG{R}+AJ{R})/B{R},\"\")")
        ws.cell(row=R, column=c + 4, value=f"=IF(B{R}>0,(AM{R}+AP{R})/B{R},\"\")")
        ws.cell(row=R, column=c + 5, value=f"=IF(AQ{R}>0,AR{R}/AQ{R}*100,\"\")")
    last = H + n
    R = last + 1
    ws.cell(row=R, column=1, value="İLÇE (Endeksa)").font = Font(name=FONT, bold=True)
    c = 3
    for b in AGE_BANDS:
        for sfx in ("Total", "Male", "Female"):
            ws.cell(row=R, column=c, value=county[f"Age_{b}_{sfx}"])
            c += 1
    ws.cell(row=R, column=2, value=f"=SUMPRODUCT((MOD(COLUMN(C{R}:AR{R})-3,3)=0)*C{R}:AR{R})")
    for c in range(1, len(heads) + 1):
        ws.cell(row=R, column=c).fill = SUB_FILL
    for c in range(2, 45):
        col_fmt(ws, c, "#,##0", H + 1, R)
    for c in range(45, 50):
        col_fmt(ws, c, "0.0%", H + 1, R)
        color_scale(ws, c, H + 1, last)
    col_fmt(ws, 50, "0", H + 1, R)
    finish(ws, H, {c: 7 for c in range(3, 45)})

    # ---- Eğitim + Medeni
    ws = wb.create_sheet("Eğitim-Medeni")
    ws["A1"] = "Eğitim düzeyi (6+ yaş, kişi) ve medeni hal (15+ yaş, kişi) — Endeksa 2024. Paylar formül."
    ws["A1"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 3
    heads = ["Mahalle"] + [lbl for _, lbl in EDU] + ["Eğitim toplamı", "İlkokul ve altı payı", "Orta-lise payı", "Lisans+ payı", ""] + [lbl for _, lbl in MARITAL] + ["15+ toplam", "Evli payı", "Boşanmış payı", "Hiç evlenmemiş payı"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=H, column=i, value=h)
    style_header(ws, H, len(heads))

    def edu_row(R, q, name, bold=False):
        ws.cell(row=R, column=1, value=name).font = Font(name=FONT, bold=bold, size=10)
        for j, (k, _) in enumerate(EDU, 2):
            ws.cell(row=R, column=j, value=q[k])
        ws.cell(row=R, column=12, value=f"=SUM(B{R}:K{R})")
        ws.cell(row=R, column=13, value=f"=IF(L{R}>0,(B{R}+C{R}+D{R})/L{R},\"\")")
        ws.cell(row=R, column=14, value=f"=IF(L{R}>0,(E{R}+F{R}+G{R})/L{R},\"\")")
        ws.cell(row=R, column=15, value=f"=IF(L{R}>0,(H{R}+I{R}+J{R})/L{R},\"\")")
        for j, (k, _) in enumerate(MARITAL, 17):
            ws.cell(row=R, column=j, value=q[k])
        ws.cell(row=R, column=21, value=f"=SUM(Q{R}:T{R})")
        ws.cell(row=R, column=22, value=f"=IF(U{R}>0,R{R}/U{R},\"\")")
        ws.cell(row=R, column=23, value=f"=IF(U{R}>0,S{R}/U{R},\"\")")
        ws.cell(row=R, column=24, value=f"=IF(U{R}>0,Q{R}/U{R},\"\")")

    for i, r in enumerate(rows):
        R = H + 1 + i
        if r["placeholder"]:
            ws.cell(row=R, column=1, value=r["name"] + " (veri yok)")
            continue
        edu_row(R, r["q"], r["name"])
    last = H + n
    edu_row(last + 1, county, "İLÇE (Endeksa)", bold=True)
    for c in range(1, len(heads) + 1):
        ws.cell(row=last + 1, column=c).fill = SUB_FILL
    for c in list(range(2, 13)) + list(range(17, 22)):
        col_fmt(ws, c, "#,##0", H + 1, last + 1)
    for c in (13, 14, 15, 22, 23, 24):
        col_fmt(ws, c, "0.0%", H + 1, last + 1)
        color_scale(ws, c, H + 1, last)
    finish(ws, H, {16: 2})

    # ---- SES-Gelir
    ws = wb.create_sheet("SES-Gelir")
    ws["A1"] = "Sosyo-ekonomik statü (kişi), gelir ve aylık hane harcaması (₺) — Endeksa modeli (tahmin, TÜİK değil). Paylar formül."
    ws["A1"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 3
    heads = ["Mahalle", "Türkiye endeksi", "İl endeksi"] + [f"SES {lbl}" for _, lbl in SES] + ["SES toplam", "AB payı", "D payı", "Hane geliri", "Kişi başı gelir", "Tasarruf", "Harcama toplamı"] + [lbl for _, lbl in EXPENSE] + ["Mülk sahibi", "Kiracı", "GSYH ₺", "Mobil kullanıcı", "Araç sayısı"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=H, column=i, value=h)
    style_header(ws, H, len(heads))

    def ses_row(R, q, name, bold=False):
        ws.cell(row=R, column=1, value=name).font = Font(name=FONT, bold=bold, size=10)
        ws.cell(row=R, column=2, value=q.get("TurkeyIndex"))
        ws.cell(row=R, column=3, value=q.get("CityIndex"))
        for j, (k, _) in enumerate(SES, 4):
            ws.cell(row=R, column=j, value=q[k])
        ws.cell(row=R, column=9, value=f"=SUM(D{R}:H{R})")
        ws.cell(row=R, column=10, value=f"=IF(I{R}>0,(D{R}+E{R}+F{R})/I{R},\"\")")
        ws.cell(row=R, column=11, value=f"=IF(I{R}>0,H{R}/I{R},\"\")")
        ws.cell(row=R, column=12, value=q["HouseIncomeTotal"])
        ws.cell(row=R, column=13, value=q["HouseIncome"])
        ws.cell(row=R, column=14, value=q["SavingTotal"])
        ws.cell(row=R, column=15, value=q["ExpenseTotal"])
        for j, (k, _) in enumerate(EXPENSE, 16):
            ws.cell(row=R, column=j, value=q[k])
        ws.cell(row=R, column=28, value=q["OwnerShare"] / 100)
        ws.cell(row=R, column=29, value=q["RentedShare"] / 100)
        ws.cell(row=R, column=30, value=q["GSYH"])
        ws.cell(row=R, column=31, value=q["MobileUser"])
        ws.cell(row=R, column=32, value=q["CarCount"])

    for i, r in enumerate(rows):
        R = H + 1 + i
        if r["placeholder"]:
            ws.cell(row=R, column=1, value=r["name"] + " (veri yok)")
            continue
        ses_row(R, r["q"], r["name"])
    last = H + n
    ses_row(last + 1, county, "İLÇE (Endeksa)", bold=True)
    for c in range(1, len(heads) + 1):
        ws.cell(row=last + 1, column=c).fill = SUB_FILL
    for c in list(range(4, 10)) + list(range(12, 28)) + [30, 31, 32]:
        col_fmt(ws, c, "#,##0", H + 1, last + 1)
    for c in (10, 11, 28, 29):
        col_fmt(ws, c, "0.0%", H + 1, last + 1)
    for c in (10, 12):
        color_scale(ws, c, H + 1, last)
    finish(ws, H, {2: 12, 3: 12})

    # ---- Konut
    ws = wb.create_sheet("Konut-Emlak")
    ws["A1"] = "Konut stoğu ve tapu satışları (adet, yıl) — Endeksa. 2024 kısmi yıl."
    ws["A1"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 3
    years = list(range(2012, 2025))
    heads = ["Mahalle", "Konut", "Yazlık", "Ticari birim", "Konut/hane"] + [f"Konut satış {y}" for y in years] + [f"Arsa-tarla satış {y}" for y in years] + [f"İlan {y}" for y in range(2014, 2025)] + ["Konut m² satış ₺", "Konut m² kira ₺", "Arsa m² ₺", "Tarla m² ₺"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=H, column=i, value=h)
    style_header(ws, H, len(heads))

    def housing_row(R, q, name, bold=False):
        ws.cell(row=R, column=1, value=name).font = Font(name=FONT, bold=bold, size=10)
        ws.cell(row=R, column=2, value=q["HousingCount"])
        ws.cell(row=R, column=3, value=q["SummerResortCount"])
        ws.cell(row=R, column=4, value=q["CommercialCount"])
        ws.cell(row=R, column=5, value=(f"=IF({q['HouseholdCount']}>0,B{R}/{q['HouseholdCount']},\"\")") if q["HouseholdCount"] else None)
        c = 6
        for y in years:
            ws.cell(row=R, column=c, value=q.get(f"Total_BB_Sale_{y}"))
            c += 1
        for y in years:
            ws.cell(row=R, column=c, value=q.get(f"Total_AT_Sale_{y}"))
            c += 1
        for y in range(2014, 2025):
            ws.cell(row=R, column=c, value=q.get(f"Total_Listing_{y}"))
            c += 1
        for k in ("HouseUnitPriceForSale", "HouseUnitPriceForRent", "PlotUnitPriceForSale", "LandUnitPriceForSale"):
            ws.cell(row=R, column=c, value=q[k] or None)
            c += 1

    for i, r in enumerate(rows):
        housing_row(H + 1 + i, r["q"], r["name"])
    last = H + n
    housing_row(last + 1, county, "İLÇE (Endeksa)", bold=True)
    for c in range(1, len(heads) + 1):
        ws.cell(row=last + 1, column=c).fill = SUB_FILL
    for c in range(2, len(heads) + 1):
        col_fmt(ws, c, "#,##0", H + 1, last + 1)
    col_fmt(ws, 5, "0.00", H + 1, last + 1)
    finish(ws, H, {c: 8 for c in range(6, len(heads) - 3)})

    # ---- Seçim 2024 pivot
    ws = wb.create_sheet("Seçim 2024")
    ws["A1"] = f"{ELECTION_LABEL[FOCUS_ELECTION]} — mahalle × parti. Oy sayıları kaynaktan, paylar geçerli oya bölünerek formül. Küçük partiler kaynakta 'Diğer' altında."
    ws["A1"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 3
    parties: list[str] = []
    for did, lst in el_q.items():
        e = next((x for x in lst if x["Code"] == FOCUS_ELECTION), None)
        if e:
            for s in e["Secenekler"]:
                if s["Secenek"] not in parties:
                    parties.append(s["Secenek"])
    # order parties by county votes
    ec = next((x for x in raw["election"]["county"] if x["Code"] == FOCUS_ELECTION), None)
    cv = {s["Secenek"]: s["OySayisi"] for s in ec["Secenekler"]} if ec else {}
    parties.sort(key=lambda p: -cv.get(p, 0))
    heads = ["Mahalle", "Sandık", "Kayıtlı", "Kullanılan", "Geçerli", "Geçersiz", "Katılım"] + parties + [f"{p} %" for p in parties] + ["1. parti"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=H, column=i, value=h)
    style_header(ws, H, len(heads))
    P = len(parties)

    def el_row(R, e, name, bold=False):
        ws.cell(row=R, column=1, value=name).font = Font(name=FONT, bold=bold, size=10)
        if not e:
            return
        ws.cell(row=R, column=2, value=e["SandikSayisi"])
        ws.cell(row=R, column=3, value=e["KayitliSecmen"])
        ws.cell(row=R, column=4, value=e["KullanilanOy"])
        ws.cell(row=R, column=5, value=e["GecerliOy"])
        ws.cell(row=R, column=6, value=e["GecersizOy"])
        ws.cell(row=R, column=7, value=f"=IF(C{R}>0,D{R}/C{R},\"\")")
        votes = {s["Secenek"]: s["OySayisi"] for s in e["Secenekler"]}
        for j, p in enumerate(parties):
            ws.cell(row=R, column=8 + j, value=votes.get(p, 0))
            L = get_column_letter(8 + j)
            ws.cell(row=R, column=8 + P + j, value=f"=IF(E{R}>0,{L}{R}/E{R},\"\")")
        first = get_column_letter(8)
        lastc = get_column_letter(7 + P)
        hdr = f"${first}${H}:${lastc}${H}"
        ws.cell(row=R, column=8 + 2 * P, value=f"=IF(E{R}>0,INDEX({hdr},MATCH(MAX({first}{R}:{lastc}{R}),{first}{R}:{lastc}{R},0)),\"\")")

    for i, r in enumerate(rows):
        e = next((x for x in el_q.get(r["did"], []) if x["Code"] == FOCUS_ELECTION), None)
        el_row(H + 1 + i, e, r["name"])
    last = H + n
    el_row(last + 1, ec, "İLÇE", bold=True)
    for c in range(1, len(heads) + 1):
        ws.cell(row=last + 1, column=c).fill = SUB_FILL
    for c in list(range(2, 7)) + list(range(8, 8 + P)):
        col_fmt(ws, c, "#,##0", H + 1, last + 1)
    col_fmt(ws, 7, "0.0%", H + 1, last + 1)
    color_scale(ws, 7, H + 1, last)
    for c in range(8 + P, 8 + 2 * P):
        col_fmt(ws, c, "0.0%", H + 1, last + 1)
        color_scale(ws, c, H + 1, last)
    finish(ws, H, {c: 9 for c in range(2, 8 + 2 * P)})

    # ---- Seçimler (long)
    ws = wb.create_sheet("Seçimler")
    ws["A1"] = "Tüm seçimler, uzun tablo — filtreleyip özet tablo (pivot) kurmak için. Pay = oy / geçerli oy (formül)."
    ws["A1"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 3
    heads = ["Mahalle", "Seçim kodu", "Seçim", "Sandık", "Kayıtlı", "Kullanılan", "Geçerli", "Geçersiz", "Parti / aday", "Oy", "Pay"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=H, column=i, value=h)
    style_header(ws, H, len(heads))
    R = H + 1
    for r in rows + [{"name": "İLÇE", "did": "__county__"}]:
        lst = raw["election"]["county"] if r["did"] == "__county__" else el_q.get(r["did"], [])
        for e in lst:
            for s in e["Secenekler"]:
                ws.append([r["name"], e["Code"], ELECTION_LABEL.get(e["Code"], e["Title"]), e["SandikSayisi"], e["KayitliSecmen"], e["KullanilanOy"], e["GecerliOy"], e["GecersizOy"], s["Secenek"], s["OySayisi"], f"=IF(G{R}>0,J{R}/G{R},\"\")"])
                R += 1
    for c in (4, 5, 6, 7, 8, 10):
        col_fmt(ws, c, "#,##0", H + 1, R - 1)
    col_fmt(ws, 11, "0.0%", H + 1, R - 1)
    finish(ws, H, {2: 30, 3: 26, 9: 24})

    # ---- Hemşehri
    ws = wb.create_sheet("Hemşehri")
    ws["A1"] = "Mahalle sakinlerinin nüfusa kayıtlı olduğu il — ilk 10 il (kişi), Endeksa. Pay = il / mahalle nüfusu (formül, Özet sayfasından)."
    ws["A1"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 3
    heads = ["Mahalle", "Sıra", "Kayıtlı il", "Kişi", "Mahalle nüfusu", "Pay"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=H, column=i, value=h)
    style_header(ws, H, len(heads))
    R = H + 1
    for r in rows + [{"name": "İLÇE", "did": "__county__", "q": county}]:
        f = raw["fellows"]["county"] if r["did"] == "__county__" else fel_q.get(r["did"], {})
        popn = r["q"]["PopulationTotal"]
        for k, x in enumerate((f or {}).get("FellowCountryman", []), 1):
            ws.append([r["name"], k, x["CitizenCity"].title(), x["CountOf"], popn, f"=IF(E{R}>0,D{R}/E{R},\"\")"])
            R += 1
    col_fmt(ws, 4, "#,##0", H + 1, R - 1)
    col_fmt(ws, 5, "#,##0", H + 1, R - 1)
    col_fmt(ws, 6, "0.0%", H + 1, R - 1)
    finish(ws, H, {3: 16, 5: 14})

    # ---- TÜİK serisi
    ws = wb.create_sheet("TÜİK Nüfus")
    ws["A1"] = "TÜİK ADNKS mahalle nüfusu 2013-2025 (toplam, 18+, 0-17, erkek, kadın) — VeriAtlas ambarı (tuik_medas)."
    ws["A1"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 3
    yrs = sorted({y for s in series.values() for y in s})
    heads = ["Mahalle", "MEDAS kimlik"] + [f"Toplam {y}" for y in yrs] + [f"18+ {y}" for y in yrs] + [f"0-17 {y}" for y in yrs] + [f"Erkek {y}" for y in yrs] + [f"Kadın {y}" for y in yrs] + [f"Değişim {yrs[0]}→{yrs[-1]}", f"18+ payı {yrs[-1]}", f"Kadın payı {yrs[-1]}"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=H, column=i, value=h)
    style_header(ws, H, len(heads))
    Y = len(yrs)

    def tuik_val(t, y, key):
        cell = t.get(y, {})
        if key == "all|all":
            return cell.get("all|all") or (sum(v for k, v in cell.items() if k.endswith("|all") and not k.startswith("all")) or None)
        return cell.get(key)

    for i, r in enumerate(rows):
        R = H + 1 + i
        t = r["tuik"]
        ws.cell(row=R, column=1, value=r["name"])
        ws.cell(row=R, column=2, value=r["area_id"])
        c = 3
        for key in ("all|all", "18+|all", "0-17|all", "all|male", "all|female"):
            for y in yrs:
                v = tuik_val(t, y, key)
                if v is None and key in ("all|male", "all|female"):
                    sx = key.split("|")[1]
                    a = t.get(y, {})
                    v = (a.get(f"18+|{sx}", 0) + a.get(f"0-17|{sx}", 0)) or None
                ws.cell(row=R, column=c, value=v)
                c += 1
        t0, t1 = get_column_letter(3), get_column_letter(2 + Y)
        ws.cell(row=R, column=c, value=f"=IF(AND(ISNUMBER({t0}{R}),{t0}{R}>0),{t1}{R}/{t0}{R}-1,\"\")")
        a18 = get_column_letter(2 + 2 * Y)
        ws.cell(row=R, column=c + 1, value=f"=IF(AND(ISNUMBER({a18}{R}),{t1}{R}>0),{a18}{R}/{t1}{R},\"\")")
        kf = get_column_letter(2 + 5 * Y)
        ws.cell(row=R, column=c + 2, value=f"=IF(AND(ISNUMBER({kf}{R}),{t1}{R}>0),{kf}{R}/{t1}{R},\"\")")
    last = H + n
    R = last + 1
    ws.cell(row=R, column=1, value="Mahalleler toplamı").font = Font(name=FONT, bold=True)
    for c in range(3, 3 + 5 * Y):
        L = get_column_letter(c)
        ws.cell(row=R, column=c, value=f"=SUM({L}{H + 1}:{L}{last})")
    for c in range(1, len(heads) + 1):
        ws.cell(row=R, column=c).fill = SUB_FILL
    for c in range(3, 3 + 5 * Y):
        col_fmt(ws, c, "#,##0", H + 1, R)
    for c in range(3 + 5 * Y, 6 + 5 * Y):
        col_fmt(ws, c, "0.0%", H + 1, R)
        color_scale(ws, c, H + 1, last)
    finish(ws, H, {2: 18, **{c: 8 for c in range(3, 3 + 5 * Y)}})

    # ---- Ham
    ws = wb.create_sheet("Ham (Endeksa)")
    ws["A1"] = "Endeksa demografi yanıtının tüm alanları, mahalle başına bir satır (ilçe ilk satır). Alan adları kaynaktaki gibi."
    ws["A1"].font = Font(name=FONT, italic=True, size=9, color="595959")
    H = 3
    keys = [k for k in county.keys()]
    for i, k in enumerate(keys, 1):
        ws.cell(row=H, column=i, value=k)
    style_header(ws, H, len(keys))
    ws.append([county.get(k) for k in keys])
    for r in rows:
        ws.append([r["q"].get(k) for k in keys])
    finish(ws, H, {c: 12 for c in range(2, len(keys) + 1)}, first_width=8)
    ws.freeze_panes = ws.cell(row=H + 1, column=1)

    # ---- Notlar
    ws = wb.create_sheet("Notlar")
    notes = [
        ("Kaynak", "Endeksa (endeksa.com) demografi, seçim, hemşehri uç noktaları; dökümü " + raw["county"].get("_meta", {}).get("fetched", "") + ". TÜİK ADNKS mahalle serisi VeriAtlas ambarından (public/population-neighbourhood.csv.gz)."),
        ("Yıl", "Endeksa tek kesit: nüfus TÜİK ADNKS 2024 ile birebir. Seçimler kendi tarihlerinde. Emlak satışları yıllık seri (2024 kısmi)."),
        ("Veri yok", "Küçük eski köylerde Endeksa mahalle düzeyi demografi üretmiyor; bu satırlar Özet'te 'Veri = hayır' ve ilgili sayfalarda '(veri yok)'. Seçim ve hemşehri bu mahallelerde de dolu."),
        ("Tahmin", "SES, gelir, harcama, tasarruf, mülk/kiracı Endeksa modelidir; TÜİK sayımı değildir. Yaş, cinsiyet, eğitim, medeni hal TÜİK kökenli görünüyor."),
        ("Tür", "'merkez' = Endeksa kimliği < 100000 (ilçe merkezinin eski belediye mahalleleri); 'kır' = 2014 öncesi köy/belde. Belde ayrımı bu sürümde yapılmadı."),
        ("Formüller", "Pay, yoğunluk, katılım, 1. parti gibi sütunlar formüldür; sayım sütunu düzeltilirse güncellenir. Dosya Excel'de açılınca hesaplanır."),
        ("Seçim", "Küçük partiler kaynakta 'Diğer' altında; tam döküm için YSK. 'Oran' alanı kaynakta hatalı olduğundan kullanılmadı, paylar yeniden hesaplandı."),
        ("Lisans", "Endeksa verisi araştırma amaçlı kopyadır; yayım kararı verilmedi."),
    ]
    ws["A1"] = "Notlar"
    ws["A1"].font = Font(name=FONT, bold=True, size=14)
    for i, (k, v) in enumerate(notes, 3):
        ws.cell(row=i, column=1, value=k).font = Font(name=FONT, bold=True, size=10)
        c = ws.cell(row=i, column=2, value=v)
        c.font = Font(name=FONT, size=10)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 45
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 110

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--district", required=True, help="VeriAtlas district id, e.g. TR-16-006")
    ap.add_argument("--dump", type=Path, help="single endeksaFetch.download() JSON to unpack first")
    ap.add_argument("--raw", type=Path, default=Path("C:/veri/raw/endeksa"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    raw_dir = a.raw / a.district
    if a.dump:
        unpack_dump(a.dump, raw_dir)
    raw = load_raw(raw_dir)
    areas, series = load_tuik(a.district)
    out = a.out or (a.raw / f"{a.district}-endeksa.xlsx")
    build(a.district, raw, areas, series, out)
    print(out)


if __name__ == "__main__":
    main()
