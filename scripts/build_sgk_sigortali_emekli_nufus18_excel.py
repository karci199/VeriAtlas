"""İl bazında sigortalı/nüfus, emekli/nüfus, toplamı/nüfus — 18+ nüfusa göre, 2025.

Aynı önceki hesap (build_sgk_sigortali_emekli_nufus_excel.py) ama payda toplam nüfus
değil **18 yaş ve üzeri nüfus**: çocuklar sigortalı ya da emekli olamayacağı için
paydaya girmemeli, tek yaş nüfus dosyası (population-age1.csv.gz) bunu tam sınırında
kesmeye izin veriyor — 5'lik yaş bandı (15-19) 18'i ortadan keserdi.

Run:  uv run python scripts/build_sgk_sigortali_emekli_nufus18_excel.py
"""

from __future__ import annotations

import csv
import gzip
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
TARGET = PUBLIC.parent / "cikti" / "analiz-sgk-sigortali-emekli-nufus18-il-2025.xlsx"


def read_active() -> dict[int, float]:
    path = next(SGK2025.glob("*Sigortalı ve İş Yeri*.xlsx"))
    wb = openpyxl.load_workbook(str(path), data_only=True)
    ws = wb["TABLO-1.7"]
    out = {}
    for row in ws.iter_rows(min_row=9, max_row=100, values_only=True):
        code, il, total = row[0], row[1], row[20]
        try:
            plate = int(code)
        except (TypeError, ValueError):
            continue
        if not il or total is None:
            continue
        out[plate] = float(total)
    return out


def read_pensioners() -> dict[int, dict[str, float]]:
    path = SGK2025 / "YILLIK BÖLÜM 2 Aylık ve Gelir Alan İstatistikleri _2025.xlsx"
    wb = openpyxl.load_workbook(str(path), data_only=True)
    out: dict[int, dict[str, float]] = {}

    ws_a = wb["TABLO- 2.5"]
    for row in ws_a.iter_rows(min_row=8, max_row=95, values_only=True):
        code, il = row[0], row[1]
        try:
            plate = int(code)
        except (TypeError, ValueError):
            continue
        if not il:
            continue
        emekli = (row[4] or 0) + (row[7] or 0)
        out.setdefault(plate, {}).update({"il": str(il).strip(), "emekli_a": emekli})

    ws_b = wb["TABLO- 2.19"]
    for row in ws_b.iter_rows(min_row=9, max_row=95, values_only=True):
        code, il = row[0], row[1]
        try:
            plate = int(code)
        except (TypeError, ValueError):
            continue
        if not il:
            continue
        emekli = (row[4] or 0) + (row[7] or 0) + (row[18] or 0) + (row[21] or 0)
        out.setdefault(plate, {}).update({"emekli_b": emekli})

    ws_c = wb["TABLO-2.32"]
    for row in ws_c.iter_rows(min_row=8, max_row=95, values_only=True):
        code, il = row[0], row[1]
        try:
            plate = int(code)
        except (TypeError, ValueError):
            continue
        if not il:
            continue
        emekli = (row[4] or 0) + (row[7] or 0) + (row[10] or 0)
        out.setdefault(plate, {}).update({"emekli_c": emekli})

    return out


def read_population_18plus(year: int) -> dict[int, float]:
    out: dict[int, float] = {}
    with gzip.open(PUBLIC / "population-age1.csv.gz", "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["level"] != "province" or int(row["year"]) != year:
                continue
            age = row["age"]
            is_adult = age == "75+" or (age.isdigit() and int(age) >= 18)
            if not is_adult:
                continue
            plate = int(row["area_id"].split("-")[1])
            out[plate] = out.get(plate, 0.0) + float(row["value"])
    return out


def main() -> None:
    active = read_active()
    pensioners = read_pensioners()
    population = read_population_18plus(2025)

    rows = []
    for plate, data in pensioners.items():
        if "il" not in data:
            continue
        emekli = data.get("emekli_a", 0) + data.get("emekli_b", 0) + data.get("emekli_c", 0)
        sigortali = active.get(plate, 0)
        nufus18 = population.get(plate, 0)
        rows.append(
            {
                "il": data["il"],
                "plaka": plate,
                "sigortali": sigortali,
                "emekli": emekli,
                "nufus18": nufus18,
                "sigortali_nufus": sigortali / nufus18 if nufus18 else None,
                "emekli_nufus": emekli / nufus18 if nufus18 else None,
                "toplam_nufus": (sigortali + emekli) / nufus18 if nufus18 else None,
            }
        )
    frame = pl.DataFrame(rows)
    if len(frame) != 81:
        print(f"uyari: 81 il beklenirken {len(frame)} satir okundu")

    ranked_frame = ranked(
        frame.select(
            "il", "plaka", "sigortali", "emekli", "nufus18",
            "sigortali_nufus", "emekli_nufus", "toplam_nufus",
        ),
        "toplam_nufus",
    )

    tr_s, tr_e, tr_n = frame["sigortali"].sum(), frame["emekli"].sum(), frame["nufus18"].sum()
    tr = pl.DataFrame([{
        "sigortali": tr_s, "emekli": tr_e, "nufus18": tr_n,
        "sigortali_nufus": tr_s / tr_n, "emekli_nufus": tr_e / tr_n, "toplam_nufus": (tr_s + tr_e) / tr_n,
    }])

    # region Yazma
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))
    style = styles(book)
    left = book.add_format({"align": "left", "valign": "vcenter", "indent": 1})

    headers = {
        "il": "İl", "plaka": "Plaka", "sira": "Sıra",
        "sigortali": "Aktif sigortalı", "emekli": "Emekli sayısı", "nufus18": "Nüfus (18+)",
        "sigortali_nufus": "Sigortalı / Nüfus(18+)", "emekli_nufus": "Emekli / Nüfus(18+)",
        "toplam_nufus": "(Sigortalı + Emekli) / Nüfus(18+)",
    }
    counts = ("sigortali", "emekli", "nufus18")
    percents = ("sigortali_nufus", "emekli_nufus", "toplam_nufus")
    formats = {
        "il": left, "plaka": style["text"], "sira": style["text"],
        **{c: style["count"] for c in counts},
        **{c: style["percent"] for c in percents},
    }
    widths = {"il": 22, "plaka": 8, "sira": 7, "sigortali": 16, "emekli": 16, "nufus18": 14}

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

    write_sheet("İller", ranked_frame)
    write_sheet("Türkiye", tr)

    notes_sheet(
        book,
        [
            "İl bazında sigortalı/nüfus(18+), emekli/nüfus(18+) ve toplamı — 2025",
            "",
            "Sigortalı = aktif sigortalı, 4/1-a+4/1-b+4/1-c toplamı (Tablo 1.7).",
            "Emekli = malullük+yaşlılık aylığı alanlar, ölüm aylığı hariç",
            "(Tablo 2.5+2.19+2.32). Nüfus(18+) = TÜİK ADNKS tek yaş nüfus dosyasından",
            "18 ve üzeri toplamı, 2025 — çocuk nüfus paydadan çıkarıldı çünkü zaten",
            "sigortalı ya da emekli olamaz.",
            "",
            "Toplam sütunu nüfusun (18+) ne kadarının SGK sistemiyle bağlantılı",
            "olduğunu gösteriyor — geri kalan pay öğrenci, ev hanımı, işsiz ve",
            "bakmakla yükümlü olunan yetişkinler.",
            "",
            "KAYNAK",
            "SGK İstatistik Yıllığı 2025, Tablo 1.7, 2.5, 2.19, 2.32 +",
            "population-age1.csv.gz (TÜİK ADNKS, tek yaş).",
        ],
    )
    book.close()
    # endregion

    print("yazildi:", TARGET)


if __name__ == "__main__":
    main()
