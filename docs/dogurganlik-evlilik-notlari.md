# Doğurganlık, evlenme yaşı ve anne doğum yaşı — bulgular ve sıradaki iş

Bu dosya henüz koda girmemiş bulguları kaydeder. İki yeni kaynak masaüstünden
geldi, ikisi de depoya alınmadı — burada iz olarak duruyor, sonra yüklenecek.

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

## Bulgu 9 — dört göstergenin il tablosu; kesitte GDH ~ doğum aralığı r=−0,96

Bulgu 8 yalnız *değişim* ilişkisini kaydetmişti (GDH düşüşü ~ aralık açılması,
r=0,64). Aynı veriyle **seviye** ilişkisine bakıldığında bağ çok daha sıkı:
2025 kesitinde 81 il için GDH ile doğum aralığı arasında **r = −0,96**. Aralığı
bilen ilin GDH'sini bilir. Karşılaştırma: GDH ~ ilk doğum yaşı r=−0,74,
GDH ~ ortalama anne yaşı r=−0,48.

**Doğum aralığı süresi nedir:** bir annenin *son iki doğumu arasında* geçen
ortalama yıl. O yıl ilk çocuğunu doğuranlar kapsam dışı — yani "ne zaman
başlıyor" değil, *başladıktan sonra ne kadar ara veriyor* ölçüsü. Doğurganlık
penceresi kabaca sabit olduğundan aralık açıldıkça pencereye sığan doğum azalır;
mekanizma budur. Evlenme/ilk doğum yaşı ertelemesi değil, evlilik içi planlama.

GDH burada **genel doğurganlık hızı** = 1.000 kadın (15-49) başına canlı doğum;
ambardaki `births` ve `population` sayımlarından türetildi (ambarda hazır
gösterge yok). Diğer üç sütun TÜİK'in kendi hesabı. Pencere 2019-2025 —
aralık serisi 2019'da başlıyor. İller GDH'ye göre azalan sırada.

⚠️ Kaba/genel hızlar toplanamaz: bu tablonun il satırları birleştirilemez.

| İl | GDH ‰ 2025 | İlk doğum yaşı | Ort. anne yaşı | Aralık (yıl) | Aralık değ. 2019→2025 |
|---|---|---|---|---|---|
| **Türkiye** | **40,8** | **27,5** | **29,4** | **4,76** | **+0,14** |
| Şanlıurfa | 96,6 | 24,4 | 28,2 | 3,32 | +0,3 |
| Şırnak | 80,2 | 25,9 | 29,1 | 3,54 | +0,41 |
| Mardin | 68,6 | 26,1 | 29,2 | 3,88 | +0,43 |
| Ağrı | 66,6 | 24,7 | 27,7 | 4,06 | +0,65 |
| Siirt | 66,5 | 25,9 | 28,9 | 4,04 | +0,52 |
| Bitlis | 64,8 | 25,7 | 28,6 | 4,15 | +0,6 |
| Diyarbakır | 64,6 | 26,2 | 29,2 | 4,17 | +0,44 |
| Muş | 62,3 | 24,9 | 28,2 | 4,05 | +0,6 |
| Batman | 61,2 | 26,7 | 29,7 | 4,17 | +0,44 |
| Gaziantep | 59,2 | 25,3 | 28,1 | 4,32 | +0,26 |
| Van | 59,2 | 26,2 | 28,9 | 4,42 | +0,63 |
| Kilis | 57,4 | 25,1 | 27,8 | 4,21 | +0,13 |
| Adıyaman | 54,5 | 26,7 | 29,8 | 4,57 | +0,38 |
| Hakkari | 53,7 | 27,7 | 30,2 | 4,46 | +0,49 |
| Hatay | 50,8 | 25,9 | 28,2 | 4,34 | +0,24 |
| Iğdır | 50,2 | 26,2 | 28,6 | 4,54 | +0,54 |
| Kars | 49,5 | 26,1 | 28,3 | 4,5 | +0,4 |
| Kahramanmaraş | 48,1 | 25,6 | 28,5 | 4,91 | +0,21 |
| Osmaniye | 47 | 25,9 | 28,6 | 4,5 | +0,04 |
| Bingöl | 46 | 27,5 | 30,3 | 5,02 | +0,61 |
| Konya | 44,4 | 26,3 | 28,8 | 5,07 | +0,09 |
| Erzurum | 44,2 | 27,1 | 29,5 | 4,75 | +0,44 |
| Aksaray | 43,4 | 26,2 | 28,5 | 5,01 | +0,11 |
| Adana | 43,1 | 26,7 | 29 | 4,67 | +0,14 |
| Ardahan | 42,9 | 26,5 | 28,7 | 4,97 | −0,01 |
| Niğde | 42 | 25,8 | 28,2 | 4,94 | +0,19 |
| Afyonkarahisar | 40,7 | 26,1 | 28,3 | 4,81 | +0,07 |
| Sakarya | 40,6 | 27,5 | 29,6 | 5,16 | +0,09 |
| Kocaeli | 40,2 | 28 | 29,8 | 5,19 | +0,11 |
| Mersin | 39,6 | 27,2 | 29,4 | 4,84 | +0,15 |
| Manisa | 39,1 | 27 | 28,9 | 5,08 | +0,03 |
| Erzincan | 38,9 | 28 | 29,9 | 5,04 | −0,27 |
| Tekirdağ | 38,8 | 27,6 | 29,2 | 5,21 | −0,06 |
| Kayseri | 38,8 | 27,1 | 29,3 | 5,17 | +0,11 |
| Malatya | 38,7 | 27,9 | 30,2 | 5,04 | +0,14 |
| Yalova | 38,5 | 28,4 | 29,9 | 4,97 | +0,01 |
| Düzce | 38,4 | 27,4 | 29,5 | 5,26 | −0,06 |
| Tunceli | 38,1 | 28,9 | 30,2 | 4,72 | −0,2 |
| Elazığ | 38,1 | 27,9 | 30,2 | 5,11 | +0,19 |
| Karaman | 37,8 | 27 | 29,4 | 5,26 | +0,08 |
| Nevşehir | 37,4 | 26,3 | 28,5 | 5,23 | −0,16 |
| Bursa | 37,4 | 27,8 | 29,7 | 5,12 | +0,02 |
| Çankırı | 37,1 | 27 | 29 | 5,02 | +0,07 |
| Rize | 36,8 | 28,7 | 30,7 | 5,23 | +0,09 |
| Burdur | 36,1 | 26,8 | 29 | 5,25 | −0,32 |
| Yozgat | 36,1 | 26,6 | 28,9 | 5,26 | +0,19 |
| Bilecik | 36,1 | 27,6 | 29,5 | 5,44 | +0,09 |
| Aydın | 36 | 27,1 | 29,1 | 5,05 | +0,07 |
| Trabzon | 35,9 | 28,7 | 30,9 | 5,13 | +0,15 |
| Sivas | 35,9 | 27,1 | 29,3 | 5,06 | +0,07 |
| Artvin | 35,6 | 29 | 30,8 | 5,21 | +0,25 |
| Bayburt | 35,3 | 27,8 | 29,9 | 5,09 | +0,1 |
| Ordu | 35,3 | 27,4 | 29,5 | 5,29 | +0,17 |
| Kastamonu | 35,2 | 27,6 | 29,5 | 5,18 | −0,09 |
| Amasya | 34,8 | 27,7 | 29,6 | 5,31 | +0,16 |
| Samsun | 34,7 | 27,6 | 29,6 | 5,26 | +0,28 |
| Denizli | 34,5 | 27,6 | 29,6 | 5,39 | −0,14 |
| Kırşehir | 34,4 | 27,4 | 29,3 | 5,31 | +0,18 |
| Sinop | 34,1 | 27,5 | 29,6 | 5,13 | +0,22 |
| Balıkesir | 33,9 | 27,4 | 29,1 | 5,25 | −0,18 |
| Tokat | 33,8 | 26,8 | 29,1 | 5,03 | +0,07 |
| Çorum | 33,6 | 27,2 | 29,4 | 5,35 | +0,04 |
| İstanbul | 33,3 | 28,9 | 30,4 | 5,1 | +0,11 |
| Bolu | 33,3 | 28,2 | 30,1 | 5,42 | −0,04 |
| Antalya | 33,2 | 28,3 | 29,9 | 5,2 | −0,01 |
| Isparta | 33,2 | 27,6 | 29,6 | 5,31 | −0,07 |
| Muğla | 33,1 | 28,6 | 30 | 5,25 | −0,01 |
| Gümüşhane | 32,7 | 28 | 30,4 | 5,19 | +0,29 |
| Kırklareli | 32,2 | 28 | 29,4 | 5,63 | −0,05 |
| Giresun | 32,2 | 28,3 | 30,3 | 5,39 | −0,05 |
| Uşak | 32,1 | 27 | 28,7 | 5,31 | +0,11 |
| Kırıkkale | 31,9 | 27 | 29 | 5,29 | −0,12 |
| Ankara | 31,8 | 28,6 | 30,1 | 5,4 | +0,09 |
| Çanakkale | 31,7 | 28,1 | 29,6 | 5,31 | −0,25 |
| Edirne | 31,7 | 27,6 | 28,7 | 5,19 | −0,37 |
| Eskişehir | 31,3 | 28,6 | 30 | 5,34 | +0,07 |
| Karabük | 31,1 | 27,7 | 29,8 | 5,47 | −0,02 |
| İzmir | 30,7 | 28,7 | 30,1 | 5,36 | +0,09 |
| Kütahya | 30,5 | 27 | 29,3 | 5,55 | −0,09 |
| Bartın | 29 | 27,2 | 29,2 | 5,52 | +0,14 |
| Zonguldak | 28,5 | 27,9 | 29,5 | 5,25 | −0,16 |

**Tablonun okunuşu:** yukarıdan aşağı GDH düşerken aralık sütunu düzenli
biçimde büyüyor (Şanlıurfa 96,6 ‰ / 3,32 yıl → Zonguldak 28,5 ‰ / 5,25 yıl);
r=−0,96 tam olarak bu. Son sütun kimin hızla değiştiğini verir: Ağrı +0,65,
Van +0,63, Bingöl +0,61, Bitlis/Muş +0,60 — *hâlâ en sık doğuran* iller aynı
zamanda aralığı *en hızlı açan* iller, düşüş oradan geliyor. Batıda tablo
duruyor: Edirne −0,37, Burdur −0,32, Çanakkale −0,25 (aralık zaten genişti,
düşüş varsa doğrudan az-çocuk kararıyla — Bulgu 8'deki negatif artık grubu).

**Okuma uyarısı (aralık dosyası):** MEDAS'ın yıl sütunu blok başında bir kez
dolu ve tipi karışık — `2025.0` sayı, `2024(r)` metin. Yalnız sayı tipini
süzen okuma ara blokları sessizce 2025'e yazar ve TR 2025 değeri 4,76 yerine
4,60 çıkar. Rakam süzerek okunmalı.

