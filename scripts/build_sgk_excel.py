"""İllere göre 4/1-a, 4/1-b, 4/1-c aktif sigortalı sayısı ve payı — 2014 vs 2025.

5510 sayılı Kanun'un 4. maddesindeki üç sigortalılık statüsü:

* **4/1-a (eski SSK)** — hizmet akdiyle bir işverene bağlı çalışan işçiler.
* **4/1-b (eski Bağ-Kur)** — kendi hesabına çalışanlar: esnaf, çiftçi, serbest meslek.
* **4/1-c (eski Emekli Sandığı)** — devlet memurları, kamu görevlileri.

Kaynak: SGK İstatistik Yıllığı, "TABLO 1.7 — Aktif Sigortalıların İl ve
Sigortalılık Türüne Göre Dağılımı" (sgk.gov.tr/Istatistik/Yillik). Yıllığın zip
paketleri sgk.gov.tr'den elle indirilip yerelde açıldı.

En geriye giden yıl **2014**: SGK'nın yıllık listesi 2007'ye kadar iniyor ama
2007-2013 arası ayrı bir alt sayfa gerektiriyor ve doğrudan zip linki bu betiğin
kapsadığı 2014-2025 grubunda değil — buraya alınmadı. 2014-2025 arası iki farklı
sütun düzeni var (aşağıda `LAYOUTS`), ikisi de elle doğrulandı.

En yeni yıl **2025**: yıl henüz tamamlanmadığı için (yıllık yayın Temmuz 2026'da
hazırlanmış) kısmi yıl olabilir — bu, TÜRKİYE toplamının önceki yıllardan düşük
çıkmasının olası bir nedeni, kontrol edilmedi.

Run:  uv run python scripts/build_sgk_excel.py
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
TARGET = PUBLIC.parent / "cikti" / "analiz-sgk-4a-4b-4c-il-yillara-gore.xlsx"

#: Yıla göre iki farklı sütun düzeni. Değer: (dosya yolu, a-index, b-index, c-index,
#: toplam-index, veri başlangıç satırı [0-based, openpyxl iter_rows min_row karşılığı]).
LAYOUTS = {
    2014: dict(
        path=SCRATCH / "sgk2014" / "sgk_2014"
        / "2014 YILLIK BÖLÜM 1 İsyeri ve Sigortalılara Ait İstatistikler.xlsx",
        a=2,
        b=13,
        c=14,
        total=15,
        min_row=7,
        max_row=100,
    ),
    2025: dict(
        path=SCRATCH / "sgk2025" / "YILLIK BÖLÜM 1 Sigortalı ve İş Yeri İstatistikleri_2025.xlsx",
        a=2,
        b=11,
        c=17,
        total=20,
        min_row=9,
        max_row=90,
    ),
}


def read_year(year: int) -> pl.DataFrame:
    layout = LAYOUTS[year]
    wb = openpyxl.load_workbook(str(layout["path"]), data_only=True)
    ws = wb["TABLO-1.7"]

    rows = []
    for row in ws.iter_rows(
        min_row=layout["min_row"], max_row=layout["max_row"], values_only=True
    ):
        code, il = row[0], row[1]
        if not il or not str(code).strip():
            continue
        try:
            plate = int(code)
        except (TypeError, ValueError):
            # Yazdırma sayfası kırılımında başlık satırı ara ara tekrarlanıyor —
            # il kodu sayı değilse veri satırı değildir, atlanır.
            continue
        a, b, c, total = (
            row[layout["a"]],
            row[layout["b"]],
            row[layout["c"]],
            row[layout["total"]],
        )
        if a is None:
            continue
        rows.append(
            {
                "il": il,
                "plaka": plate,
                "a": float(a),
                "b": float(b),
                "c": float(c),
                "toplam": float(total),
            }
        )
    frame = pl.DataFrame(rows)
    if len(frame) != 81:
        print(f"uyari [{year}]: 81 il beklenirken {len(frame)} satir okundu")
    return frame.with_columns(
        (pl.col("a") / pl.col("toplam")).alias("a_pay"),
        (pl.col("b") / pl.col("toplam")).alias("b_pay"),
        (pl.col("c") / pl.col("toplam")).alias("c_pay"),
    )


def main() -> None:
    first, last = 2014, 2025
    early = read_year(first)
    late = read_year(last)

    def tag(frame: pl.DataFrame, suffix: str) -> pl.DataFrame:
        return frame.select(
            "il",
            "plaka",
            pl.col("a").alias(f"a_{suffix}"),
            pl.col("b").alias(f"b_{suffix}"),
            pl.col("c").alias(f"c_{suffix}"),
            pl.col("toplam").alias(f"toplam_{suffix}"),
            pl.col("a_pay").alias(f"a_pay_{suffix}"),
            pl.col("b_pay").alias(f"b_pay_{suffix}"),
            pl.col("c_pay").alias(f"c_pay_{suffix}"),
        )

    compare = (
        tag(late, str(last))
        .join(tag(early, str(first)).drop("plaka"), on="il")
        .with_columns(
            (pl.col(f"a_pay_{last}") - pl.col(f"a_pay_{first}")).alias("a_pay_fark"),
            (pl.col(f"b_pay_{last}") - pl.col(f"b_pay_{first}")).alias("b_pay_fark"),
            (pl.col(f"c_pay_{last}") - pl.col(f"c_pay_{first}")).alias("c_pay_fark"),
            (pl.col(f"toplam_{last}") / pl.col(f"toplam_{first}") - 1).alias(
                "toplam_oran"
            ),
        )
    )
    compare = ranked(
        compare.select(
            "il",
            "plaka",
            f"toplam_{first}",
            f"toplam_{last}",
            "toplam_oran",
            f"a_pay_{first}",
            f"a_pay_{last}",
            "a_pay_fark",
            f"b_pay_{first}",
            f"b_pay_{last}",
            "b_pay_fark",
            f"c_pay_{first}",
            f"c_pay_{last}",
            "c_pay_fark",
        ),
        "c_pay_fark",
    )

    turkiye_rows = []
    for year, frame in ((first, early), (last, late)):
        totals = frame.select(pl.exclude("il", "plaka").sum()).to_dicts()[0]
        for key in ("a_pay", "b_pay", "c_pay"):
            totals[key] = totals[key.split("_")[0]] / totals["toplam"]
        totals["yil"] = year
        turkiye_rows.append(totals)
    country = pl.DataFrame(turkiye_rows).select(
        "yil", "a", "b", "c", "toplam", "a_pay", "b_pay", "c_pay"
    )

    # region Yazma
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    book = xlsxwriter.Workbook(str(TARGET))
    style = styles(book)
    left = book.add_format({"align": "left", "valign": "vcenter", "indent": 1})

    headers = {
        "il": "İl",
        "plaka": "Plaka",
        "sira": "Sıra",
        "yil": "Yıl",
        "a": "4/1-a sayısı",
        "b": "4/1-b sayısı",
        "c": "4/1-c sayısı",
        "toplam": "Toplam aktif sigortalı",
        "a_pay": "4/1-a payı",
        "b_pay": "4/1-b payı",
        "c_pay": "4/1-c payı",
        f"toplam_{first}": f"Toplam · {first}",
        f"toplam_{last}": f"Toplam · {last}",
        "toplam_oran": "Toplam değişimi",
        f"a_pay_{first}": f"4/1-a payı · {first}",
        f"a_pay_{last}": f"4/1-a payı · {last}",
        "a_pay_fark": "4/1-a payı farkı",
        f"b_pay_{first}": f"4/1-b payı · {first}",
        f"b_pay_{last}": f"4/1-b payı · {last}",
        "b_pay_fark": "4/1-b payı farkı",
        f"c_pay_{first}": f"4/1-c payı · {first}",
        f"c_pay_{last}": f"4/1-c payı · {last}",
        "c_pay_fark": "4/1-c payı farkı",
    }
    counts = ("a", "b", "c", "toplam", f"toplam_{first}", f"toplam_{last}")
    shares = tuple(c for c in compare.columns if "pay" in c or c == "toplam_oran") + (
        "a_pay",
        "b_pay",
        "c_pay",
    )
    formats = {
        "il": left,
        "plaka": style["text"],
        "sira": style["text"],
        "yil": style["text"],
        **{c: style["count"] for c in counts},
        **{c: style["percent"] for c in shares},
    }
    widths = {"il": 22, "plaka": 8, "sira": 7, "yil": 8}

    def write_sheet(name: str, data: pl.DataFrame) -> None:
        page = book.add_worksheet(name)
        page.freeze_panes(1, 1)
        page.set_row(0, 40)
        columns = data.columns
        for index, column in enumerate(columns):
            page.set_column(
                index, index, widths.get(column, 16), formats.get(column, style["text"])
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

    write_sheet(f"{first} vs {last}", compare)
    write_sheet(str(last), late.sort("il"))
    write_sheet(str(first), early.sort("il"))
    write_sheet("Türkiye", country)

    notes_sheet(
        book,
        [
            f"İllere göre 4/1-a, 4/1-b, 4/1-c aktif sigortalı sayısı ve payı — {first} vs {last}",
            "",
            "5510 sayılı Kanun'un 4. maddesindeki üç sigortalılık statüsü:",
            "· 4/1-a (eski SSK) — hizmet akdiyle çalışan işçiler, özel sektörün",
            "  çoğunluğu.",
            "· 4/1-b (eski Bağ-Kur) — kendi hesabına çalışanlar: esnaf, çiftçi,",
            "  serbest meslek sahibi, şirket ortağı.",
            "· 4/1-c (eski Emekli Sandığı) — devlet memurları, kamu görevlileri.",
            "",
            "Pay = o statüdeki sigortalı / ilin toplam aktif sigortalısı (üç statünün",
            "toplamı). Nüfusa ya da işgücüne oranlanmadı, sigortalı içindeki dağılım.",
            "",
            f"'{first} vs {last}' sayfası 4/1-c payı farkına göre sıralı geliyor ama",
            "her sütun ayrıca sıralanabilir.",
            "",
            "KAYNAK VE SINIR",
            "SGK İstatistik Yıllıkları, TABLO 1.7 (sgk.gov.tr/Istatistik/Yillik).",
            f"{first}, bu betiğin kapsadığı en eski yıl — 2007-2013 arası ayrı bir",
            "alt sayfa gerektiriyor, buraya alınmadı. İki yılın sütun düzeni farklı",
            "(2014'te 4/1-b tek sütunda, 2025'te zorunlu/isteğe bağlı/muhtar ayrı) ama",
            "üç ana toplam (4a, 4b, 4c) ikisinde de doğrulandı: toplamların toplamı",
            "grand total'a birebir eşit.",
            f"{last} yılı henüz tamamlanmamış olabilir (yıllık Temmuz 2026'da",
            "hazırlanmış) — Türkiye toplamının kısmi yıl etkisi taşıyıp taşımadığı",
            "kontrol edilmedi.",
        ],
    )
    book.close()
    # endregion

    print("yazildi:", TARGET)


if __name__ == "__main__":
    main()
