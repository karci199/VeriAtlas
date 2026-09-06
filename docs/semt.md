# Semt

Semtin yasal tanımı, sınırı ve resmî kaydı **yoktur**. NVİ'nin Adres Kayıt Sistemi
il → ilçe → mahalle → sokak üzerinden çalışır; semt hiçbir resmî katmanda geçmez.

Ülke çapında tek liste, PTT posta kodu tablosundaki `semt_bucak_belde` sütunudur ve
bugünkü PTT sitesinde o sütun da kaldırılmıştır. 2022 tarihli dosya
`semihs/il-ilce-semt-mahalle` deposundan alındı → `raw/ptt/ptt_semt_2022.csv`
(73.305 satır, 81 il, 973 ilçe, 2.771 semt).

## Semt bir dağıtım bölgesidir

PTT bir ilçeyi posta dağıtımının böl(dür)düğü yerde böler, böl(dür)mediği yerde bırakır.
Sütun bu yüzden dört ayrı şeyi aynı adla taşır (`raw/ptt/semt_tablo.py`):

| tür | adet | ne demek |
| --- | ---: | --- |
| semt | 951 | gerçek kentsel dağıtım bölgesi — Çarşı, Sanayi, Bahçelievler |
| belde | 772 | adı kayıttaki bir **belediyenin** adı: semt değil, belde katmanı |
| kır torbası | 723 | ilçenin köylerinin atıldığı kutu; PTT çoğu yerde `MERKEZKÖYLER` yazar |
| bölünmemiş | 325 | ilçede tek semt var ve adı ilçenin adı — sütun bilgi taşımıyor |

**Belde bulgusu.** Gerçek kentsel kutuların %45'i (772 kutu, 17,9 M kişi) kayıttaki bir
belediyenin adıdır. Yani PTT'nin "semt" dediği şeyin yarıya yakını halk coğrafyası değil,
6360 öncesi/sonrası **belde** katmanıdır. Sınama, mahalle kaydının `municipality`
sütununa karşı yapılır (`semt_analiz.beldeler()`); `bölünmemiş` ilçelerde sınama anlamsız
olduğu için (semt adı = ilçe adı = ilçe belediyesinin adı) o tür ayrı tutulur.

**Kır torbası ölçüt.** Önce PTT'nin kendi etiketi okunur — 450 ilçede kutunun adı
`MERKEZKÖYLER`, birkaç yerde bir beldenin köyleri (`ERKİLET KÖYLER`, `YUKARI KÖYLER`).
Etiket yoksa mahalle başına 500 kişiden az olma ölçütü kullanılır. Ad ölçütü şart:
Aksaray/Merkez'in 77 köylük torbası mahalle başına 647 kişiyle eşiği geçiyor ve
etiket olmasa kentsel semt sayılırdı.

**Bölünme kentleşmeyle gider.** İstanbul'da 39 ilçenin 38'i bölünmüş; Ankara ve Bursa'da
yalnız merkez ilçeler. Bu yüzden ülke çapında karşılaştırmalı bir semt tablosu Kastamonu
ile İstanbul'u aynı sütunda gösterdiği anda yanlış olur. Semt yalnızca (a) bölünmüşlüğü
yüksek illerde mahalle üstü bir gösterim katmanı, (b) "PTT dağıtım bölgesi" adıyla,
ne olduğu açıkça yazılarak kullanılabilir.

## Dış kaynak sınaması

**OpenStreetMap.** Overpass ile Türkiye'nin tamamı çekildi: `place=suburb` 10.871 +
`place=quarter` 680 düğüm. Bunlar semt değil, mahalle: OSM adlarının %74'ü PTT mahalle
adı, yalnız %13'ü semt adı. Yani semtin ikinci bir kaynağı yoktur.

**Bucak değil.** Semt adlarının yalnız %2'si köy kaydındaki bucak adına denk gelir;
2014'te kaldırılan bucak katmanı semtin karşılığı değildir.

**Görünmeyen semtler.** OSM düğümleri ilçe sınırlarına düşürüldüğünde, PTT'nin
bölmediği 325 ilçenin **291'inde** iki ya da daha fazla adlı düğüm çıkıyor (2.955 nokta).
Çoğu köy adı — Kayseri/Pınarbaşı'nın 128 düğümü ilçenin köyleridir — ama bir kısmı
gerçek: Bodrum bölünmemiş görünüyor, oysa Türkbükü, Gölköy, Akyarlar bilinen semtler;
Menemen'de Ulukent aynı durumda. Yani PTT eksiktir, ama OSM de yerine geçemez.
Betik: `scratchpad/osm_semt.py` deseni, Overpass alan kimliği `3600174737`.

## Eşleme tuzakları

- PTT merkez ilçeye `MERKEZ` der, kayıt ilin adını verir (Kastamonu/Merkez ↔
  Kastamonu/Kastamonu); her arama iki anahtarla yapılır.
- `AĞIT MAH (ZÜMRÜT KÖYÜ)` gibi satırlar köyün kendisine bağlanır. Ad iki parantez
  taşıyabilir (`AYDINLIK MAH (ZUĞUR MAH) (DALLARCA KÖYÜ)`) — **son** grup okunur.
- `(… BELDESİ)` bunun tersidir: belde bir bucaktır, yerleşim parantezin **önündeki**
  addır (`ABIMISTIK MAH (ÇAKIRHÜYÜK BELDESİ)` = Çakırhüyük bucağındaki Abımıstık köyü).
- Bir ad iki kayıtta birden durabilir: 2013'te mahalleye dönen köyün kapalı kaydı ile
  yaşayan mahalle kaydı. `last_seen` en geç olan kazanır; dosya sırasına bırakmak
  toplamdan beş milyon kişi düşürüyordu.
- Aynı yerleşim birden çok PTT satırında geçer. Tekilleştirme **semt içinde** yapılır
  (21.730 satır atlanır), ülke çapında değil: 296 yerleşim iki semtte birden geçer ve
  ikisine de aittir. Ülke toplamı bu yüzden sütun toplamı değil, tekil alanların
  birleşimidir — 84.088.334 kişi; sütun toplamı 85.425.701.

## Kapsam

Eşleşen 49.030 alan, 84.088.334 kişi — kayıttaki 86.063.197'nin **%97,7**'si.
Eşleşmeyen 2.160 PTT satırının 147'si organize sanayi bölgesidir (nüfusu yok, eşleşmemesi
doğru); gerisi düz ad uyuşmazlığıdır, en çok Kastamonu, Tokat ve Afyonkarahisar'da.

## Çıktılar

`raw/ptt/semt_tablo.xlsx|csv|html` (semt başına nüfus, çocuk, seçmen, katılım, parti ve
ittifak payları), `semt_arayuz.html`, `semt_analiz.html` (il/ilçe bazında bölünme
anatomisi). Köylerin 18± kırılımı kaynakta olmadığı için kır torbalarında çocuk sütunu
boştur.
