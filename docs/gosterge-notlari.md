# Gösterge notları

Ekrandan kaldırılan uzun tanımlar. Bunlar ekranda değil, çünkü okuyan kişi seçmediği ayarların tuzaklarını da okumak zorunda kalıyordu; ekranın altındaki "Bu ekranda ne var" bloğu artık yalnızca açık olan ayarları anlatıyor. Buradaki notlar kaynağın sınırlarını ve göstergenin okunma tuzaklarını kayıt altında tutmak içindir.

## births

Yıl içindeki canlı doğum sayısı, annenin ikamet ettiği ile göre. Kaynak dosya ayları
ayrı veriyor; burada yıla toplanmış olarak duruyor — mevsimlilik ayrı bir sorudur ve
sorulduğunda ham dosyadan ay kırılımıyla yeniden yüklenir. **Cinsiyet kırılımı yok**: bu
çekimde MEDAS doğumu yalnız aya bölüyor. İl ve Türkiye düzeyinde var, 2009'dan itibaren.

## deaths

Yıl içindeki ölüm sayısı, ölen kişinin ikamet ettiği ile göre, cinsiyet kırılımıyla.
Kaynak dosya ayrıca ayı da veriyor; yıla toplanmış olarak duruyor. **Yaş kırılımı yok**
— bu yüzden piramit çizilmez ve yaşa göre ölümlülük bu göstergeden okunamaz. Ham sayı
nüfusla birlikte okunmalı: İstanbul'un ölümü Tunceli'ninkinden çok olduğu için değil,
kalabalık olduğu için yüksektir. Kaba ölüm hızı ayrı bir gösterge değildir — "Alan
nüfusunun %'si" kipi bu sayıyı nüfusa bölerek onu zaten verir. 2009'dan itibaren.

## divorces

Yıl içinde kesinleşen boşanma kararı sayısı. Evlenme sayısıyla **aynı yılın oranı
değildir**: bu yıl boşananlar başka yıllarda evlenmiş çiftlerdir, o yüzden ikisinin
bölümü "evliliklerin yüzde kaçı bitiyor" sorusunu yanıtlamaz — evlenmenin düştüğü bir
yılda bu oran, hiçbir şey değişmeden yükselir. 2001'den itibaren.

## foreign_population

İlde ikamet eden yabancı uyruklu kişi sayısı, cinsiyet kırılımıyla. İkamet edilen yere
göre sayılır, uyruk kırılımı bu çekimde yok.

## household_by_type

Hanelerin yapısına göre dağılımı: tek kişilik, tek çekirdek aileli, çekirdek aile ve
diğer kişiler, çekirdek ailesiz çok kişili. Dördü birbirini dışlar ve toplamı hanehalkı
sayısını verir. TÜİK bunların altında beş alt tip daha yayımlıyor (anne ve çocuklar,
sadece eşler gibi); onlar burada saklanmıyor, çünkü kardeş sanılıp toplanırlarsa hane
sayısı %78 fazla çıkar. 2014'ten itibaren var.

## household_count

Toplam hane sayısı. Nüfustan ayrı bir büyüklük: nüfus artmadan da hane sayısı artabilir
— aynı insanlar daha küçük hanelerde yaşamaya başladığında. 2012'den itibaren var.

## household_size

Hane başına düşen kişi. Şırnak 4,84, Tunceli 2,49 — doğurganlık, birlikte yaşama
biçimleri ve göçün birlikte okunduğu tek sayı. Türkiye genelinde uzun süredir düşüyor.

## infant_mortality

Bin canlı doğum başına, bir yaşını doldurmadan ölen bebek sayısı. Paydası nüfus değil
canlı doğumdur. Yaş yapısından etkilenmediği için iller arası karşılaştırmaya kaba
hızlardan daha uygundur ve klasik olarak sağlık hizmetine erişimin göstergesi sayılır.
Küçük illerde payı birkaç yüz doğum olduğu için yıl yıl zıplar — eğilim için hareketli
ortalama işe yarar.

## marital_status

15 yaşını doldurmuş nüfusun medeni durumu — hiç evlenmedi, evli, boşandı, eşi öldü —
cinsiyet ve beşli yaş grubu kırılımıyla. Üç kırılım aynı anda yayımlandığı için "40-44
yaş kadınlarda boşanmışların sayısı" doğrudan sorulabiliyor. **Yaş 15'ten başlar**:
medeni durum daha küçükler için yayımlanmaz, yani 0-14 eksik değil yoktur — bu
göstergenin toplamı ilin nüfusu değildir. Bilinmeyen kategorisi son yıllarda kayboluyor;
o yıllarda sütun sıfır değil, hiç yok. Türkiye, İBBS ve il düzeyinde var, ilçe kırılımı
çekilmedi.

## marriages

Yıl içinde kıyılan resmî nikâh sayısı. **Olayın yerine göre**, yani nikâhın kıyıldığı
ile göre sayılır — doğum ve ölümdeki gibi ikametgaha göre değil, çünkü TÜİK evlenmeyi bu
biçimde yayımlıyor. Küçük ilçelerinde çok nikâh kıyılan turistik illerde bu ikisi
ayrışır. Kaba evlenme hızı ayrı bir gösterge değildir: "Alan nüfusunun %'si" kipi bu
sayıyı nüfusa bölerek onu verir. 2001'den itibaren.

## mean_first_marriage_age

Hayatında ilk kez evlenenlerin ortalama yaşı, cinsiyete göre. "İnsanlar kaç yaşında
evleniyor" sorusunun karşılığı budur ve doğurganlıkla birlikte okunur: ilk evlenme
yaşının yükseldiği yerde ilk doğum da geç oluyor. Türkiye'de erkek ile kadın arasında
uzun süredir üç yaş dolayında bir fark var. **Toplam yok** — ve burası ortalama evlenme
yaşından ayrılır: bir evlilik erkeğin ilki, kadının ikincisi olabilir, yani ilk kez
evlenen erkek ve kadın sayısı eşit değildir. İkisini tek sayıda birleştirmek elimizde
olmayan ağırlıkları gerektirir, o yüzden uydurulmuyor. 2001'den itibaren.

## mean_marriage_age

O yıl evlenen herkesin ortalama yaşı, cinsiyete göre — ikinci ve sonraki evlilikler
dahil. Bu yüzden ilk evlenme yaşından yüksektir ve aradaki fark, boşanma sonrası yeniden
evlenmenin ne kadar yaygın olduğuyla birlikte hareket eder. İkisi ayrı göstergedir çünkü
ayrı soruları yanıtlar. **Toplam** bizim hesabımızdır (rozet: türetilmiş) ve burada iki
ortalamanın ortalaması **tam olarak doğrudur**: her nikâhta bir damat ve bir gelin
vardır, yani iki ortalamanın ağırlığı tanım gereği eşittir. Ortanca yaşta yasak olan
işlem burada serbest, çünkü orada ağırlıklar eşit değildi. 2001'den itibaren.

## median_age

Nüfusu tam ortadan ikiye bölen yaş: yarısı bundan genç, yarısı yaşlıdır. Ortalama yaştan
farkı, uçlardaki birkaç çok yaşlıdan etkilenmemesidir. TÜİK yalnızca erkek ve kadını
ayrı ayrı yayımlıyor; **Toplam** bizim hesabımızdır (rozet: türetilmiş) ve iki
ortancanın ortalaması değil, tek yaş nüfus dağılımının tam ortasıdır. Yöntem yayımlanan
erkek/kadın değerlerine karşı sınandı: 3.116 karşılaştırmada ortalama mutlak fark 0,05
yıl, yani TÜİK'in kendi yuvarlaması kadar. İl ve Türkiye düzeyinde var, ilçe kırılımı
yok.

## migration_from_abroad

Yıl içinde yurt dışından ile taşınan kişi sayısı. İç göçten ayrı tutulur: ülke
toplamında iç göç sıfırlanırken bu sıfırlanmaz, nüfusa net katkıdır.

## migration_in

Yıl içinde ile başka bir ilden taşınan kişi sayısı. Kaynak dosyada cinsiyet ve yaş
kırılımı da var; burada toplam olarak saklanıyor. Yurt dışından gelen göç buna dahil
değil, ayrı göstergedir.

## migration_net

Aldığı göç eksi verdiği göç. Eksi değer il nüfusunun göçle azaldığını söyler. 2025'te
Ankara +31.172, İstanbul −41.346. Ülke toplamı sıfırdır, o yüzden Türkiye düzeyinde
yayımlanmaz.

## migration_net_rate

Net göçün bin kişiye oranı. Net göçün mutlak sayısı büyük illeri öne çıkarır; hız, küçük
bir ilin nüfusunun yüzde ikisini kaybetmesini görünür kılar. 2025'te Yalova +20,5, Ağrı
−27,0.

## migration_out

Yıl içinde ilden başka bir ile taşınan kişi sayısı. Türkiye genelinde aldığı göç toplamı
ile verdiği göç toplamı tanım gereği eşittir — her taşınma bir il için giriş, başka bir
il için çıkıştır — ve veri bunu tutuyor (2025'te ikisi de 2.475.019).

## migration_to_abroad

Yıl içinde ilden yurt dışına taşınan kişi sayısı.

## natural_increase

Doğum sayısı eksi ölüm sayısı: bir yerin kendi kendine kazandığı ya da kaybettiği nüfus.
Nüfusun gerçek değişimiyle arasındaki fark göçtür — ikisi birlikte okunduğunda bir ilin
büyümesinin ne kadarının doğumdan, ne kadarının gelenden geldiği görünür. Eksi değer,
ölümün doğumu geçtiği yer demektir. Türkiye 2009'da 897 binken 2025'te 404 bine indi.
Bizim çıkarmamızdır (rozet: türetilmiş), iki yayımlanmış sayının tam farkı. Her iki
tarafın da yayımlandığı yıllarda var: 2009-2025.

## pop_age_structure

Nüfusun yaş gruplarına dağılımı. 2013 öncesi kent/kır ayrımı da taşınabilir; o satırlar
IPF ile üretildiği için kalite bayrağı `estimated` olur.

## population

İkamet edilen yerin nüfusu, beşli yaş grubu ve cinsiyet kırılımıyla. Nüfus piramidi bu
göstergeden çizilir. En üst grup 75+ olarak kapalıdır; kaynak dosya tek yaş verirken
75'ten sonrasını toplulaştırıyor.

## population_density

Kilometrekareye düşen kişi sayısı. İstanbul 2.943, Tunceli 11 — nüfusun kendisinden
farklı bir soruyu yanıtlar: kaç kişi değil, ne kadar sıkışık. Yüzölçümü sabit olduğu
için yıllar arası değişimi nüfusun değişimiyle aynı biçimde hareket eder.

## registry_population

Bir ile nüfusa kayıtlı kişi sayısı — orada yaşayan değil, nerede yaşarsa yaşasın o ilin
kütüğünde duran. Nüfusla oranı, kuşaklar boyu göçün tek sayıya inmiş hâlidir: 2019'da
Ardahan'ın kütüğünde ilde yaşayanın **5,5 katı** kişi var, İstanbul'un kütüğünde ise
ilde yaşayanın ancak **%16'sı**. Yıl içi bir hareketi değil, birikmiş bir durumu anlatır
— bu yüzden aldığı/verdiği göçle aynı şey değildir. **Kırılım nerede yaşadıklarını
söyler.** "Tümü (topla)" kütüğün tamamı; "İlinde" o ilde yaşayan kendi kütüklüleri
(İstanbul'da yaşayan İstanbullular); "İl dışında" kütükte olup başka yerde yaşayanlar.
"Nerede yaşıyor içinde %" kipi de kütüğün yüzde kaçının hâlâ ilde olduğunu verir —
2025'te Şanlıurfa'da yüksek, İstanbul'da düşük. Üçünün de yıllık değişimi türetmeden
okunur, yani kütüğün ildeki ve dışarıdaki kısmı ayrı ayrı ne hızla büyüyor sorusu
doğrudan sorulabilir. Yabancı uyruklu nüfus buna dahil değildir: kütüğü olmayan kişi
hiçbir ilin kütüğünde sayılmaz. Türkiye toplamıyla ADNKS nüfusu arasındaki fark da bu
kadardır (2019'da 1,53 milyon). 2007-2025'in tamamı var; kaynakta ikamet ili kırılımı
zorunlu olduğu için ölçü 81 gösterge × 82 alan ve on dokuz yıl birlikte 126 bin hücreyle
sınırı aştığından yıl yıl indirildi (`fetch_medas_simple kutuk-nufusu --yil=2019`).

## tfr

Bir kadının doğurgan çağı boyunca, o yılın yaşa özel doğurganlık hızları geçerli
kalsaydı doğuracağı ortalama çocuk sayısı. Yenilenme düzeyi 2,10 kabul edilir. TÜİK
yalnızca il düzeyinde yayımlıyor, ilçe kırılımı yok.

## under5_mortality

Bin canlı doğum başına, beşinci yaş gününü görmeden ölen çocuk sayısı. Bebek ölüm hızını
**içerir**, onun yanına eklenmez: aradaki fark bir ile beş yaş arasındaki ölümlerdir.
Türkiye'de bu fark küçüktür, yani iki seri birbirine yakın seyreder.
