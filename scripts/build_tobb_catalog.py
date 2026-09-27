r"""Write the TOBB capacity entries of indicators.toml from TOBB's product code list.

4,673 product codes and their names come from the code list the adapter reads
(`src/veriatlas/adapters/tobb_capacity.py`). The block between `# BEGIN tobb_capacity` /
`# END tobb_capacity` is rewritten on every run.

    .venv\Scripts\python.exe scripts\build_tobb_catalog.py
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

from veriatlas.adapters.tobb_capacity import STAFF_BANDS, UNITS, products
from veriatlas.config import DATA

TOML = DATA / "indicators.toml"
BEGIN, END = "# BEGIN tobb_capacity (generated)", "# END tobb_capacity"
SOURCE = (
    "TOBB Sanayi Bilgi Sistemi (sanayi.org.tr), odaların verdiği kapasite raporlarının "
    "kaydı, 2026-09-27 anlık görüntüsü; yıllık seri değil, 2026 yılına yazıldı. Kimliği "
    "belli olmayan il (BİLİNMEYEN) dışarıda. Personel sütunları alınmadı: aynı üreticinin "
    "personeli her ürün ve sektör satırında tekrar ediyor (Türkiye toplamı 41,5 milyon). "
    "Adaptör src/veriatlas/adapters/tobb_capacity.py."
)
UNIT_TR = {
    "kilogram": "Kilogram",
    "item": "Adet",
    "square_metre": "Metrekare",
    "litre": "Litre",
    "cubic_metre": "Metreküp",
    "pair": "Çift",
    "kilowatt_hour": "Kilovat saat",
    "metre": "Metre",
    "tonne": "Ton",
    "joule": "Joule",
    "deadweight_tonne": "DWT (detveyt ton)",
    "kilometre": "Kilometre",
    "gram": "Gram",
    "carat": "Karat",
    "box": "Kutu",
}
PRODUCT = (
    "Ürün kodu TOBB'un listesi: 4.673 kodun 2.421'i PRODTR, kalanı TOBB'un eklediği "
    "kodlar; ürünler toplanmaz (bir üretici birden çok ürün yapar). Aynı ildeki "
    "üreticiler ürünü farklı birimle (kg, adet ...) bildirebilir; birim ayrı kırılım."
)
INDICATORS = {
    "tobb_product_producers": (
        "Ürüne göre kapasite raporlu üretici sayısı",
        "Producers with a capacity report, by product",
        "company",
        ["tobb_product", "tobb_unit"],
        ["table", "map", "bar"],
        "Ürünü kapasite raporunda gösteren kayıtlı üretici sayısı, il ve birim başına. "
        + PRODUCT,
    ),
    "tobb_product_capacity": (
        "Ürüne göre kayıtlı üretim kapasitesi",
        "Registered production capacity, by product",
        "source_unit",
        ["tobb_product", "tobb_unit"],
        ["table", "map", "bar"],
        "Kapasite raporlarındaki yıllık üretim kapasitesi, ürünün birimiyle. Üç ve daha az "
        "üreticili illerde kaynak gizliyor ('*'); bunlar boş bırakıldı, sıfır değil. "
        + PRODUCT,
    ),
    "tobb_producers_by_activity": (
        "Ana faaliyete göre kapasite raporlu üretici sayısı",
        "Producers with a capacity report, by main activity",
        "company",
        ["nace_division"],
        ["table", "map", "bar"],
        (
            "Üreticinin ana faaliyetinin NACE bölümüne göre sayısı; Türkiye ve il. İstanbul "
            "kaynakta yok (sorgu boş dönüyor); Türkiye toplamı İstanbul'u içeriyor. 32.50 "
            "kaynakta 32'den ayrı satır."
        ),
    ),
    "tobb_producers_by_staff": (
        "Personel büyüklüğüne göre kapasite raporlu üretici sayısı",
        "Producers with a capacity report, by staff size",
        "company",
        ["nace_division", "producer_staff_band"],
        ["table", "map", "bar"],
        (
            "Sektör ve personel aralığına göre üretici sayısı; Türkiye ve il (İstanbul dahil). "
            "'total' kaynaktaki toplam; 170 satırda aralıklar toplamdan az (personeli "
            "bildirilmemiş üretici), hiçbirinde fazla değil."
        ),
    ),
    "tobb_producers_district": (
        "İlçeye göre kapasite raporlu üretici sayısı",
        "Producers with a capacity report, by district",
        "company",
        ["nace_division"],
        ["table", "map", "bar"],
        (
            "İlçe başına üretici sayısı, tüm faaliyetler ('total') ve sektör sektör. Yalnız "
            "ilçesi kayıtlı üreticiler: ilçe toplamı il toplamının %70-77'si; büyükşehirlerde "
            "'MERKEZ' ve 'BELİRTİLMEMİŞ' yazılanlar dışarıda. Sektörler toplanmaz: birden çok "
            "sektörde üreten firma her birinde sayılıyor."
        ),
    ),
    "tobb_foreign_product_producers": (
        "Ürüne göre yabancı sermayeli kapasite raporlu üretici sayısı",
        "Foreign-capital producers with a capacity report, by product",
        "company",
        ["tobb_product"],
        ["table", "map", "bar"],
        (
            "Yabancı sermayeli üretici sayısı, ürün başına; Türkiye ve il. Türkiye satırı "
            "kaynağın kendi toplamı, illerin toplamını 1.362 ürünün 1.357'sinde tutuyor. "
            "Aynı kaynağın ürün × il listesi (yabanciSermayeGenelDurumu) daha küçük sayılar "
            "veriyor ve bazı ürünleri iki kez yazıyor; alınmadı. TOBB'un güncel kod "
            "listesinde olmayan 10 eski kod (Türkiye satırında 23 üretici) dışarıda. "
            "Ürünler toplanmaz."
        ),
    ),
    "tobb_foreign_producers_district": (
        "İlçeye göre yabancı sermayeli kapasite raporlu üretici sayısı",
        "Foreign-capital producers with a capacity report, by district",
        "company",
        ["nace_division"],
        ["table", "map", "bar"],
        (
            "İlçe başına yabancı sermayeli üretici sayısı, tüm faaliyetler ('total') ve "
            "sektör sektör. Yalnız ilçesi kayıtlı üreticiler; büyükşehirlerde 'MERKEZ' ve "
            "'BELİRTİLMEMİŞ' dışarıda. Sektörler toplanmaz."
        ),
    ),
}


def q(text: str) -> str:
    return json.dumps(" ".join(str(text).split()), ensure_ascii=False)


def main() -> None:
    codes = products()
    if set(UNIT_TR) != set(UNITS.values()):
        raise SystemExit("UNIT_TR ile UNITS aynı birimleri tutmuyor")
    lines = [
        BEGIN,
        "# Do not edit by hand: scripts/build_tobb_catalog.py rewrites it.",
        "",
        "[dim.tobb_product]",
        'label_tr = "Sanayi ürünü (TOBB kodu)"',
        'label_en = "Industrial product (TOBB code)"',
        "",
        "[dim.tobb_product.values]",
        *(f'"{code}" = {q(c["name"])}' for code, c in codes.items()),
        "",
        "[dim.tobb_unit]",
        'label_tr = "Ölçü birimi"',
        'label_en = "Unit of measure"',
        "",
        "[dim.tobb_unit.values]",
        *(f"{u} = {q(tr)}" for u, tr in UNIT_TR.items()),
        "",
        "[dim.producer_staff_band]",
        'label_tr = "Personel sayısı"',
        'label_en = "Staff"',
        "",
        "[dim.producer_staff_band.values]",
        *(f'"{band}" = "{band}"' for band in STAFF_BANDS.values()),
        'total = "Toplam"',
        "",
    ]
    for ident, (tr, en, unit, dims, views, note) in INDICATORS.items():
        lines += [
            f"[indicator.{ident}]",
            f"label_tr = {q(tr)}",
            f"label_en = {q(en)}",
            'topic = "reel_kesim"',
            f'unit = "{unit}"',
            'frequency = "annual"',
            "additive = false",
            "dims = [" + ", ".join(f'"{d}"' for d in dims) + "]",
            "views = [" + ", ".join(f'"{v}"' for v in views) + "]",
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
    print(len(codes), "ürün,", len(UNIT_TR), "birim")


if __name__ == "__main__":
    main()
