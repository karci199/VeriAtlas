# BTK elektronik haberleşme

Kaynak: BTK "Türkiye Elektronik Haberleşme Sektörü Üç Aylık Pazar Verileri" raporları,
PDF 2009 … 2026-Q1 (masaüstü `Analiz/Elektronik Haberleşme`). Transkripsiyon betikleri
`scripts/btk_*_dataset.py` (ilk olarak `claude/elektronik-haberlesme-datasets-2aee0f` dalında),
çıktı CSV'leri `C:\veri-ham\btk`, adaptör `src/veriatlas/adapters/btk.py`. Türkiye geneli;
BTK il kırılımı yayımlamıyor.

| Gösterge | Kırılım | Dönem |
|---|---|---|
| `btk_internet_subscribers` | teknoloji (xDSL, kablo, FTTH, FTTB, sabit kablosuz, mobil) | yıl sonu 2008-2025, 2026-1 |
| `btk_fixed_broadband_revenue` | — | 2020-2025 |
| `btk_fixed_voice_lines` | TT / alternatif × PSTN, ISDN, VoIP, ankesör | çeyreklik 2014-4 … 2026-1 |
| `btk_call_minutes` | mobil / sabit | 2009-2025 |
| `btk_turk_telekom_traffic` | arama yönü | çeyreklik 2014-4 … 2026-1 |
| `btk_mobile_traffic_by_operator` | işletmeci | çeyreklik 2024-1 … 2026-1 |
| `btk_m2m_subscribers` | — | yıllık 2011-2025, çeyreklik 2024-1 … 2026-1 |
| `btk_mobile_arpu` | işletmeci × ön ödemeli / faturalı, cari TL/ay | çeyreklik 2011-1 … 2026-1 |

## Kontroller

- `tests/test_btk_*.py`: örtüşen rapor pencereleri ikinci okumayla karşılaştırılır, bileşenler
  toplamı tutar; 286 test geçer. ARPU'nun kur/reel çevrim testleri `raw/ref/makro_ceyreklik.csv`
  olmadan atlanır, transkripsiyon testleri çalışır.
- Genişbant: 2014'ten sonra basılı "fiber" = FTTH + FTTB; çift sayılmasın diye yalnız 2010-2013'te
  tutulur, her yıl parçalar TOPLAM'ı verir.
- BTK geçmiş çeyrekleri sessizce düzeltir: her dönem onu basan en yeni rapordan.

## 2026-09-16 eklenenler (sitedeki PDF'lerden)

PDF'ler `scripts/fetch_btk_pdfs.py` ile `C:\veri-ham\btk\pdf\<sayfa>` altına indi. Pazar
raporlarının metin katmanı sayfa sayfa `C:\veri-ham\btk\pdf\text\<rapor>.json` dosyalarında.
Sitede 67 pazar raporu var; 2018-Q2 ve 2018-Q4 yok.

| Gösterge | Kaynak | Dönem |
|---|---|---|
| `btk_mobile_arpu_usd`, `btk_mobile_arpu_real` | ARPU ÷ çeyrek ortalama dolar kuru; × TÜFE oranı (depodaki EVDS) | 2011-1 … 2026-1 |
| `btk_operators`, `btk_sector_revenue`, `btk_sector_investment`, `btk_subscribers_summary`, `btk_messages`, `btk_minutes_of_use`, `btk_arpu_summary`, `btk_data_traffic`, `btk_data_per_subscriber`, `btk_fiber_length` | yıl sonu raporu "Özet Bilgiler" tablosu (`btk_summary.py`) | yıllık 2012-2025 |
| aynıları `_quarterly` sonekiyle (fiber ve SMS hariç) | İletişim Hizmetleri İstatistikleri, çeyreklik tek sayfa | 2015-4 … 2026-1 |
| `btk_imei_*` (ithalat, imalat, yolcu, mahkeme kapama, çalıntı ihbar, çağrı merkezi) | IMEI istatistikleri PDF'leri (`btk_imei.py`) | yıllık 2007-2015 |
| `btk_operator_revenue`, `btk_operator_investment` | çizelge: TT, Turkcell, Vodafone, TT Mobil | çeyreklik 2010-1 / 2012-1 … 2026-1 |
| `btk_other_operator_revenue` (yetkilendirme türüne göre), `btk_other_operator_investment` | çizelge | çeyreklik 2012-1 … 2026-1 |
| `btk_consumer_complaints` | çizelge, sektöre göre | çeyreklik 2014-1 … 2026-1 |
| `btk_pamr*`, `btk_directory_*`, `btk_cable_services`, `btk_satellite_*`, `btk_gmpcs_*`, `btk_fixed_telephony_revenue`, `btk_infrastructure_revenue`, `btk_satellite_platform_revenue` | çizelgeler (`btk_tables.py`) | çeyreklik 2011/2012 … 2026-1 |
| `btk_fiber_alternative*` (eski tanım), `btk_fiber_operators*` (2022'den geniş tanım) | çizelge, sahiplik ve omurga/erişim | çeyreklik 2014-1 … 2025-4 / 2019-1 … 2025-3 |
| `btk_mobile_broadband_tech` | 3G/4.5G abone, mobil internet, TB | çeyreklik 2011-3 … 2026-1 (boşluklu) |
| `btk_carrier_selection`, `btk_messages_by_operator` | çizelge | çeyreklik 2014-1 … 2026-1 |

### Kontroller

- **İki kaynak karşılaştırması:** Çizelgelerdeki işletmeci geliri ile diğer işletmeci gelirinin
  toplamı, çeyreklik özet sayfasındaki sektör geliriyle karşılaştırıldı. 2015-4 ile 2026-1
  arasındaki 41 çeyreğin 35'inde fark %0,05'in altında. Sapmalar:
  - 2021-4, 2022-3, 2025-1: yaklaşık %0,3.
  - 2018-3: %2.
- **M2M:** Özet tablodaki M2M, eski `btk_m2m_subscribers` serisiyle her yıl birebir aynı.
- **Genişbant:** Özet tablolarda genişbant parçaları, her rapor ve her sütunda basılı toplamı veriyor.
- **Basılı toplam hataları:** BTK'nın kendi toplamları bazen satırları tutmuyor. Bunlar kodda
  listelendi; toplamlar değil satırlar yüklendi:
  - Diğer işletmeci geliri 2012'de %2-7 fazla (listede olmayan bir tür).
  - Şikâyet 2024-1'de +90.
  - IMEI tablolarında 6 hücre.
  - 2021-3/4 raporlarında 2021-1 fiber satırı.
- **Geriye dönük düzeltmeler:** BTK geçmiş dönemleri düzeltiyor; her dönem onu basan en yeni
  rapordan alındı. Büyük düzeltmeler:
  - 2014 sektör geliri 35,5 milyardan 33,7 milyara.
  - 2024-1 Türk Telekom ARPU'su 79,5'ten 112,8'e.
  - 2019-1 M2M 6,69 milyondan 5,30 milyona.
- **Okunamayan raporlar:**
  - 2019 raporları ve 2020-Q2 dergi düzeninde; tablolar satır olarak çıkmıyor.
  - 2021-Q1 kodlanmış fontla basılmış.
  - Bu yüzden 2018-4 çeyreği çizelgelerde yok.
- **Metin katmanı bozuklukları:** Kesik hane ("5.945.413.12") ya da kaymış hücre içeren satır o
  raporda atlandı. Aynı dönem komşu rapordan geliyor ve o raporda toplam kontrolü yapılmadı.

## Kalanlar (zor, sonraya)

- **Mobil abone, işletmeci bazında 2008-2025** ve ön ödemeli/faturalı kırılımı: yalnız grafikte
  var. Eski CSV kayıp; etiketler sayfa render edilip okunmalı. Toplam mobil abone yıllık
  2012+ ve çeyreklik 2015-4+ özetten depoda.
- **Numara taşıma:** yalnız grafikte.
- **Sektör geliri ve sabit abone 2009-2011:** özet tablo 2012'den başlıyor; öncesi grafikte.
- **Grafik-only diğerleri:** churn, AB ülkeleriyle MoU karşılaştırması, hıza göre genişbant, mobil
  gelir kırılımı (UFRS/VUK), faturalı/ön ödemeli mobil genişbant.
- **Yıllık gelir tabloları:** 2019-2020 raporlarında UFRS/VUK ayrımıyla basılı. Çeyreklik seri
  depoda olduğundan yüklenmedi.
- **Pazar payı tabloları** (STH, İSS, uydu, GMPCS, rehberlik, altyapı, posta): yüzde, işletmeci
  adları değişken; yüklenmedi.
- **Sıralama tabloları:** en çok aranan kısa numaralar, en çok trafik alan ülkeler.
- **Nitelikli e-imza sertifikaları ve KEP hesapları:** başlıkları çok satırlı; 2016-2026 arası orta
  zorlukta.
- **Posta sektörü raporları** (2021-1 … 2025-2, 6 aylık): şube, gönderi, kargo, gelir, istihdam,
  yatırım, şikâyet. Rakamlar grafik etiketinde; x konumuna göre dönemle eşleştirilmeli (orta).
- **Gizli damga:** 2024-Q2, 2024-Q3, 2025-Q1…Q3 ve 2026-Q1 raporlarında bazı sayfalar "GİZLİ — SADECE
  KURUM İÇİ" damgalı (rehberlik, uydu payları, fiber uzunluğu). Karar verilene kadar bu sayfalar
  okunmuyor; dönemler komşu raporlardan geliyor. Bu yüzden `btk_fiber_operators` 2025-3'te bitiyor.

## Yıllık İl İstatistikleri (depoda, 2026-09-15)

Kaynak: btk.gov.tr/yillik-il-istatistikleri. 14 Excel dosyası var, her biri altı yıllık bir pencere (2007-2012 … 2020-2025). Ham dosyalar `C:\veri-ham\btk\il` klasöründe. Adaptör: `src/veriatlas/adapters/btk_province.py`. Yüklenen göstergeler (hepsi `btk_province_*`):

- sabit hat
- santral kapasitesi
- ankesör
- mobil abone: toplam ve nesle göre
- genişbant: fiber, xDSL, kablo, diğer, mobil bilgisayar, mobil cep
- kablo TV
- fiber km
- 4.5G kapsama

Nasıl okundu, nelere dikkat:

- **Yıl seçimi:** BTK geçmiş yılları düzeltiyor. Her yıl, onu basan en yeni dosyadan alındı; aynı yıla ait eski ve yeni dosyalar arasında 4.666 hücre farkı var.
- **Sabit hat:** TOPLAM satırı illerin toplamından yılda yaklaşık 300 bin hat fazla; bu hatlar hiçbir ile dağıtılmamış. "Diğer" genişbantta aynı fark yaklaşık 24 bin.
- **Basılı toplamlar:** Dosya başına 1-6 il-yılda BTK'nın basılı genişbant toplamı parçaların toplamını tutmuyor (örnek: İstanbul 2011'de +15 bin, Tunceli 2020'de +2 bin). Toplamlar yüklenmedi, parçalar yüklendi.
- **Nüfus:** yüklenmedi, depoda TÜİK ADNKS zaten var.
- **Veri başlangıçları:**
  - Genişbantın il dağılımı 2011'den başlıyor.
  - 2G ayrımı 2010'dan başlıyor.
  - Kablo TV yalnız 25 ilde var.
  - 4.5G kapsama yalnız 2025 için basılı.

