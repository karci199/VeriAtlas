# ETKB / EİGM — devreye giren santraller

Enerji ve Tabii Kaynaklar Bakanlığı, Enerji İşleri Genel Müdürlüğü her yıl "enerji
yatırımları" tablosunu yayımlıyor: o yıl **geçici kabulü yapılan** santral üniteleri —
şirket, santral adı, il, kaynak, ünite gücü, ünite sayısı, eklenen kurulu güç ve kabul
tarihi. Tek düz adres, yılı değiştirmek yeterli:
`enerji.gov.tr/Media/Dizin/EIGM/tr/Raporlar/EY/<yıl>.xls` (2014'ten sonra `.xlsx`).

- İndirme: [`scripts/fetch_etkb.py`](../scripts/fetch_etkb.py) → `C:\veri-ham\etkb\<yıl>.xls[x]`
  (2003-2025, 23 dosya).
- Adaptör: [`src/veriatlas/adapters/etkb.py`](../src/veriatlas/adapters/etkb.py).
- Göstergeler: `etkb_added_capacity` (MW), `etkb_added_plants` (santral sayısı); il düzeyi,
  yıllık, kırılım `energy_source`. 2×1.663 satır, 80 il.

## Okuma ve doğrulama

Sütunlar her dosyada başlık satırından bulunuyor (`SIRA NO` içeren satır); il `İL` sütunu,
kaynak `KAYNAK` / `YAKIT CİNSİ`, güç `İLAVE …` ile başlayan sütun. 2014'ten sonra araya
`LİSANS TARİHİ` / `LİSANS SAYISI` giriyor, bu yüzden sütun adı sabit, sırası değil.

Her dosyanın sonunda o yılın kaynak grubuna göre toplamı basılı (TERMİK / HES / RES … ve
TOPLAM). Okunan satırların toplamı bu basılı toplamla karşılaştırılıyor; 23 yılın hepsi
tutuyor (en büyük fark 2014: 6.209'a karşı 6.305 MW, %1,5 — basılı özetin santral satırlarına
girmeyen kalemleri). Özet bloğunun satırları ili il olmadığı için kendiliğinden atlanıyor.

## Bilinen sınırlar

- **Lisanssız güneş yok.** Tablo geçici kabul edilen (çoğunlukla lisanslı) santralleri
  sayıyor; 2003-2025 toplamı güneşte 3.058 MW, oysa Türkiye'nin kurulu güneş gücü çok daha
  yüksek — çatı/arazi lisanssız GES bu seriye girmiyor. Kömür, doğal gaz, rüzgâr ve hidroda
  böyle bir boşluk yok.
- **İki illi santral.** "EDİRNE-TEKİRDAĞ" gibi yazılan santraller ilk ile yazıldı.
- **Emeklilik/devreden çıkma yok.** Seri yalnızca eklemeyi veriyor, net kurulu güç değil;
  yıllar toplanarak stok elde edilmez.
- 2026 dosyası henüz yayımlanmadı.
