# İznik vaka analizi — sur içi/dışı, kent/kır, yaşlanma

Kodlanmadı, göstergeye girmedi — tek ilçeye özel, el yapımı bir model (sur içi alan
payları elle ölçüldü) VeriAtlas'ın "genel gösterge" felsefesine uymuyor (K4). Bulgular
ve tam tablolar [vaka-iznik.xlsx](vaka-iznik.xlsx)'te, 7 sayfa: Özet, Sur İçi-Dışı
(yıllık, 1935-2025), Mahalle yaş grupları, Kent-Kır-İlçe (2024), Sur içi-dışı yaş
(2024), Hanehalkı tipleri, Yöntem ve kaynaklar.

## Ana bulgular

- Sur içi nüfus payı 1980 öncesi ~%100'den 2025'te **%48,9**'a düşmüş.
- Sur dışı nüfus 2007-2025 arası **4,2 kat** artmış (3.386 → 14.298 kişi).
- En hızlı büyüyen mahalleler Eşrefzade ve Yeşil Camii (Topkapı bölgesi, kuzeydoğu),
  aynı zamanda en genç nüfuslu; Mahmut Çelebi en yaşlı ve küçülen mahalle.
- Kır, kent'ten iki kat hızlı yaşlanıyor (+8,9 yıl vs +4,4 yıl, 2007-2024).
- İlçe genelinde 65+ nüfus %66 artmış, 0-14 nüfus %26 azalmış (2007-2025).
- Ortalama hanehalkı büyüklüğü 3,32'den 2,94'e düşmüş (2014-2025).

## Yöntem — kısaca

Beyler ve Mahmut Çelebi mahalleleri tamamen sur içinde. Diğer 5 mahallenin sur içi
alan payı uydu görüntüsünden elle ölçüldü (m²). Beyler+Mahmut Çelebi'nin o yılki
gerçek yoğunluğu (nüfus/sabit alan), diğer mahallelerin ölçülen sur-içi alanına
uygulanarak sur-içi nüfus tahmin edildi. Toplam sur-içi alan (1,4185 km²) elle
tahmin edilen sur alanıyla (1,41 km²) örtüştü — iç tutarlılık kontrolü.

**1980-2007 arası sur içi/dışı sayıları ölçüm değil**, iki sabit noktadan (1980'de
~0, 1990'da ~300 kişi sur dışı) üstel enterpolasyonla üretilmiş bir model.

Ayrıntılı yöntem ve bilinen zayıf noktalar için xlsx'in "Yöntem ve kaynaklar" sayfası.

## Kaynak dosyalar (masaüstü `demografi/` klasörü)

`iznik.xls`, `iznik_18.xls`, `iznik_kent_kir.xlsx`, `iznikfull.xls`,
`hanehalkı tipleri iznik.xls` — hiçbiri `raw/`e taşınmadı, bu tek seferlik bir
oturum analizi.
