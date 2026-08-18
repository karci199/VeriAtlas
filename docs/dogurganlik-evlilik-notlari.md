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
| İl ve Annenin Yaş Grubuna Göre Doğumlar | 2009-2025 | ✔ 81 il | Bkz. Bulgu 9, 10, 11 (kullanıldı) — bant tahmininin tam hassas karşılığı |
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

## Bulgu 9 — TFR düşüşünün yarısı tek bir yaş bandında: 20-24

Kaynak: masaüstündeki *İl ve Annenin Yaş Grubuna Göre Doğumlar* (11 bant, 81 il,
2009-2025) — envanterde "tam hassas karşılık" diye işaretlenen dosya. Yaşa özel
doğurganlık hızı (ASFR) türetildi: pay bu dökümden, payda ambardaki tek yaş kadın
nüfusundan.

**Doğrulama.** Dökümün 1394 hücresinin tamamı ambardaki `births` ile birebir tuttu.
Bu yolla hesaplanan TFR ile TÜİK'in resmi il TFR'si arasındaki fark 2025'te ortanca
0,006, en büyüğü 0,029 — türetme kalibre.

Türkiye, TFR 2,096 → 1,419 (−0,677). Bantların katkısı:

| Bant | ASFR 2009 | ASFR 2025 | Değişim | TFR'ye katkı | Pay |
|---|---|---|---|---|---|
| 15-17 | 17,3 | 2,8 | −%84 | −0,043 | %6 |
| 18-19 | 67,0 | 18,5 | −%72 | −0,097 | %14 |
| **20-24** | **117,3** | **53,9** | **−%54** | **−0,317** | **%47** |
| 25-29 | 126,1 | 95,3 | −%24 | −0,154 | %23 |
| 30-34 | 84,4 | 79,7 | −%6 | −0,024 | %4 |
| 35-39 | 41,6 | 36,7 | −%12 | −0,024 | %4 |
| 40-44 | 10,8 | 8,4 | −%23 | −0,012 | %2 |
| 45-49 | 1,7 | 0,7 | −%58 | −0,005 | %1 |

Ergen doğurganlık oransal olarak en sert çöken bant ama nüfus payı küçük olduğu için
toplama katkısı %20'de kalıyor. 30 yaş üstü Türkiye genelinde neredeyse sabit.

**İl düzeyinde iki ayrı rejim var.** Düşüşün 30+ bandından gelen payı:

| İl | TFR 2009→2025 | 15-19 | 20-24 | 25-29 | 30+ | Anne yaşı |
|---|---|---|---|---|---|---|
| Şanlıurfa | 4,54 → 3,14 | %9 | %9 | %22 | **%61** | −0,05 |
| Şırnak | 4,69 → 2,53 | %10 | %18 | %22 | %50 | +0,86 |
| Hakkari | 3,33 → 1,70 | %11 | %22 | %20 | %47 | — |
| Van | 3,90 → 1,89 | %16 | %25 | %20 | %39 | +1,78 |
| Kars | 2,94 → 1,60 | %23 | %38 | %20 | %18 | +2,13 |
| İstanbul | 1,76 → 1,14 | %16 | %52 | %26 | %6 | +2,36 |
| Denizli | 1,74 → 1,26 | %24 | %68 | %25 | −%18 | +2,63 |
| Kırklareli | 1,39 → 1,15 | %25 | %96 | %23 | **−%43** | +2,08 |

Eksi pay, o bandın doğurganlığının **arttığı** anlamına gelir. Batıda (Kırklareli, Bolu,
Eskişehir, Balıkesir, Çanakkale, Kütahya) 30+ doğurganlığı 2009-2025 arasında yükseldi;
toplam yine düştü çünkü genç bantlar boşaldı — klasik erteleme. Güneydoğuda düşüşün
%36-61'i 30 yaş üstünden geliyor: kesilen şey geç yaştaki yüksek sıralı doğumlar, 5. ve
6. çocuk. İl medyanı %3, yani ülkenin yarısı ikisinin arasında.

**Bulgu 6-8 ile birlikte:** aralık açılması tezinin sayısal karşılığı bu. Şanlıurfa ile
Şırnak aynı %50-61 civarı 30+ payına sahip görünüyor ama Şırnak'ta genç bantlar da
çökmüş (20-24 −%44) ve ortalama anne yaşı +0,86 artmış; Şanlıurfa'da 20-24 yalnız −%13
düşmüş ve yaş hiç oynamamış. Aynı tabloda iki farklı mekanizma.

## Bulgu 10 — bant orta noktası tahmininin sapması küçük: Bulgu 1 ayakta

Bulgu 1, 9 bantlı `annedogumyas.xls` üzerinden orta nokta yöntemiyle hesaplanmıştı.
11 bantlı dosya aynı yöntemle yeniden hesaplandı; iki hesap arasındaki tek fark
15-19'un 15-17 + 18-19 olarak açılması, yani ölçülen şey tam olarak bant kabalığı.

| | İnce (11 bant) | Kaba (Bulgu 1) | Sapma |
|---|---|---|---|
| TR 2009 | 26,991 | 26,922 | −0,069 |
| TR 2025 | 28,962 | 28,928 | −0,034 |
| TR değişim | +1,970 | +2,007 | **+0,036** |
| İl sapması 2009 | | | ortanca −0,072, uç −0,119 (Ardahan) |
| İl sapması 2025 | | | ortanca −0,030, uç −0,071 |
| İl değişim sapması | | | uç +0,082 (Çorum) |

Kaba tahmin ortalama yaşı sistematik olarak ~0,07 yıl **düşük** gösteriyor: 15-19
bandına 17 orta noktası veriliyor ama doğumların çoğu 18-19'da. Sapma zamanla küçülüyor
(genç doğum azaldıkça), bu yüzden **değişim** ~0,04 yıl abartılıyor.

Sıralamaya etkisi yok denecek kadar az: en çok artan 12 il iki yöntemde de aynı sırada
(Çorum, Yozgat, Kırşehir, Ordu, Kütahya, Tokat...). 81 ilin 24'ünde sıra oynadı, en
büyük kayma Ardahan 41→36. Bulgu 3'teki yakınsama okuması bant seçiminin eseri değil.

Sapmanın en büyük olduğu iller (Çorum, Yozgat, Çankırı, Kırıkkale, Ardahan) aynı zamanda
Bulgu 1'in en çok artan illeri — o listeyi ~%3 oranında abartmış. Yön doğru, büyüklük
hafif şişkin.

## Bulgu 11 — 30+ doğum payı ile ortalama anne yaşı aynı şeyi ölçüyor (r=0,94)

Kullanıcının sorusu: "30+ payının kendi toplamına göre değişimi" ile ortalama anne yaşı
aynı şeyi mi söylüyor, yoksa biri eksik mi?

Doğumların 30 yaş ve üstü anneye ait olan payı, TR: %30,7 → %43,8 (+13,0 puan).

En çok artan: Artvin +20,4 puan (%34,9→%55,3), Çorum +19,0, Gümüşhane +18,9, Kütahya
+18,8, Sinop +18,6, Samsun +18,4, Trabzon +18,3, Ordu +18,3. En az artan: **Şanlıurfa
+0,4 puan** (%35,6→%36,0), Kilis +4,1, Gaziantep +5,0, Şırnak +5,5, Ağrı +5,9. 2025'te
en yüksek seviye Artvin %55,3, Trabzon %54,2, Rize %53,1; en düşük Ağrı %32,0.

**Cevap: neredeyse birebir aynı şeyi söylüyorlar.** r(pay değişimi, yaş değişimi) = 0,942;
seviyelerde r = 0,987 (2025) ve 0,976 (2009). Uyum doğrusu: pay puanı = −0,37 + 6,63 ×
yaş değişimi. Yani 30+ payı bağımsız bir bilgi değil, ortalama yaşın tek eşikli vekili.

**İkisinin de kaçırdığı şey aynı:** doğumların yaş dağılımı, kaç çocuk doğduğuna dair
hiçbir şey söylemiyor. Şanlıurfa'nın TFR'si 1,40 düştü; ne ortalama anne yaşı (−0,05) ne
30+ payı (+0,4 puan) bunu görüyor. Miktar (quantum) ile takvim (tempo) ayrı ölçü ister:
birincisi ASFR, ikincisi bunlar. Bu yüzden Bulgu 9'daki ayrıştırma bu ikisinin yerine
geçmiyor, onları tamamlıyor.

**Ayrıştıkları yer bilgi taşıyor.** Yaş artışına göre beklenenden fazla pay kayması:
Artvin +2,9 puan, Sinop +2,5, Trabzon +2,3, Gümüşhane +2,2, Bolu +2,1 — kayma tam 30
eşiğinin üstüne oturmuş. Beklenenden az: Yozgat −3,6 puan, Kırıkkale −3,2, Nevşehir
−2,9, Çankırı −2,5, Kırşehir −2,2 — Yozgat'ta ortalama yaş +3,11 yıl artmış ama hareket
30 eşiğini geçmemiş, 15-19'dan 20'li yaşlara olmuş. Tek eşikli oran dağılımın nerede
hareket ettiğini gizliyor; ortalama yaş gizlemiyor.

## Bu üç bulgunun kendi hataları

**Revize yıl işareti sessizce beş yıl yuttu.** Kaynak dosyada 2020-2024 yılları
`2024(r)` biçiminde yazılı (revize edilmiş veri). `float("2024(r)")` hata verdi, hatayı
yutan `except` o satırları atladı ve döküm 17 yıl yerine 12 yılla okundu — çıktı hatasız
görünüyordu, yalnız 1389 satır vardı, 1394 değil. Yıl sayısını sayana kadar fark
edilmedi. Ders: kaynağın satır sayısı beklenen çarpıma (17 yıl × 82 alan) eşit mi diye
bakmak, `except: continue` yazılan her yerde zorunlu.

**Ayrıştırma tablosunun sütun başlığı yanlış okundu.** "30+" sütunu düşüşün kaynağını
gösteriyor, doğumların yaş payını değil; kullanıcı haklı olarak "%61'i 30 yaşından sonra
mı doğuruyor?" diye sordu. Değil — o oran %36 ve 2009'dan beri sabit. Panelde sütun
altına bu ayrım yazıldı. İki farklı yüzde aynı tabloda yan yana durunca başlık tek
başına yetmiyor.
