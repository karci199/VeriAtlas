"""İllere göre 4/1-a sektörel yapı (tarım/sanayi/inşaat/hizmet) — 2025.

SGK İstatistik Yıllığı 2025, Tablo 1.11: "4/1-a Kapsamındaki İş Yerleri ile Zorunlu
Sigortalıların Faaliyet Grubu ve İle Göre Dağılımı" — NACE Rev.2.1 iki haneli faaliyet
kodu (91 satır) × il (işyeri + sigortalı, iki sütun) tam çapraz tablo. Tek yıl, yalnız
4/1-a (özel/kamu işçi statüsü — esnaf/çiftçi 4/1-b'de, memur 4/1-c'de, burada yok).

91 NACE kodu okunması güç; dört kaba makro sektöre toplanıyor (TÜİK'in kendi üç-sektör
ayrımına inşaat eklenmiş hali):

* Tarım — 01-03 (bitkisel/hayvansal üretim, ormancılık, balıkçılık)
* Sanayi — 05-39 (madencilik, imalat, enerji, su/atık) — 01-03 ile 41-43 arası
* İnşaat — 41-43
* Hizmet — 45 ve üzeri (ticaret, ulaştırım, konaklama, bilgi, finans, kamu, eğitim,
  sağlık, diğer) — kalan her şey

Run:  uv run python scripts/build_sgk_sector_excel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import polars as pl
import xlsxwriter

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from build_analysis_books import notes_sheet, ranked, styles

from veriatlas.config import PUBLIC

SCRATCH = Path(
    r"C:\Users\katan\AppData\Local\Temp\claude\C--veri--claude-worktrees-nerede-kaldik-4998d7"
    r"\289f51e5-ac10-4275-b09d-211258ba36af\scratchpad"
)
TARGET = PUBLIC.parent / "cikti" / "analiz-sgk-sektorel-yapi-il-2025.xlsx"


def macro(code: str) -> str | None:
    try:
        n = int(code)
    except ValueError:
        return None
    if 1 <= n <= 3:
        return "tarim"
    if 5 <= n <= 39:
        return "sanayi"
    if 41 <= n <= 43:
        return "insaat"
    if n >= 45:
        return "hizmet"
    return None


def main() -> None:
    path = next((SCRATCH / "sgk2025").glob("*.xlsx"))
    wb = openpyxl.load_workbook(str(path), data_only=True)
    ws = wb["TABLO-1.11"]

    # İl adları ve (işyeri, sigortalı) sütun çiftleri, satır 5'ten okunuyor —
    # her il iki sütun kaplıyor, ad yalnız ilk sütunda yazılı (birleştirilmiş hücre).
    provinces: list[tuple[str, int, int]] = []
    last_name = None
    for col in range(3, ws.max_column + 1):
        name = ws.cell(row=6, column=col).value
        if name and str(name).strip():
            last_name = str(name).strip()
        header2 = ws.cell(row=7, column=col).value or ""
        if last_name and "İş yeri" in str(header2):
            provinces.append((last_name, col, col + 1))

    sigortali = {p[0]: {"tarim": 0.0, "sanayi": 0.0, "insaat": 0.0, "hizmet": 0.0} for p in provinces}
    isyeri = {p[0]: {"tarim": 0.0, "sanayi": 0.0, "insaat": 0.0, "hizmet": 0.0} for p in provinces}

    for row in range(9, ws.max_row + 1):
        code = ws.cell(row=row, column=1).value
        sector = macro(str(code).strip()) if code else None
        if not sector:
            continue
        for il, col_w, col_s in provinces:
            w = ws.cell(row=row, column=col_w).value or 0
            s = ws.cell(row=row, column=col_s).value or 0
            isyeri[il][sector] += float(w)
            sigortali[il][sector] += float(s)

    rows = []
    for il in sigortali:
        if "Genel toplam" in il or "General Total" in il:
            continue
        s = sigortali[il]
        total = sum(s.values())
        if total == 0:
            continue
        rows.append(
            {
                "il": il,
                "sigortali_tarim": s["tarim"],
                "sigortali_sanayi": s["sanayi"],
                "sigortali_insaat": s["insaat"],
                "sigortali_hizmet": s["hizmet"],
                "sigortali_toplam": total,
                "pay_tarim": s["tarim"] / total,
                "pay_sanayi": s["sanayi"] / total,
                "pay_insaat": s["insaat"] / total,
                "pay_hizmet": s["hizmet"] / total,
            }
        )
    frame = pl.DataFrame(rows)
    if len(frame) != 81:
        print(f"uyari: 81 il beklenirken {len(frame)} satir okundu")

    by_sanayi = ranked(
        frame.select("il", "pay_tarim", "pay_sanayi", "pay_insaat", "pay_hizmet", "sigortali_toplam"),
        "pay_sanayi",
    )
    by_tarim = ranked(
        frame.select("il", "pay_tarim", "pay_sanayi", "pay_insaat", "pay_hizmet", "sigortali_toplam"),
        "pay_tarim",
    )
    by_insaat = ranked(
        frame.select("il", "pay_tarim", "pay_sanayi", "pay_insaat", "pay_hizmet", "sigortali_toplam"),
        "pay_insaat",
    )

    tr_total = frame.select(pl.col("sigortali_tarim").sum(), pl.col("sigortali_sanayi").sum(),
                             pl.col("sigortali_insaat").sum(), pl.col("sigortali_hizmet").sum(),
                             pl.col("sigortali_toplam").sum()).to_dicts()[0]
    tr = pl.DataFrame([{
        "sektor": "Tarım", "sigortali": tr_total["sigortali_tarim"],
        "pay": tr_total["sigortali_tarim"] / tr_total["sigortali_toplam"],
    }, {
        "sektor": "Sanayi", "sigortali": tr_total["sigortali_sanayi"],
        "pay": tr_total["sigortali_sanayi"] / tr_total["sigortali_toplam"],
    }, {
        "sektor": "İnşaat", "sigortali": tr_total["sigortali_insaat"],
        "pay": tr_total["sigortali_insaat"] / tr_total["sigortali_toplam"],
    }, {
        "sektor": "Hizmet", "sigortali": tr_total["sigortali_hizmet"],
        "pay": tr_total["sigortali_hizmet"] / tr_total["sigortali_toplam"],
    }])

    # region Yazma
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))
    style = styles(book)
    left = book.add_format({"align": "left", "valign": "vcenter", "indent": 1})

    headers = {
        "il": "İl", "sira": "Sıra", "sektor": "Sektör",
        "sigortali_toplam": "Toplam sigortalı (4/1-a)", "sigortali": "Sigortalı",
        "pay": "Türkiye payı",
        "pay_tarim": "Tarım payı", "pay_sanayi": "Sanayi payı",
        "pay_insaat": "İnşaat payı", "pay_hizmet": "Hizmet payı",
    }
    shares = ("pay_tarim", "pay_sanayi", "pay_insaat", "pay_hizmet", "pay")
    formats = {
        "il": left, "sira": style["text"], "sektor": left,
        **{c: style["percent"] for c in shares},
        "sigortali_toplam": style["count"], "sigortali": style["count"],
    }
    widths = {"il": 22, "sira": 7, "sektor": 14, "sigortali_toplam": 18}

    def write_sheet(name: str, data: pl.DataFrame) -> None:
        page = book.add_worksheet(name)
        page.freeze_panes(1, 1)
        page.set_row(0, 40)
        columns = data.columns
        for index, column in enumerate(columns):
            page.set_column(index, index, widths.get(column, 15), formats.get(column, style["text"]))
        rows_ = [list(r) for r in data.rows()]
        page.add_table(
            0, 0, max(len(rows_), 1), len(columns) - 1,
            {
                "data": rows_,
                "columns": [
                    {"header": headers.get(c, c), "header_format": style["head"], "format": formats.get(c, style["text"])}
                    for c in columns
                ],
                "banded_rows": True,
            },
        )

    write_sheet("Sanayi payına göre", by_sanayi)
    write_sheet("Tarım payına göre", by_tarim)
    write_sheet("İnşaat payına göre", by_insaat)
    write_sheet("Türkiye", tr)

    notes_sheet(
        book,
        [
            "İllere göre 4/1-a sektörel yapı (tarım/sanayi/inşaat/hizmet) — 2025",
            "",
            "Yalnız 4/1-a (işçi statüsü) kapsıyor — esnaf/çiftçi (4/1-b) ve memur",
            "(4/1-c) bu tabloda yok, o yüzden 'tarım payı' burada SGK'nın tarım işçisi",
            "(ırgat, mevsimlik vb.) kaydını gösteriyor, çiftçinin kendisini değil.",
            "",
            "91 NACE Rev.2.1 iki haneli kod dört kaba makro sektöre toplandı:",
            "· Tarım — 01-03",
            "· Sanayi — 05-39 (madencilik, imalat, enerji, su/atık)",
            "· İnşaat — 41-43",
            "· Hizmet — 45 ve üzeri (ticaret, ulaştırım, konaklama, bilgi, finans,",
            "  kamu, eğitim, sağlık, diğer hizmetler)",
            "",
            "KAYNAK",
            "SGK İstatistik Yıllığı 2025, Tablo 1.11 (sgk.gov.tr/Istatistik/Yillik).",
            "",
            "NOT",
            "SGK'nın istatistik yıllıkları 2007'ye, il/sektör detayı olmadan başka",
            "tablolarla daha geriye gidiyor ama format yıldan yıla değişiyor ve",
            "birleştirmek elle doğrulama gerektiriyor — şimdilik tek yıl (2025) alındı.",
        ],
    )
    book.close()
    # endregion

    print("yazildi:", TARGET)


if __name__ == "__main__":
    main()
