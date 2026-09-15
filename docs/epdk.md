# EPDK — enerji piyasası il verisi

Durum 2026-09-15: 2025 Gelişim Raporu Excel ekleri **depoda** (`adapters/epdk.py`, 6 gösterge).

## Akış

1. `raw/epdk/envanter.tsv` — elektrik, doğalgaz, petrol, LPG, enerji dönüşümü, şarj rapor
   sayfalarındaki 507 belge bağlantısı (sayfalar düz HTML, `curl`/`httpx` yeter).
2. `scripts/fetch_epdk_documents.py` — hepsini `raw/epdk/files/<piyasa>/<id>.<uzantı>` olarak
   indirir (492 belge, 1,25 GB): Excel eki, Word ve PDF raporlar, aylık resmi istatistikler.

## Depoda

| Gösterge | Kapsam | Denetim |
|---|---|---|
| `epdk_electricity_consumption`, `_consumers` | il × tüketici türü, 2024-2025 | tür → il toplamı, il → genel toplam |
| `epdk_natural_gas_sales` | il × sektör (Sm3), 2025 | şirket satırları → il TOPLAM |
| `epdk_natural_gas_subscribers` | il, abone / serbest tüketici, 2025 | şirketler → il, iller → genel toplam |
| `epdk_fuel_sales` | il × ürün (ton), 2025 | ürünler → il toplamı, iller → Türkiye |
| `epdk_lpg_sales` | il × tüplü/dökme/otogaz (ton), 2025 | türler → il, iller → Türkiye |

## Tuzaklar

- Genel toplam satırının il hücresi boş; il adını aşağı taşıyan okuyucu onu son ile (Bayburt)
  yazar — Bayburt Türkiye kadar elektrik tüketir görünür (test: `test_epdk.py`).
- Doğalgaz Tablo-13'ün son bloğu `DİĞER`: iletim şebekesi ve depolamada kullanılan gaz, il yok.
- Elektrik Excel'i ile PDF il tablosu 66/69 ilde aynı. Yalova: Excel yalnız dağıtım (iletim
  bağlantılı 44 GWh yok). Yozgat: Excel 876, PDF dağıtım 832 + iletim 1.059 GWh — tutmuyor.
- TÜİK il elektrik tüketimi ile oran ortancası 1,07; Çanakkale 2,17, Karabük 1,73, Yalova 1,60
  (iletim bağlantılı sanayi/santral farklı sayılıyor). Ayrı gösterge, karıştırma.
- Faturalanan tüketim: Şırnak mesken 2023→2025 %80 artış, abone %5 — faturalamanın sıkılaşması.

## Sıradaki

Aylık resmi istatistik Excel'leri (2024-2026: il × kaynak kurulu güç, iletim-dağıtım kırılımlı
tüketim, serbest tüketici) ve Word/PDF raporlardan 2014-2023 il tabloları (doğalgaz il tüketimi,
akaryakıt il satışı, LPG il satışı).
