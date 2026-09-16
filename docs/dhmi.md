# DHMİ — havalimanı istatistikleri (depoda, 2026-09-16)

Kaynak: dhmi.gov.tr istatistik sayfası. Her ay için tek Excel; yıl sekmeleri JavaScript ile
dolduğu için HTML'de yalnız o yılın bağlantıları var. Dosyalar düz bir yolda duruyor
(`/Lists/Istatislikler/Attachments/<id>/TÜMÜ.xlsx`) ve her dosya hangi döneme ait olduğunu
kendi başlığında yazıyor; arşiv bu yüzden numara tarayarak bulundu.

- İndirme: `scripts/fetch_dhmi.py` → `C:\veri-ham\dhmi` (212 dosya, 2008-2026).
- Adaptör: `src/veriatlas/adapters/dhmi.py`.
- Göstergeler: `dhmi_air_traffic` (uçak, tüm/ticari), `dhmi_air_passengers` (yolcu),
  `dhmi_air_freight` (yük = bagaj+kargo+posta, ve kargo). Hepsi iç hat / dış hat kırılımlı,
  havalimanı kırılımıyla il düzeyinde, aylık.
- Kapsam: 208 ay (2008-03 … 2026-08), 52 il, 58 havalimanı, 90.409 satır.

## Nasıl okundu

- Dosyalar **yıl başından o aya birikimli**. Aylık değer, önceki aydan çıkarılarak bulundu;
  ocak ayı birikimli değerin kendisi. Önceki ayı olmayan ay atlandı.
- Her ay **iki dosyada** basılı: kendi yılının dosyasında ve bir yıl sonraki dosyanın
  karşılaştırma sütununda. İkisi karşılaştırıldı; 2011 yılının dosyaları sitede olmadığı için
  o yıl yalnız karşılaştırma sütunundan geldi.
- Sayfa adları yıllara göre değişiyor ("TÜM UÇAK", "TUM_UCAK", "TÜM", "Sayfa1"), o yüzden
  sayfalar ilk hücredeki başlıktan tanınıyor.
- Havalimanı adları da değişiyor (Muş / Muş Sultan Alparslan, Balıkesir Körfez / Koca Seyit).
  `AIRPORTS` tablosu her adı tek bir havalimanı koduna ve ile bağlıyor.

## Kontroller ve bulunan tutarsızlıklar

- **Raporlar arası fark:** 96.042 birikimli hücrenin 146'sında iki dosya farklı değer basıyor;
  neredeyse hepsi 2016 Mayıs yük verisinin sonradan revize edilmesinden. En yeni dosya esas alındı.
- **İç + dış ≠ toplam:** 38 hücrede DHMİ'nin bastığı toplam, iki parçanın toplamını tutmuyor
  (en büyüğü 2024 Mayıs İstanbul kargosunda %12). Toplam sütunu yüklenmedi, yalnız parçalar alındı.
- **Negatif ay:** Revizyon nedeniyle 88 ay (90.500 kaydın %0,1'i) negatif çıktı, atıldı.
- **Basılı "DHMİ TOPLAMI" satırı kullanılmadı:** İstanbul, Sabiha Gökçen, Zafer, Çaycuma,
  Gazipaşa, Çıldır ve Hasan Polatkan özel işletmeci tarafından işletildiği için o toplamın
  dışında tutuluyor; illerin toplamı bu satırla eşleşmez.
- **Çukurova havalimanı** Tarsus'ta, yani Mersin'de; DHMİ listesinde Adana'dan ayrı satır.
  Mersin iline yazıldı.

## Doğrulama örnekleri

- 2024 Türkiye toplamı 230,3 milyon yolcu; İstanbul 121,9 milyon, Antalya 39,2 milyon.
- Antalya'nın 2024 aylık seyri: ocak 1,0 milyon, ağustos 5,9 milyon — turizm mevsimi görünüyor.
- 2024 kargo 2,41 milyon ton.
