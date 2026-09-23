r"""Retail and service networks: one status table for every chain, fetched or not.

Rows in the warehouse are counted from `public/fact.parquet` (stores, provinces and
districts per brand), so they never go stale. Everything that is not in the warehouse —
raw dumps waiting for an adapter, pages the user saved by hand, sites that refused, brands
never tried — is listed by hand in `OFF_WAREHOUSE` below; that list is the part to keep
current.

Writes `docs/perakende-durum.md` and `docs/perakende-durum.html` (a sortable, filterable
page published as an artifact).

Run:  uv run python scripts/build_retail_status.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tomllib
from pathlib import Path

import polars as pl

sys.path.insert(0, "src")

from veriatlas.config import DOCS, PUBLIC

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src" / "veriatlas" / "data" / "indicators.toml"

# Status labels, in the order the page shows them.
DEPODA = "Depoda"
HAM = "Ham veri var, bekliyor"
KISMI = "Kısmi, tamamlanmalı"
BOS = "Kayıt boş, yeniden kaydet"
KAPALI = "Alınamadı"
DENENMEDI = "Denenmedi"
STATUSES = [DEPODA, HAM, KISMI, BOS, KAPALI, DENENMEDI]

#: indicator -> (category, how it was fetched)
INDICATORS = {
    "chain_stores": ("Perakende", "mağaza bulucu"),
    "chain_restaurants": ("Yeme-içme", "mağaza bulucu"),
    "fashion_stores": ("Giyim", "mağaza bulucu"),
    "furniture_stores": ("Mobilya", "bayi paneli"),
    "telecom_dealers": ("Operatör", "bayi bulucu"),
    "cargo_branches": ("Kargo", "şube bulucu"),
    "post_offices": ("Kargo", "PTT iş yeri bulucu"),
}

#: chain_stores brands by kind; anything unlisted is a grocer.
STORE_KIND = {
    "gratis": "Kozmetik", "rossmann": "Kozmetik", "flormar": "Kozmetik",
    "madame_coco": "Ev", "karaca": "Ev", "englishhome": "Ev", "chakra": "Ev", "mudo": "Ev",
    "vatan": "Elektronik", "vestel": "Elektronik", "teknosa": "Elektronik",
    "koctas": "Yapı market", "macfit": "Spor", "intersport": "Spor",
    "opmar": "Optik", "atasay": "Kuyum", "avva": "Giyim",
}  # fmt: skip

#: Notes on warehouse rows: (indicator, brand) -> (method, note).
NOTES = {
    ("chain_stores", "bim"): ("ilçe sayımı", "BİM ve FİLE birlikte; mağaza değil ilçe toplamı"),
    ("chain_stores", "migros"): ("ilçe sayımı", "Migros, MJet, Macrocenter birlikte; ilçe toplamı"),
    ("chain_stores", "sec_market"): ("ilçe etiketi", "12 mağazanın ilçe etiketi bozuk, dışarıda"),
    ("chain_stores", "englishhome"): ("Ticimax ortak ucu", "42 yurt dışı mağaza ayıklandı"),
    ("chain_stores", "avva"): ("Ticimax ortak ucu", "23 yurt dışı mağaza ayıklandı"),
    ("chain_stores", "opmar"): ("Ticimax ortak ucu", ""),
    ("chain_stores", "atasay"): ("Akinon ortak ucu", "9 yurt dışı mağaza ayıklandı"),
    ("chain_stores", "flormar"): ("Akinon ortak ucu", ""),
    ("chain_stores", "mudo"): ("Akinon ortak ucu", ""),
    ("chain_stores", "intersport"): ("Akinon ortak ucu", ""),
    ("chain_stores", "chakra"): ("Akinon ortak ucu", "18 yurt dışı mağaza ayıklandı"),
    ("chain_stores", "teknosa"): ("elle kaydedilen sayfa", "robots 403; sayfanın kendi toplamı 136"),
    ("chain_stores", "rossmann"): ("mağaza bulucu", "23.09 elle kayıtta 211 mağaza; tutarlı"),
    ("chain_restaurants", "kofteci_yusuf"): ("elle kaydedilen sayfa", "bot kontrolü; sayfa 308 şube / 43 il diyor"),
    ("cargo_branches", "yurtici"): ("şube kimliği taraması", "1-12000 tarandı; doğu 8010-8499"),
    ("cargo_branches", "kolay_gelsin"): ("teslimat noktası haritası", "yalnız DN/DM birimleri; ~990 anlaşmalı nokta ham veride"),
    ("cargo_branches", "surat"): ("ilçe ilçe sorgu", "388'i acente; 33 koordinatsız dışarıda"),
    ("telecom_dealers", "turk_telekom_office"): ("bayi bulucu", "yalnız markalı ofis ve mağaza; bayi ağı elde yok"),
    ("telecom_dealers", "vodafone_shop"): ("bayi bulucu", "Cep Merkezi ve kurumsal mağaza"),
    ("telecom_dealers", "vodafone_dealer"): ("bayi bulucu", "hat satan bayi (hizmet noktası)"),
    ("telecom_dealers", "vodafone_payment"): ("bayi bulucu", "yalnız fatura ödeme; mağaza değil"),
    ("telecom_dealers", "turkcell_dealer"): ("Turkcell'in PDF listesi", "elle kaydedilen PDF, 3.516 bayi; 31'i ilçesiz"),
}  # fmt: skip

#: Everything not in the warehouse: (brand, category, status, stores or "", method, note).
OFF_WAREHOUSE = [
    # raw dumps waiting for an adapter
    ("FLO", "Giyim", HAM, 321, "elle kaydedilen sayfa", "robots Claude'u engelliyor; 321 koordinatlı mağaza, sayfa 319 diyor"),
    ("Watsons", "Kozmetik", HAM, 535, "elle kaydedilen sayfa", "79 il tam; ilçe %75, 136 mağaza elle yerleştirilecek"),
    ("Sephora", "Kozmetik", HAM, 45, "elle kaydedilen sayfa", "ad ve adres var, koordinat yok"),
    ("Kahve Dünyası", "Yeme-içme", HAM, 355, "mağaza bulucu", "adresten il ve ilçe çıkarılacak"),
    ("Toyzz Shop", "Oyuncak", HAM, 263, "mağaza bulucu", "yalnız serbest adres"),
    ("Bizim Toptan", "Market", HAM, 172, "mağaza bulucu", "il ve ilçe etiketi var"),
    ("Onur Market", "Market", HAM, 154, "mağaza bulucu", "il ve ilçe etiketi var, ilk satır bozuk"),
    ("Happy Center", "Market", HAM, 194, "mağaza bulucu", "il yok, yalnız adres"),
    ("Usta Dönerci", "Yeme-içme", HAM, "", "mağaza bulucu", "yalnız il sayıları"),
    ("KFC", "Yeme-içme", HAM, 43, "mağaza bulucu", "yarım kaldı"),
    ("Turkcell Ev Müşteri Merkezleri", "Operatör", HAM, 38, "Turkcell'in PDF listesi", "25 il, yalnız Superbox"),
    ("Turkcell mağaza sayfası", "Operatör", KISMI, 74, "elle kaydedilen sayfa", "yalnız Adana; ad ve telefon, ilçe yok; 48'i DSN listesinde"),
    ("Avis", "Oto kiralama", HAM, 94, "elle kaydedilen sayfa", "şehir 55, havalimanı 35, Avis Yanında 4; çoğu koordinatlı"),
    ("Budget", "Oto kiralama", HAM, 67, "elle kaydedilen sayfa", "şehir 33, havalimanı 26, İstediğin Yerde 8; çoğu koordinatlı"),
    ("Garenta", "Oto kiralama", HAM, 110, "elle kaydedilen sayfa", "şube adları, koordinat yok"),
    ("Zeplin Car", "Oto kiralama", HAM, 115, "elle kaydedilen sayfa", "ofis adları, koordinat yok"),
    ("Sixt", "Oto kiralama", HAM, 71, "elle kaydedilen sayfa", "sayfada dünya geneli 1.197 şube; Türkiye kutusunda 71, koordinatlı"),
    ("Enterprise", "Oto kiralama", HAM, 121, "elle kaydedilen sayfa", "121 koordinatlı nokta"),
    ("Europcar", "Oto kiralama", HAM, 46, "elle kaydedilen sayfa", "ofis adları, havalimanı ve şehir ayrı; koordinat yok"),
    ("Rent Go", "Oto kiralama", HAM, 24, "elle kaydedilen sayfa", "24 ofis kartı"),
    ("Petlas", "Oto servis", HAM, 549, "elle kaydedilen sayfa", "bayi araması reCAPTCHA'lı, sayfa elle kaydedildi; 521'i koordinatlı"),
    ("Lassa", "Oto servis", HAM, 573, "elle kaydedilen sayfa", "573 bayi kaydı"),
    ("Yerel marketler (22 zincir)", "Market", HAM, 327, "kendi siteleri", "3-44 mağazalık bölge zincirleri; Söz depoda"),
    # partial
    ("Arçelik", "Beyaz eşya", KISMI, 1000, "elle kaydedilen sayfa", "sayfa 500 bayi sınırı; A-E ve S-Z var, F-R yok; il il kayıt gerek"),
    ("Beko", "Beyaz eşya", KISMI, 991, "elle kaydedilen sayfa", "sayfa 500 sınırı; A-G ve O-Z var, H-N yok; il il kayıt gerek"),
    ("Tekzen", "Yapı market", KISMI, 1, "Ticimax ortak ucu", "uç yalnız 1 mağaza döndürdü"),
    # empty saves
    ("MediaMarkt", "Elektronik", BOS, "", "elle kaydedilen sayfa", "liste yüklenmeden kaydedildi; arama yapıp kaydet"),
    ("Boyner", "Giyim", HAM, 132, "elle kaydedilen sayfa", "ad ve adres, koordinat yok; ayrıca YKM 3, Costa Coffee 4"),
    # refused
    ("A101", "Market", KAPALI, "", "mağaza ucu bulundu", "IP 403, robots 500; kendi açıklaması ~13.500"),
    ("CarrefourSA", "Market", KAPALI, "", "", "robots 403"),
    ("Decathlon", "Spor", KAPALI, "", "", "robots 403"),
    ("Pandora", "Kuyum", KAPALI, "", "", "robots 403"),
    ("Mado", "Yeme-içme", KAPALI, "", "", "403"),
    ("Altus", "Beyaz eşya", KAPALI, "", "", "yalnız adres arama haritası"),
    ("Bosch, Siemens, Profilo", "Beyaz eşya", KAPALI, "", "", "bayi sayfaları 403 (eski not)"),
    ("Bauhaus", "Yapı market", KAPALI, "", "", "mağaza sayfası Cloudflare"),
    ("Bosch Car Service", "Oto servis", KAPALI, "", "", "yönlendirme izlenmedi"),
    ("Petzz", "Evcil hayvan", KAPALI, "", "", "bağlantı kurulamadı"),
    ("Atasun Optik", "Optik", KAPALI, "", "", "bağlantı kurulamadı"),
    ("Noter", "Kamu", KAPALI, "", "", "Noterler Birliği reCAPTCHA; elle: il seçmeden Aramaya Başla, sonra kaydet"),
    ("HepsiJet", "Kargo", KAPALI, "", "", "robots 403"),
    ("UPS", "Kargo", KAPALI, "", "", "Access Denied"),
    ("Sendeo", "Kargo", KAPALI, "", "", "alan adı çözülmüyor"),
    ("Trendyol Express", "Kargo", KAPALI, "", "", "şube bulucu yok"),
    ("Garanti BBVA ATM", "Banka", KAPALI, "", "", "ATM listesi alınamadı"),
    # never tried; robots allows and a store page exists unless noted
    ("D&R", "Kitap", DENENMEDI, "", "/magazalar", ""),
    ("Remzi", "Kitap", DENENMEDI, "", "/magazalarimiz/", ""),
    ("Altınbaş", "Kuyum", DENENMEDI, "", "/magazalar", ""),
    ("Penti", "Giyim", DENENMEDI, "", "/tr/store-finder/stores", ""),
    ("Deichmann", "Giyim", DENENMEDI, "", "/tr-tr/storefinder", ""),
    ("Kiğılı", "Giyim", DENENMEDI, "", "/pages/stores", ""),
    ("Derimod", "Giyim", DENENMEDI, "", "/pages/magazalar", "Akinon ucu sayı vermedi"),
    ("Lescon", "Giyim", DENENMEDI, "", "/magazalarimiz/", ""),
    ("Suwen", "Giyim", DENENMEDI, "", "/magazalar", ""),
    ("Jimmy Key", "Giyim", DENENMEDI, "", "", "mağaza sayfası bulunamadı"),
    ("Taç", "Ev", DENENMEDI, "", "/magazalar", ""),
    ("Paşabahçe", "Ev", DENENMEDI, "", "/magazalar/", ""),
    ("Özdilek", "Ev", DENENMEDI, "", "/tr/departman-magazalar", ""),
    ("Eve Shop", "Kozmetik", DENENMEDI, "", "", "mağaza sayfası bulunamadı"),
    ("Ebebek", "Bebek", DENENMEDI, "", "/magazalar", ""),
    ("Tchibo", "Yeme-içme", DENENMEDI, "", "/service/storefinder/", ""),
    ("Gloria Jeans", "Yeme-içme", DENENMEDI, "", "/store-finder", ""),
    ("Baydöner", "Yeme-içme", DENENMEDI, "", "/restoranlar", ""),
    ("Popeyes", "Yeme-içme", DENENMEDI, "", "/subeler", "Arby's ile aynı altyapı"),
    ("Arby's", "Yeme-içme", DENENMEDI, "", "/restoranlar", "Popeyes ile aynı altyapı"),
    ("Hatemoğlu", "Yeme-içme", DENENMEDI, "", "/magazalarimiz", ""),
    ("Özsüt", "Yeme-içme", DENENMEDI, "", "/tr/magazalar", ""),
    ("Tavuk Dünyası", "Yeme-içme", DENENMEDI, "", "", "robots yok (404)"),
    ("Little Caesars", "Yeme-içme", DENENMEDI, "", "", "site yanıtı yarım"),
    ("Pizza Hut", "Yeme-içme", DENENMEDI, "", "", "zaman aşımı"),
    ("Caribou", "Yeme-içme", DENENMEDI, "", "", "robots yok (404)"),
    ("Arabica, Coffy", "Yeme-içme", DENENMEDI, "", "", ""),
    ("Metro Grossmarket", "Market", DENENMEDI, "", "", ""),
    ("Carrefour Express", "Market", DENENMEDI, "", "", "CarrefourSA robots 403"),
    ("Hertz, Thrifty, Dollar", "Oto kiralama", DENENMEDI, "", "", ""),
    ("Green Motion", "Oto kiralama", DENENMEDI, "", "", ""),
    ("Çizgi Rent a Car", "Oto kiralama", DENENMEDI, "", "", ""),
    ("Otomobil bayileri", "Otomotiv", DENENMEDI, "", "", "Renault, Fiat, Toyota…"),
]  # fmt: skip


def labels() -> dict[str, dict[str, str]]:
    cat = tomllib.loads(CATALOG.read_text("utf-8"))
    out = {}
    for dim, spec in cat.get("dim", {}).items():
        values = spec.get("values", {})
        out[dim] = {
            k: (v["label_tr"] if isinstance(v, dict) else v) for k, v in values.items()
        }
    return out


def warehouse_rows() -> list[dict]:
    names = labels()
    fact = pl.scan_parquet(PUBLIC / "fact.parquet")
    ids = list(INDICATORS) + [
        "bank_branch_locations",
        "bank_atm_locations",
        "pharmacies",
        "fuel_stations",
        "charging_stations",
    ]
    counted = (
        fact.filter(pl.col("indicator_id").is_in(ids) & (pl.col("value") > 0))
        .group_by("indicator_id", "dims", "area_level")
        .agg(
            pl.col("value").sum().alias("stores"),
            pl.len().alias("areas"),
            pl.col("retrieved_at").max().alias("date"),
        )
        .collect()
    )
    by = {}
    for r in counted.iter_rows(named=True):
        by.setdefault((r["indicator_id"], r["dims"]), {})[r["area_level"]] = r

    def row(ind, dims, brand, category, method, note, stores=None):
        levels = by[(ind, dims)]
        prov, dist = levels.get("province"), levels.get("district")
        date = (prov or dist)["date"]
        return {
            "brand": brand,
            "category": category,
            "status": DEPODA,
            "stores": int(stores if stores is not None else prov["stores"]),
            "provinces": prov["areas"] if prov else None,
            "districts": dist["areas"] if dist else None,
            "indicator": ind,
            "method": method,
            "note": note,
            "date": str(date)[:10] if date else "",
        }

    rows = []
    for (ind, dims), _ in sorted(by.items()):
        if ind not in INDICATORS:
            continue
        dim, _, key = dims.partition("=")
        category, method = INDICATORS[ind]
        if ind == "chain_stores":
            category = STORE_KIND.get(key, "Market")
        m, note = NOTES.get((ind, key), (method, ""))
        rows.append(row(ind, dims, names.get(dim, {}).get(key, key), category, m, note))
    # banks: one row each, branches counted, ATMs in the note
    for (ind, dims), _ in sorted(by.items()):
        if ind != "bank_branch_locations":
            continue
        key = dims.partition("=")[2]
        atm = by.get(("bank_atm_locations", dims), {}).get("province")
        note = f"ATM {int(atm['stores']):,}".replace(",", ".") if atm else "ATM yok"
        rows.append(
            row(
                ind,
                dims,
                names.get("bank", {}).get(key, key),
                "Banka",
                "şube ve ATM bulucu",
                note,
            )
        )
    for ind, brand, category, method, note in [
        ("pharmacies", "Eczaneler", "Eczane", "TİTCK ruhsat kaydı", "resmî ve tam liste"),
        ("fuel_stations", "Akaryakıt istasyonları", "Akaryakıt", "EPDK lisans kaydı", "32 dağıtıcı birlikte"),
        ("charging_stations", "Şarj istasyonları", "Şarj", "EPDK lisans kaydı", "resmî ve tam liste"),
    ]:  # fmt: skip
        dims = next(d for (i, d) in by if i == ind)
        total = sum(v["province"]["stores"] for (i, _), v in by.items() if i == ind)
        r = row(ind, dims, brand, category, method, note, stores=total)
        # Several brands in one row: count the areas any of them reaches, once each.
        for level, column in (("province", "provinces"), ("district", "districts")):
            r[column] = (
                fact.filter(
                    (pl.col("indicator_id") == ind)
                    & (pl.col("area_level") == level)
                    & (pl.col("value") > 0)
                )
                .select(pl.col("area_id").n_unique())
                .collect()
                .item()
            )
        rows.append(r)
    return rows


def all_rows() -> list[dict]:
    rows = warehouse_rows()
    for brand, category, status, stores, method, note in OFF_WAREHOUSE:
        rows.append(
            {
                "brand": brand,
                "category": category,
                "status": status,
                "stores": stores if stores != "" else None,
                "provinces": None,
                "districts": None,
                "indicator": "",
                "method": method,
                "note": note,
                "date": "",
            }
        )
    return rows


def markdown(rows: list[dict], today: str) -> str:
    out = [
        "# Perakende ve hizmet ağları: durum",
        "",
        (
            f"**Bu dosya elle yazılmaz.** `scripts/build_retail_status.py` üretir ({today}). "
            "Depodaki satırlar `fact.parquet`'ten sayılır; depo dışındakiler betikteki "
            "`OFF_WAREHOUSE` listesindedir. Sıralanabilir sürüm: `perakende-durum.html`."
        ),
        "",
    ]
    for status in STATUSES:
        group = [r for r in rows if r["status"] == status]
        if not group:
            continue
        out += [f"## {status} ({len(group)})", ""]
        out += ["| Marka | Tür | Mağaza | İl | İlçe | Yöntem | Not |", "|---|---|---|---|---|---|---|"]  # fmt: skip
        for r in sorted(group, key=lambda r: (r["category"], -(r["stores"] or 0))):
            cells = [
                r["brand"],
                r["category"],
                f"{r['stores']:,}".replace(",", ".") if r["stores"] else "",
                str(r["provinces"] or ""),
                str(r["districts"] or ""),
                r["method"],
                r["note"],
            ]
            out.append("| " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out)


def page(rows: list[dict], today: str) -> str:
    template = (ROOT / "scripts" / "retail_status_page.html").read_text("utf-8")
    data = json.dumps(
        {"rows": rows, "statuses": STATUSES, "today": today}, ensure_ascii=False
    )
    return template.replace("/*DATA*/null", data)


def main() -> None:
    today = dt.datetime.now(tz=dt.UTC).astimezone().strftime("%d.%m.%Y")
    rows = all_rows()
    (DOCS / "perakende-durum.md").write_text(markdown(rows, today), "utf-8")
    (DOCS / "perakende-durum.html").write_text(page(rows, today), "utf-8")
    counts = {s: sum(r["status"] == s for r in rows) for s in STATUSES}
    print(len(rows), "satır", counts)


if __name__ == "__main__":
    main()
