"""İl bazında iş kazası oranı (4/1-a) — 2025.

SGK İstatistik Yıllığı 2025, Bölüm 3-1 (İş Kazası ve Meslek Hastalığı İstatistikleri,
4/1-a): Tablo 3.1.4 (iş kazası geçiren sigortalı sayısı, il+cinsiyet) ve Tablo 3.1.5
(iş kazası/meslek hastalığı sonucu ölen, il+cinsiyet). Yalnız 4/1-a — esnaf/çiftçi
(4/1-b) ve memur (4/1-c) ayrı yayımlanıyor ama bu depoda henüz çekilmedi.

Oran = kaza/ölüm sayısı / 4/1-a aktif sigortalı sayısı (Tablo 1.7), binde ve yüz
binde. Ham sayı değil oran kullanmak şart — büyük ilin kaza sayısı da büyük olur,
soru "işçi başına ne kadar riskli" olmalı.

Run:  uv run python scripts/build_sgk_iskazasi_excel.py
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
SGK2025 = SCRATCH / "sgk2025"
TARGET = PUBLIC.parent / "cikti" / "analiz-sgk-is-kazasi-il-2025.xlsx"


def read_active_4a() -> dict[int, float]:
    path = next(SGK2025.glob("*Sigortalı ve İş Yeri*.xlsx"))
    wb = openpyxl.load_workbook(str(path), data_only=True)
    ws = wb["TABLO-1.7"]
    out = {}
    for row in ws.iter_rows(min_row=9, max_row=100, values_only=True):
        code, il, a_toplam = row[0], row[1], row[2]
        try:
            plate = int(code)
        except (TypeError, ValueError):
            continue
        if not il or a_toplam is None:
            continue
        out[plate] = float(a_toplam)
    return out


def read_kaza() -> dict[int, dict[str, float]]:
    path = SGK2025 / "YILLIK BÖLÜM 3-1 İş Kazası ve Meslek Hastalığı İstatistikleri -(4a)-2025.xlsx"
    wb = openpyxl.load_workbook(str(path), data_only=True)
    out: dict[int, dict[str, float]] = {}

    ws4 = wb["Tablo 3.1.4 (4a)"]
    for row in ws4.iter_rows(min_row=7, max_row=95, values_only=True):
        code, il = row[0], row[1]
        try:
            plate = int(code)
        except (TypeError, ValueError):
            continue
        if not il:
            continue
        out.setdefault(plate, {}).update(
            {"il": str(il).strip(), "kaza": row[16] or 0, "meslek_hastaligi": (row[17] or 0) + (row[18] or 0)}
        )

    ws5 = wb["Tablo 3.1.5 (4a)"]
    for row in ws5.iter_rows(min_row=6, max_row=95, values_only=True):
        code, il = row[0], row[1]
        try:
            plate = int(code)
        except (TypeError, ValueError):
            continue
        if not il:
            continue
        olum = (row[4] or 0) + (row[7] or 0)
        out.setdefault(plate, {}).update({"olum": olum})

    return out


def main() -> None:
    active = read_active_4a()
    kaza = read_kaza()

    rows = []
    for plate, data in kaza.items():
        if "il" not in data:
            continue
        sigortali = active.get(plate, 0)
        rows.append(
            {
                "il": data["il"],
                "plaka": plate,
                "sigortali_4a": sigortali,
                "kaza": data.get("kaza", 0),
                "olum": data.get("olum", 0),
                "kaza_binde": 1000 * data.get("kaza", 0) / sigortali if sigortali else None,
                "olum_yuzbinde": 100_000 * data.get("olum", 0) / sigortali if sigortali else None,
            }
        )
    frame = pl.DataFrame(rows)
    if len(frame) != 81:
        print(f"uyari: 81 il beklenirken {len(frame)} satir okundu")

    by_kaza = ranked(
        frame.select("il", "plaka", "sigortali_4a", "kaza", "kaza_binde"), "kaza_binde"
    )
    by_olum = ranked(
        frame.select("il", "plaka", "sigortali_4a", "olum", "olum_yuzbinde"), "olum_yuzbinde"
    )

    tr_sigortali = frame["sigortali_4a"].sum()
    tr_kaza = frame["kaza"].sum()
    tr_olum = frame["olum"].sum()
    tr = pl.DataFrame([{
        "sigortali_4a": tr_sigortali, "kaza": tr_kaza, "olum": tr_olum,
        "kaza_binde": 1000 * tr_kaza / tr_sigortali, "olum_yuzbinde": 100_000 * tr_olum / tr_sigortali,
    }])

    # region Yazma
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))
    style = styles(book)
    left = book.add_format({"align": "left", "valign": "vcenter", "indent": 1})
    rate_fmt = book.add_format({"num_format": "0.00", "align": "center", "valign": "vcenter"})

    headers = {
        "il": "İl", "plaka": "Plaka", "sira": "Sıra",
        "sigortali_4a": "4/1-a aktif sigortalı", "kaza": "İş kazası geçiren",
        "olum": "İş kazası/meslek hastalığı sonucu ölen",
        "kaza_binde": "İş kazası ‰ (binde)", "olum_yuzbinde": "Ölüm 100 binde",
    }
    counts = ("sigortali_4a", "kaza", "olum")
    formats = {
        "il": left, "plaka": style["text"], "sira": style["text"],
        **{c: style["count"] for c in counts},
        "kaza_binde": rate_fmt, "olum_yuzbinde": rate_fmt,
    }
    widths = {"il": 22, "plaka": 8, "sira": 7, "sigortali_4a": 18}

    def write_sheet(name: str, data: pl.DataFrame) -> None:
        page = book.add_worksheet(name)
        page.freeze_panes(1, 1)
        page.set_row(0, 40)
        columns = data.columns
        for index, column in enumerate(columns):
            page.set_column(index, index, widths.get(column, 16), formats.get(column, style["text"]))
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

    write_sheet("İş kazası oranı", by_kaza)
    write_sheet("Ölüm oranı", by_olum)
    write_sheet("Türkiye", tr)

    notes_sheet(
        book,
        [
            "İl bazında iş kazası oranı (4/1-a) — 2025",
            "",
            "Yalnız 4/1-a (işçi statüsü) — esnaf/çiftçi (4/1-b) ve memur (4/1-c) için",
            "ayrı iş kazası tabloları var ama bu depoda henüz çekilmedi.",
            "",
            "İş kazası ‰ = iş kazası geçiren sigortalı sayısı / 4/1-a aktif sigortalı,",
            "binde. Ölüm 100 binde = iş kazası + meslek hastalığı sonucu ölen /",
            "4/1-a aktif sigortalı, yüz binde — standart iş güvenliği göstergesi bu",
            "ölçekte ifade edilir.",
            "",
            "Meslek hastalığı ayrı bir sütunda tutulmadı (ölüm oranına dahil ama",
            "kaza oranına dahil değil) — meslek hastalığı vakası çok az (Türkiye",
            "genelinde binlerce iş kazasına karşı yüzlerce vaka), oranı bozmadan",
            "ölüm tarafında toplandı.",
            "",
            "KAYNAK",
            "SGK İstatistik Yıllığı 2025, Tablo 3.1.4, 3.1.5 (Bölüm 3-1, 4/1-a) +",
            "Tablo 1.7 (sgk.gov.tr/Istatistik/Yillik).",
        ],
    )
    book.close()
    # endregion

    print("yazildi:", TARGET)


if __name__ == "__main__":
    main()
