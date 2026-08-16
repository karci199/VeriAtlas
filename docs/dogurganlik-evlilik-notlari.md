# Doğurganlık, evlenme yaşı ve anne doğum yaşı — bulgular ve sıradaki iş

Bu dosya henüz koda girmemiş bulguları kaydeder. İki yeni kaynak masaüstünden
geldi, ikisi de depoya alınmadı — burada iz olarak duruyor, sonra yüklenecek.

## Özet — bugüne kadar ne bulundu

Ana soru: Türkiye'de doğurganlık düşüyor, **mekanizması ne?**

| Aday mekanizma | Kanıt (aynı pencere, 2019-2025) | Karar |
|---|---|---|
| Doğum aralığının açılması | değişimde r=+0,64, kısmi +0,56 | ✅ en güçlü katkı |
| İlk doğumun ertelenmesi | değişimde r=+0,50, kısmi +0,35 | ✅ **bağımsız katkı var** |
| Evlenmenin ertelenmesi | r=+0,06 | ❌ ilgisiz |
| Hiç evlenmeme | kesitte r=+0,11; birlikte açıklama gücü düşüyor | ❌ reddedildi (Bulgu 11) |

Doğurganlık, insanlar geç **evlendiği** için düşmüyor — evlenme yaşıyla bağ yok.
**İkisi birden** düşürüyor: ilk doğumun ertelenmesi ve sonraki çocukların arasının
açılması. Aralık biraz daha güçlü, ama "tek mekanizma" değil (Bulgu 14 düzeltmesi).

⚠️ **İki büyük çekince** (Bulgu 14-15):
- Kesitteki r=−0,96 **bölge içinde geçerli değil** (orta 27 il: −0,32). Üstünlük
  büyük ölçüde doğu-batı ekseninden geliyor.
- İlişki **doğrusal değil, doyuyor**: ilk doğum yaşı 25,7→26,9 iken GDH 58,1→38,5
  (−19,6), ama 26,9→28,4 iken yalnız 38,5→34,3 (−4,2). ~27 yaştan sonra ilk doğum
  yaşı doğurganlığı belirlemiyor. Türkiye'nin çoğu ili bu eşiği geçmiş, yani
  **ileriye dönük olarak ilk doğum yaşı bir kaldıraç değil.**
- Aralık serisi yalnız 7 yıl (2019-2025); bütün aralık sonuçları kısa panele dayanıyor.

**İki farklı yol, aynı sonuç** (Bulgu 9): güneydoğu erken evlenip araları açıyor;
batı/Trakya geç başlıyor, aralığı zaten geniş, doğurganlığı doğrudan çocuk
sayısını keserek düşürüyor. Tek eksenli "doğu geleneksel–batı modern" okuması yanlış.

**Sınır** (Bulgu 10): il toplamında aralık ~5,2 yılda duruyor. Ama yaş grubu
içinde 5,2 rahatça aşılıyor (35-39: 6,72) — tavan davranışsal değil, ilin **yaş
bileşiminin** sınırı. Batı tavana dayanmış; güneydoğu 3,3-4,2'de, **1-1,9 yıl
yolu var**. Düşüşün geri kalanı oradan gelecek.

**Ölçü uyarısı** (Bulgu 11): "hiç evlenmemiş oranı" tek başına yorumlanamaz —
güneydoğuda kayıt dışı evliliği, metropolde bekârlığı, Karadeniz'de çocuksuzluğu
ölçüyor. Doğum tarafındaki medeni durum sütunlarıyla birlikte okunmalı.

**Açık uçlar:** akraba evliliği paneli (2010-2025, 81 il) hazır ama kullanılmadı;
il düzeyinde yaşa özel doğurganlık hızı türetilebilir (TÜİK yayınlamıyor);
Türkiye'de 2016'da başlayan sert evlenmeme kırılması açıklanmadı.

## Yeni kaynaklar (henüz `raw/`e taşınmadı, depoya alınmadı)

- `annedogumyas.xls` — İkametgah yerine göre doğum sayısı, **annenin yaş
  grubuna göre** (9 bant: -15, 15-19, ..., 45-49, 50+, Bilinmeyen). 81 il,
  2009-2025. Toplamları `births.csv.gz`'deki değerlerle birebir tutuyor
  (2009: 1.266.751, 2025: 895.374) — yani `births` göstergesinin bir kırılım
  fazlası, `deaths`in yaş dosyasıyla aynı ilişki.
- `16_17_evlenenkadinorani.xls` — 16-17 yaş grubunda evlenenlerin toplam
  evlenmeler içindeki oranı (%), kadın, 81 il, **2002-2025**. Türkiye
  toplamı dosyada yok, yalnız iller.

İkisi de `xlrd` ile okundu (eski `.xls` formatı, MEDAS'ın kendi
`|`-ayraçlı yapısı yerine gerçek Excel hücreleri — hücre tipi (metin/sayı)
karışabiliyor, yıl sütunu metin olarak geldi ve ilk denemede sessizce 0 satır
okundu).

## Bulgu 1 — ortalama anne doğum yaşı, bant orta noktalarıyla hesaplandı

TR: 26,92 → 28,93 (+2,01 yıl), 2009-2025. İlk evlenme yaşındaki artışla
(+2,5 yıl) aynı yönde ama büyüklüğü farklı — evlenme erteleniyor, doğum da
erteleniyor, aynı oranda değil.

En çok artan 10 il **Çorum, Yozgat, Kırşehir, Ordu, Kütahya, Tokat, Giresun,
Amasya, Samsun, Kastamonu** — İç Anadolu/Karadeniz. En az artan 10 **Siirt,
Diyarbakır, Mardin, Hatay, Osmaniye, Ağrı, Gaziantep, Şırnak, Kilis,
Şanlıurfa** (Şanlıurfa −0,06, tek il gerçekte artmamış).

## Bulgu 2 — 16-17 yaş evlenme oranı, 2002'den beri düşüşün coğrafyası tersine döndü

2002'de en yüksek oran İç Anadolu'daydı (Nevşehir %16,7, Kırıkkale/Çankırı
%14,8). Bu iller en hızlı düşenler oldu (Nevşehir −14,4 puan) ve 2025'te
neredeyse sıfırlandılar. Buna karşılık 2002'de zaten orta/düşük olan
güneydoğu (Ağrı, Bitlis, Muş, Kars) **şimdi Türkiye'nin en yükseği** ve
düşüş en yavaş — Ağrı 23 yılda tek **artan** il (+0,4 puan).

## Bulgu 3 — dört gösterge aynı ~8 ili işaret ediyor, ama iki farklı grup var

Evlenme yaşı artışı, GDH düşüşü, anne doğum yaşı artışı, çocuk evliliği
düşüşü — dördünde de en az değişen grup: **Ağrı, Şanlıurfa, Gaziantep,
Kilis, Muş, Şırnak, Mardin, Diyarbakır.** Tutarlı.

Ama en çok değişen taraf beklenmedik: **Çorum, Yozgat, Kırşehir, Ordu,
Kütahya, Tokat** — "geleneksel doğu" hikâyesine uymuyorlar. Bu iller
başlangıçta (2002-2009) en geride olan gruptu, şimdi en hızlı değişen taraf.
Yani coğrafya sabit bir "doğu-batı" ekseni değil, **başlangıç noktasına
göre yakınsama** — geriden başlayanlar hızlı kapatıyor.

## Doğu illerinde evlenme yaşının az artmama nedeni araştırıldı, veri yetersiz

Üç hipotez test edildi, üçü de zayıf çıktı: 2009'da düşük başlama (taban
etkisi, r=-0,22), net göç (r=+0,12), nüfus yoğunluğu (r=-0,11). Yabancı
uyruklu nüfus göstergesi Suriyeli mülteci etkisini test etmek için
kullanılamaz — `foreign_population` yalnız ikamet izinli yabancıları
sayıyor, geçici koruma statüsünü kapsamıyor (Şanlıurfa 2025: 5.397 —
gerçek sayı yüz binlerce olmalı). Kadın eğitim süresi, işgücüne katılım,
kırsal/muhafazakâr norm gibi olası nedenler depoda yok.

## Sıradaki iş

1. İki dosyayı `raw/medas/` altına taşı, adaptör yaz (anne yaş bandı `deaths`
   yaş kırılımıyla aynı desen — `births` göstergesine `age` dim eklenir;
   çocuk evliliği oranı yeni ve küçük bir gösterge, `topic.evlenme_bosanma`).
2. Anne doğum yaşını `deaths`teki gibi türetme yap: ortalama anne doğum yaşı,
   il ve Türkiye, bant orta noktalarıyla — `mean_death_age` ile aynı desen.
3. Regresyon artığı yöntemini (evlenme gecikmesi ~ GDH düşüşü) koda geçir,
   Şanlıurfa gibi küçük paydalı illerin oranı patlatmasını önlemek için.

## Yeni kaynak — TÜİK'in kendi ilk doğum yaşı tablosu, bant tahminini doğruluyor

`İllere Göre İlk Doğumdaki Ortalama Anne Yaşı.xls` — TÜİK'in doğrudan
hesapladığı, yalnız ilk çocuk, il düzeyinde, **2014-2025**. Bant orta
noktasıyla tahmin değil, gerçek TÜİK ortalaması.

TR: 25,51 (2014) → 27,46 (2025), +1,94 yıl. Bulgu 1'deki tüm-doğumlar
tahminiyle (+2,01 yıl, 2009-2025) artış hızı neredeyse örtüşüyor — bant
orta noktası yöntemi doğrulandı. Seviye farkı beklenen yönde: tüm doğumlar
2025'te 28,93, ilk doğum 27,46 — ikinci/üçüncü çocuklar ortalamayı yukarı
çekiyor.

**Çelişkili bulgu:** Van, Kars, Hakkari, Bayburt, Siirt, Erzurum — Bulgu 1'de
"en az değişen" gruptaydı, burada **ilk doğumu en çok geciktiren** 10 il
içindeler. Yorum: bu illerde ilk çocuk gecikiyor ama doğum aralıkları hâlâ
sıkı, toplam doğurganlığın ortalaması bu yüzden az değişmiş görünüyor —
geç başlayıp hızlı devam ediyorlar. Şanlıurfa tek istisna: hem tüm
doğumlarda hem ilk doğumda tutarlı biçimde en az değişen il (+0,83 yıl,
2014-2025 — listenin sonuncusu).

Bu üçüncü kaynak da henüz depoya alınmadı.

## Dördüncü kaynak — TÜİK'in resmi tüm-doğumlar ortalama yaşı, bant tahminini test etti

`İllere Göre Annenin Ortalama Yaşı (TR,DF_DOGUM_ANNE_ORTYAS_C,1.0).xlsx` —
TÜİK'in kendi resmi ortalaması (bant orta noktası tahmini değil), 2009-2025,
81 il. `openpyxl` ile okundu; `read_only=True` bu dosyada satırları
göremedi (1 satır döndürdü), normal modda doğru okundu — not edilsin.

TR: 27,43 (2009) → 29,42 (2025). Bulgu 1'deki bant tahminim (26,92 → 28,93)
sistematik olarak **~0,5 yıl düşük** çıkıyor — yön ve artış hızı doğru
(+1,99 vs +2,01), seviye hafif iyimser. Bant orta noktaları (`-15`→13,
`50+`→52 gibi) kabaca seçilmişti; gerçek dağılım bandın üst yarısına
kaymış olabilir.

## Bulgu 4 — "ortalama anne yaşı eksi ilk doğum yaşı" endeksi, 81 ilin hepsinde daralıyor

Fark = kaçıncı çocuğun ortalamayı ne kadar yukarı çektiğinin dolaylı ölçüsü;
büyük fark = çok çocuklu il. TR: 2,85 yıl (2014) → 1,96 yıl (2025), endeks
(fark/ilk doğum yaşı) %13,7 → %7,1.

**81 ilin hiçbirinde fark büyümedi.** En az daralan (zaten küçük, düşük
doğurganlıklı): Karabük, Bilecik, Tekirdağ, Bursa, İstanbul (2,14→1,46),
Ankara. En çok daralan (2014'te dev, hızla eriyen): Kars, Hakkari, Şırnak,
Aksaray, **Siirt (4,86→3,06, −1,80 yıl)** — GDH'si en hızlı düşen illerle
bire bir örtüşüyor (bkz. Bulgu 3).

Dördüncü kaynak da henüz depoya alınmadı.

## Beşinci kaynak — anne yaşı × doğum sırası kesişimi, yalnız Türkiye 2025

`Annenin Yaş Grubu ve Doğum Sırasına Göre Doğumlar (...DF_DOGUM_ANNE_YAS_DOGUM_SIRA_C,1.0).xlsx`
— il yok, tek yıl (2025), ama anne yaş grubu (10 bant: <15…50+) ile doğum
sırasının (1, 2, 3, 4+) tam kesişimi var. TR 2025 toplam 895.374 doğumun
383.482'si ilk çocuk, 273.052'si ikinci, 138.465'i üçüncü.

Bu tek yıl-tek coğrafya olduğu için zaman/il karşılaştırması yapılamıyor;
ama önceki bulguların (ortalama-ilk doğum farkı, Bulgu 4) arkasındaki ham
dağılımı doğrulamak için kullanılabilir — doğum sırasına göre yaş
dağılımının şekli burada görünür.

## TÜİK Veri Portalı — kullanıcının bulduğu bağlantılar, henüz taranmadı

Not olarak bırakılıyor, WebFetch sayfayı boş döndürdü (JavaScript ile
render ediliyor, tarayıcıyla açmak gerekiyor):

- `veriportali.tuik.gov.tr/tr/bulk-download` — toplu indirme sayfası
- `veriportali.tuik.gov.tr/tr/popular-comparisons` — popüler karşılaştırmalar
- `veriportali.tuik.gov.tr/tr/infographics` — infografikler
- `.../databrowser/.../DF_EVLENME_ORT_ILK_EVL_YAS,1.0` — ort. ilk evlenme yaşı tablosu
- `.../search?q=anne&type=2,5` — "anne" araması, sayfa 2
- `.../databrowser/.../DF_DOGUM_ORTYAS_ILKDOG_C,1.0` — ilk doğumda ort. anne yaşı (muhtemelen elimdeki `.xls` ile aynı seri, tazelenmiş sürümü)

## Masaüstünde 15 yeni MEDAS dökümü (henüz depoya alınmadı)

Hepsi `C:\Users\katan\OneDrive\Desktop\demografi\` altında, sadece envanteri
çıkarıldı:

| Dosya | Kapsam | İl var mı | İçerik |
|---|---|---|---|
| İl ve Annenin Yaş Grubuna Göre Doğumlar | 2009-2025 | ✔ 81 il | Yaş grubu × il × yıl — bant tahminimin **tam hassas** karşılığı, artık tahmine gerek yok |
| Yaşa Özel Doğurganlık Hızı | 2001-2025 | ✘ TR toplam | 15-19…40+ her yaş grubunun kendi doğurganlık hızı, TFR'nin bileşenleri |
| Temel Doğurganlık Göstergeleri | 2001-2025 | ✘ TR toplam | Doğum sayısı, kaba doğum hızı, GDH, TFR, adölesan doğurganlık hızı — hazır |
| İl ve annenin yasal medeni durumuna göre doğumlar | 2012-2025 | ✔ 81 il | Hiç evlenmedi / evli / eşi öldü — bkz. Bulgu 5 aşağıda |
| Annenin yaş grubu ve eğitim durumuna göre doğumlar | 2015-2025 | ✘ TR toplam | Eğitim düzeyi × yaş |
| İl ve annenin evlilik süresine göre doğumlar | 2015-2025 | ✔ 81 il | Evlilikten 1 yıldan az / 1 / 2... yıl sonra doğum |
| İllere ve doğum sırasına göre son iki doğum arası ortalama süre | 2019-2025 | ✔ 81 il | Doğum aralığı, yıl cinsinden |
| Annenin doğum sırasına göre son iki doğum arası aylık aralık | ? | ? | Aylık çözünürlük, bakılmadı |
| Annenin yaş grubu ve doğum sırasına göre son iki doğum arası aylık aralık | ? | ? | Bakılmadı |
| Doğum sırasına göre doğumların oranı | 2012-2025 | ✘ TR toplam | %1./2./3./4+ doğum payı, yıl yıl |
| Annenin yaş grubu ve doğum sırasına göre doğumlar | 2025 tek yıl | ✘ TR toplam | Bkz. Bulgu 4'ün altındaki not — il/zaman yok |
| İllere Göre Annenin Ortalama Yaşı | 2009-2025 | ✔ 81 il | Bkz. Bulgu 4 (kullanıldı) |
| İllere Göre İlk Doğumdaki Ortalama Anne Yaşı | 2014-2025 | ✔ 81 il | Bkz. Bulgu 2 (kullanıldı) |
| annedogumyas.xls | 2009-2025 | ✔ 81 il | Bkz. Bulgu 1 (kullanıldı, bant tahmini) |
| 16_17_evlenenkadinorani.xls | 2002-2025 | ✔ 81 il | Bkz. Bulgu 2 (kullanıldı) |

## Bulgu 5 — "hiç evlenmedi" doğum oranı, il düzeyi, 2012→2025

⚠️ **Okuma uyarısı:** "yasal medeni durum" resmi nikahı ölçüyor. Türkiye'de
dini nikahlı ama resmi nikahsız birliktelikler yaygın, özellikle doğu/
güneydoğuda — bu kategori büyük olasılıkla batılı anlamda "evlilik dışı
doğum" değil, **resmî kaydı olmayan fiili evlilik**. Şanlıurfa'nın en
yüksek çıkması ve bölge içi ters yönlü hareketler bunu destekliyor.

TR: %2,09 (2012) → %2,27 (2025), neredeyse sabit.

2025 en yüksek: Şanlıurfa %7,73, Adana %4,74, Osmaniye %4,04, Diyarbakır
%3,77, Karabük %3,23. En düşük: Rize %0,48, Trabzon %0,53 — Karadeniz
neredeyse sıfır.

En çok artan: Şanlıurfa +3,41 puan, Karabük +2,19, Eskişehir +1,05. En çok
azalan: Hakkari −2,52, Şırnak −2,38, Aksaray −1,99, Bingöl −1,88 — **aynı
bölgede Şanlıurfa yükselirken komşuları düşüyor, bölge homojen değil.**

## Bulgu 6 — doğum aralığı güneydoğuda daralmıyor, açılıyor

"İllere ve Annenin Doğum Sırasına Göre Son İki Doğumu Arasındaki Ortalama
Süre" (2019-2025, il düzeyi). TR: 4,62 → 4,76 yıl (açılıyor).

2025 en kısa aralık: Şanlıurfa 3,32 yıl, Şırnak 3,54, Mardin 3,88 — hâlâ en
sık doğuran iller. Ama **en çok açılan** da aynı bölge: Ağrı +0,65 yıl,
Van +0,63, Bingöl +0,61, Bitlis +0,60, Muş +0,60, Iğdır +0,54, Siirt +0,52,
Hakkari +0,49 (2019-2025). GDH'nin en hızlı düştüğü illerle bire bir aynı
liste (bkz. Bulgu 3).

## Bulgu 7 — evlenir evlenmez ilk çocuk hâlâ güneydoğuda, ama hızla azalıyor

"İl ve annenin evlilik süresine göre doğumlar" (2015-2025, il düzeyi).
Evlilikten <1 yıl içinde doğum oranı, TR: %11,55 → %10,03.

2025 en yüksek: Hakkari %14,77, Şırnak %14,72, Diyarbakır %14,71, Ağrı
%14,34, Van %13,85 — hep güneydoğu. En düşük: Tunceli %5,22, Bayburt %6,97,
Erzincan %7,11 — Karadeniz + Tunceli.

En çok azalan: Bingöl −6,04 puan, Tunceli −4,61, Kars −4,00 — bu davranış
da hızla değişiyor, ama Bulgu 6'daki aralık açılmasından daha yavaş.

**Üç bulgu (5,6,7) birlikte:** güneydoğu illeri hâlâ evlenir evlenmez ilk
çocuğu yapıyor (evlenme davranışı değişmedi) ama **ilk çocuktan sonraki
aralığı hızla açıyor** (doğurganlık düşüşünün mekanizması burada) —
evlenmeyi erteleme değil, aile planlamasının evlilik içinde değişmesi.

## Bulgu 8 — GDH düşüşü, doğum aralığı açılmasını güçlü açıklıyor (r=0,64)

Regresyon artığı yöntemi (Bulgu 3'teki gibi): x = GDH düşüşü % (2019-2025,
aralık verisiyle aynı pencere), y = doğum aralığı değişimi (yıl). Doğru:
aralık = -0,675 + 0,0319 × GDH_düşüşü, r=0,64 — evlenme yaşı ~ GDH
ilişkisindeki r=0,06'dan (Bulgu 3) çok daha güçlü.

**Yorum:** doğurganlık düşüşünün asıl mekanizması evlenmenin ertelenmesi
değil, doğum aralığının açılması.

Pozitif artık (GDH düşüşünden beklenenden fazla aralık açmış) — hep
güneydoğu: Gümüşhane +0,40, Şırnak +0,35, Siirt +0,33, Bitlis +0,32,
Şanlıurfa +0,31, Diyarbakır +0,31, Hakkari +0,29, Mardin +0,28 yıl.

Negatif artık (aralık beklenenden az açılmış — düşüş büyük olasılıkla
doğrudan çocuk sayısını azaltarak, "1 çocukta durarak" gerçekleşiyor):
**Tunceli −0,50** (en uç), Kırıkkale −0,32, Çanakkale −0,27, Zonguldak
−0,27, Erzincan −0,25, Denizli −0,24, Antalya/Çorum −0,23.

**İki mekanizma haritası (Bulgu 3+8 birlikte):** güneydoğuda evlenme erken
kalıyor, doğurganlık aralık açılarak düşüyor; Trakya/Batı'da (Tunceli,
Antalya, Denizli, Çanakkale) doğurganlık zaten düşük, aralık sabit kalıyor
— düşüş muhtemelen doğrudan az-çocuk kararıyla oluyor, aralık değişmeden.

## Bulgu 9 — dört göstergenin onluk tabloları; kesitte GDH ~ doğum aralığı r=−0,96

Bulgu 8 yalnız *değişim* ilişkisini kaydetmişti (GDH düşüşü ~ aralık açılması,
r=0,64). **Seviye** ilişkisi çok daha sıkı: 2025 kesitinde 81 il için
GDH ~ doğum aralığı **r = −0,96**. Karşılaştırma: GDH ~ ilk doğum yaşı r=−0,74,
GDH ~ ortalama anne yaşı r=−0,48.

**Doğum aralığı nedir:** annenin *son iki doğumu arasında* geçen ortalama yıl.
O yıl ilk çocuğunu doğuranlar kapsam dışı — "ne zaman başlıyor" değil,
*başladıktan sonra ne kadar ara veriyor* ölçüsü. Doğurganlık penceresi kabaca
sabit olduğundan aralık açıldıkça pencereye sığan doğum azalır. Mekanizma bu.

GDH = genel doğurganlık hızı, 1.000 kadın (15-49) başına canlı doğum; ambardaki
`births` ve `population` sayımlarından türetildi (hazır gösterge yok). Diğer üç
sütun TÜİK'in kendi hesabı. Pencere 2019-2025 (aralık serisi 2019'da başlıyor).

⚠️ Genel/kaba hızlar toplanamaz: bu tabloların il satırları birleştirilemez.


### A. GDH'si en yüksek 10 il

| İl | GDH ‰ | İlk doğum | Ort. anne | Aralık | Aralık değ. | GDH düşüşü |
|---|---|---|---|---|---|---|
| *Türkiye* | *40,8* | *27,5* | *29,4* | *4,76* | *+0,14* | *%26,2* |
| Şanlıurfa | 96,6 | 24,4 | 28,2 | 3,32 | +0,3 | %20,7 |
| Şırnak | 80,2 | 25,9 | 29,1 | 3,54 | +0,41 | %23,1 |
| Mardin | 68,6 | 26,1 | 29,2 | 3,88 | +0,43 | %25,9 |
| Ağrı | 66,6 | 24,7 | 27,7 | 4,06 | +0,65 | %35,1 |
| Siirt | 66,5 | 25,9 | 28,9 | 4,04 | +0,52 | %27,1 |
| Bitlis | 64,8 | 25,7 | 28,6 | 4,15 | +0,6 | %30 |
| Diyarbakır | 64,6 | 26,2 | 29,2 | 4,17 | +0,44 | %25,3 |
| Muş | 62,3 | 24,9 | 28,2 | 4,05 | +0,6 | %38 |
| Batman | 61,2 | 26,7 | 29,7 | 4,17 | +0,44 | %26,4 |
| Gaziantep | 59,2 | 25,3 | 28,1 | 4,32 | +0,26 | %26,1 |

**Çıkarım:** dört sütun da aynı yöne bakıyor. Yüksek GDH grubunda ilk doğum yaşı
Türkiye'nin **2,3 yıl altında** (25,6 vs 27,8) ama aralık **1,4 yıl daha dar**
(3,97 vs 5,37). Yani iki dezavantaj üst üste binmiyor — asıl ayrım aralıkta.
İlk doğum yaşındaki 2,3 yıllık fark tek başına 96,6 ‰ ile 30,8 ‰ arasındaki
üç katlık farkı açıklayamaz; aralıktaki 1,4 yıl açıklar. Liste hemen hemen
tümüyle güneydoğu — bu bir bölge tablosu.

### B. GDH'si en düşük 10 il

| İl | GDH ‰ | İlk doğum | Ort. anne | Aralık | Aralık değ. | GDH düşüşü |
|---|---|---|---|---|---|---|
| *Türkiye* | *40,8* | *27,5* | *29,4* | *4,76* | *+0,14* | *%26,2* |
| Zonguldak | 28,5 | 27,9 | 29,5 | 5,25 | −0,16 | %24,4 |
| Bartın | 29 | 27,2 | 29,2 | 5,52 | +0,14 | %25,2 |
| Kütahya | 30,5 | 27 | 29,3 | 5,55 | −0,09 | %21,6 |
| İzmir | 30,7 | 28,7 | 30,1 | 5,36 | +0,09 | %28,4 |
| Karabük | 31,1 | 27,7 | 29,8 | 5,47 | −0,02 | %16 |
| Eskişehir | 31,3 | 28,6 | 30 | 5,34 | +0,07 | %22,9 |
| Edirne | 31,7 | 27,6 | 28,7 | 5,19 | −0,37 | %15,8 |
| Çanakkale | 31,7 | 28,1 | 29,6 | 5,31 | −0,25 | %21,6 |
| Ankara | 31,8 | 28,6 | 30,1 | 5,4 | +0,09 | %29 |
| Kırıkkale | 31,9 | 27 | 29 | 5,29 | −0,12 | %27,2 |

**Çıkarım:** ayna görüntü: aralık 5,2-5,6 yıl bandında toplanmış, ilk doğum yaşı 27-28,7.
Dikkat: bu illerde aralık değişimi **sıfıra yakın ya da eksi** (ortalama −0,06).
Yani düşük doğurganlık burada "aralık açarak" sürdürülmüyor — zaten açılmış,
tavana dayanmış. Bir ilin aralığı ~5,4 yıla gelince o kaldıraç bitiyor; bundan
sonraki düşüş başka yoldan (hiç çocuk yapmama / 1 çocukta durma) gelmek zorunda.
Karabük %16, Edirne %15,8 gibi çok yavaş düşüşler bunun işareti.

### C. Doğum aralığını en çok açan 10 il

| İl | GDH ‰ | İlk doğum | Ort. anne | Aralık | Aralık değ. | GDH düşüşü |
|---|---|---|---|---|---|---|
| *Türkiye* | *40,8* | *27,5* | *29,4* | *4,76* | *+0,14* | *%26,2* |
| Ağrı | 66,6 | 24,7 | 27,7 | 4,06 | +0,65 | %35,1 |
| Van | 59,2 | 26,2 | 28,9 | 4,42 | +0,63 | %34,5 |
| Bingöl | 46 | 27,5 | 30,3 | 5,02 | +0,61 | %35 |
| Bitlis | 64,8 | 25,7 | 28,6 | 4,15 | +0,6 | %30 |
| Muş | 62,3 | 24,9 | 28,2 | 4,05 | +0,6 | %38 |
| Iğdır | 50,2 | 26,2 | 28,6 | 4,54 | +0,54 | %36,3 |
| Siirt | 66,5 | 25,9 | 28,9 | 4,04 | +0,52 | %27,1 |
| Hakkari | 53,7 | 27,7 | 30,2 | 4,46 | +0,49 | %27,3 |
| Batman | 61,2 | 26,7 | 29,7 | 4,17 | +0,44 | %26,4 |
| Diyarbakır | 64,6 | 26,2 | 29,2 | 4,17 | +0,44 | %25,3 |

**Çıkarım:** **tablonun en önemlisi.** Onunun da GDH'si Türkiye ortalamasının üstünde ve
onunun da GDH düşüşü %25'in üstünde. Yani *hâlâ en sık doğuran* iller aynı
zamanda aralığı *en hızlı açan* iller. Bu, "doğu değişmiyor" tezinin tam tersi:
değişim orada, üstelik en hızlı orada. Ağrı +0,65, Van +0,63, Bingöl +0,61.

### D. Doğum aralığını daraltan / sabit tutan 10 il

| İl | GDH ‰ | İlk doğum | Ort. anne | Aralık | Aralık değ. | GDH düşüşü |
|---|---|---|---|---|---|---|
| *Türkiye* | *40,8* | *27,5* | *29,4* | *4,76* | *+0,14* | *%26,2* |
| Edirne | 31,7 | 27,6 | 28,7 | 5,19 | −0,37 | %15,8 |
| Burdur | 36,1 | 26,8 | 29 | 5,25 | −0,32 | %14 |
| Erzincan | 38,9 | 28 | 29,9 | 5,04 | −0,27 | %20,6 |
| Çanakkale | 31,7 | 28,1 | 29,6 | 5,31 | −0,25 | %21,6 |
| Tunceli | 38,1 | 28,9 | 30,2 | 4,72 | −0,2 | %30,5 |
| Balıkesir | 33,9 | 27,4 | 29,1 | 5,25 | −0,18 | %19,5 |
| Zonguldak | 28,5 | 27,9 | 29,5 | 5,25 | −0,16 | %24,4 |
| Nevşehir | 37,4 | 26,3 | 28,5 | 5,23 | −0,16 | %22,9 |
| Denizli | 34,5 | 27,6 | 29,6 | 5,39 | −0,14 | %24,3 |
| Kırıkkale | 31,9 | 27 | 29 | 5,29 | −0,12 | %27,2 |

**Çıkarım:** C'nin tersi ve tuzağı burada: bu iller aralığı **kapatıyor** ama GDH'leri
yine de düşüyor. Edirne −0,37 yıl aralık, buna rağmen %15,8 GDH düşüşü. Demek ki
düşüşün ikinci bir yolu var — aralık değil, *hiç ikinci çocuk yapmamak*.
Tunceli en uç örnek: aralık −0,20 (daralıyor) ama GDH düşüşü %30,5. Bulgu 8'deki
"negatif artık" grubu bunlar. **İki farklı mekanizma aynı sonucu veriyor.**

### E. GDH'si en hızlı düşen 10 il

| İl | GDH ‰ | İlk doğum | Ort. anne | Aralık | Aralık değ. | GDH düşüşü |
|---|---|---|---|---|---|---|
| *Türkiye* | *40,8* | *27,5* | *29,4* | *4,76* | *+0,14* | *%26,2* |
| Muş | 62,3 | 24,9 | 28,2 | 4,05 | +0,6 | %38 |
| Iğdır | 50,2 | 26,2 | 28,6 | 4,54 | +0,54 | %36,3 |
| Ağrı | 66,6 | 24,7 | 27,7 | 4,06 | +0,65 | %35,1 |
| Bingöl | 46 | 27,5 | 30,3 | 5,02 | +0,61 | %35 |
| Van | 59,2 | 26,2 | 28,9 | 4,42 | +0,63 | %34,5 |
| Erzurum | 44,2 | 27,1 | 29,5 | 4,75 | +0,44 | %31,3 |
| Tunceli | 38,1 | 28,9 | 30,2 | 4,72 | −0,2 | %30,5 |
| İstanbul | 33,3 | 28,9 | 30,4 | 5,1 | +0,11 | %30,3 |
| Kars | 49,5 | 26,1 | 28,3 | 4,5 | +0,4 | %30,1 |
| Bitlis | 64,8 | 25,7 | 28,6 | 4,15 | +0,6 | %30 |

**Çıkarım:** dokuzunda aralık açılıyor (+0,40…+0,65) — mekanizma net. Tek istisna
**Tunceli (−0,20)**: Türkiye'nin en yüksek ilk doğum yaşı (28,9) ve düşen aralık
ile %30,5 düşüş. Tunceli D grubunun mantığıyla, kalan dokuz il C grubunun
mantığıyla düşüyor. Aynı sıralamada iki ayrı hikâye.

### F. GDH'si en yavaş düşen 10 il

| İl | GDH ‰ | İlk doğum | Ort. anne | Aralık | Aralık değ. | GDH düşüşü |
|---|---|---|---|---|---|---|
| *Türkiye* | *40,8* | *27,5* | *29,4* | *4,76* | *+0,14* | *%26,2* |
| Burdur | 36,1 | 26,8 | 29 | 5,25 | −0,32 | %14 |
| Edirne | 31,7 | 27,6 | 28,7 | 5,19 | −0,37 | %15,8 |
| Kastamonu | 35,2 | 27,6 | 29,5 | 5,18 | −0,09 | %16 |
| Karabük | 31,1 | 27,7 | 29,8 | 5,47 | −0,02 | %16 |
| Gümüşhane | 32,7 | 28 | 30,4 | 5,19 | +0,29 | %17,6 |
| Bolu | 33,3 | 28,2 | 30,1 | 5,42 | −0,04 | %17,7 |
| Yalova | 38,5 | 28,4 | 29,9 | 4,97 | +0,01 | %17,8 |
| Balıkesir | 33,9 | 27,4 | 29,1 | 5,25 | −0,18 | %19,5 |
| Kırklareli | 32,2 | 28 | 29,4 | 5,63 | −0,05 | %20 |
| Erzincan | 38,9 | 28 | 29,9 | 5,04 | −0,27 | %20,6 |

**Çıkarım:** hepsi zaten düşük doğurganlıklı batı/Karadeniz illeri ve aralıkları zaten
geniş (5,0-5,6). Yavaş düşmelerinin nedeni muhafazakârlık değil **taban etkisi**:
kullanacak kaldıraç kalmamış. Bu, Bulgu 3'teki "başlangıç noktasına göre
yakınsama" gözlemiyle aynı şey — geriden başlayan hızlı kapatıyor, önde olan
yavaşlıyor.

### Hepsinden ne çıkıyor

1. **Doğurganlık düşüşünün asıl kaldıracı doğum aralığı.** Kesitte r=−0,96,
   değişimde r=0,64. Evlenme yaşı ertelemesiyle bağ neredeyse yok (r=0,06,
   Bulgu 3), ilk doğum yaşıyla orta (r=−0,74) — ve o ilişkinin bir kısmı
   zaten aralıkla birlikte hareket ettiği için.
2. **İki ayrı mekanizma var, ikisi de aynı sonuca çıkıyor.** Güneydoğu (C):
   erken evlen, erken başla, ama araları aç. Batı/Trakya (D): geç başla, aralığı
   zaten geniş, düşüşü doğrudan çocuk sayısını keserek yap. Tek bir "modernleşme
   ekseni" yok.
3. **Aralık kaldıracının bir tavanı var, ~5,4 yıl.** B ve F grupları o tavana
   dayanmış; oradaki iller artık aralık açarak düşemiyor, bu yüzden GDH düşüşleri
   yavaşlamış görünüyor. Güneydoğu (3,3-4,2 yıl) tavana daha çok var — **düşüşün
   hızlı kısmı orada henüz bitmedi.**
4. **Politika/tahmin açısından:** bir ilin gelecekteki doğurganlığını tahmin
   etmek için evlenme yaşına değil, doğum aralığının tavana ne kadar uzak
   olduğuna bakmak gerekiyor. Grup ortalamaları: yüksek10 aralık 3,97 /
   değişim +0,46; düşük10 aralık 5,37 / değişim −0,06.

**Okuma uyarısı (aralık dosyası):** MEDAS'ın yıl sütunu blok başında bir kez dolu
ve tipi karışık — `2025.0` sayı, `2024(r)` metin. Yalnız sayı tipini süzen okuma
ara blokları sessizce 2025'e yazar; TR 2025 değeri 4,76 yerine 4,60 çıkar.
Rakam süzerek okunmalı.

Tam 81 il tablosu üretilebilir: `ai/ornekler/002-gdh-ilk-dogum-yasi-dogum-araligi-tablosu.md`


## Bulgu 10 — "aralık tavanı" iddiası test edildi: tavan var, ama sayı 5,4 değil ~5,2

Bulgu 9'da "aralık kaldıracının ~5,4 yıl tavanı var" denmişti. O sayı test
edilmemişti: düşük GDH'li 10 ilin *o anki düzeyine* bakıp gözle okunmuştu, ki bu
yanlış tahmin edici — bir grubun bugünkü düzeyi onun durduğu yeri değil, sadece
bulunduğu yeri verir. Yedi yıllık panelle (81 il × 2019-2025, 567 gözlem) sınandı.

### Test 1 — yakınsama regresyonu

`değişim(2019→2025) ~ düzey(2019)`: eğim **−0,290**, sabit +1,532, **r = −0,831**.
Değişimin sıfırlandığı düzey = 1,532 / 0,290 = **5,28 yıl**. Yani dar aralıklı
iller hızla açılıyor, geniş olanlar duruyor ve sistem 5,3'e doğru yakınsıyor.

Havuzlanmış yıllık farklarla (486 gözlem) aynı hesap: eğim −0,066, r=−0,328,
denge **5,16 yıl**. İki yöntem 5,2-5,3 aralığında buluşuyor; **5,4 fazla yüksek.**

### Test 2 — başlangıç düzeyine göre dilimler

| 2019'daki grup | Ort. düzey 2019 | Ort. değişim | Aralığı açan il |
|---|---|---|---|
| En dar 20 il | 3,82 | **+0,427** | **20/20** |
| Orta 41 il | 5,01 | +0,100 | 35/41 |
| En geniş 20 il | 5,45 | **−0,101** | 4/20 |

Tek istisnasız: 3,8'den başlayan yirmi ilin yirmisi de açıldı; 5,45'ten başlayan
yirmi ilin on altısı daraldı. Tavan tek bir regresyon katsayısına değil, sayıma
dayanıyor.

### Test 3 — sınır yukarı kayıyor mu? (asıl test)

Tavan gerçekse dağılımın üst ucu yıllar içinde sabit kalmalı; "henüz ulaşılmamış
sınır" olsaydı yukarı sürüklenirdi.

| Yıl | Max | 95. yüzdelik | 5,4 üstü il |
|---|---|---|---|
| 2019 | 5,68 | 5,56 | 12 |
| 2021 | 5,54 | 5,40 | 5 |
| 2023 | 5,66 | 5,37 | 3 |
| 2025 | 5,63 | 5,44 | 7 |

Yedi yılda ülke ortalaması 4,83 → 4,96 çıkarken **üst uç kımıldamadı** — hatta
95. yüzdelik hafif geriledi. 567 gözlemin tarihsel maksimumu 5,75 ve hiçbir il
orada kalamadı. Sert bir duvar.

### Test 4 — 2019'da zaten 5,3 üstü olan 20 il

16'sı 2025'te daha düşük bitirdi; 17'sinin zirvesi 2019 ya da 2020'de. Örnekler:
Edirne 5,56→5,19, Burdur 5,58→5,25, Çanakkale 5,57→5,31, Kütahya 5,65→5,55,
Kırklareli 5,68→5,63 (zirve 5,74, sonra geri düştü). Tavana çarpıp sekiyorlar.

### Beş ilin yörüngesi

| İl | 2019 | 2021 | 2023 | 2025 | Toplam |
|---|---|---|---|---|---|
| Şanlıurfa | 3,02 | 3,12 | 3,15 | 3,32 | +0,30 |
| Ağrı | 3,41 | 3,51 | 3,79 | 4,06 | +0,65 |
| Konya | 4,98 | 4,89 | 5,03 | 5,07 | +0,09 |
| Kırklareli | 5,68 | 5,51 | 5,51 | 5,63 | −0,05 |
| Edirne | 5,56 | 5,40 | 5,30 | 5,19 | −0,37 |
| *Türkiye* | *4,62* | *4,57* | *4,68* | *4,76* | *+0,14* |

Ağrı düz tırmanıyor, Şanlıurfa yavaş ama tek yönlü, Konya duraklamış, Kırklareli
5,5-5,7 arasında salınıyor, Edirne geri çekiliyor. Düzey arttıkça hareket
tükeniyor.

### ⚠️ İki ciddi çekince — tavan "davranışsal" olmayabilir

1. **Bileşim etkisi (asıl şüphe).** Bu ölçü yalnız *o yıl en az ikinci çocuğunu
   doğuran* anneleri kapsıyor. Doğurganlık düştükçe ikinci çocuk yapanlar giderek
   *seçilmiş* bir grup oluyor — çok çocuk isteyen, dolayısıyla sık doğuran tip.
   Yani düşük doğurganlıklı ilde payda değiştiği için ortalama mekanik olarak
   yukarı çıkamıyor olabilir. Tavan gerçek bir davranış sınırı değil, **ölçünün
   kendi tanımından doğan bir sınır** olabilir. Ayırt etmek için doğum sırasına
   göre ayrı seriler (2.-1. arası, 3.-2. arası) karşılaştırılmalı — dosyada var,
   yapılmadı.
2. **Galton yanlılığı.** Yakınsama regresyonunda başlangıç düzeyindeki ölçüm
   gürültüsü eğimi olduğundan daha negatif gösterir; 5,28 bir üst sınır tahmini
   sayılmalı, nokta tahmini değil. Test 3 bu yanlılıktan etkilenmiyor ve tavanı
   bağımsız olarak destekliyor — asıl dayanak o.

**Bulgu 9'un 3. maddesi düzeltilmeli:** tavan ~5,4 değil **~5,2**. Sonuç değişmiyor,
hatta güçleniyor: batı/Karadeniz illeri (5,2-5,6) tavanın *üstünde ya da üzerinde*,
kaldıraçları bitmiş; güneydoğu 3,3-4,2'de, tavana 1-1,9 yıl var. Türkiye
doğurganlığındaki düşüşün aralık kaynaklı kısmı ağırlıkla oradan gelecek.

## Masaüstü dizininin ikinci taraması — envantere girmemiş dosyalar

Yukarıdaki 15'lik envanter dizinin tamamı değilmiş. `Desktop\demografi\` yeniden
tarandı; aşağıdakiler eksikti. İkisi bu projeyi doğrudan ilgilendiriyor.

### 1. Akraba evliliği oranı, il düzeyi, 2010-2025 — **en değerli yeni kaynak**

`İllere Göre Evlenme Sayısı ile Akraba Evliliği Sayısı ve Oranı
(TR,DF_EVLENME_AKRABA_EVLILIK,1.0).xlsx` — 81 il, 16 yıl, evlenme sayısı +
akraba evliliği sayısı + oranı (%).

TR: **%5,93 (2010) → %3,01 (2025)**, neredeyse yarıya inmiş.

2025 en yüksek: Şanlıurfa %16,9, Mardin %11,0, Siirt %10,8, Muş %9,8,
Şırnak %9,2, Bitlis %9,0, Diyarbakır %8,8, Ağrı %8,1.
En düşük: Kütahya %0,4, Edirne %0,4, Çanakkale %0,5, Karabük %0,6, Bolu %0,6.
**Kırk kat fark** ve sıralama Bulgu 9'un A tablosuyla (en yüksek GDH) neredeyse
birebir örtüşüyor.

Neden önemli: "Doğu illerinde evlenme yaşının az artmama nedeni araştırıldı, veri
yetersiz" başlığındaki üç hipotez de zayıf çıkmıştı (taban etkisi r=−0,22, net göç
r=+0,12, yoğunluk r=−0,11) ve "kırsal/muhafazakâr norm depoda yok" denmişti.
Akraba evliliği oranı tam da o eksik değişkenin ölçülebilir bir vekili —
üstelik 16 yıllık il paneli. **Sıradaki iş:** GDH, doğum aralığı ve ilk evlenme
yaşıyla korelasyonu; ve akraba evliliğindeki *düşüşün* aralık açılmasını
Bulgu 8'in artıklarını açıklayıp açıklamadığı.

### 2. Yaş grubu × doğum sırası × aralık (2019-2025, TR) — Bulgu 10'u sarsıyor

`Annenin Yaş Grubu ve Doğum Sırasına Göre Son İki Doğumu Arasındaki Ortalama
Süre.xls`. Bulgu 10'un 1. çekincesini (bileşim etkisi) test etmek için lazım olan
dosya buymuş. TR 2025, yaş grubuna göre aralık:

| Anne yaşı | Toplam | 2.-1. arası | 3.-2. arası |
|---|---|---|---|
| <25 | 2,44 | 2,46 | 2,48 |
| 25-29 | 3,72 | 3,69 | 4,07 |
| 30-34 | 5,10 | 4,97 | 5,76 |
| 35-39 | **6,72** | 6,63 | 7,59 |
| 40-44 | **8,31** | 8,35 | 9,69 |
| 45+ | 10,34 | 10,58 | 12,78 |
| *Toplam* | *4,76* | *4,34* | *5,50* |

**Bulgu 10 için sonuç:** aralık, yaş grubu içinde 5,2'yi rahatça aşıyor —
35-39'da 6,72, 40-44'te 8,31. Yani **~5,2 bireysel davranışta bir sınır değil.**
İl toplamındaki tavan, ilin yaş bileşiminin sınırı: bir ilin annelerinin tamamı
40'lı yaşlara kayamayacağı için toplam ortalama ~5,2'de takılıyor. Bulgu 10'daki
1. çekince (tavan davranışsal değil, tanımsal/bileşimsel) böylece **desteklendi**.

Bulgu 10'un ampirik kısmı (yakınsama r=−0,83, üst ucun 7 yıl kımıldamaması)
geçerliliğini koruyor — il düzeyinde tavan gerçek. Değişen şey yorumu:
"iller kaldıraçlarını tüketti" değil, **"il toplamı yaş bileşiminin izin verdiği
sınıra dayandı"**. Güneydoğu için çıkarım aynı kalıyor (tavana 1-1,9 yıl var),
ama nedeni farklı: oradaki anneler hâlâ genç yaş gruplarında yoğun.

### 3. Doğum aralığının dağılımı (yalnız ortalama değil)

`Annenin Doğum Sırasına Göre Son İki Doğumu Arasındaki Aylık Doğum Aralığı.xls` —
TR, doğum sırasına göre, aralığın **ay bantlarına dağılımı** (6-17 ay, … sayı ve %).
2025: 500.165 doğum, %7,3'ü 6-17 ay aralıkla. Ortalamanın gizlediği şekli
gösterir; tavanın ortalama artefaktı mı yoksa dağılımın gerçekten kayması mı
olduğunu ayırt etmek için kullanılabilir. Eşi: `Annenin Yaş Grubu ve Doğum
Sırasına Göre ... Aylık Doğum Aralığı.xls`.

### 4. İkincil / büyük olasılıkla zaten depoda olanlar

| Dosya | İçerik | Durum |
|---|---|---|
| `Annenin Yaş Grubuna Göre Doğum Yüzdesi.xls` | TR, 2001-, yaş bandı payları (%) | `annedogumyas` bandının yüzde hali |
| `İl, tek yaş ve cinsiyete göre nüfus.xls` | 81 il × tek yaş × cinsiyet | ambardaki `population` ile aynı olmalı |
| `FavoriRaporlar.xlsx` | 31.12.2025 ADNKS: il/ilçe/büyükşehir/belediye/mahalle/köy/kent-kır | depodaki nüfus dosyalarıyla örtüşüyor olmalı |
| `Annenin Doğum Sırasına Göre ... Ortalama Süre.xls` | il kırılımsız (TR) sürüm | ilçeli sürümü zaten kullanıldı |

### 5. Bu projeyle ilgisiz — İznik özel çalışması

`pivot.xls`, `yaslar2013sonrasi.xls`, `kentkiryaslar.xls`, `iznik_kent_kir.xlsx`,
`Bursa_Mahalleler_18.csv`, `OrtancaYas.csv` ve `cikti\`, `demografi1\`,
`demografi2\` klasörleri — Bursa/İznik kent-kır yaş yapısı çalışması, seçmen
verisi, fotoğraflar. Doğurganlık işine girmiyor, taranmasına gerek yok.

## Bulgu 11 — "hiç evlenmemiş" oranı: üçüncü mekanizma hipotezi çürüdü, gösterge çift anlamlı

Hipotez şuydu: ortalama ilk evlenme yaşı yalnız *evlenenleri* ölçüyor, hiç
evlenmeyenler o ortalamada görünmüyor. Batıdaki doğurganlık düşüşü (Bulgu 9'un D
grubu, "doğrudan çocuk sayısını kesme") aslında **hiç evlenmeme** olabilir; öyleyse
iki mekanizma haritası üçe çıkar.

Kaynak: ambardaki `marital_status` — 2008-2025, 81 il, cinsiyet × beşli yaş ×
medeni durum, 182.501 il satırı. Bugüne kadar hiç kullanılmamış. Pay
`never_married`, payda `unknown` hariç toplam. Kadın.

### Türkiye — asıl haber burada: 2016'da yön değişti

| Yıl | 25-29 | 30-34 | 35-39 | 40-44 |
|---|---|---|---|---|
| 2008 | 23,3 | 12,3 | 8,6 | 6,8 |
| 2012 | 24,2 | 12,0 | 8,5 | 6,7 |
| **2016** | 26,6 | **11,6** | 8,2 | 6,9 |
| 2020 | 32,5 | 13,1 | 8,2 | 6,9 |
| 2025 | **40,7** | **17,3** | 9,9 | 7,3 |

30-34 bandı 2008-2016 arasında **düşüyordu** (12,3 → 11,6), sonra sert döndü ve
dokuz yılda 17,3'e çıktı. 25-29 bandı 23,3'ten 40,7'ye — neredeyse iki katı; her
beş kadından ikisi 25-29 yaşında hiç evlenmemiş. Bu, deponun herhangi bir
göstergesindeki en keskin kırılma. Kırılma yılı ~2016-2017.

### Hipotez testi: çürüdü

| İlişki (81 il) | r |
|---|---|
| Hiç evlenmemiş (30-34, 2025) ~ GDH 2025 | **+0,109** |
| Hiç evlenmemiş ~ ilk doğum yaşı | +0,439 |
| Hiç evlenmemiş ~ doğum aralığı | −0,188 |
| Hiç evlenmemiş **artışı** ~ GDH düşüşü | **−0,370** |
| Hiç evlenmemiş **artışı** ~ aralık değişimi | −0,485 |

Kesitte GDH ile ilişki **sıfır** (+0,11). Dahası artış ilişkisi *ters*: hiç
evlenmeme oranı en çok artan iller, GDH'si en **az** düşen iller. İki değişkeni
standartlaştırıp toplayınca GDH düşüşünü açıklama gücü artmıyor, **düşüyor**
(tek başına aralık r=0,640 → ikisi birlikte r=0,267). Üçüncü mekanizma yok.

### Neden sıfır çıktı: gösterge tek şey ölçmüyor

2025'te 30-34 yaş hiç evlenmemiş oranı en yüksek iller **hem en doğurgan hem en
az doğurgan** illerden oluşuyor — bu yüzden korelasyon sönümleniyor.

| İl | Stok % | Hiç-evlenmedi doğum % | Boşanmış anne doğum % | GDH |
|---|---|---|---|---|
| Hakkari | 27,6 | 2,45 | **0,12** | 53,7 |
| İstanbul | 23,6 | 2,33 | 0,62 | 33,3 |
| Şırnak | 21,4 | 2,90 | **0,27** | 80,2 |
| Tunceli | 21,0 | **0,41** | 0,96 | 38,1 |
| Rize | 20,3 | **0,48** | 0,48 | 36,8 |
| Diyarbakır | 19,6 | 3,77 | 0,61 | 64,6 |
| Antalya | 18,8 | 2,13 | **1,27** | 33,2 |

Doğum tarafındaki iki sütun üç ayrı tipi ayırıyor:

1. **Güneydoğu tipi** (Hakkari, Şırnak, Diyarbakır, Mardin, Batman): stok yüksek,
   hiç-evlenmedi doğum yüksek (%2,5-3,8), boşanmış anne doğumu ~sıfır. Bulgu 5'in
   uyarısıyla tutarlı — resmî nikâhsız fiili evlilik. Kadın "hiç evlenmedi"
   sayılıyor ama evli ve doğuruyor.
2. **Metropol tipi** (İstanbul, İzmir, Ankara, Antalya): stok yüksek, boşanmış
   anne doğumu **en yüksek** (%0,6-1,3). Gerçek bekârlık + gerçek boşanma.
3. **Karadeniz/Tunceli tipi** (Tunceli, Rize, Trabzon, Gümüşhane): stok yüksek ama
   hiç-evlenmedi doğum **en düşük** (%0,4-0,7). Evlenmiyorlar ve doğurmuyorlar —
   gerçek bekârlık, evlilik dışı doğum yok.

⚠️ **Bu yüzden "hiç evlenmemiş oranı" tek başına yorumlanamaz.** Aynı sayı
Hakkari'de kayıt dışılığı, İstanbul'da bekârlığı, Rize'de çocuksuzluğu gösteriyor.
Doğum tarafındaki medeni durum sütunlarıyla birlikte okunmalı.

Not: kayıt-dışılık açıklaması tek başına da yetmiyor — stok ile hiç-evlenmedi
doğum payı arasında r = **+0,169**. Yani güneydoğunun yüksek stoğu tümüyle
kayıt sorunu değil.

### Artışı ne açıklıyor: göç

| İlişki | r |
|---|---|
| Hiç evlenmemiş **artışı** ~ kümülatif net göç oranı | **+0,421** |
| Hiç evlenmemiş **stoğu** ~ kümülatif net göç oranı | −0,037 |
| Hiç evlenmemiş stoğu ~ kadın medyan yaş | −0,153 |

Göç alan iller (İstanbul +9,4, Antalya +9,2, Muğla +9,1 puan) hiç evlenmemiş
oranını en çok artıranlar; göç veren güneydoğu illerinde oran **düşüyor**
(Şanlıurfa −4,4, Hatay −3,9, Mardin −3,6, Bingöl −3,3). Yani artışın önemli
kısmı davranış değil **bileşim**: genç bekârlar batıya gidiyor. Stok düzeyi ise
göçle açıklanmıyor — o yapısal.

### Yan ürün — boşanmış anneden doğum, hiç bakılmamıştı

TR: **%0,63 (2012) → %0,84 (2025)**. 2025 en yüksek Uşak %2,00, Edirne %1,64,
Aydın %1,47, Sinop %1,47, Adana %1,46. En düşük Hakkari %0,12, Artvin %0,15,
Şırnak %0,27, Van %0,33. Temiz bir batı-doğu eğimi; boşanma sonrası yeniden aile
kurmanın ölçüsü olarak kullanılabilir. Bulgu 5 bu sütuna hiç bakmamıştı.

### Sonuç

Üçüncü mekanizma hipotezi **reddedildi**: hiç evlenmeme, iller arası doğurganlık
düşüşünü sürükleyen bağımsız bir kanal değil. Bulgu 9'un iki mekanizmalı haritası
geçerliliğini koruyor. Ama iki yeni şey çıktı: (a) Türkiye düzeyinde 2016'da
başlayan çok sert bir evlenmeme kırılması — bu **zaman serisi** olgusu, iller
arası kesitte görünmüyor; (b) göstergenin üç ayrı olguyu tek sayıda topladığı,
dolayısıyla tek başına kullanılmasının hatalı olduğu.

## Bulgu 12 — medeni duruma göre doğurganlık hızı; düşüşün %98'i evliliğin içinde

Bulgu 5 ve Bulgu 11 annenin medeni durumunu **ham pay** olarak kullanmıştı
(o durumdaki anneden doğum / tüm doğumlar). Ham pay iki şeyi karıştırıyor: ilde
kaç boşanmış kadın olduğu ile onların doğurma eğilimi. Doğru payda `marital_status`
stoğu — 2008-2025, 81 il, kadın 15-49, medeni duruma göre. İkisi de elimizdeydi,
birleştirilmemişti.

**Yeni gösterge:** o medeni durumdaki 1.000 kadın başına doğum.

### Türkiye

| Yıl | Evli | Boşanmış | Hiç evlenmemiş | Dul |
|---|---|---|---|---|
| 2012 | 97,5 | 11,9 | 4,29 | 4,39 |
| 2014 | **101,0** | 12,6 | 4,54 | 4,97 |
| 2017 | 96,2 | 11,8 | 4,38 | 6,18 |
| 2020 | 84,0 | 9,8 | 3,25 | 5,27 |
| 2025 | **68,8** | **6,8** | **2,50** | 4,11 |

**Evli kadın doğurganlığı 2014'te tepe yapıp %32 düşmüş** (101,0 → 68,8).
Dönüm noktası ~2016 — Bulgu 11'deki evlenmeme kırılmasıyla **aynı yıl**. İki ayrı
göstergede aynı tarihte kırılma; ortak bir neden aranmalı (ekonomik? kuşak?).

Boşanmış kadınların doğurganlığı daha da hızlı düşmüş (11,9 → 6,8, −%43).

### Bu, ana tezin en temiz kanıtı

Evli kadın doğurganlığı bileşim etkisinden arınmış bir ölçü: kimin evlendiği,
kaç kişinin evlendiği, evlenme yaşı — hepsi paydada nötrleniyor. Geriye yalnız
*evli çiftlerin davranışı* kalıyor.

| İlişki (81 il) | r |
|---|---|
| Evli kadın doğurganlığı 2025 ~ GDH 2025 | **+0,982** |
| Evli kadın doğurganlığı ~ doğum aralığı | −0,956 |
| Evli doğurganlık **düşüşü** ~ aralık **açılması** | **+0,817** |

İl GDH'sinin neredeyse tamamı (r=0,982) evli kadınların doğurganlığı. Evlenme
davranışının iller arası farka katkısı ihmal edilebilir. Ve düşüş-açılma ilişkisi
ham GDH ile ölçülenden çok daha güçlü (0,817 vs Bulgu 8'in 0,640) — bileşim
gürültüsü temizlenince mekanizma daha net görünüyor. **Bulgu 8-9'un tezi
güçlendirildi.**

En çok düşen: Ağrı 210→112 (−%47), Muş 198→107 (−%46), Van 186→102 (−%45),
Iğdır 153→87 (−%43), Hakkari 174→104 (−%40).
En az düşen: Burdur 68→63 (−%8), Tunceli 83→74 (−%10), Kırklareli 59→51 (−%14),
Yalova 76→65 (−%15), Edirne 63→53 (−%16).

### ⚠️ Bulgu 11'in "yan ürün" sonucu YANLIŞTI — düzeltme

Bulgu 11'de boşanmış anneden doğum **ham payına** bakılıp "temiz batı-doğu eğimi,
boşanma sonrası yeniden aile kurmanın ölçüsü" denmişti. Yanlış. Ham pay ile
normalize hız arasında **r = −0,133** — ilişki yok, hatta ters.

| İl | Boşanmış kadın doğurganlığı | Ham pay |
|---|---|---|
| Şanlıurfa | **41,5 ‰** | %0,84 |
| Bitlis | 24,8 | %0,52 |
| Ağrı | 23,1 | %0,55 |
| Eskişehir | **3,8 ‰** | %0,83 |
| Giresun | 3,4 | %0,51 |
| Artvin | **1,6 ‰** | %0,15 |

Şanlıurfa ile Eskişehir'in ham payı neredeyse aynı (%0,84 vs %0,83) ama gerçek
hızları **on bir kat** farklı. Ham pay ilin boşanmış kadın *sayısını* ölçüyordu;
batıda çok boşanmış kadın var, doğurmuyorlar. Normalize edilince harita tersine
dönüyor: boşanmış kadın doğurganlığı en yüksek yer güneydoğu.

**Kural:** bu dosyadaki "…anneden doğum yüzdesi" biçimindeki her sonuç şüpheli.
Payda `marital_status` stoğu olmalı. Bulgu 5'in "hiç evlenmedi" payı da aynı
düzeltmeyi bekliyor (normalize hız TR: 4,29 → 2,50 ‰, yani o da düşüyor —
ham pay %2,09 → %2,27 ile *artıyor* görünürken).

## Bulgu 13 — evli olmayan anneden doğum oranı, 81 il (2012 vs 2025)

Betimleyici soru: doğum yapan kadınların yüzde kaçı **yasal olarak evli değil**?
Pay = hiç evlenmedi + boşandı + eşi öldü. Payda = toplam doğum **eksi bilinmeyen**
(TR 2025'te bilinmeyen payı %0,48).

Not: bu bir *pay*, Bulgu 12'deki gibi normalize hız değil — soru zaten "doğumların
yüzde kaçı" olduğu için doğru ölçü budur. Bulgu 12'nin uyarısı yalnız "hangi grup
daha çok doğuruyor" sorusuna geçilirse geçerli.

**TR: %2,83 (2012) → %3,21 (2025).** Bileşimi: hiç evlenmemiş %2,28, boşanmış
%0,85, dul %0,08.

### Sıralamanın başı iki farklı yoldan doluyor

| İl | Evli değil % | Hiç evl. | Boşanmış |
|---|---|---|---|
| Şanlıurfa | **8,74** | **7,74** | 0,84 |
| Adana | 6,35 | 4,75 | 1,46 |
| Osmaniye | 5,57 | 4,05 | 1,34 |
| Karabük | 4,63 | 3,25 | 1,27 |
| Diyarbakır | 4,47 | 3,77 | 0,61 |
| Edirne | 4,34 | 2,67 | **1,65** |
| Uşak | 3,64 | 1,43 | **2,01** |

Üst sırada iki ayrı olgu var: Şanlıurfa/Diyarbakır'da neredeyse tamamı "hiç
evlenmemiş" (kayıt dışı fiili evlilik — Bulgu 5 uyarısı), Uşak/Edirne'de ağırlık
"boşanmış"ta. Aynı orana iki farklı yoldan varılıyor; sütunlara bakmadan sıralama
yorumlanamaz.

En düşük: Ardahan %0,68, Bayburt %0,81, Artvin %0,85, Rize %0,99, Trabzon %1,03
— Karadeniz neredeyse sıfır.

### Değişim: güneydoğuda düşüyor, batıda artıyor

En çok **artan**: Şanlıurfa +3,98, Karabük +2,81, Osmaniye +1,74, Uşak +1,27,
Sinop +1,21 puan.
En çok **azalan**: Hakkari −2,59, Şırnak −2,49, Aksaray −2,20, Yozgat −1,94,
Bingöl −1,61 puan.

Şanlıurfa dışındaki güneydoğu illeri hızla düşüyor — resmî nikâh kaydı
yaygınlaşıyor gibi görünüyor. **Şanlıurfa bu bölgesel eğilimin tek istisnası ve
sebebi açıklanmadı**; Bulgu 5'te de aynı aykırılık not edilmişti. Karabük'ün
+2,81'i de açıklanmamış bir aykırılık (Karadeniz'de, komşuları çok düşük).

Tam 81 il tablosu üretimi: `scratchpad` betiği, kaynak
`İl ve annenin yasal medeni durumuna göre doğumlar.xls` (2012-2025, 81 il).

## Bulgu 14 — DÜZELTME: iki mekanizma ayrıştırılmamıştı, geç ilk annelik yanlış değişkenle elenmişti

Bulgu 8-9-12'nin çerçevesi ("asıl mekanizma aralık, evlenme/doğum ertelemesi
ilgisiz") fazla keskindi. Üç kusur bulundu.

### Kusur 1 — eş doğrusallık test edilmemişti

**r(doğum aralığı, ilk doğum yaşı) = +0,713.** Doğuda ikisi de düşük, batıda ikisi
de yüksek. İki mekanizma aynı coğrafi eksende hareket ediyor; ham korelasyonları
karşılaştırmak ayrıştırma sayılmaz.

Kısmi korelasyon (2025 kesiti) yine de aralığı destekliyor:

| İlişki | Ham | Diğeri sabitken |
|---|---|---|
| GDH ~ aralık | −0,956 | **−0,908** |
| GDH ~ ilk doğum yaşı | −0,738 | **−0,272** |

Yani kesitte aralığın üstünlüğü gerçek.

### Kusur 2 — r=−0,96 bölge içinde geçerli değil

| Grup (GDH'ye göre üçe bölünmüş) | r(GDH, aralık) | r(GDH, ilk doğum) |
|---|---|---|
| En doğurgan 27 il | **−0,943** | −0,528 |
| Orta 27 | **−0,323** | −0,008 |
| En az doğurgan 27 | **−0,397** | −0,074 |

−0,96'nın neredeyse tamamı **doğu-batı ekseninden** geliyor. Benzer iller kendi
aralarında karşılaştırılınca ilişki −0,32'ye düşüyor. Bulgu 9'daki "aralığı bilen
GDH'yi bilir" ifadesi iller arası genel eğilim için doğru, **bir ilin kendi
içindeki mekanizmayı kanıtlamıyor.**

### Kusur 3 (en ciddi) — geç ilk annelik YANLIŞ DEĞİŞKENLE elendi

Bulgu 3/9'da "evlenme yaşı ~ GDH düşüşü r=+0,06" bulunup mekanizma elenmişti.
Ama **ortalama evlenme yaşı ile ilk doğum yaşı ayrı değişkenler** ve ilk doğum
yaşı değişim tarafında hiç hesaplanmamıştı. Aynı 7 yıllık pencerede:

| İlişki (2019-2025, 81 il) | r | Diğeri sabitken |
|---|---|---|
| GDH düşüşü ~ **ilk doğum yaşı artışı** | **+0,504** | **+0,353** |
| GDH düşüşü ~ aralık açılması | +0,640 | +0,555 |
| GDH düşüşü ~ evlenme yaşı artışı | +0,06 | — |

İlk doğum yaşı 0,06 değil **0,50**, ve kısmi korelasyonda da ayakta (+0,35).
12 yıllık uzun pencerede (2014-2025) r=+0,42 — daha uzun veride de duruyor.

**İkisi de doğurganlığı düşürüyor.** Doğru ifade "asıl mekanizma aralık, öteki
ilgisiz" değil, **"ikisi de katkı veriyor, aralık biraz daha fazla"**.

### Kusur 4 — pencereler eşit değildi

Aralık serisi yalnız **2019-2025 (7 yıl)**; ilk doğum yaşı 12, GDH 17 yıl.
Karşılaştırmalar eşitlenmemişti. Eşitlenince aralığın üstünlüğü 0,640 vs 0,504'e
daralıyor. Bütün aralık sonuçları kısa bir panele dayanıyor — bu sınır her
kullanımda anılmalı.

### Özet tablosunda düzeltilecekler

- "İlk doğumun ertelenmesi ⚠️ kısmi" → **bağımsız katkısı var** (değişimde
  r=+0,50, kısmi +0,35).
- "Doğum aralığı ✅ asıl mekanizma" → **kesitte baskın, ama bölge içinde zayıf
  (−0,32…−0,40); üstünlüğü doğu-batı ekseninden geliyor.**
- "Evlenmenin ertelenmesi ❌ ilgisiz" → bu satır doğru, değişmiyor.

## Bulgu 15 — ilk anne olma yaşına göre ham kesit: ilişki doğrusal değil, DOYUYOR

Korelasyon yerine ham gruplama: 81 il 2025 ilk doğum yaşına göre sıralanıp dörde
bölündü. Hiçbir normalizasyon, TR'ye göre sapma yok — çıplak ortalamalar.

| Grup | İlk doğum yaşı | GDH ‰ | Doğum aralığı |
|---|---|---|---|
| En erken 20 il | 25,7 | **58,1** | 4,34 |
| 2. çeyrek 20 | 26,9 | **38,5** | 5,08 |
| 3. çeyrek 21 | 27,6 | **37,0** | 5,18 |
| En geç 20 il | 28,4 | **34,3** | 5,22 |

**Bütün fark ilk basamakta.** 25,7 → 26,9 arasında GDH 19,6 puan çöküyor
(58,1→38,5). Sonraki 1,5 yıllık gecikme yalnız 4,2 puan getiriyor (38,5→34,3).
İlişki **doyuyor**: ilk doğum yaşı ~27'yi geçtikten sonra doğurganlığı neredeyse
hiç etkilemiyor. Aralık sütunu aynı deseni gösteriyor (4,34 → 5,08 → 5,18 → 5,22).

Uç iller bunu doğruluyor: Tunceli 28,9 yaşta GDH 38,1; İzmir 28,7 yaşta 30,7;
Trabzon 28,7 yaşta 35,9. Geç uçta **aynı yaşta GDH 30'dan 38'e kadar dağılıyor** —
ilk doğum yaşı orada hiçbir şey belirlemiyor. Erken uçta ise sıkı: Şanlıurfa
24,4 → 96,6.

### Bu, Bulgu 14'ün 2. kusurunu açıklıyor

Bulgu 14'te bölge içi korelasyonların çöktüğü bulunmuştu (orta 27 il: r=−0,32).
Sebebi gürültü değil, **doyma**: orta ve düşük doğurganlıklı illerin hepsi zaten
düz bölgede. Değişken orada gerçekten bilgi taşımıyor.

**Yöntem dersi:** bu veri kümesinde tek bir korelasyon katsayısı yanıltıyor.
Doğrusal r hem erken uçtaki sıkı ilişkiyi hem geç uçtaki yokluğu tek sayıya
eziyor. Bundan sonraki her ilişki iddiası ham gruplamayla da gösterilmeli.

## Bulgu 16 — boşanma hızı, doğru paydayla: 81 ilin 80'inde artıyor, doğuda katlanarak

`meta.json` uyarıyordu: boşanmayı aynı yılın evlenmesine bölmek yanlış, bu yıl
boşananlar başka yıllarda evlenmiş çiftler. Doğru payda **risk altındaki nüfus**,
yani evli stok. `marital_status`'tan alındı (2008-2025, 81 il).

**Gösterge: evli 1.000 kadın başına boşanma.** Kadın alındı — bir boşanma bir evli
kadın + bir evli erkek demek, ikisi toplanırsa çift sayılır. Yaş 15+ (15-49 değil;
boşanma her yaşta oluyor, dar bant yaşlı nüfuslu illeri yanlış gösterir).

### Türkiye

| Yıl | Boşanma | Evli kadın | Hız ‰ | Naif (boş/evlenme) % |
|---|---|---|---|---|
| 2010 | 118.568 | 17.534.635 | **6,76** | 20,3 |
| 2016 | 126.164 | 19.084.665 | **6,61** | 21,2 |
| 2019 | 156.587 | 19.654.736 | **7,97** | 28,9 |
| 2025 | 193.793 | 20.592.954 | **9,41** | 35,1 |

Gerçek artış **%39** (6,76→9,41). Naif oran aynı dönemde **%73** artmış gösteriyor —
neredeyse iki katı abartı. Sebep: naif oranın paydası (evlenme sayısı) küçülüyor,
evli stok ise büyüyor. **Naif oran boşanmadaki artışın yarısını evlenmedeki
düşüşten devşiriyor.**

Yükseliş 2016'da başlıyor — Bulgu 11 (evlenmeme kırılması) ve Bulgu 12 (evli
doğurganlığın tepesi) ile **aynı yıl**. Üçüncü gösterge de aynı tarihi işaret
ediyor; ortak neden aranmalı.

### Sıralama: naif oran bu kez o kadar da yanlış değil, ama uçlarda çuvallıyor

r(doğru hız ~ naif oran) = **+0,926**. Bulgu 12'deki felaketten (r=−0,13) farklı;
genel sıralama tutuyor. Ama tek tek iller kayıyor:

| İl | Doğru hız (sıra) | Naif oran (sıra) |
|---|---|---|
| Tunceli | 9,89‰ (22.) | %53,5 (**1.**) |
| Edirne | 9,16‰ (34.) | %43,3 (13.) |
| Hatay | 9,74‰ (**24.**) | %31,1 (51.) |
| Gaziantep | 9,17‰ (33.) | %26,3 (59.) |

Tunceli naif oranda Türkiye birincisi, doğru hızda 22. — çünkü orada çok az
evlenme oluyor, payda küçük. Hatay/Gaziantep tam tersi.

### 2025 düzeyi: beş kat batı-doğu farkı

En yüksek: İzmir 13,33‰, Antalya 13,20, Muğla 12,31, Denizli 12,16, Mersin 11,90,
Karaman 11,71, Eskişehir 11,67, Uşak 11,50, Aydın 11,48, Ankara 11,02.
En düşük: Hakkari 2,71, Şırnak 3,02, Bitlis 3,04, Muş 3,44, Van 3,49, Siirt 3,75,
Bingöl 3,82, Bayburt 3,83, Gümüşhane 3,92, Batman 4,25.

### Ama değişimde yakınsama — doğu katlanarak artıyor

**81 ilin 80'inde arttı** (tek istisna Aksaray 11,17→10,42).

| 2008 grubu | 2008 | 2025 | Kat |
|---|---|---|---|
| En düşük 27 | 2,38‰ | 5,02‰ | **2,4×** |
| Orta 27 | 4,77‰ | 8,81‰ | 1,9× |
| En yüksek 27 | 7,01‰ | 10,53‰ | 1,5× |

r(2008 düzeyi ~ kaç kat arttığı) = **−0,740**. Klasik yakınsama.
En çok katlananlar hep güneydoğu: Bitlis 0,67→3,04 (4,5×), Siirt 0,89→3,75 (4,2×),
Van 0,94→3,49 (3,7×), Ağrı 1,27→4,57 (3,6×), Hakkari 0,80→2,71 (3,4×).

**Doğurganlıktaki desenin aynısı** (Bulgu 3, 9): mutlak düzeyde en geride olan
bölge, oransal değişimde en hızlısı. Doğu-batı farkı duruyor ama kapanıyor.

### ⚠️ Sınırlar

- `divorces` yaş kırılımı taşımıyor → **yaşa göre standardize edilemedi**, bu kaba
  bir hız. Evli nüfusun yaş yapısı farklı olan iller haksız karşılaştırılıyor
  olabilir; yaşlı evli nüfus boşanma riskini düşürür.
- Pay da payda da **resmî kayıt**. Dinî nikâhlı birliktelikler ikisinde de yok;
  güneydoğu için "resmî evliliklerin boşanma hızı" okunmalı. Gerçek birliktelik
  çözülmesi bundan yüksek olabilir.
- Evlilik süresi kırılımı yok → boşanma riskinin evlilik yaşına göre dağılımı
  (hazard) hesaplanamıyor. Bunun için ayrı bir MEDAS dökümü gerekir.

## Bulgu 17 — yaşa göre standardize ölüm hızı: yaş yapısı haritanın neredeyse tamamını gizliyormuş

Kaba ölüm hızı yaş yapısının esiri: yaşlı nüfuslu il, her yaş grubunda ülke
ortalaması kadar ölse bile ölümcül görünür. **Doğrudan standardizasyon** yapıldı —
her ilin yaşa özel ölüm hızları tek bir sabit nüfusa uygulandı.

Yöntem: `deaths` (17 yaş bandı × cinsiyet, 81 il, 2009-2025) ÷ `population` (tek
yaş, aynı bantlara toplandı). Standart nüfus: **Türkiye 2025**. Cinsiyetler
birleşik. 65+ kesitinden üstün, çünkü tüm yaş yapısını kullanıyor.

⚠️ 72 il hesaplanabildi. Eksik 9: Bilecik, Bolu, Nevşehir, Tunceli, Uşak, Bayburt,
Bartın, Ardahan, Karabük — küçük iller, bazı yaş bandında hücre bastırılmış.

### Türkiye — ve COVID'in gerçek büyüklüğü

| Yıl | Kaba ‰ | Standardize ‰ |
|---|---|---|
| 2010 | 4,97 | **6,79** |
| 2016 | 5,30 | **6,56** |
| 2019 | 5,25 | **6,17** |
| 2020 | 6,09 | **7,01** |
| 2021 | 6,69 | **7,65** |
| 2025 | 5,71 | **5,71** |

TR 2009→2025: **7,05 → 5,71 (−%19).** (2025'te kaba = standardize, çünkü standart
nüfus 2025.)

**2021'de standardize hız 7,65** — 2009'un (7,05) üstünde. COVID, ölümlülükte on
iki yıllık ilerlemeyi silip geriye atmış. Kaba hızda bu 6,69 olarak görünüyor ve
etki küçük sanılıyor; standardize edilince gerçek boyutu çıkıyor.

### Kaba hız haritayı yanlış çiziyor

**r(kaba hız, standardize hız) = +0,355.** Neredeyse ilişkisiz. Yani il ölüm
haritası bugüne kadar büyük ölçüde **yaş yapısı haritasıydı**, ölümlülük haritası
değil.

2025 standardize, **en yüksek**: Kilis 6,64, Manisa 6,52, Afyonkarahisar 6,48,
Edirne 6,41, Adana 6,29, Kırklareli 6,28, Tekirdağ 6,26.
**En düşük**: Hakkari 4,78, Gümüşhane 4,91, Şırnak 4,93, Muğla 5,09, Trabzon 5,10,
Mardin 5,13.

Güneydoğu en düşük çıkıyor — sezgiye aykırı, bu yüzden doğrulandı.

### Doğrulama: TÜİK'in kendi yaşam beklentisiyle

**r(standardize ölüm hızı 2025 ~ TÜİK yaşam beklentisi 2023) = −0,826.**

TÜİK'in kendi bağımsız hesabı da aynı yönü gösteriyor: yaşam beklentisi en yüksek
iller Tunceli 80,8, Şırnak 79,6, Mardin 79,6, Bingöl 79,3; en düşük Gaziantep 76,2,
Kilis 76,2, Adana 76,8. Yani sonuç yöntem hatası değil.

⚠️ Ama ikisi de **aynı ölüm kayıt verisinden** türüyor. Kayıt eksikliği varsa ikisi
birden yanılır; doğrulama yöntemi doğruluyor, **veriyi değil**.

### Değişim: yine yakınsama, yine aynı iller

**72 ilin 72'sinde düştü.** En çok düşenler: Hakkari −%39,4 (7,89→4,78),
Muş −%38,0, Şırnak −%35,5, Van −%34,1, Bingöl −%33,0, Ağrı −%32,9, Kars −%30,2,
Bitlis −%29,7.
En az düşenler: Burdur −%7,1, Giresun −%7,7, Adıyaman −%7,9, Isparta −%10,1,
Manisa −%10,6, Edirne −%10,8.

**Üçüncü kez aynı desen.** Doğurganlıkta (Bulgu 3, 9), boşanmada (Bulgu 16) ve
şimdi ölümlülükte: geriden başlayan güneydoğu en hızlı değişen, ileride olan
batı yavaşlamış. Üç bağımsız demografik alanda **yakınsama** — bu artık tesadüf
değil, dosyanın en tekrar eden bulgusu ve kendi başına bir başlık hak ediyor.

## Bulgu 18 — yeniden evlenme makası: 81 ilin 81'inde açılıyor, kadınlarda üç katına

`mean_marriage_age` (o yıl evlenen herkes) ile `mean_first_marriage_age` (ilk kez
evlenenler) arasındaki **fark**. Herkes ilk kez evlenseydi ikisi çakışırdı; makası
açan şey ikinci ve sonraki evliliklerdir. Yani **yeniden evlenmenin vekil ölçüsü**.
İkisi de ambarda, 2001-2025, 81 il, cinsiyete göre — birleştirilmemişti.

Zaman gürültüsünü kırmak için uç noktalar **üçer yıllık ortalama**.

### Türkiye

| Pencere | Erkek | Kadın |
|---|---|---|
| 2001-03 | 1,60 | 0,80 |
| 2008-10 | 1,87 | 1,20 |
| 2015-17 | 2,17 | 1,53 |
| 2023-25 | **2,87** | **2,50** |

Yıl yıl (erkek) düzgün tırmanıyor, sıçrama yok: 1,60 · 1,60 · 1,60 · 1,60 · 1,50 ·
1,60 · 1,60 · 1,70 · 2,00 · 1,90 · 2,00 · 2,10 · 2,10 · 2,10 · 2,10 · 2,20 · 2,20 ·
2,40 · 2,40 · 2,50 · 2,50 · 2,70 · 2,80 · 2,90 · 2,90. Gürültü sorunu yok.

**Kadınlarda makas üç katına çıkmış** (0,80→2,50), erkeklerde %79 artmış. Cinsiyet
farkı 0,80 yıldan 0,37'ye inmiş: yeniden evlenme **cinsiyet bakımından
simetrikleşiyor.** Eskiden dul/boşanmış erkek yeniden evlenirdi, kadın evlenmezdi;
bu kapanıyor.

### İl: dört kat fark, ve bir bölge hiç kıpırdamıyor

**2023-25 en yüksek** (erkek): Muğla 4,40, Sinop 4,33, Aydın 4,30, Antalya 4,27,
Balıkesir 4,17, Çanakkale 4,17.
**En düşük**: Ağrı 0,87, Şırnak 0,93, Siirt 0,93, Bitlis 0,97, Batman 1,00, Van 1,00.

Kadınlarda uçlar daha da keskin: Muğla 4,30 · Antalya 4,13 · Aydın 4,13 karşısında
**Hakkari 0,30 · Batman 0,43 · Şırnak 0,43 · Siirt 0,53 · Van 0,57.**

**81 ilin 81'inde arttı** (her iki cinsiyette). Ama büyüklük uçurum:

| İl (kadın) | 2001-03 | 2008-10 | 2015-17 | 2023-25 | Değişim |
|---|---|---|---|---|---|
| Antalya | 1,07 | 1,83 | 2,60 | 4,13 | **+3,07** |
| Muğla | 1,50 | 2,23 | 2,97 | 4,30 | +2,80 |
| Tunceli | 0,53 | 0,90 | 1,47 | 3,23 | +2,70 |
| Diyarbakır | 0,07 | 0,20 | 0,27 | 0,60 | **+0,53** |
| Şırnak | 0,10 | 0,10 | 0,10 | 0,43 | +0,33 |
| Hakkari | 0,10 | 0,10 | 0,07 | 0,30 | **+0,20** |

Hakkari'de kadınların makası 25 yılda 0,10'dan 0,30'a çıkmış. Pratikte **sıfır** —
o illerde boşanmış ya da dul kadın yeniden evlenmiyor.

### Bulgu 16 ile birlikte okunduğunda: birikiyor

Bulgu 16: güneydoğuda boşanma hızı düşük ama **3-4,5 kat artmış** (Bitlis 0,67→3,04).
Bulgu 18: aynı illerde kadınların yeniden evlenmesi hâlâ sıfıra yakın.

İkisi birlikte şunu söylüyor: **o illerde boşanmış ve yeniden evlenmeyen kadın
stoğu hızla büyüyor.** Bu, hane yapısı ve yoksulluk açısından takip edilmesi gereken
bir birikim. `household_by_type` (2014-2025, 81 il, tek kişilik hane payı) ile
sınanabilir — henüz kullanılmadı.

### ⚠️ Sınırlar

- Makas dolaylı bir ölçü: hem *yeniden evlenme yaygınlaşınca* hem de *yeniden
  evlenenlerin yaşı ilk evlenenlere göre yükselince* açılır. İkisini ayıramıyoruz;
  bunun için evlilik sırasına göre evlenme sayısı gerekir (MEDAS'ta olabilir,
  bakılmadı).
- Küçük illerde üçer yıllık ortalama bile yetmiyor: Bartın 1,37→3,47→2,80→3,83,
  Zonguldak 1,47→3,97→3,00→3,63 gibi zikzaklar var. Bu iki il için değişim rakamı
  güvenilmez; büyük illerde seriler düzgün.
- `mean_first_marriage_age`in toplamı yok (bir evlilik erkeğin ilki, kadının
  ikincisi olabilir) — bu yüzden cinsiyetler ayrı verildi, birleştirilmedi.

## Bulgu 19 — eş yaş farkı: 12 yıl hiç kıpırdamadı, 2013'te daralmaya başladı; doğu donmuş

İlk evlenme yaşının cinsiyet farkı = erkek − kadın. `mean_first_marriage_age`
cinsiyet kırılımlı, 2001-2025, 81 il. Yıllık veri az olduğu için pencere değil
**her yıl** verildi; il uçları yine üçer yıllık ortalama.

### Türkiye — kırılma 2013'te, 2016'da değil

| Yıl | Erkek | Kadın | Fark |
|---|---|---|---|
| 2001 | 26,0 | 22,7 | **3,3** |
| 2005 | 26,5 | 23,2 | **3,3** |
| 2009 | 26,8 | 23,5 | **3,3** |
| 2012 | 27,2 | 23,9 | **3,3** |
| 2013 | 27,3 | 24,1 | 3,2 |
| 2015 | 27,5 | 24,4 | 3,1 |
| 2018 | 27,8 | 24,8 | 3,0 |
| 2021 | 28,1 | 25,4 | 2,7 |
| 2025 | 28,5 | 26,0 | **2,5** |

**2001-2012 arası fark tam 3,3'te sabit** — on iki yıl boyunca erkek de kadın da
aynı hızda gecikmiş, makas hiç değişmemiş. 2013'ten itibaren kadınların evlenme
yaşı erkeklerinkinden hızlı artmaya başlıyor ve fark 3,3 → 2,5'e iniyor.

Not: bu tarih dosyadaki **2016 kırılmasından farklı**. Evlenmeme, evli doğurganlık
ve boşanma 2016'da dönerken eş yaş farkı 2013'te dönmüş — ayrı bir süreç.

### İl: 79'unda daraldı, ama en yüksek dördü donmuş

**En yüksek 10 (2023-25):**

| İl | 2001-03 | 2023-25 | Değişim |
|---|---|---|---|
| Muş | 3,93 | **3,97** | **+0,03** |
| Ardahan | 4,20 | 3,87 | −0,33 |
| Ağrı | 3,90 | **3,83** | **−0,07** |
| Kars | 4,57 | 3,80 | −0,77 |
| Bitlis | 3,70 | **3,57** | **−0,13** |
| Iğdır | 3,90 | 3,40 | −0,50 |
| Hatay | 4,13 | 3,20 | −0,93 |
| Tunceli | 3,53 | 3,13 | −0,40 |
| Kilis | 3,17 | 3,03 | −0,13 |
| Kırklareli | 3,37 | 3,00 | −0,37 |

**En düşük 10:** Ankara 2,03 · Elazığ 2,03 · Bolu 2,13 · Karabük 2,13 ·
Kastamonu 2,13 · Malatya 2,17 · İstanbul 2,20 · Samsun 2,20 · Konya 2,23 ·
Eskişehir 2,23.

En çok daralan: Rize 4,27→2,50 (−1,77), Malatya −1,17, Elazığ −1,13,
Ankara/İstanbul/Eskişehir −1,03.
Genişleyen yalnız iki il: Muş +0,03, Aksaray +0,17.

### ⚠️ Burada yakınsama deseni KIRILIYOR

r(2001-03 düzeyi ~ değişim) = **−0,474** — Bulgu 16'daki (−0,74) ve 17'deki güçlü
yakınsamadan belirgin biçimde zayıf. Ve asıl mesele ortalamada değil uçta:
**listenin en tepesindeki Muş, Ağrı, Bitlis, Siirt 25 yılda neredeyse hiç
kıpırdamamış** (+0,03 … −0,13). En çok daralanlar Karadeniz ve İç Anadolu.

Doğurganlıkta, boşanmada ve ölümlülükte güneydoğu **en hızlı değişen** taraftı
(Bulgu 3, 9, 16, 17). Burada tam tersi: **en durağan** taraf. Yani "geriden
başlayan hızlı kapatıyor" kuralı evrensel değil — demografik davranış (doğum
aralığı, boşanma) hızla değişirken, evlilikteki cinsiyet hiyerarşisini gösteren
bu ölçü aynı illerde donmuş durumda.

Bu, dosyanın tekrar eden yakınsama bulgusuna gerçek bir karşı örnek ve
"modernleşme tek pakettir" okumasını zayıflatıyor.

## Yol haritası — elimizdeki tüm veriyle yapılabilecek analizler

On dokuz bulgu sonrası envanter. Ambar + masaüstü dosyaları taranarak çıkarıldı.
Sıra kabaca getiriye göre. "Hazır" = ek dosya gerekmez, ambarda var.

### A. Kütük nüfus — hiç dokunulmamış, en büyük boşluk

`registry_population` 2007-2025, 81 il, **`residence=own` / `residence=elsewhere`
kırılımlı**. Yani "bu ile nüfusu kayıtlı olup burada yaşayanlar / yaşamayanlar".

| # | Analiz | Neden |
|---|---|---|
| A1 | Kütük / ikamet oranı | Ömür boyu net göçün doğrudan ölçüsü. Ardahan 6,13 · Kars 3,78 · Bayburt 3,50 karşısında İstanbul 0,17 · Kocaeli 0,32 · Ankara 0,35. Yıllık göç akımlarından çok daha güçlü bir "kök" göstergesi |
| A2 | `residence=elsewhere` payının 2007-2025 seyri | Boşalma hızlanıyor mu, duruyor mu? İl bazında |
| A3 | Kütük oranı ~ doğurganlık / boşanma / ölümlülük | Bulgu 17'deki "güneydoğu neden en düşük ölümlülük" şüphesinin testi: payda şişkinliği hipotezi |

⚠️ Köken×varış matrisi **yok** — "İstanbul'daki Sivaslılar" bu veriyle çıkmaz,
yalnız "Sivas'tan gitmiş olanların sayısı" çıkar.

### B. Hane — tamamı kullanılmamış

| # | Analiz | Veri |
|---|---|---|
| B1 | Tek kişilik hane payı, il, 2014-2025 | `household_by_type` · Bulgu 18'in "boşanmış ve yeniden evlenmeyen kadın birikiyor" tahminini sınar |
| B2 | Hane sayısı artışı vs nüfus artışı | `household_count` + `population` · hane nüfustan hızlı artıyorsa atomlaşma |
| B3 | Hane büyüklüğü ~ doğurganlık | `household_size` 2008-2025 · GDH ile ilişki |
| B4 | Çekirdeksiz / çekirdek+diğer hane payı | Geniş ailenin çözülme hızı, il il |

### C. Ölüm — Bulgu 17 sadece kapıyı açtı

| # | Analiz | Neden |
|---|---|---|
| C1 | **Fazla ölüm (excess mortality) 2020-21, il** | Bulgu 17'de TR standardize hız 6,17→7,65 çıktı. 2015-19 taban çizgisine göre il il fazla ölüm — pandeminin coğrafyası. En yüksek getirili ölüm analizi |
| C2 | Bebek ve 5 yaş altı ölümlülük | `infant_mortality`, `under5_mortality` 2009-2025 · zaten normalize, hiç bakılmadı. Güneydoğudaki −%39'luk düşüşün ne kadarı bebek ölümünden? |
| C3 | Cinsiyete göre standardize ölüm makası | `deaths` cinsiyet kırılımlı · erkek-kadın ölümlülük farkı, il il |
| C4 | İlçe düzeyinde ölüm | `deaths` ilçe kırılımı taşıyor · il içi eşitsizlik |

### D. Medeni hal — `marital_status` en zengin kullanılmamış kaynak

182.501 il satırı, cinsiyet × beşli yaş × 5 durum, 2008-2025.

| # | Analiz | Neden |
|---|---|---|
| D1 | **Evlenme hızı doğru paydayla** | Evlenme / hiç evlenmemiş kadın stoku. Bulgu 11'in bilmecesini çözer: evlenmeme oranı arttı çünkü *hız mı düştü*, yoksa *genç kuşak mı büyük*? Stok ayıramaz, hız ayırır |
| D2 | Boşanmış kadın stoğunun büyümesi | Bulgu 16+18'in birleşik tahmininin doğrudan testi |
| D3 | Dulluk oranı, yaşa ve cinsiyete göre | Kadın dulluğu erkeğinkinin kaç katı, nerede |

### E. Doğurganlık — kalan parçalar

| # | Analiz | Veri |
|---|---|---|
| E1 | **İl düzeyinde yaşa özel doğurganlık hızı** | TÜİK yayınlamıyor, malzemesi bizde. Bulgu 15'teki doyma eşiğinin hangi yaş grubundan geldiğini söyler |
| E2 | Akraba evliliği, 81 il, 2010-2025 | Masaüstü · "muhafazakâr norm"un tek ölçülebilir vekili; Bulgu 8 artıklarını açıklıyor mu |
| E3 | Çocuk evliliğini normalize et | 16-17 yaştaki kız 1.000 başına evlenme. Bulgu 2'nin "coğrafya tersine döndü" sonucu naif paydaya dayanıyor, şüpheli |
| E4 | Anne eğitimi × yaş | Masaüstü, **yalnız TR** · il yok, en zayıfı |

### F. Yapısal / birleştirici

| # | Analiz | Neden |
|---|---|---|
| F1 | **Nüfus değişimi ayrıştırması** | `natural_increase` + `migration_net` · her ilin büyümesinin ne kadarı doğum fazlası, ne kadarı göç? Kolay ve hiç yapılmamış |
| F2 | 2016 kırılması taraması | Üç göstergede (evlenmeme, evli doğurganlık, boşanma) aynı yıl; eş yaş farkı ise 2013. Tüm göstergeleri tarayıp kırılma yılı haritası çıkarmak |
| F3 | Yakınsama endeksi | Doğurganlık, boşanma, ölümlülük yakınsıyor (Bulgu 3/9/16/17); eş yaş farkı yakınsamıyor (Bulgu 19). Hangi boyut yakınsıyor hangisi donmuş — tek tabloda |
| F4 | Yurtdışı göç | `migration_to_abroad` / `from_abroad` 2016-2025 · hiç bakılmadı |

### Öneri sırası

1. **A1 — kütük/ikamet oranı.** Hazır, tek sorgu, tamamen yeni bir eksen açıyor ve
   Bulgu 17'nin şüphesini test ediyor.
2. **C1 — il düzeyinde fazla ölüm 2020-21.** Bulgu 17 zaten altyapıyı kurdu.
3. **D1 — evlenme hızı.** Bulgu 11'in çözülmemiş bilmecesini kapatır.
4. **E1 — il düzeyinde ASFR.** Bulgu 15'in doyma eşiğini açıklar.
5. **F1 — nüfus değişimi ayrıştırması.** Ucuz, tanımlayıcı, her şeyi çerçeveler.

### Kontrol edilecek

`meta.json` ağacında "Yapı ruhsatı" konusu var ama ambarın `fact` tablosunda
yapı ruhsatı göstergesi görünmedi; `cikti\TUIK_yapi_ruhsati_*.csv` masaüstünde
duruyor. Konut arzı ↔ hane kurulumu ↔ evlenme zinciri kurulabilir mi, önce
verinin nerede olduğu netleşmeli.

## Bulgu 20 — pandeminin il haritası: güneydoğu en ağır, kaba hız etkiyi abartıyor

Bulgu 17'nin altyapısıyla. Taban çizgisi **2015-19 ortalaması**; pandemi ölçüsü
2020 ve 2021'in bu tabana göre fazlası. Hem kaba hem yaşa göre standardize hız,
yanına doğum ve doğal artış. 69 il hesaplanabildi (yaş bandı bastırması).

### Türkiye

| Yıl | Kaba ölüm ‰ | Std. ölüm ‰ | Kaba doğum ‰ | Doğal artış ‰ |
|---|---|---|---|---|
| 2019 | 5,25 | 6,17 | 14,33 | 9,08 |
| 2020 | 6,09 | 7,01 | 13,40 | 7,31 |
| **2021** | **6,69** | **7,65** | **12,83** | **6,13** |
| 2022 | 5,93 | 6,65 | 12,22 | 6,29 |
| 2025 | 5,71 | 5,71 | 10,40 | 4,69 |

2015-19 tabanı: std 6,37 · kaba 5,24 · doğum 15,84 · doğal artış 10,61.

| | Std. fazla | Kaba fazla |
|---|---|---|
| 2020 | **+%10,2** | +%16,3 |
| 2021 | **+%20,1** | +%27,8 |

**Kaba hız pandemiyi abartıyor.** Aradaki fark (27,8 vs 20,1) pandemi değil,
nüfusun yaşlanması. Dürüst rakam 2021 için **+%20**, +%28 değil. Bulgu 17'de kaba
hızın haritayı yanlış çizdiği bulunmuştu; burada **zaman serisinde de** yanlış
çizdiği görülüyor.

Doğum da düştü (14,33 → 12,83), yani doğal artış iki uçtan birden sıkıştı:
9,08 → 6,13.

### En ağır etkilenen iller (2020-21 ortalaması, standardize)

| İl | Std. fazla % | Kaba fazla % | Yalnız 2021 |
|---|---|---|---|
| Batman | **+35,0** | +30,6 | +35,6 |
| Diyarbakır | **+33,9** | +31,1 | +35,2 |
| Mardin | +27,7 | +25,1 | +25,9 |
| Ağrı | +26,2 | +26,7 | +31,9 |
| Siirt | +25,9 | +25,8 | +26,3 |
| Konya | +25,0 | +31,8 | +27,8 |
| Gaziantep | +24,4 | +25,4 | +22,9 |
| Hatay | +24,3 | +28,0 | +25,8 |
| Elazığ | +23,7 | +31,2 | +26,6 |
| Bitlis | +23,6 | +25,3 | +21,1 |

**En az etkilenen:** Kars +1,3 · Iğdır +4,3 · Balıkesir +7,5 · Niğde +8,8 ·
Çanakkale +8,9 · Yalova +9,0 · İzmir +9,2 · Kastamonu +9,7.

Batman ve Diyarbakır'da ölümlülük **üçte biri kadar** arttı; İzmir'de onda biri.
Güneydoğu listenin başında — Bulgu 17'de en **düşük** ölümlülüğe sahip görünen
bölge, şoka en kırılgan çıkmış.

⚠️ **Şüpheli:** Kars +1,3 ve Iğdır +4,3, hemen yanı başındaki Ağrı +26,2 iken.
Komşu illerde bu kadar farklı bir salgın seyri olası değil; ölüm kaydı gecikmesi
ya da eksikliği araştırılmalı. Bu iki ilin rakamı kullanılmadan önce doğrulanmalı.

### Doğal nüfus artışı: en çok düşen 12

| İl | Taban ‰ | 2021 ‰ | 2025 ‰ | Değişim |
|---|---|---|---|---|
| Ağrı | 23,94 | 17,60 | 13,08 | **−10,85** |
| Muş | 23,12 | 18,42 | 12,37 | −10,76 |
| Iğdır | 17,73 | 12,68 | 8,04 | −9,68 |
| Van | 22,42 | 16,15 | 12,75 | −9,68 |
| Bitlis | 21,76 | 17,56 | 12,95 | −8,81 |
| Bingöl | 16,02 | 11,62 | 7,84 | −8,19 |
| Diyarbakır | 21,72 | 16,53 | 13,62 | −8,09 |
| Şanlıurfa | 28,70 | 25,27 | 20,64 | −8,06 |
| Mardin | 22,23 | 18,51 | 14,41 | −7,82 |
| Adıyaman | 16,61 | 12,06 | 8,81 | −7,80 |
| Siirt | 21,90 | 17,65 | 14,10 | −7,80 |
| Batman | 21,15 | 17,24 | 13,36 | −7,79 |

Yine güneydoğu — ama burada en yüksekten başlayan grup oldukları için beklenen
sonuç. TR 10,61 → 4,69: doğal artış **yarıdan fazla** erimiş.

### 2025'te doğal artışı NEGATİF olan 14 il

Giresun −2,76 · Kastamonu −2,60 · Edirne −2,21 · Balıkesir −1,97 ·
Çanakkale −1,93 · Kırklareli −1,42 · Zonguldak −1,36 · Çorum −1,19 ·
Kütahya −0,87 · Ordu −0,50 · Amasya −0,48 · Burdur −0,39 (+2 il).

Bu illerde ölüm doğumu geçti; nüfusları artık yalnız göçle ayakta. 2021'de 12 il
negatifti — pandemi geçici olarak değil **kalıcı** olarak bu eşiğe taşımış
görünüyor, çünkü 2025'te sayı azalmadı arttı.
