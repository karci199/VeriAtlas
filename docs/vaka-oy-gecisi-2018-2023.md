# 2018 → 2023 oy geçişleri (kestirim, ölçüm değil)

**Bu bir vaka analizidir, gösterge değildir.** Sonuçlar depoya `fact` satırı olarak girmez;
K4'e uymaz, çünkü ölçülmüş bir büyüklük değil, veriyle en tutarlı senaryodur.

Yöntem fikri Erol Taymaz'ın 2018 tarihli Sarkaç yazısından alındı
(<https://sarkac.org/2018/05/partiler-arasi-oy-gecisleri/>): anket yerine, aynı yerleşimin iki
seçimdeki sonucunu yan yana koyup geçiş olasılıklarını kestiren **ekolojik çıkarım**.

## Ne yapıldı

`scripts/analiz/oy_gecisi_2018_2023.py`. Girdi `public/tiles/secim-mv2018-mahalle-TR-*.json` ve
`secim-mv2023-mahalle-TR-*.json`; her kayıtta kayıtlı seçmen (`k`), oy kullanan (`o`), geçerli oy
(`g`) ve parti dökümü (`v`) var.

Her mahalle için 2018 ve 2023 oyları **kayıtlı seçmene** oranlandı; oy kullanmayan da ayrı bir
kategori olarak modele girdi. Geçiş matrisi, seçmen sayısıyla ağırlıklandırılmış **negatif
olmayan en küçük kareler** (Goodman ekolojik regresyonu) ile sütun sütun çözüldü, sonra satırlar
1'e normalize edildi.

**Eleme:** 47.404 ortak mahalleden 28.555'i kullanıldı (40,7 milyon seçmen). Elenenler: seçmeni
100'ün altındakiler ve **seçmen sayısı iki seçim arasında %15'ten fazla değişenler** — göç ve
sınır değişikliği geçiş kestirimini bozduğu için.

## Sonuç: 2018 (satır) → 2023 (sütun), %

| | AKP | CHP | YSP | MHP | İYİ | YRP | ZAFER | diğer | katılmadı |
|---|---|---|---|---|---|---|---|---|---|
| AKP | **80,0** | 0,2 | 0,0 | 5,8 | 0,0 | 5,6 | 1,6 | 5,2 | 1,5 |
| CHP | 0,6 | **81,9** | 0,0 | 0,0 | 6,6 | 0,0 | 1,4 | 9,5 | 0,0 |
| HDP | 0,0 | 5,8 | **81,6** | 0,0 | 0,0 | 0,0 | 0,0 | 2,2 | 10,5 |
| MHP | 7,5 | 5,5 | 0,0 | **71,0** | 5,5 | 1,2 | 2,3 | 3,4 | 3,6 |
| İYİ | 0,0 | 17,8 | 0,0 | 1,4 | **74,0** | 0,0 | 6,8 | 0,0 | 0,0 |
| SP | 17,1 | 37,2 | 0,0 | 0,0 | 9,0 | 22,3 | 12,8 | 1,7 | 0,0 |
| diğer18 | 78,1 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 10,6 | 11,3 |
| katılmayan | 7,9 | 0,3 | 0,0 | 0,0 | 1,8 | 0,0 | 0,0 | 7,6 | **82,5** |

2018 tabanı (seçmen içindeki pay): AKP %36,1 · CHP %20,8 · HDP %9,6 · MHP %9,5 · İYİ %9,1 ·
SP %1,2 · diğer %1,6 · katılmayan %12,1.

**Okunanlar:** AKP'nin kaybı karşı bloğa değil sağa gitmiş (%5,8 MHP, %5,6 Yeniden Refah; CHP'ye
%0,2). MHP en çok sızdıran parti (%71 tutma). İYİ Parti'den CHP'ye %17,8. HDP'nin kaybı başka
partiye değil **sandığa gitmemeye** (%10,5). Saadet dağılmış: %37 CHP, %22 YRP, %17 AKP. 2018'de
oy kullanmayanın %82,5'i 2023'te de kullanmamış.

## Neden ölçüm sayılmaz — üç sınır

1. **Ekolojik yanılgı.** Yerleşim düzeyindeki değişimden birey davranışı çıkarılıyor. "AKP
   seçmeninin %5,6'sı YRP'ye geçti" bir olgu değil, veriyle tutarlı bir kestirimdir.
2. **Eleme yanlılığı — en ağırı.** Seçmeni %15'ten fazla değişen mahalleler elendi; bunlar
   ağırlıklı olarak **hızlı büyüyen kentsel mahalleler**. Tablo kırsala doğru ağırlıklı ve göçün
   yoğun olduğu yerleri temsil etmiyor.
3. **Sıfırlar gerçek sıfır değil.** Negatif olmayan en küçük karelerde katsayı sınırda sıfıra
   yapışır; "İYİ → AKP %0" geçiş olmadığı anlamına gelmez, veriden ayırt edilemediği anlamına gelir.

Belirsizlik payı hesaplanmadı. Yayımlanacaksa önyükleme (bootstrap) ile güven aralığı üretilmeli
ve elenen mahalleler için ayrı bir duyarlılık denemesi yapılmalı.
