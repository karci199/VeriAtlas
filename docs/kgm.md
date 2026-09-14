# KGM (Karayolları Genel Müdürlüğü) — site envanteri ve belgeler

Durum 2026-09-14 (akşam): mesafeler, yol uzunlukları, otoyol ve köprüler **depoda**
(`adapters/kgm.py`, 8 gösterge, 1,01 mn satır). Trafik ve Ulaşım Bilgileri ciltleri henüz okunmadı.

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

## Depoya yüklenenler (2026-09-14)

| Gösterge | Kapsam | Denetim |
|---|---|---|
| `road_distance_between_provinces` | 81 × 80 il, Mart 2026 | simetrik; büyükşehir merkez noktaları ilçe cetveliyle 870/870 aynı |
| `road_distance_between_districts` | 1.003 × 1.002 yer | tam kare; köşegen iki kez basılı (0), atıldı |
| `road_length_by_surface` | il × devlet/il yolu × kaplama, 01.01.2026 | satır toplamları ve devlet + il = birleşik tablo, 81 il |
| `divided_road_length` | il × yol sınıfı | |
| `road_length_history` | TR, kaplama türü, 1967-2025 | binlik ayırıcı boşluk: satır toplamını tutan tek bölünme aranır |
| `motorway_length` | il (28), 2000-2025 | il toplamı her yıl Türkiye toplamına eşit |
| `bridges`, `bridge_length` | TR × yol sınıfı × malzeme, 2002-2024 | aşağıdaki iki kaynak hatası |

Tuzaklar:

- İlçe cetvelinde `MERKEZ`: 51 ilde il adını taşıyan merkez ilçe; 30 büyükşehirde ilçe
  değil, il merkezi noktası — il düzeyinde (`TR-06`) saklandı. Eyüp → Eyüpsultan,
  Ondokuzmayıs → 19 Mayıs.
- İl cetveli başlığında `KOCAELİ (İZMİT)`; otoyol tablosunda `K.Maraş`, `Ş.Urfa`.
- Köprü PDF'inde birleşik tablonun 2023 satırı 2024'ün kopyası (devlet 6.165 + il 2.045 ≠
  8.189); il yolu 2014 malzeme toplamı tutmuyor. Parçalar saklandı, basılı toplam değil.
- Tünel envanteri **bölge müdürlüğü** düzeyinde; alan düzeyi olmadığı için yüklenmedi.
- Viyadük ayrı sayılmıyor, köprü envanterinin (büyük sanat yapısı) içinde.
- Trafik ve Ulaşım Bilgileri PDF'lerinde harita sayfalarının fontu bozuk (`cid:`); tablo sayfaları okunuyor.
- Düşük değerli belgeler (bakım maliyeti, faaliyet raporu, anket) kullanıcı kararıyla işlenmeyecek.
