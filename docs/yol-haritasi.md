# Yol haritası

Bu dosya "sırada ne var" sorusunun tek cevabı. Kararların gerekçesi
[kararlar.md](kararlar.md)'de; burası yalnızca sıra.

Son güncelleme: 2026-09-12.

## Nerede duruyoruz

Depoda **27 gösterge, 4,07 milyon satır**. Altı coğrafi düzey: ülke, İBBS (türetilen),
il, ilçe, mahalle, köy.

| Gösterge | Düzey | Yıl | Kırılım |
|---|---|---|---|
| Nüfus | Türkiye, il | 2007-2025 | tek yaş × cinsiyet |
| Nüfus | mahalle (38.408) | **2007**-2025 | 0-17 / 18+ |
| Nüfus | köy (35.345) | **2007**-2025 | yok |
| Nüfus | ilçe | *çekim sürüyor* | 5'lik yaş × cinsiyet |
| Medeni durum | Türkiye, il, **ilçe (989)** | 2008-2025 | medeni durum × cinsiyet × yaş |
| Doğum | Türkiye, il | 2009-2025 | **annenin yaş grubu** |
| Doğum | ilçe (975) | 2014-2025 | yok |
| Ölüm | Türkiye, il | 2009-2025 | yaş grubu × cinsiyet |
| Ölüm | ilçe (989) | 2009-2025 | cinsiyet |
| Evlenme / boşanma | Türkiye, il | 2001-2025 | yok |
| Evlenme / boşanma (ilçe) | ilçe (975) | 2014-2025 | yok — **ayrı gösterge**, farklı tanım |
| Ortanca yaş | Türkiye, il | 2007-2025 | cinsiyet |
| Toplam doğurganlık hızı | Türkiye, il | 2009-2025 | yok |
| Göç (4 ölçü), hanehalkı (3), yabancı uyruklu, kütük, yaşam süresi | Türkiye, il | değişken | değişken |

Mahalle ve köy serileri 2013'ten **2007'ye** indi. İkisi birbirini doğruluyor: 2012'de
34.292 köy varken 2013'te 18.108 kalıyor, aynı geçişte mahalle 18.883'ten 31.653'e
çıkıyor — 6360 sayılı yasanın dönüşümü iki taraftan birden görünüyor.

## Sıra

### 1. İlçe nüfusunun yaş × cinsiyet kırılımı

Ham verisi 2026-09-07 kaybında gitti; yeniden çekiliyor (19 yıl, yıl başına bir sorgu).
Bitince yüklenecek. `public/population-district.csv.gz` bu sırada git'teki tam haliyle
(696.900 satır) korunuyor — yani sayfa bozuk değil, yalnız yeniden üretilemez durumda.

### 2. Kütük nüfusu 2007-2009

Ham verisi indi, yüklenmeyi bekliyor. Aynı şekilde `registry-population.csv.gz` git'ten
korunuyor.

### 3. Ölüm, ölenin tek yaşıyla

Ülke düzeyinde 200 gösterge (100 yaş × cinsiyet), 2009-2025, ham verisi hazır.
Yüklenmesi bir karar gerektiriyor: aynı gösterge ülkede tek yaş, ilde yaş grubu taşır —
nüfusun ilde tek yaş, ilçede beşli bant taşıması gibi (K16). İl düzeyinde tek yaş
**yok**, MEDAS vermiyor.

### 4. Kent / kır ayrımının yeniden kurulması

Bugünkü ayrım yalnız yerleşim türünden çıkıyor (belediye mahallesi = kent, köy = kır) ve
yalnız 51 ilde işliyor, çünkü 6360 büyükşehirlerde köy bırakmadı. Elimizdeki mahalle ve
köy serileri artık 2007'ye kadar indiği için ayrımı yerleşimin gerçek karakterine göre
kurmanın veri tabanı var. Kaynak seçenekleri kararlar.md'de (Wikipedia ilçe sayfaları,
TÜİK'in üçlü sınıflaması, seçim verisindeki kent-kır etiketi).

### 5. Evlenme ve boşanmanın kırılımları

Taraması yapıldı, hiç çekilmedi. İki ölçü de geniş: evlenme 121 gösterge (kadının/erkeğin
yaş grubu, önceki medeni durum, eğitim durumu), boşanma 118 (yaş farkı, **evliliğin bitiş
nedeni**, **evlilik süresi**, eğitim). Ayrıca `Yaş grubuna göre ilk defa evlenen sayısı`
11 göstergeyle ucuz ve 25 yıl uzunluğunda.

### 6. Mahallede cinsiyet kesiti

MEDAS bu düzeyde yaş *ya da* cinsiyet veriyor, ikisini birlikte değil. Ayrı bir çekim,
aynı kayıt, `dims` sayesinde aynı göstergeye ek satır.

### 7. Ortanca yaşta toplam

Elimizdeki dosyada yalnız erkek/kadın var; iki medyanın ortalaması medyan değildir.

### 8. EVDS ve Dünya Bankası

Adaptör sözleşmesi (K8) bunlar için kuruldu, ikisi de yazılmadı.

### 9. Zamana bağlı coğrafya

Hâlâ açık ve hâlâ zor. İlçelerin geçerlilik aralıkları gözlemden çıkarıldı (K11), ama
**ardıl eşlemesi** yok. 2007-2012 geriye doldurması bunun beş vakasını görünür kıldı
(Akköy → Pamukkale gibi) ve köy defterine takma ad olarak yazıldı; ilçe düzeyinde aynı
iş yapılmadı. Bu olmadan uzun ilçe serileri sessizce yanlış: 2014'ün Aksaray Merkez'i ile
2020'ninki aynı alan değil.

## Kaynak kısıtları

MEDAS'ın vermedikleri kararlar.md'de ayrı başlıkta: ölüm × medeni durum (düğme
kayboluyor), ölenin tek yaşı il düzeyinde, ilçede bebek ölümü, sektörel GSYİH, ilçe TFH.

## Ekran — OWID'e göre eksikler

Sıralama değişmedi: dağılım grafiği (scatter) · yıl aralığı seçimi · görüntü olarak
indirme · gömme (embed) · kaynaklar sekmesi · yığılmış alan · eğim grafiği · harita
projeksiyonu.
