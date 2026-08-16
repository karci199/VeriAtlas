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
