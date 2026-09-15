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

## Kayıp / alınmayan (zor olanlar)

- **Mobil abone, işletmeci bazında çeyreklik 2008-2025** ve ön ödemeli/faturalı kırılımı:
  girdi CSV'si (`mobil_abone_isletmeci.csv`) 2026-09 worktree temizliğinde silindi; grafik
  etiketlerinden PDF'lerden yeniden okunmalı (`scripts/btk_mobile_dataset.py` payları taşıyor).
- Numara taşıma, sektör geliri, sabit telefon abonesi (2009-2025): eski notta çıkarılmıştı,
  betikleri dalda yok, CSV'leri kayıp.
- ARPU ve genişbant gelirinin USD/EUR/reel sürümleri: ECB, Eurostat, FRED indirmesi gerekir
  (`scripts/build_quarterly_macro.py`); depoda nominal TL var, EVDS kur/TÜFE ile çevrilebilir.
- Adaylar (eski not): yatırımlar, işletmeci gelirleri, fiber uzunluğu, şikâyetler, uydu/kablo/IPTV,
  SMS/MMS (metin katmanında, kolay); churn, MoU, hız dağılımı (grafik, zor).
- 2026-Q1 raporunda "GİZLİ — SADECE KURUM İÇİ" damgalı sayfalar (82, 86): kullanıcı kararı bekliyor.

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

Sitenin geri kalanında (iletişim hizmetleri istatistikleri, IMEI, posta sektörü, yıllık pazar bülteni, faaliyet raporları) yalnız PDF var. Çeyreklik pazar raporları zaten işlendi.
