"""Kaba nüfus vs 18+ nüfus paydası — sıra karşılaştırması, 2025.

Aynı (sigortalı+emekli) toplamı iki farklı paydaya bölündüğünde il sırası nasıl
değişiyor. build_sgk_sigortali_emekli_nufus_excel.py (kaba nüfus) ile
build_sgk_sigortali_emekli_nufus18_excel.py (18+ nüfus) sonuçlarını birleştiriyor.

Run:  uv run python scripts/build_sgk_nufus_karsilastirma_excel.py
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
TARGET = PUBLIC.parent / "cikti" / "analiz-sgk-nufus-paydasi-karsilastirma-il-2025.xlsx"


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


def read_population(year: int) -> dict[int, float]:
    out: dict[int, float] = {}
    with gzip.open(PUBLIC / "population.csv.gz", "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["level"] != "province" or int(row["year"]) != year:
                continue
            plate = int(row["area_id"].split("-")[1])
            out[plate] = out.get(plate, 0.0) + float(row["value"])
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
    nufus = read_population(2025)
    nufus18 = read_population_18plus(2025)

    rows = []
    for plate, data in pensioners.items():
        if "il" not in data:
            continue
        emekli = data.get("emekli_a", 0) + data.get("emekli_b", 0) + data.get("emekli_c", 0)
        sigortali = active.get(plate, 0)
        toplam = sigortali + emekli
        n = nufus.get(plate, 0)
        n18 = nufus18.get(plate, 0)
        rows.append(
            {
                "il": data["il"],
                "plaka": plate,
                "cocuk_orani": (n - n18) / n if n else None,
                "oran_kaba": toplam / n if n else None,
                "oran_18": toplam / n18 if n18 else None,
            }
        )
    frame = pl.DataFrame(rows)
    if len(frame) != 81:
        print(f"uyari: 81 il beklenirken {len(frame)} satir okundu")

    sira_kaba = (
        frame.sort("oran_kaba", descending=True)
        .with_row_index("sira_kaba_0")
        .with_columns((pl.col("sira_kaba_0").cast(pl.Int64) + 1).alias("sira_kaba"))
        .drop("sira_kaba_0")
    )
    sira_both = (
        sira_kaba.sort("oran_18", descending=True)
        .with_row_index("sira_18_0")
        .with_columns((pl.col("sira_18_0").cast(pl.Int64) + 1).alias("sira_18"))
        .drop("sira_18_0")
        .with_columns((pl.col("sira_kaba") - pl.col("sira_18")).alias("sira_farki"))
    )

    result = ranked(
        sira_both.select(
            "il", "plaka", "cocuk_orani", "oran_kaba", "sira_kaba",
            "oran_18", "sira_18", "sira_farki",
        ),
        "sira_farki",
    )

    # region Yazma
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))
    style = styles(book)
    left = book.add_format({"align": "left", "valign": "vcenter", "indent": 1})

    headers = {
        "il": "İl", "plaka": "Plaka", "sira": "Sıra (fark)",
        "cocuk_orani": "18 altı nüfus payı",
        "oran_kaba": "(Sigortalı+Emekli)/Kaba nüfus", "sira_kaba": "Sıra · kaba nüfus",
        "oran_18": "(Sigortalı+Emekli)/Nüfus(18+)", "sira_18": "Sıra · nüfus(18+)",
        "sira_farki": "Sıra farkı (+ = 18+'da düşen, kabada avantajlıydı)",
    }
    percents = ("cocuk_orani", "oran_kaba", "oran_18")
    formats = {
        "il": left, "plaka": style["text"], "sira": style["text"],
        "sira_kaba": style["text"], "sira_18": style["text"], "sira_farki": style["text"],
        **{c: style["percent"] for c in percents},
    }
    widths = {"il": 22, "plaka": 8, "sira": 8, "sira_kaba": 12, "sira_18": 12, "sira_farki": 14}

    page = book.add_worksheet("Sıra karşılaştırması")
    page.freeze_panes(1, 1)
    page.set_row(0, 44)
    columns = result.columns
    for index, column in enumerate(columns):
        page.set_column(index, index, widths.get(column, 16), formats.get(column, style["text"]))
    rows_ = [list(r) for r in result.rows()]
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

    notes_sheet(
        book,
        [
            "Kaba nüfus vs 18+ nüfus paydası — sıra karşılaştırması, 2025",
            "",
            "Aynı pay ((Sigortalı+Emekli) toplamı) iki farklı paydaya bölündüğünde",
            "il sırası nasıl değişiyor. '18 altı nüfus payı' sütunu ilin çocuk",
            "nüfus ağırlığını gösteriyor — bu ağırlık yüksekse kaba nüfus paydası",
            "o ili yapay olarak geride bırakır, 18+'a geçince sıra düzelir (yükselir).",
            "",
            "Sıra farkı = kaba nüfustaki sıra − 18+ nüfustaki sıra. Pozitifse il",
            "18+ paydasında YÜKSELDİ (kaba nüfus onu haksız yere geride",
            "bırakıyordu); negatifse DÜŞTÜ (kaba nüfus ona haksız avantaj",
            "sağlıyordu — düşük çocuk payı sayesinde).",
            "",
            "KAYNAK",
            "SGK İstatistik Yıllığı 2025 (sigortalı+emekli) + population.csv.gz ve",
            "population-age1.csv.gz (nüfus, TÜİK ADNKS).",
        ],
    )
    book.close()
    # endregion

    print("yazildi:", TARGET)


if __name__ == "__main__":
    main()
