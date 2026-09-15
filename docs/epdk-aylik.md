# EPDK aylık il serileri

`src/veriatlas/adapters/epdk_monthly.py`. Kaynak: EPDK resmi istatistik sayfaları (3-0-166
doğalgaz, 3-0-168 petrol, 3-0-169 LPG), aylık sektör raporları. İndirme:
`scripts/fetch_epdk_documents.py dogalgaz_resmi petrol_resmi lpg_resmi`. Web'e aktarılmaz,
yalnız depoda.

| Gösterge | Kırılım | Dönem | Kaynak tablo |
|---|---|---|---|
| `epdk_natural_gas_consumption_monthly` | il × temin şekli (m3) | 2015-01 – 2025-12 | Word, Tablo 5.2 |
| `epdk_fuel_sales_monthly` | il × ürün (ton) | 2016-02 – 2025-11 | Word, Tablo 3.1 |
| `epdk_lpg_sales_monthly` | il × ürün (ton) | 2011-08 – 2025-12, boşluklu | Word Tablo 3.9 / 4.7 / 3.8; 2011-2016 PDF |

Her tablo satır toplamına ve Türkiye toplamına karşı sınanır; 12 ayın toplamı yıllık raporla
karşılaştırıldı (en büyük fark %0,5).

## Eksik aylar

- Doğalgaz: 2017-10 (sayfada Eylül 2017 raporu iki kez; Ekim yok).
- Akaryakıt: 2016-01, 2025-12; 2011-2015 raporlarında il × ürün tablosu yok.
- LPG: 2011-09, 2012-12, 2013-02 – 2014-02 (sayfada bu aylara rapor dosyası bulunamadı).
  2009 – 2011-07 aylık raporlarda il tablosu yok. PDF okunurken düzeltilenler: Ekim 2012
  Konya toplam hücresinde bir rakam bozuk karakter (ürünlerden yeniden kuruldu), Mart 2015
  "KAHRAMANMA|RAŞ" iki satıra bölünmüş, 2016 tabloları üç sayfaya yayılıyor.

## Kaynak hataları (il değerleri kullanıldı)

- Doğalgaz 2016-05: satır ve Türkiye toplamlarına "CNG Diğer" eklenmemiş.
- Doğalgaz 2019-01: Ankara satır toplamı 648,585 basılmış, sütunlar 649,785 veriyor.
- LPG 2019-05, 2021-04: basılı Türkiye toplamı illerin toplamı değil; il payları il
  toplamına göre hesaplanmış, o yüzden il değerleri doğru kabul edildi.

## Alınmayanlar

- Petrol teslim türü (bayiye / serbest kullanıcıya / diğer) il × şirket: Excel yalnız
  2024-09 – 2025-12.
- LPG il × şirket × ürün: Excel yalnız 7 ay.
- Doğalgaz il × şirket × sektör (aylık bölüm 8), abone sayıları (aylık Tablo 5.3).
- Şarj: EPDK il kırılımı yayımlamıyor; resmi istatistik sayfası boş.

## Son notlar (2026-09-15)

- EPDK kapandı: yıllık il serileri (elektrik 2016-2025, doğalgaz 2015-2025, akaryakıt
  2015-2025, LPG 2006-2025, kurulu güç) ve aylık il serileri (doğalgaz, akaryakıt, LPG) depoda.
- Zorluk kaynağın biçimindeydi: PDF'te boş hücre ve sütun kaybı, yıldan yıla değişen tablo
  adları, sayfaya bölünen tablolar, bozuk karakterler ve EPDK'nın kendi baskı hataları.
- Ders: yeni kaynağa başlamadan 5 dakikalık keşif (API / Excel / Word / PDF, yıl kapsamı, biçim
  değişimi) ve "kolay / orta / zor" kararı; PDF zor çıkarsa baştan atlanabilir.
- Her tablo basılı toplamlara karşı sınanır; tutmayan ay yüklenmez, nedeni burada yazılır.
