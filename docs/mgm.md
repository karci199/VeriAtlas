# MGM — iklim normalleri ve rekorlar (depoda, 2026-09-16)

Kaynak: mgm.gov.tr "İl ve İlçeler İstatistik" sayfaları; her il için düz HTML tablo.
robots.txt bize izin veriyor (yalnız Meta ve Amazon ajanları engelli).

- İndirme: `scripts/fetch_mgm.py` → `C:\veri-ham\mgm\iklim.json` (81 il).
- Adaptör: `src/veriatlas/adapters/mgm.py`.
- Göstergeler: `mgm_temperature` (ortalama, ortalama en yüksek/en düşük, ölçülmüş en
  yüksek/en düşük), `mgm_sunshine`, `mgm_rainy_days`, `mgm_precipitation`,
  `mgm_measurement_period`, ve rekorlar: `mgm_record_daily_precipitation`,
  `mgm_record_wind_speed`, `mgm_record_snow_depth`.
- Kapsam: 81 il, 12 ay, 13.856 kayıt.

## İki normal var

MGM iki ayrı normal yayımlıyor, `normals_period` kırılımı ikisini ayırıyor:

- `station`: istasyonun **tüm ölçüm dönemi** ortalaması. Dönem ile göre değişiyor
  (Ankara 1927-2025, Şırnak 1970-2025); ilk ve son yıl `mgm_measurement_period`'de duruyor.
- `1991_2020`: standart 30 yıllık normal; 81 ilin 79'unda var.

Normaller bir yıla ait olmadığı için, ortalamanın kapsadığı dönemin son yılına yazıldı.
Sayfadaki "Yıllık" sütunu veri satırlarında boş, o yüzden alınmadı. İki tablo farklı
noktalama kullanıyor (biri "0,4", öteki "0.9"); ikisi de okunuyor.

Rekorlar tek bir olay olduğu için kendi tarihine yazıldı (frekans günlük). Bir ilde kar
rekoru yok.

## Notlar

- Mersin, MGM'de hâlâ "İÇEL" adıyla dosyalanmış; adaptör bunu eşliyor.
- İlçe sayfaları farklı adlandırmayla geliyor (`m=IZNIK` boş döndü), ilçe düzeyi alınmadı.

## Örnek bulgu

Ankara'da temmuz ortalaması, istasyonun 1927-2025 dönemine göre 23,5 °C; 1991-2020
normalinde 24,2 °C. Yani son otuz yılın normali, yüz yıllık ortalamanın 0,7 derece üstünde.
