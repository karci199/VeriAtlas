"""İllere göre öğrenci, şube, derslik, okul, öğretmen sayıları ve oranları — 2012-2024.

Kaynak beş ayrı `.xls` pivot dosyası, masaüstünde elle indirilmiş
(`C:\\Users\\katan\\OneDrive\\Desktop\\demografi\\`, MEB istatistik portalından).
Her dosya aynı şekilde kurulu: satırlar eğitim düzeyi × yıl, sütunlar il (plaka
numarasıyla etiketli). Öğrenci ve öğretmen için ayrıca cinsiyet kırılımlı ikizleri
var (`... Cinsiyet.xls`) — burada kullanılmıyor, bu dosya yalnız toplamı okuyor.

Dört eğitim düzeyi toplanıyor: Okul Öncesi, İlkokul, Ortaokul, Ortaöğretim.
"Ortaöğretim" satırı zaten Genel + Mesleki ve Teknik Ortaöğretim toplamı
(doğrulandı: iki alt düzeyin toplamı her il-yılda Ortaöğretim satırına birebir
eşit) — o yüzden alt düzeyler ayrıca toplanmıyor, çift sayım olurdu.

Üç oran hesaplanıyor, üçü de farklı bir şeyi ölçtüğü için birlikte tutuluyor:

* **Öğrenci/Şube** — ortalama sınıf mevcudu, kalabalık göstergesi.
* **Şube/Derslik** — ikili öğretim göstergesi: 1'e yakınsa tekli, yükseldikçe aynı
  derslik günde birden fazla şubeye hizmet ediyor demektir.
* **Öğrenci/Derslik** — fiziksel derslik başına öğrenci; ikili öğretim etkisini de
  içerir, o yüzden Şube/Derslik'ten ayrı okunmalı.

Ayrıca öğretmen/okul ve öğrenci/okul (okul büyüklüğü) sütunları da var.

Run:  uv run python scripts/build_education_excel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import xlrd
import xlsxwriter

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from build_analysis_books import notes_sheet, ranked, styles

from veriatlas.config import PUBLIC

SOURCE = Path(r"C:\Users\katan\OneDrive\Desktop\demografi")
TARGET = PUBLIC.parent / "cikti" / "analiz-egitim-il-yillara-gore.xlsx"

#: Dosya adı → çıktı sütunu. Cinsiyet kırılımlı ikizler bilerek dışarıda.
FILES = {
    "ogrenci": "İllere ve Yıllara Göre Eğitim Düzeyi Öğrenci Sayıları.xls",
    "sube": "İllere ve Yıllara Göre Eğitim Düzeyi Şube Sayıları.xls",
    "derslik": "İllere ve Yıllara Göre Eğitim Düzeyi Derslik Sayıları.xls",
    "okul": "İllere ve Yıllara Göre Eğitim Düzeyi Okul Sayıları.xls",
    "ogretmen": "İllere ve Yıllara Göre Eğitim Düzeyi Öğretmen Sayıları.xls",
}

#: Toplanacak dört düzey. "Ortaöğretim" Genel + Mesleki'yi zaten içeriyor.
LEVELS = {"Okul Öncesi", "İlkokul", "Ortaokul", "Ortaöğretim"}


def read_metric(path: Path) -> dict[tuple[int, int], float]:
    """Bir dosyadan (plaka, yıl) → dört düzeyin toplamı."""
    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_index(0)

    plates = []
    for col in range(3, sheet.ncols):
        label = sheet.cell_value(1, col)
        plates.append(int(label.rsplit("-", 1)[1]) if label else None)

    totals: dict[tuple[int, int], float] = {}
    level = None
    for row in range(4, sheet.nrows):
        cell = sheet.cell_value(row, 1)
        if cell:
            level = cell.strip()
        year_cell = sheet.cell_value(row, 2)
        if level not in LEVELS or not year_cell:
            continue
        year = int(year_cell)
        for col, plate in enumerate(plates, start=3):
            if plate is None:
                continue
            value = sheet.cell_value(row, col)
            if value != "":
                key = (plate, year)
                totals[key] = totals.get(key, 0.0) + float(value)
    return totals


def main() -> None:
    per_metric = {key: read_metric(SOURCE / name) for key, name in FILES.items()}
    years = sorted({year for values in per_metric.values() for _, year in values})
    first, last = years[0], years[-1]

    provinces = (
        pl.read_csv("src/veriatlas/data/areas_tr.csv")
        .filter(
            pl.col("area_id").str.starts_with("TR-")
            & (pl.col("area_id").str.len_chars() == 5)
        )
        .with_columns(pl.col("area_id").str.slice(3).cast(pl.Int64).alias("plaka"))
    )

    rows = []
    for plate, il in provinces.select("plaka", "name_tr").iter_rows():
        for year in years:
            rows.append(
                {
                    "il": il,
                    "plaka": plate,
                    "yil": year,
                    "ogrenci": per_metric["ogrenci"].get((plate, year), 0.0),
                    "sube": per_metric["sube"].get((plate, year), 0.0),
                    "derslik": per_metric["derslik"].get((plate, year), 0.0),
                    "okul": per_metric["okul"].get((plate, year), 0.0),
                    "ogretmen": per_metric["ogretmen"].get((plate, year), 0.0),
                }
            )
    long = pl.DataFrame(rows).with_columns(
        (pl.col("ogrenci") / pl.col("sube")).alias("ogrenci_sube"),
        (pl.col("sube") / pl.col("derslik")).alias("sube_derslik"),
        (pl.col("ogrenci") / pl.col("derslik")).alias("ogrenci_derslik"),
        (pl.col("ogretmen") / pl.col("okul")).alias("ogretmen_okul"),
        (pl.col("ogrenci") / pl.col("okul")).alias("ogrenci_okul"),
    )

    country = (
        long.group_by("yil")
        .agg(
            pl.col("ogrenci").sum(),
            pl.col("sube").sum(),
            pl.col("derslik").sum(),
            pl.col("okul").sum(),
            pl.col("ogretmen").sum(),
        )
        .with_columns(
            (pl.col("ogrenci") / pl.col("sube")).alias("ogrenci_sube"),
            (pl.col("sube") / pl.col("derslik")).alias("sube_derslik"),
            (pl.col("ogrenci") / pl.col("derslik")).alias("ogrenci_derslik"),
            (pl.col("ogretmen") / pl.col("okul")).alias("ogretmen_okul"),
            (pl.col("ogrenci") / pl.col("okul")).alias("ogrenci_okul"),
        )
        .sort("yil")
    )

    # İlk ve son yılın yan yana konduğu, değişimin sıralanabildiği karşılaştırma sayfası.
    def at(year: int, tag: str) -> pl.DataFrame:
        return long.filter(pl.col("yil") == year).select(
            "il",
            "plaka",
            pl.col("ogrenci").alias("ogrenci" + tag),
            pl.col("sube").alias("sube" + tag),
            pl.col("derslik").alias("derslik" + tag),
            pl.col("okul").alias("okul" + tag),
            pl.col("ogretmen").alias("ogretmen" + tag),
            pl.col("ogrenci_sube").alias("ogrenci_sube" + tag),
            pl.col("sube_derslik").alias("sube_derslik" + tag),
            pl.col("ogrenci_derslik").alias("ogrenci_derslik" + tag),
            pl.col("ogretmen_okul").alias("ogretmen_okul" + tag),
            pl.col("ogrenci_okul").alias("ogrenci_okul" + tag),
        )

    compare = ranked(
        at(last, "_" + str(last))
        .join(at(first, "_" + str(first)).drop("plaka"), on="il")
        .with_columns(
            (
                pl.col(f"ogrenci_sube_{last}") - pl.col(f"ogrenci_sube_{first}")
            ).alias("ogrenci_sube_fark"),
            (
                pl.col(f"sube_derslik_{last}") - pl.col(f"sube_derslik_{first}")
            ).alias("sube_derslik_fark"),
            (
                pl.col(f"ogrenci_derslik_{last}") - pl.col(f"ogrenci_derslik_{first}")
            ).alias("ogrenci_derslik_fark"),
            (
                pl.col(f"ogretmen_okul_{last}") - pl.col(f"ogretmen_okul_{first}")
            ).alias("ogretmen_okul_fark"),
            (
                pl.col(f"ogrenci_okul_{last}") - pl.col(f"ogrenci_okul_{first}")
            ).alias("ogrenci_okul_fark"),
        )
        .select(
            "il",
            "plaka",
            f"ogrenci_sube_{first}",
            f"ogrenci_sube_{last}",
            "ogrenci_sube_fark",
            f"sube_derslik_{first}",
            f"sube_derslik_{last}",
            "sube_derslik_fark",
            f"ogrenci_derslik_{first}",
            f"ogrenci_derslik_{last}",
            "ogrenci_derslik_fark",
            f"ogretmen_okul_{first}",
            f"ogretmen_okul_{last}",
            "ogretmen_okul_fark",
            f"ogrenci_okul_{first}",
            f"ogrenci_okul_{last}",
            "ogrenci_okul_fark",
        ),
        "ogrenci_sube_fark",
    )

    # region Yazma
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))
    style = styles(book)
    left = book.add_format({"align": "left", "valign": "vcenter", "indent": 1})

    headers = {
        "il": "İl",
        "plaka": "Plaka",
        "yil": "Yıl",
        "sira": "Sıra",
        "ogrenci": "Öğrenci",
        "sube": "Şube",
        "derslik": "Derslik",
        "okul": "Okul",
        "ogretmen": "Öğretmen",
        "ogrenci_sube": "Öğrenci/Şube",
        "sube_derslik": "Şube/Derslik",
        "ogrenci_derslik": "Öğrenci/Derslik",
        "ogretmen_okul": "Öğretmen/Okul",
        "ogrenci_okul": "Öğrenci/Okul",
        "ogrenci_sube_fark": "Öğrenci/Şube farkı",
        "sube_derslik_fark": "Şube/Derslik farkı",
        "ogrenci_derslik_fark": "Öğrenci/Derslik farkı",
        "ogretmen_okul_fark": "Öğretmen/Okul farkı",
        "ogrenci_okul_fark": "Öğrenci/Okul farkı",
    }
    for tag in (first, last):
        headers[f"ogrenci_sube_{tag}"] = f"Öğrenci/Şube · {tag}"
        headers[f"sube_derslik_{tag}"] = f"Şube/Derslik · {tag}"
        headers[f"ogrenci_derslik_{tag}"] = f"Öğrenci/Derslik · {tag}"
        headers[f"ogretmen_okul_{tag}"] = f"Öğretmen/Okul · {tag}"
        headers[f"ogrenci_okul_{tag}"] = f"Öğrenci/Okul · {tag}"

    counts = ("ogrenci", "sube", "derslik", "okul", "ogretmen")
    ratio_cols = [c for c in compare.columns if c not in ("il", "plaka", "sira")]

    formats = {
        "il": left,
        "plaka": style["text"],
        "yil": style["text"],
        "sira": style["text"],
        **{c: style["count"] for c in counts},
        **{c: style["rate"] for c in ratio_cols},
    }
    widths = {"il": 22, "plaka": 8, "yil": 8, "sira": 7}
    for c in ratio_cols:
        widths[c] = 16

    def write_sheet(name: str, data: pl.DataFrame) -> None:
        page = book.add_worksheet(name)
        page.freeze_panes(1, 1)
        page.set_row(0, 40)
        columns = data.columns
        for index, column in enumerate(columns):
            page.set_column(
                index, index, widths.get(column, 14), formats.get(column, style["text"])
            )
        rows_ = [list(r) for r in data.rows()]
        page.add_table(
            0,
            0,
            max(len(rows_), 1),
            len(columns) - 1,
            {
                "data": rows_,
                "columns": [
                    {
                        "header": headers.get(c, c),
                        "header_format": style["head"],
                        "format": formats.get(c, style["text"]),
                    }
                    for c in columns
                ],
                "banded_rows": True,
            },
        )

    write_sheet("İl-Yıl", long.sort(["il", "yil"]))
    write_sheet(f"{first} vs {last}", compare)
    write_sheet("Türkiye", country)

    notes_sheet(
        book,
        [
            f"İllere göre öğrenci, şube, derslik, okul, öğretmen sayıları — {first}-{last}",
            "",
            "Dört eğitim düzeyinin toplamı: Okul Öncesi, İlkokul, Ortaokul, Ortaöğretim",
            "(Ortaöğretim = Genel + Mesleki ve Teknik Ortaöğretim, kaynak dosyada zaten",
            "toplanmış geliyor — ayrıca eklenmedi, çift sayım olurdu). Cinsiyet kırılımı",
            "yok: kaynakta ayrı cinsiyetli dosyalar da var, burada yalnız toplam okundu.",
            "",
            "ORANLAR",
            "· Öğrenci/Şube — ortalama sınıf mevcudu, kalabalık göstergesi.",
            "· Şube/Derslik — ikili öğretim göstergesi: 1'e yakınsa tekli öğretim,",
            "  yükseldikçe aynı derslik günde birden fazla şubeye hizmet ediyor demektir.",
            "· Öğrenci/Derslik — fiziksel derslik başına öğrenci; ikili öğretim etkisini",
            "  de içerir, Şube/Derslik'ten ayrı okunmalı. Yüksek Öğrenci/Şube + yüksek",
            "  Şube/Derslik = idare ikili öğretimle kalabalığı çözmüş; yüksek Öğrenci/Şube",
            "  + Şube/Derslik ~1 = derslik yeterli ama norm/yönetim kalabalık bırakıyor.",
            "· Öğretmen/Okul, Öğrenci/Okul — okul büyüklüğü göstergeleri.",
            "",
            f"'{first} vs {last}' sayfası her oranı iki yılda yan yana koyuyor ve farkı",
            "hesaplıyor; 'Öğrenci/Şube farkı'na göre sıralı geliyor ama her sütun ayrıca",
            "sıralanabilir (sıra numarası hangi sıralamayla açıldığını gösterir).",
            "",
            "KAYNAK",
            "MEB Strateji Geliştirme Başkanlığı istatistik portalı (istatistik.meb.gov.tr),",
            "masaüstünde elle indirilmiş beş ayrı .xls: Öğrenci, Şube, Derslik, Okul,",
            f"Öğretmen sayıları — il × yıl ({first}-{last}) × eğitim düzeyi pivot tabloları.",
            "Henüz depoya (raw/) alınmadı, bu dosya kaynağı doğrudan okuyor.",
        ],
    )
    book.close()
    # endregion

    print("yazildi:", TARGET)
    print("satir (il-yil):", len(long), "| yillar:", first, "-", last)


if __name__ == "__main__":
    main()
