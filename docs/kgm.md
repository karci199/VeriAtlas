# KGM (Karayolları Genel Müdürlüğü) — site envanteri ve belgeler

Durum 2026-09-14: **depoya hiçbir şey yüklenmedi.** Envanter çıkarıldı, sayısal belgelerin
bir kısmı indirildi, iki PDF okundu.

## Akış

1. `scripts/crawl_kgm_site.py` — www.kgm.gov.tr Türkçe sayfaları gezer (robots.txt yok),
   sayfa ve belge bağlantısı listesi yazar: `C:\veri-ham\kgm\site_pages.csv` (~1.000 sayfa),
   `site_documents.csv` (2.597 belge, neredeyse hepsi PDF).
2. `stat_documents.csv` — istatistik/trafik/yayın/faaliyet raporu sayfalarındaki 431 belge
   (elle filtrelendi, betik değil; yeniden üretmek için site_documents.csv'yi `page` sütununa
   göre süz).
3. `scripts/fetch_kgm_documents.py` — sayısal belgeleri indirir, `C:\veri-ham\kgm\pdf\<sayfa>\`.
   Kullanıcı isteğiyle yarıda durduruldu: 75 dosya, 1,9 GB. Yeniden çalıştırınca inenleri atlar.

## Değerli belgeler

| Belge | Kapsam | Not |
|---|---|---|
| Trafik Kazalarına Ait Özet Bilgiler 2025 | TR geneli + KGM ağı (otoyol/devlet/il yolu), 2016-2025 | metin tablosu okunuyor; bazı tablolar döndürülmüş, harf harf dağılıyor |
| Karayolu Ulaşım İstatistikleri 2025 | yol ağı 1923-, taşıt-km/ton-km/yolcu-km 1950-, AOGT, taşıt, ulaşım türü payları | metin tablosu okunuyor |
| Trafik ve Ulaşım Bilgileri 2013-2025 (+ il yolları ciltleri) | kesim bazında trafik sayımı | 35-120 MB PDF, henüz açılmadı |
| Devlet ve İl Yolu Envanteri, Otoyol, Köprü/Tünel envanteri | il/yol | indirildi mi kontrol et |
| Bakım-İşletme Maliyetleri (yıllık, 5 yıllık 1999-) | | |
| İller ve ilçeler arası mesafe cetveli | il × il, ilçe × ilçe | |
| Faaliyet raporları 2006-2025, anketler, ağır taşıt raporları 2007-2020 | | |

Düşük değer (indirilmedi): ~1.500 aylık mali tablo PDF'i, teknik rehberler, bildiriler,
trafik hacim haritaları (görsel).

## İlk okunan sayılar (2025)

- TR: 1.549.574 kaza, 288.321 ölümlü/yaralanmalı, 6.035 ölü (2.541 olay yeri, 3.494 30 gün
  içinde); ölümlü-yaralanmalı kazaların %86,5'i yerleşim yeri içinde.
- Milyon kişi başına ölü: TR 70, Almanya 34, Fransa 46; milyon otomobil başına TR 347, Almanya 58.
- KGM ağı 68.617 km (3.796 otoyol, 30.789 devlet, 33.932 il yolu). Ölümlerin ~%70'i devlet
  yollarında (2.214). Otoyol kazası 2020'de 3.742, 2025'te 6.910.
- Kusur: %94-97 sürücü. 100 milyon taşıt-km başına ölü 2016'da 1,85, 2025'te 0,98.
- Yük ton-km'nin ~%90'ı karayolunda.

## Sıradaki

1. İndirmeyi tamamla (`fetch_kgm_documents.py`).
2. Kaza özeti ve ulaşım istatistikleri tablolarını pdfplumber ile çıkar; döndürülmüş sayfalar
   için sayfa döndürme ya da kelime koordinatları.
3. Trafik ve Ulaşım Bilgileri ciltlerinin yapısına bak (il/kesim düzeyi mi).
4. Mesafe cetvelleri (il × il) — ayrı gösterge türü, K kararı gerekebilir.
