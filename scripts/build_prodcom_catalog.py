r"""Write the PRODCOM entries of indicators.toml from TÜİK's code list.

About 9,100 product codes and their units come from the code list the adapter reads
(`src/veriatlas/adapters/prodcom.py`); writing them by hand would drift from it. The
block between `# BEGIN prodcom` / `# END prodcom` is rewritten on every run.

    .venv\Scripts\python.exe scripts\build_prodcom_catalog.py
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

from veriatlas.adapters.prodcom import code_list
from veriatlas.config import DATA

TOML = DATA / "indicators.toml"
BEGIN, END = "# BEGIN prodcom (generated)", "# END prodcom"
SOURCE = (
    "TÜİK Yıllık Sanayi Ürün İstatistikleri (PRODCOM), veri portalı tablosu, 2005-2025 "
    "(2025 geçici), Türkiye. Ürün kodu üç iç içe düzeyde: CPA (6 hane), PRODCOM (8), "
    "PRODTR (10); üst kod alt kodların toplamıdır, farklı düzeyler toplanmaz. Gizli "
    "hücreler (c) ve üretim olmayanlar (-) boş bırakıldı, sıfır yazılmadı. 2005 ve "
    "2018-2025 yalnız yıllık PRODCOM anketinden, diğer yıllar aylık sanayi üretim "
    "anketiyle birlikte derlendi. Kodlar PRODTR 2025'e göre güncellenmiş. Adaptör "
    "src/veriatlas/adapters/prodcom.py."
)
INDICATORS = {
    "industrial_product_output": (
        "Sanayi ürünleri üretim miktarı",
        "Industrial products, production volume",
        "source_unit",
        ["industrial_product", "product_unit"],
        (
            "Yıl içinde üretilen miktar, ürünün kendi biriminde (kg, adet, m² ...; birim ayrı "
            "kırılım). Birimi TL olan ürünlerde miktar yok."
        ),
    ),
    "industrial_product_sales_quantity": (
        "Sanayi ürünleri satış miktarı",
        "Industrial products, sold volume",
        "source_unit",
        ["industrial_product", "product_unit"],
        "Yıl içinde satılan miktar, ürünün kendi biriminde. Birimi TL olan ürünlerde miktar yok.",
    ),
    "industrial_product_sales_value": (
        "Sanayi ürünleri satış değeri",
        "Industrial products, sold value",
        "try",
        ["industrial_product"],
        (
            "Satış değeri, TL, cari fiyat. 'total' tüm ürünlerin toplamıdır. 28.42.24'te "
            "(2018, 2022-2025) alt kodlar üst kodu aşıyor; kaynaktaki haliyle bırakıldı."
        ),
    ),
    "industrial_product_enterprises": (
        "Sanayi ürünü üreten girişim sayısı",
        "Enterprises producing an industrial product",
        "item",
        ["industrial_product"],
        "Ürünü üreten girişim sayısı. Bir girişim birden çok ürün üretebilir; ürünler toplanmaz.",
    ),
}


def q(text: str) -> str:
    return json.dumps(" ".join(str(text).split()), ensure_ascii=False)


def main() -> None:
    codes = code_list()
    units = {c["unit"]: c["unit_tr"] for c in codes.values()}
    lines = [
        BEGIN,
        "# Do not edit by hand: scripts/build_prodcom_catalog.py rewrites it.",
        "",
        "[dim.industrial_product]",
        'label_tr = "Sanayi ürünü"',
        'label_en = "Industrial product"',
        "",
        "[dim.industrial_product.values]",
        'total = "Toplam"',
        *(f'"{code}" = {q(c["name_tr"])}' for code, c in codes.items()),
        "",
        "[dim.product_unit]",
        'label_tr = "Ölçü birimi"',
        'label_en = "Unit of measure"',
        "",
        "[dim.product_unit.values]",
        *(f"{u} = {q(tr)}" for u, tr in sorted(units.items())),
        "",
    ]
    for ident, (tr, en, unit, dims, note) in INDICATORS.items():
        lines += [
            f"[indicator.{ident}]",
            f"label_tr = {q(tr)}",
            f"label_en = {q(en)}",
            'topic = "reel_kesim"',
            f'unit = "{unit}"',
            'frequency = "annual"',
            "additive = false",
            "dims = [" + ", ".join(f'"{d}"' for d in dims) + "]",
            'views = ["table", "line", "bar"]',
            f"definition_tr = {q(note + ' ' + SOURCE)}",
            "",
        ]
    lines.append(END)
    block = "\n".join(lines) + "\n"
    toml = TOML.read_text(encoding="utf-8")
    if BEGIN in toml:
        head, rest = toml.split(BEGIN, 1)
        toml = head + block + rest.split(END + "\n", 1)[1]
    else:
        toml = toml.rstrip("\n") + "\n\n" + block
    TOML.write_text(toml, encoding="utf-8")
    print(len(codes), "ürün,", len(units), "birim")


if __name__ == "__main__":
    main()
