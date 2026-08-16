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
