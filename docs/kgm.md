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

## Wayback Machine kopyaları: il envanteri yıllara göre (2026-09-14)

KGM il bazındaki yol envanterini her yıl aynı adla üzerine yazıyor. Wayback Machine
`IllereGoreDevletVeIlYollari.pdf`'in 9 farklı sürümünü tutmuş; `scripts/fetch_kgm_wayback.sh`
indiriyor (`C:\veri-ham\kgm\wayback\`, arşiv kapalıysa bekleyip yeniden dener). Ayrı devlet
yolu / il yolu tabloları arşivde yok.

Yıllar (yıl sonu): 2009, 2011, 2014, 2016, 2017, 2020, 2021, 2022, 2025. Göstergeler
`road_length_by_surface_province`, `divided_road_length_province`. Denetim: il toplamı her
yıl güncel yıllıktaki Türkiye serisine eşit.

Tuzaklar: 2010 ve 2012 dosyalarında il yerine merkez adı (İZMİT, ADAPAZARI); 2010 dosyasının
yazı tipinde Ş harfi `6` basılı (`ESKİ6EHİR`, `6ANLIURFA`) — okunmadan 9 il sessizce düşüyordu,
81 il denetimi yakaladı.

## Wayback ile tamamlananlar (2026-09-15)

| Gösterge | Yıllar | Kaynak |
|---|---|---|
| `road_distance_between_provinces` | 2010-2018, 2026 | `ilmesafe.xls` 17 kopya + güncel xlsx |
| `road_length_by_surface`, `divided_road_length` (devlet/il yolu ayrı) | 2009, 2011, 2014, 2016, 2017, 2020-2022, 2024, 2025 | `IllereGoreDevletYollari` 11 + `IllereGoreIlYollari` 10 kopya |
| `kgm_vehicle_km`, `kgm_passenger_km`, `kgm_tonne_km` (il × otoyol/devlet/il yolu) | 2012-2025 | Trafik ve Ulaşım Bilgileri ciltleri |
| `traffic_accidents_total`, `traffic_casualties` (Türkiye) | 2006-2016 | Trafik Kazaları Özeti 2015/2016 kopyaları |

Tuzaklar: eski cetvelde `AFYON`, sağ kenarda tekrar eden `İL ADI`/`İL NO` sütunları; il
yolu 2010 dosyasında Ş `(cid:3)`; 2015 il yolu ilk kopyası satır toplamı tutmuyor (sonraki
kopya alınır); il taşıt-km'de `D.BAKIR` kısaltması ve 2016 il yolu cildinde boş bırakılan
otoyol hücresi (üç sayı eksik satır); güncel kaza özetinde Tablo 1.1 çizim, metin değil;
2009-2011 özetleri EGM+Jandarma sayımı (2008'den anlaşmalı maddi hasarlılar hariç), TÜİK
serisiyle karıştırılmadı; 2015'te ölü sayısı 30 gün içinde ölenleri katınca iki katına çıkıyor.

Çekilemeyen: güncel kaza özeti tablolarının çoğu (çizim); tünel envanteri bölge müdürlüğü
düzeyinde (alan düzeyi yok); otoyol kesim trafiği kesim adıyla basılı, ile eşleme yok.
Veri Portalı dosyaları tarayıcı dışından indirilemiyor (`Erişim engellendi`); tarayıcı paneli
yerel adrese de gönderemiyor — `scripts/receive_browser_files.py` bu yüzden kullanılamadı.
