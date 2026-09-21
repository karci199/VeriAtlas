"""İl bazında emekli sayısı (malullük+yaşlılık aylığı alan) ve aktif/pasif oranı — 2025.

SGK İstatistik Yıllığı 2025, Bölüm 2 (Aylık ve Gelir Alan İstatistikleri):
* Tablo 2.5 — 4/1-a aylık alanlar, il ve cinsiyete göre
* Tablo 2.19 — 4/1-b aylık alanlar, il ve cinsiyete göre (tarım hariç + tarım ayrı,
  toplanıyor)
* Tablo 2.32 — 4/1-c aylık alanlar, il ve cinsiyete göre

Emekli sayısı = malullük + yaşlılık aylığı alanların toplamı (kendi adına aylık).
**Ölüm aylığı (dul/yetim) dahil değil** — bu, sigortalının kendisi değil geride
kalanlara ödenen bir aylık, "emekli" kavramına girmiyor.

Aktif/pasif oranı = aktif sigortalı (Tablo 1.7) / emekli sayısı. SGK'nın kendi ulusal
göstergesi bu oranın il kırılımı — kaç çalışanın kaç emekliyi "taşıdığı".

Run:  uv run python scripts/build_sgk_emekli_excel.py
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
TARGET = PUBLIC.parent / "cikti" / "analiz-sgk-emekli-aktif-pasif-il-2025.xlsx"


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
        emekli = (row[4] or 0) + (row[7] or 0)  # malullük toplam + yaşlılık toplam
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


def main() -> None:
    active = read_active()
    pensioners = read_pensioners()

    rows = []
    for plate, data in pensioners.items():
        if "il" not in data:
            continue
        emekli = data.get("emekli_a", 0) + data.get("emekli_b", 0) + data.get("emekli_c", 0)
        aktif = active.get(plate, 0)
        rows.append(
            {
                "il": data["il"],
                "plaka": plate,
                "aktif": aktif,
                "emekli": emekli,
                "aktif_pasif": aktif / emekli if emekli else None,
            }
        )
    frame = pl.DataFrame(rows)
    if len(frame) != 81:
        print(f"uyari: 81 il beklenirken {len(frame)} satir okundu")

    by_ratio = ranked(frame.select("il", "plaka", "aktif", "emekli", "aktif_pasif"), "aktif_pasif")
    by_emekli = ranked(frame.select("il", "plaka", "emekli", "aktif", "aktif_pasif"), "emekli")

    tr_aktif = frame["aktif"].sum()
    tr_emekli = frame["emekli"].sum()
    tr = pl.DataFrame(
        [{"aktif": tr_aktif, "emekli": tr_emekli, "aktif_pasif": tr_aktif / tr_emekli}]
    )

    # region Yazma
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))
    style = styles(book)
    left = book.add_format({"align": "left", "valign": "vcenter", "indent": 1})
    ratio_fmt = book.add_format({"num_format": "0.00", "align": "center", "valign": "vcenter"})

    headers = {
        "il": "İl", "plaka": "Plaka", "sira": "Sıra",
        "aktif": "Aktif sigortalı", "emekli": "Emekli sayısı (malullük+yaşlılık)",
        "aktif_pasif": "Aktif/Pasif oranı",
    }
    formats = {
        "il": left, "plaka": style["text"], "sira": style["text"],
        "aktif": style["count"], "emekli": style["count"],
        "aktif_pasif": ratio_fmt,
    }
    widths = {"il": 22, "plaka": 8, "sira": 7, "emekli": 20}

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

    write_sheet("Aktif-Pasif oranı", by_ratio)
    write_sheet("Emekli sayısı", by_emekli)
    write_sheet("Türkiye", tr)

    notes_sheet(
        book,
        [
            "İl bazında emekli sayısı ve aktif/pasif oranı — 2025",
            "",
            "Emekli sayısı = malullük + yaşlılık aylığı alanların toplamı (4/1-a +",
            "4/1-b + 4/1-c). Ölüm aylığı (dul/yetim) DAHİL DEĞİL — bu sigortalının",
            "kendisine değil geride kalanlara ödeniyor, 'emekli' değil.",
            "",
            "Aktif/pasif oranı = aktif sigortalı (Tablo 1.7 toplamı) / emekli sayısı.",
            "SGK'nın kendi ulusal göstergesinin (Tablo 1.5) il kırılımı — bir emekliyi",
            "kaç aktif sigortalının 'taşıdığı'.",
            "",
            "'Emekli sayısı' burada o ildeki SGK il müdürlüğüne kayıtlı emekliyi",
            "gösterir — emeklinin fiilen o ilde yaşayıp yaşamadığı ayrı bir soru,",
            "büyükşehirlere emeklilikte geri dönüş (örn. sahil illeri) burada",
            "görünmeyebilir çünkü kayıt yeri değişmemiş olabilir.",
            "",
            "KAYNAK",
            "SGK İstatistik Yıllığı 2025, Tablo 2.5, 2.19, 2.32 ve 1.7",
            "(sgk.gov.tr/Istatistik/Yillik).",
        ],
    )
    book.close()
    # endregion

    print("yazildi:", TARGET)


if __name__ == "__main__":
    main()
