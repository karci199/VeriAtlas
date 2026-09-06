# Semt

Semtin yasal tanımı, sınırı ve resmî kaydı **yoktur**. NVİ'nin Adres Kayıt Sistemi
il → ilçe → mahalle → sokak üzerinden çalışır; semt hiçbir resmî katmanda geçmez.

Ülke çapında tek liste, PTT posta kodu tablosundaki `semt_bucak_belde` sütunudur ve
bugünkü PTT sitesinde o sütun da kaldırılmıştır. 2022 tarihli dosya
`semihs/il-ilce-semt-mahalle` deposundan alındı → `raw/ptt/ptt_semt_2022.csv`
(73.305 satır, 81 il, 973 ilçe, 2.771 semt).

## Semt, posta kodunun adıdır

Bu tahmin değil, ölçüm: **973 ilçenin 973'ünde de bir ilçedeki semt sayısı, o ilçedeki
tekil posta kodu sayısına eşittir.** Bire bir, istisnasız. Semt sütunu bir yer kavramı
değil, PTT'nin o posta koduna verdiği addır.

İznik bunun en temiz örneğidir. 46 yerleşimin tamamı tek posta kodunda (16860), o yüzden
tek "semt" görünür — oysa Boyalıca ve Elbeyli 2014'e kadar belediyeydi ve ilçenin köyleri
merkezden ayrı bir şeydir. Gerede'de aynı ilçe iki koda bölünmüştür: 14900 kasabanın 9
mahallesi, 14902 ilçenin 283 köyü — ve o yüzden Gerede'de "MERKEZKÖYLER" diye bir kutu
vardır, İznik'te yoktur. Aradaki fark İznik ile Gerede'nin coğrafyası değil, iki posta
müdürlüğünün numaralandırma alışkanlığıdır.

Dağılım: 325 ilçede tek kod, 301'inde iki, 132'sinde üç; en fazlası 21 (Osmangazi).

**Bölünme kentleşmeyle gitmiyor** — ilk okuma öyle diyordu, il düzeyinde bakınca
çürüyor. İlçe başına kod: İstanbul 6,8 ama **Niğde 6,0 ve Muş 5,5**; buna karşılık
**Muğla 1,0**, Ordu ve Trabzon 1,1. Bursa'da Osmangazi 21 kod taşırken İznik, İnegöl ve
Yenişehir birer kod taşır. Muğla'nın 13 ilçesinin de tek kod taşıması, Bodrum'un neden
"bölünmemiş" göründüğünü de açıklar (aş. OSM sınaması).

PTT bir ilçeyi posta dağıtımının böl(dür)düğü yerde böler, böl(dür)mediği yerde bırakır.
Sütun bu yüzden dört ayrı şeyi aynı adla taşır (`raw/ptt/semt_tablo.py`):

| tür | adet | ne demek |
| --- | ---: | --- |
| semt | 958 | gerçek kentsel dağıtım bölgesi — Çarşı, Sanayi, Bahçelievler |
| kır torbası | 714 | ilçenin köylerinin atıldığı kutu; PTT çoğu yerde `MERKEZKÖYLER` yazar |
| ilçe merkezi | 447 | adı ilçenin kendi adı, ama ilçe bölünmüş: kutu kent merkezi |
| belde | 327 | adı **başka** bir belediyenin adı: semt değil, belde katmanı |
| bölünmemiş | 325 | ilçede tek semt var ve adı ilçenin adı — sütun bilgi taşımıyor |

**Belde bulgusu ve düzeltmesi.** İlk okuma "kentsel kutuların %45'i belde" diyordu; bu
fazla genişti. Adı bir belediyeye denk gelen 772 kutunun **465'i ilçenin kendi
belediyesidir** — Bağcılar, Sincan, Çorlu bir ilçenin içindeki kasaba değil, ilçenin
merkezidir. Ayrıldıklarında geriye **307 gerçek belde** kalıyor (2,1 M kişi), ilçe
merkezi kutuları ise 465 ve 15,8 M kişi.

Ayrım adla değil **nüfusla** sınandı: her kutunun nüfusu, aynı adı taşıyan belediyenin
MEDAS'taki 2025 nüfusuyla karşılaştırıldı (`raw/medas/yerlesim/nufus-belediye-*.csv`,
3.366 belediye, 2007-2025). Gerçek beldelerin %44'ü ±%10 içinde tutuyor; tutmayanlarda
**semt her zaman daha büyük** (Adıyaman/Suvarlı: semt 4.874, belediye 1.837), çünkü
dağıtım bölgesi beldeyi çevresindeki köylerle birlikte alıyor. İlçe merkezi kutularının
%63'ü tutuyor; tutmayanlarda semt daha küçüktür, çünkü ilçe belediyesinin alanı birden
çok kutuya bölünmüştür.

Ad sınaması mahalle kaydının `municipality` sütununa karşı yapılır
(`semt_analiz.beldeler()`); `bölünmemiş` ilçelerde anlamsız olduğu için o tür ayrı tutulur.

**Kır torbası ölçüt.** Önce PTT'nin kendi etiketi okunur — 450 ilçede kutunun adı
`MERKEZKÖYLER`, birkaç yerde bir beldenin köyleri (`ERKİLET KÖYLER`, `YUKARI KÖYLER`).
Etiket yoksa mahalle başına 500 kişiden az olma ölçütü kullanılır. Ad ölçütü şart:
Aksaray/Merkez'in 77 köylük torbası mahalle başına 647 kişiyle eşiği geçiyor ve
etiket olmasa kentsel semt sayılırdı.

**Kapsama eşit değil.** İstanbul'da 39 ilçenin 38'i bölünmüş; Ankara ve Bursa'da yalnız
merkez ilçeler — ama yukarıda görüldüğü gibi bu kentleşmenin değil kod pratiğinin
sonucudur. Bu yüzden ülke çapında karşılaştırmalı bir semt tablosu Kastamonu
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

Eşleşen alanlar 84.623.999 kişi — kayıttaki 86.063.197'nin **%98,3**'ü. (Köy ve mahalle
kayıtları bölünen ilçeleri takip edecek şekilde yeniden üretildikten sonra yükseldi.)
Eşleşmeyen 2.160 PTT satırının 147'si organize sanayi bölgesidir (nüfusu yok, eşleşmemesi
doğru); gerisi düz ad uyuşmazlığıdır, en çok Kastamonu, Tokat ve Afyonkarahisar'da.

## Çıktılar

`raw/ptt/semt_tablo.xlsx|csv|html` (semt başına nüfus, çocuk, seçmen, katılım, parti ve
ittifak payları), `semt_arayuz.html`, `semt_analiz.html` (il/ilçe bazında bölünme
anatomisi). Köylerin 18± kırılımı kaynakta olmadığı için kır torbalarında çocuk sütunu
boştur.
