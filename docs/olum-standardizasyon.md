# Yaşa göre standardize ölüm hızı — yöntem ve sınırlar

Kaba ölüm hızı ölümlülüğü değil, büyük ölçüde **yaş yapısını** ölçer. Sinop'un kaba hızı
Türkiye'nin en yükseğidir (2025'te 10,83‰) çünkü nüfusu yaşlıdır; standardize edilince
6,03‰'ye, ortalamanın biraz üstüne iner. Bu dosya, o düzeltmenin nasıl yapıldığını ve
nerede durduğunu yazar.

## İki yöntem, çünkü iki farklı veri var

**İl — doğrudan standardizasyon.** Ölenin yaş grubu il düzeyinde yayımlanıyor (17 bant ×
cinsiyet, 2009-2025). İlin yaşa özel ölüm hızları hesaplanıp **standart nüfusun** yaş
yapısına uygulanıyor. Okunuşu: *bu ilin nüfusu standart kadar yaşlı olsaydı ölüm hızı ne
olurdu.*

**İlçe — dolaylı standardizasyon (SMR).** İlçede ölenin yaşı **yok**, yalnız toplam ölüm
var. O yüzden ters yön: **Türkiye'nin** yaşa özel hızları ilçenin yaş yapısına uygulanıp
*beklenen* ölüm bulunuyor, gözlenen ona bölünüyor, 100 ile çarpılıyor. 100 = Türkiye
kadar.

Buradaki referans **Türkiye'dir, ilçenin bağlı olduğu il değil.** İl hızları kullanılsaydı
sayı "ilin içinde göreli" olurdu ve iki ilin ilçeleri karşılaştırılamazdı — Şanlıurfa'nın
ilçesi 100 çıkarken Muğla'nınki de 100 çıkardı, ikisi bambaşka olduğu hâlde.

## Standart nüfus: Türkiye 2025

Uluslararası karşılaştırmada ESP2013 (Avrupa Standart Nüfusu) kullanılır. Burada kendi
nüfusumuz seçildi, çünkü bu bir Türkiye atlası ve "hangi il gerçekte daha ölümcül" sorusu
kendi yaş yapımıza göre okunduğunda doğrudan anlaşılıyor. ESP ikinci bir standart olarak
sonradan eklenebilir; yöntem aynı, değişen yalnız ağırlıklar.

**Doğrulama:** standart Türkiye'nin kendisi olduğu için Türkiye'nin kaba ve standardize
hızı **birebir aynı çıkmalı** — çıkıyor: 2025 için ikisi de 5,71‰. Zincirin doğru
kurulduğunun sınamasıdır. İlçe tarafında da ortanca SMR 101,6 (~100 beklenir).

## Bilinen sınırlar

**1. İlçede küçük sayı sorunu — açık, düzeltilmedi.**
SMR'nin paydası beklenen ölüm sayısıdır ve küçük ilçelerde bu sayı onlarla ifade edilir.
Beklenen 20 ölümde gözlenenin 25 çıkması SMR'yi 125 yapar; bu fark rastlantıyla da
oluşabilir. Yani **uçlardaki ilçeler bir ölçüde gürültüdür.** Şu anki tablolar nüfusu
20.000'in altındaki ilçeleri dışarıda bırakarak bunu kabaca sınırlıyor, ki bu bir çözüm
değil, bir eşiktir.

Doğru çözüm iki tane: birkaç yılı havuzlayıp (ör. 2023-2025 birlikte) payı ve paydayı
büyütmek, ya da güven aralığı hesaplayıp aralığı 100'ü kapsayan ilçeleri "ayırt edilemez"
saymak. **İkisi de yapılmadı, bilinçli olarak ertelendi.** Havuzlama tek yılın
karşılaştırmasını kaybettirir, güven aralığı ekranda yeni bir gösterim gerektirir; ikisi
de ayrı bir kararı hak ediyor.

**2. 0-14 hızı yalnız ölümlülük değil, doğurganlığı da taşır.**
0-14 ölümlerinin çoğu bir yaşın altındadır. Payda "çocuk nüfusu" olduğunda, doğum sayısı
düşen bir ilde bebek ölümü *çocuk başına* iki kere düşer: hem ölüm riski azaldığı için hem
yeni doğan payı küçüldüğü için. Muş'ta bebek ölüm hızı **doğum başına** %54 düştü
(21,7 → 9,9‰), aynı dönemde 0-14 standardize hızı **%79** düştü. Aradaki fark ölümlülük
değil, doğurganlıktır.

Yaş 0 ayrı bant tutularak (tek yaş nüfus dosyasıyla) yeniden hesaplandığında sonuç
neredeyse değişmiyor — Türkiye −%51,4 yerine −%53,6, sıralama sabit — yani bantlama
sorunu değil, paydanın kendisi. "Bebek ölüm hızı" göstergesi doğum başına ölçtüğü için bu
karışıklığı taşımaz; ikisi yan yana okunmalı.

**3. Bilinmeyen yaş dışarıda.**
MEDAS ölümleri "Bilinmeyen" yaş grubuyla da veriyor. Payı ihmal edilebilir: 2025'te
%0,00, en yükseği İstanbul 2009 ile %1,45. Hesaba katılmıyor, çünkü hangi bantlara
dağıtılacağı bilinmiyor ve dağıtmak veriye olmayan bir bilgi eklemek olurdu.

## Kapsam

| | Yıl aralığı | Sınırı koyan |
|---|---|---|
| İl, doğrudan standardize hız | 2009-2025 | ölenin yaş grubu (2009-10 ve 2011-25 iki ayrı dosyada) |
| İlçe, SMR | 2009-2025 | ilçe ölüm sayısı 2009'da başlıyor |

İlçe nüfusu 2007'den beri var, yani sınırı koyan ölüm tarafı.

## Ortalama ölüm yaşı — ne ölçtüğü ve ne ölçmediği

Ölenlerin ortalama yaşı, bant orta noktalarıyla hesaplanabiliyor (75+ için 82 varsayımı).
Sezgisel bir sayı ve **yanıltıcı**: ilin yaş piramidini ölçüyor, ömür uzunluğunu değil.

| İlişki | Normal yıllarda korelasyon |
|---|---|
| ortalama ölüm yaşı ~ ilin ortanca yaşı | **+0,89 … +0,93** |
| ortalama ölüm yaşı ~ yaşam süresi | +0,25 … +0,38 |
| (ölüm yaşı − ortanca yaş) ~ standardize ölüm hızı | −0,12 … −0,19 |

En açık kanıt Muş: ortalama ölüm yaşı 2009-2025 arası 43,1'den 63,9'a çıktı (+20,8 yıl),
aynı dönemde yaşam süresi 77,5'ten 77,6'ya (+0,1 yıl). Yirmi yıllık artış ömürden değil,
çocuk ölümlerinin bitmesinden ve piramidin değişmesinden geliyor. Ülke çapında da aynı
çelişki var: ortalama ölüm yaşı 2009-2025 arası +6,1 yıl artarken yaşam süresi 2013-2023
arası düştü (78,0 → 77,3).

**Fark neye yarıyor:** ölümün normal yaş desenini bozan olaylara. 2023'te (ölüm yaşı −
ortanca yaş) ile standardize hız arasındaki korelasyon −0,86'ya fırlıyor; sebep depremdir
— Adıyaman'ın ortalama ölüm yaşı 68,5'ten 43,2'ye düşüp ertesi yıl 67,6'ya dönüyor. 11
deprem ili çıkarılınca −0,44'e iniyor. 2020'de işaret ters dönüyor (+0,39): salgın yaşlıyı
öldürdüğü için ölüm yaşı yukarı gidiyor. Yani bu fark bir sağlık göstergesi değil, bir
**anomali dedektörüdür** ve ekranda öyle sunulmalı.

## Yapılacaklar

1. Ölenin yaş grubunu depoya alan adaptör (`nufus-olum-yas-*`, 2009-2025, il + Türkiye).
2. Türetilmiş iki gösterge: il için doğrudan standardize hız, ilçe için SMR.
3. Ortalama ölüm yaşı — ancak yukarıdaki uyarı ekranda yanında dururken.
4. Ertelenenler: ilçede yıl havuzlama ve güven aralığı; ESP2013 ikinci standart.
