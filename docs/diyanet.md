# Diyanet İşleri Başkanlığı istatistikleri

Strateji Geliştirme Başkanlığı'nın istatistik sayfası
(`stratejigelistirme.diyanet.gov.tr/sayfa/57/istatistikler`) on bir Excel dosyası veriyor:
personel (1.1-1.3), cami (2.1-2.2), Kur'an kursu (3.1-3.3), ihtida (4.1), hac-umre (5.1),
bütçe (6.1). Sayfada yalnız 2023 yayımı var; tabloların içinde manşet seriler 2013-2023,
il kırılımları 2023.

- İndirme: [`scripts/fetch_diyanet.py`](../scripts/fetch_diyanet.py) → `C:\veri-ham\diyanet`.
- Adaptör: [`src/veriatlas/adapters/diyanet.py`](../src/veriatlas/adapters/diyanet.py).
- 13 gösterge, 2.589 satır; konu `din`.

## İl düzeyi

İl tabloları **İBBS-3. düzey** ile basılı. Her düzey-3 bölgesi tek bir il olduğu için (TR100
İstanbul, TR622 Mersin…) veriler il düzeyine yazıldı; ayrı bir `nuts3` alan düzeyi açılmadı.
Cami tablosu (2.2) illeri sayfada yan yana iki sütun blokunda yazıyor, bu yüzden bölge kodu
A sütununda değil her hücrede aranıyor.

## Denetimler

Her yüklemede çalışan üç sınama var ve hepsi tutuyor:

- İl değerlerinin toplamı, aynı tablonun basılı Türkiye satırına eşit (cami 89.676; kurs
  16.921; kursiyer 806.785).
- Kadrolu + sözleşmeli = toplam personel, 2013-2023'ün her yılı için.
- Kur'an kursunu bitirenler, cinsiyete, eğitim durumuna ve yaş grubuna göre aynı toplama
  çıkıyor (747.424).
- Hac ve umreye gidenler, yaş gruplarının toplamı basılı toplama eşit; bütçede dört kalem
  genel toplama eşit.

## Bilinen sınırlar ve tuzaklar

- **İki farklı personel evreni.** 1.1 tüm Başkanlığı sayıyor (2023: 140.185), 1.3 yalnız
  il/ilçe müftülüklerini (136.384). Türkiye serisi 1.1'den, il verileri 1.3'ten geliyor.
- **İl satırlarının "genel toplam"ı genel idare hizmetleri personelini saymıyor**: illerin
  toplamı 127.194, üstüne genel idare 9.190 eklenince tablonun Türkiye satırı (136.384)
  çıkıyor. Bu yüzden `staff_group=total` ile `general_admin` ayrı duruyor ve denetim bu
  kimlik üzerinden yapılıyor.
- **2023'te sözleşmeli sayısı 33.436'dan 7.910'a düşüyor**, kadrolu 107.782'den 132.275'e
  çıkıyor: kadro geçişi, gerçek bir personel azalması değil. Toplam (141.218 → 140.185)
  neredeyse aynı.
- Çekilmeyenler: 1.2 (öğrenim durumuna göre personel, yalnız Türkiye ve yüzde sütunları
  bozuk), 3.1-3.2 (yerleşim yeri ve mülkiyete göre kurs sayısı — yalnız Türkiye; `settlement`
  kırılımı açılması gerekirdi), 2.2'nin yanındaki açıklama notları.
- Seri 2013'te başlıyor, daha eski yıl yayımlanmıyor; 2024 yayımı henüz yok.
