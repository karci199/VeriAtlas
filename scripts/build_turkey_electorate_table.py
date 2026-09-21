"""Turkey-wide electorate vs. population table, one row per parliamentary election.

Columns: registered voters, voters, valid, invalid (TÜİK election database) next to total
population and population aged 20+ (TÜİK NIP age-group table: censuses 1935-2000, ADNKS
2007+). Election years without a census get a geometric interpolation between the two
nearest population years and are flagged.

Outputs an Excel workbook (default: desktop) and prints the table.

Usage: python scripts/build_turkey_electorate_table.py [output.xlsx]
"""

from __future__ import annotations

import csv
import gzip
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl
import xlrd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ELECTIONS = Path(r"C:\veri\raw\tuik_secim_ilce\secim_ilce.csv")
AGE_GROUPS = Path(r"C:\veri\raw\tuik_nip_age_groups_1935_2025.xlsx")
SINGLE_AGE = Path("C:/veri/public/population-age1.csv.gz")
FOREIGN = Path("C:/veri/public/foreign.csv.gz")
FOREIGN_BY_AGE = Path("C:/veri/raw/tuik_foreign_by_age.xls")
# Registered voters abroad + customs gates (YSK): total minus domestic. Only years verified.
ABROAD_REGISTERED = {"2023": 64_113_941 - 60_697_843}
DEFAULT_OUT = Path(r"C:\Users\katan\OneDrive\Desktop\Türkiye Seçmen ve Nüfus.xlsx")

REGISTERED = "Kayıtlı seçmen sayısı"
VOTED = "Oy kullanan seçmen sayısı"
VALID = "Geçerli oy sayısı"
COUNTS = (REGISTERED, VOTED, VALID)
YEAR_LABELS = {"2015_7_haziran": "2015 Haziran", "2015_1_kasim": "2015 Kasım"}
YEAR_ORDER = {"2015_7_haziran": 2015.0, "2015_1_kasim": 2015.5}
VOTING_AGE = [(1961, 21), (1987, 20), (1995, 18)]  # legal voting age from that year on

NAVY, GREY, ZEBRA, ORANGE = "1F3A73", "6B7280", "E9EDF4", "FDE7C8"
thin = Side(style="thin", color="BFC5D2")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)


def election_year(key: str) -> int:
    return int(key[:4])


def load_elections() -> dict[str, dict[str, int]]:
    """Turkey totals per election.

    Reports up to 1987 carry an explicit 'Türkiye' row. Later reports only carry one
    total row per electoral circle under varying names, so the circle total is taken
    as the largest value among that circle's rows and summed over circles.
    """
    country: dict[str, dict[str, int]] = defaultdict(dict)
    circle_max: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    with ELECTIONS.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            measure = row["olcut"]
            if measure not in COUNTS:
                continue
            value = int(row["deger"])
            if row["birim"] == "Türkiye":
                country[row["yil"]][measure] = value
            else:
                cur = circle_max[row["yil"]][row["cevre"]]
                cur[measure] = max(cur.get(measure, 0), value)
    out: dict[str, dict[str, int]] = {}
    for key, circles in circle_max.items():
        if key in country and len(country[key]) == 3:
            out[key] = country[key]
        else:
            out[key] = {
                m: sum(c[m] for c in circles.values() if m in c) for m in COUNTS
            }
    return out


def load_population() -> dict[int, dict[str, int]]:
    """{year: {'total': n, '15-19': n, '20-24': n, ..., '85+': n}} from the NIP workbook."""
    ws = openpyxl.load_workbook(AGE_GROUPS, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    labels = {i: str(v) for i, v in enumerate(rows[4]) if v and str(v)[0].isdigit()}
    out = {}
    for r in rows[6:]:
        if not (r and str(r[0]).isdigit()):
            continue
        rec = {lab: int(r[i]) for i, lab in labels.items()}
        rec["total"] = int(r[1])
        out[int(r[0])] = rec
    return out


def load_single_age() -> dict[int, dict[int, int]]:
    """{year: {age: n}} for Turkey from the warehouse single-age file (ADNKS 2007+)."""
    out: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    with gzip.open(SINGLE_AGE, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["area_id"] != "TR":
                continue
            age = int(row["age"].rstrip("+"))
            out[int(row["year"])][age] += int(row["value"])
    return out


def load_foreign() -> dict[int, int]:
    """{year: foreign nationals living in Turkey} (ADNKS, 2008+), all ages."""
    out: dict[int, int] = defaultdict(int)
    with gzip.open(FOREIGN, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["area_id"] == "TR":
                out[int(row["year"])] += int(row["value"])
    return dict(out)


def foreign_adult_share() -> tuple[float, str]:
    """Share of foreign nationals aged 18+ (national age-group table, 15-19 split 3/5)."""
    sheet = xlrd.open_workbook(FOREIGN_BY_AGE).sheets()[0]
    header = None
    for i in range(sheet.nrows):
        vals = sheet.row_values(i)
        if "0-4" in vals:
            header = {str(v).strip(): j for j, v in enumerate(vals) if v}
        if header and str(vals[1]).startswith("Toplam yabanc"):
            under = (
                sum(vals[header[b]] for b in ("0-4", "5-9", "10-14"))
                + vals[header["15-19"]] * 3 / 5
            )
            return 1 - under / vals[3], str(sheet.row_values(0)[0]).strip()[-4:]
    raise SystemExit("foreign age table not parsed")


def band_start(label: str) -> int:
    return int(label.split("-")[0].rstrip("+"))


def aged_at_least(rec: dict[str, int], age: int) -> int:
    """Population aged >= age from 5-year bands; uniform split inside the band."""
    total = 0
    for lab, n in rec.items():
        if lab == "total":
            continue
        start = band_start(lab)
        if start >= age:
            total += n
        elif start + 5 > age:  # band straddles the cutoff
            total += round(n * (start + 5 - age) / 5)
    return total


def voting_age_population(pop, single, year: int, age: int) -> tuple[int, int, str]:
    """(total, aged >= age, source). Exact single ages for ADNKS years, bands otherwise."""
    if year in single:
        ages = single[year]
        return sum(ages.values()), sum(n for a, n in ages.items() if a >= age), "ADNKS"
    if year in pop:
        exact = age % 5 == 0
        return (
            pop[year]["total"],
            aged_at_least(pop[year], age),
            "sayım" if exact else "sayım, bant içi pay",
        )
    lo = max(y for y in pop if y < year)
    hi = min(y for y in pop if y > year)
    f = (year - lo) / (hi - lo)
    a, b = pop[lo], pop[hi]
    total = round(a["total"] * (b["total"] / a["total"]) ** f)
    va_lo, va_hi = aged_at_least(a, age), aged_at_least(b, age)
    va = round(va_lo * (va_hi / va_lo) ** f)
    return total, va, f"ara değer {lo}–{hi}"


def legal_voting_age(year: int) -> int:
    age = VOTING_AGE[0][1]
    for start, a in VOTING_AGE:
        if year >= start:
            age = a
    return age


def build_rows(elections, pop, single, foreign):
    share, _ = foreign_adult_share()
    rows = []
    for key in sorted(
        elections, key=lambda k: YEAR_ORDER[k] if k in YEAR_ORDER else float(k)
    ):
        e = elections[key]
        year = election_year(key)
        age = legal_voting_age(year)
        total, over20, source = voting_age_population(pop, single, year, age)
        rows.append(
            {
                "label": YEAR_LABELS.get(key, key),
                "registered": e[REGISTERED],
                "voted": e[VOTED],
                "valid": e[VALID],
                "total": total,
                "over20": over20,
                "source": source,
                "voting_age": age,
                "foreign": foreign.get(year),
                "foreign_adult": round(foreign[year] * share)
                if year in foreign
                else None,
                "abroad": ABROAD_REGISTERED.get(key),
            }
        )
    return rows


def style(
    cell, *, header=False, zebra=False, fmt=None, bold=False, align=CENTER, fill=None
):
    if header:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
    else:
        cell.font = Font(bold=bold, size=10)
        if fill:
            cell.fill = PatternFill("solid", fgColor=fill)
        elif zebra:
            cell.fill = PatternFill("solid", fgColor=ZEBRA)
    cell.alignment = align
    cell.border = BORDER
    if fmt:
        cell.number_format = fmt


def write_workbook(rows, path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Seçmen ve Nüfus"
    for r in range(1, 4):
        for c in range(1, 21):
            ws.cell(r, c).fill = PatternFill("solid", fgColor=ZEBRA)
    ws.merge_cells("A1:T1")
    ws.merge_cells("A2:T2")
    ws.merge_cells("A3:T3")
    ws["A1"].value = "SEÇİM · TÜRKİYE"
    ws["A1"].font = Font(bold=True, size=10, color=GREY)
    ws["A2"].value = "Kayıtlı seçmen ve nüfus — milletvekili genel seçimleri 1961–2023"
    ws["A2"].font = Font(bold=True, size=18, color=NAVY)
    ws["A3"].value = (
        "Seçmen sayıları TÜİK seçim veri tabanı (yurt içi). Nüfus TÜİK yaş grubu tablosu: "
        "sayım (1935–2000) ve ADNKS 2007+ tek yaş; turuncu satır = iki nüfus yılı arası geometrik ara değer."
    )
    ws["A3"].font = Font(size=10, color=GREY)

    head = [
        "Seçim",
        "Kayıtlı seçmen",
        "Oy kullanan",
        "Geçerli oy",
        "Geçersiz oy",
        "Toplam nüfus",
        "20+ nüfus",
        "Kayıtlı / 20+",
        "Kayıtlı / toplam",
        "Oy kullanan / 20+",
        "Katılım",
        "Geçersiz oranı",
        "Nüfus kaynağı",
    ]
    for c, text in enumerate(head, start=1):
        style(ws.cell(5, c, text), header=True)
    r = 6
    for i, row in enumerate(rows):
        fill = ORANGE if row["source"].startswith("ara") else None
        values = [
            row["label"],
            row["registered"],
            row["voted"],
            row["valid"],
            f"=C{r}-D{r}",
            row["total"],
            row["over20"],
            f"=B{r}/G{r}",
            f"=B{r}/F{r}",
            f"=C{r}/G{r}",
            f"=C{r}/B{r}",
            f"=E{r}/C{r}",
            row["source"],
        ]
        fmts = [None] + ["#,##0"] * 6 + ["0.0%"] * 5 + [None]
        for c, (v, f) in enumerate(zip(values, fmts), start=1):
            style(
                ws.cell(r, c, v),
                zebra=i % 2 == 1,
                fmt=f,
                bold=(c == 1),
                align=LEFT if c == 20 else CENTER,
                fill=fill,
            )
        r += 1

    r += 1
    notes = [
        "Geçersiz oy = oy kullanan − geçerli. Katılım = oy kullanan / kayıtlı.",
        (
            "Beklenen seçmen = seçmen yaşı nüfus − yabancı 18+ (ADNKS yabancı nüfusu 2008+, 18+ payı Türkiye geneli "
            "yaş grubu tablosundan, %83,8). 2008 öncesi yabancı düşülmez. Beklenen − kayıtlı: er/erbaş, hükümlü, "
            "kütük gecikmesi ve yurt dışına gidip kütükten düşmeyenler; eksi değer = kütük şişkin."
        ),
        (
            "Oy hakkı yaşı 1961–1983'te 21, 1987–1991'de 20, 1995'ten beri 18; seçmen yaşı nüfus o seçimin yaşına göre. "
            "2007+ tek yaş (ADNKS); 2000 ve öncesi 5'lik yaş bandı, 18 ve 21 kesimi bant içinde eşit dağılım varsayımıyla."
        ),
        (
            "2007 öncesi seçmen kütüğü ayrı yazımla tutuluyordu; 2007'den itibaren adres kayıt sisteminden (ADNKS) "
            "türetiliyor. İki dönemin oranı aynı şeyi ölçmez."
        ),
        (
            "Kayıtlı seçmen yurt içi sandıklar. Yurt dışı + gümrük seçmeni (2014'ten beri) ayrı sütunda, YSK; "
            "ADNKS nüfusunda olmadıkları için beklenen seçmenle karşılaştırılmaz. Yalnız doğrulanan yıl yazıldı."
        ),
        "Sayım nüfusu Ekim ayı (seçim yılıyla çakışan 1965: sayım 24 Ekim, seçim 10 Ekim); ADNKS 31 Aralık.",
        (
            "Kaynak: TÜİK Seçim Sonuçları Veri Tabanı (biruni.tuik.gov.tr/secimdagitimapp); "
            "TÜİK Nüfus İstatistikleri Portalı, Yaş grubuna göre nüfus 1935–2025."
        ),
    ]
    for text in notes:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=20)
        cell = ws.cell(r, 1, text)
        cell.font = Font(size=9, color=GREY)
        cell.alignment = LEFT
        ws.row_dimensions[r].height = 26
        r += 1

    for i, w in enumerate(
        [14, 14, 13, 13, 12, 14, 8, 14, 12, 11, 12, 10, 10, 12, 12, 14, 14, 11, 13, 22],
        start=1,
    ):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B6"
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 130
    wb.save(path)


def print_table(rows):
    print(
        f"{'Seçim':<13}{'Kayıtlı':>12}{'Oy kul.':>12}{'Geçerli':>12}{'Toplam nüf.':>13}"
        f"{'Yaş':>5}{'Seçmen yaşı':>13}{'Kay/sy':>8}{'Yab.18+':>11}{'Beklenen':>13}{'Bek-kay':>12}{'Fark%':>7}  Kaynak"
    )
    for r in rows:
        exp = r["over20"] - (r["foreign_adult"] or 0)
        print(
            f"{r['label']:<13}{r['registered']:>12,}{r['voted']:>12,}{r['valid']:>12,}"
            f"{r['total']:>13,}{r['voting_age']:>4}+{r['over20']:>13,}"
            f"{r['registered'] / r['over20']:>8.1%}{(r['foreign_adult'] or 0):>11,}{exp:>13,}{exp - r['registered']:>12,}"
            f"{(exp - r['registered']) / exp:>7.1%}  {r['source']}"
        )


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    rows = build_rows(
        load_elections(), load_population(), load_single_age(), load_foreign()
    )
    if len(rows) != 17:
        raise SystemExit(f"expected 17 elections, got {len(rows)}")
    print_table(rows)
    write_workbook(rows, out)
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
