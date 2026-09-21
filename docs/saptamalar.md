# Saptamalar — Türkiye

Elimizdeki veriden çıkan, **yayımlanan sayıya bakınca görünmeyen** bulgular. Her biri
depodaki `fact.parquet`'ten hesaplandı; hesabın kendisi yazılı, çünkü bir saptamanın
değeri kaynağının izlenebilmesinde.

Bu dosya rapor sayfalarının iskeletini belirliyor: bir sayfada bir bölüm varsa, buradaki
bir saptamayı gösterdiği için var.

## 1. Ölüm artıyor, ölümlülük azalıyor

Türkiye'de yıllık ölüm sayısı 2009'da 368.740, 2025'te 491.684 — **%33 artış**. Aynı
dönemde ölümlülük *düştü*.

| | 2009 | 2025 | Değişim |
|---|---|---|---|
| Ölüm sayısı | 368.740 | 491.684 | **+%33** |
| Kaba ölüm hızı (‰) | 5,08 | 5,71 | +%12 |
| **Yaşa göre standartlaştırılmış hız (‰)** | 5,08 | **4,04** | **−%20** |

Standartlaştırma: her yılın yaş-cinsiyet ölüm hızları **2009'un nüfus yapısına**
uygulandı. Yani "nüfus 2009'daki gibi kalsaydı kaç kişi ölürdü". Cevap: çok daha az.

Aradaki fark tamamen **yaşlanma**. 65+ payı %7,08'den %11,13'e çıktı; ölümlerin çoğu bu
yaşta olduğu için toplam ölüm, kişi başına risk azalırken bile artıyor.

**Neden görünmüyor:** TÜİK kaba ölüm hızını yayımlıyor, yaşa göre standartlaştırılmışı
yayımlamıyor. Kaba hıza bakan biri Türkiye'de sağlığın kötüleştiği sonucuna varır. Tam
tersi doğru.

## 2. Pandeminin ve depremin faturası, fazla ölüm olarak

2019'un yaş-cinsiyet ölümlülüğü sabit tutulup her yılın kendi nüfus yapısına
uygulandığında beklenen ölüm sayısı çıkıyor. Gerçekleşenle farkı:

| Yıl | Beklenen | Gerçekleşen | Fazla | % |
|---|---|---|---|---|
| 2020 | 448.736 | 509.147 | **+60.411** | +13,5 |
| 2021 | 457.319 | 566.745 | **+109.426** | +23,9 |
| 2022 | 469.633 | 505.540 | +35.907 | +7,6 |
| 2023 | 484.867 | 526.534 | +41.667 | +8,6 |
| 2024 | 506.678 | 489.734 | −16.944 | −3,3 |
| 2025 | 531.453 | 491.684 | **−39.769** | −7,5 |

İki yılda **170 bin fazla ölüm**. 2023'teki 41.667 fazlanın büyük kısmı depremdir. Ve
2024-25'te ölümlülük 2019'un *altına* indi: aynı nüfus yapısında 2019 hızlarıyla 531 bin
ölüm beklenirken 492 bin gerçekleşti.

**Neden görünmüyor:** ham ölüm sayısı 2021'de 566 bin, 2025'te 492 bin. "Düştü" denip
geçilir. Oysa 2025'in nüfusu daha yaşlı; aynı ölümlülükle 531 bin ölmesi gerekirdi.

## 3. Doğum düşüşü, sayının gösterdiğinden derin

| | 2009 | 2025 | Değişim |
|---|---|---|---|
| Doğum sayısı | 1.266.751 | 895.374 | −%29 |
| 15-49 yaş kadın | 19.493.140 | 21.948.521 | **+%13** |
| **Genel doğurganlık hızı (‰)** | 65,0 | **40,8** | **−%37** |

Doğuracak yaştaki kadın sayısı 2,5 milyon **arttığı hâlde** doğum 371 bin azaldı. Kadın
başına düşüş, doğum sayısının düşüşünden yaklaşık sekiz puan daha sert.

**Neden görünmüyor:** doğum sayısı tek başına, paydası büyüyen bir kesirin payıdır.

## 4. Doğurganlıkta doğu-batı makası kapanıyor

Genel doğurganlık hızı (15-49 kadın başına, binde), 2009 → 2025:

| İl | 2009 | 2025 | Değişim |
|---|---|---|---|
| Van | 124,2 | 59,2 | **−%52** |
| Ağrı | 137,8 | 66,6 | −%52 |
| Muş | 127,5 | 62,3 | −%51 |
| Siirt | 131,8 | 66,5 | −%50 |
| Şanlıurfa | 139,6 | 96,6 | −%31 |
| İzmir | 47,4 | 30,7 | −%35 |
| Zonguldak | 51,7 | **28,5** | −%45 |

En hızlı düşüş **doğuda**. Şanlıurfa hâlâ zirvede ama makas daralıyor: 2009'da en yüksek
il en düşüğün 3,0 katıydı, 2025'te 3,4 katı — Şanlıurfa'nın direnci yüzünden makas tam
kapanmadı, ama Van ve Ağrı gibi iller batı seviyelerine doğru hızla iniyor.

Zonguldak binde 28,5 ile Türkiye'nin en düşüğü — bu, Güney Avrupa'nın en düşük
düzeyleriyle aynı bölgede.

## 5. En hızlı yaşlanan yer, en çok göç veren yer

65+ payındaki artış (puan), 2007 → 2025:

| İl | 2007 | 2025 | Puan |
|---|---|---|---|
| Zonguldak | %8,1 | %16,8 | **+8,7** |
| Yozgat | %8,2 | %16,0 | +7,8 |
| Tokat | %9,2 | %16,6 | +7,4 |
| Edirne | %10,7 | %18,0 | +7,4 |
| Giresun | %12,7 | %20,0 | +7,3 |
| Şırnak | %3,4 | %3,8 | +0,4 |

Yaşlanma yalnız uzun yaşamak değil: Zonguldak'ın nüfusu 2009-2025 arasında %5,6 düştü
**ama doğal artışı artı** (+31.148). Yani doğan ölenden fazla, buna rağmen nüfus azalıyor
— genci gidiyor. Yaşlanmayı yapan şey göç.

**On bir il aynı durumda** — doğal artışı artı, nüfusu eksi: Yozgat, Ağrı, Kars, Erzurum,
Zonguldak, Çorum, Ardahan, Muş, Tokat, Sivas, Kütahya. Ağrı'da doğal artış +202.401 iken
nüfus 8,6% düşmüş; giden 248 bin kişi.

**Tersi yalnız bir il:** Kastamonu. Doğal artışı eksi (−1.513) ama nüfusu %5,6 artmış —
tamamen göçle.

**Neden görünmüyor:** nüfus artış hızı tek sayıdır ve iki ters kuvvetin toplamıdır.

## 6. İller ölümlülükte birbirine yakınsıyor

65+ ölüm hızının iller arasındaki dağılımı:

| Yıl | Ortalama (‰) | Standart sapma | En yüksek − en düşük |
|---|---|---|---|
| 2009 | 46,49 | 3,59 | 18,38 |
| 2019 | 41,99 | 2,97 | 16,05 |
| 2021 | 50,58 | 3,83 | 22,40 |
| **2023** | 40,80 | 4,97 | **37,18** |
| 2025 | 38,54 | **2,50** | 14,73 |

Hem seviye düşüyor hem de iller birbirine yaklaşıyor: 2025 en düşük sapmanın görüldüğü
yıl. İki istisna kendini ele veriyor — 2021'de pandemi dağılımı açıyor, 2023'te deprem
makası 37 punto ile tarihin en yükseğine çıkarıyor.

**Neden görünmüyor:** yakınsama bir ilin serisinde görünmez, ancak illerin *dağılımına*
bakınca görünür. Hiçbir yayımlanan tablo bu satırı vermiyor.

## 7. Evlilik azaldı, boşanma iki katına çıktı, dulluk kadının

| | 2001/2008 | 2025 |
|---|---|---|
| Evlenme sayısı | 641.973 (2008) | 552.237 |
| Kaba evlenme hızı (‰) | 9,04 (2007) | **6,41** |
| Boşanma sayısı | 91.994 (2001) | **193.793** |
| Kaba boşanma hızı (‰) | 1,33 (2007) | 2,25 |
| Ortalama ilk evlenme yaşı, erkek | 26,0 | 28,5 |
| Ortalama ilk evlenme yaşı, kadın | 22,7 | 26,0 |

15+ nüfusun medeni durumu, 2008 → 2025: evli %64,4 → %60,2; **boşanmış %2,58 → %5,20**
(iki katı); hiç evlenmemiş %27,7 → %29,0.

Cinsiyete göre bakınca ayrı bir şey çıkıyor: **eşi ölmüş kadın oranı %9,53, erkek %1,69**
— altı katı. Sebebi ikili: kadın daha uzun yaşıyor (65+ ölüm hızı 33,8‰'e karşı 43,4‰) ve
kadın kendinden ortalama 2,5 yaş büyük biriyle evleniyor. İkisi birleşince yaşlılıkta
yalnızlık büyük ölçüde kadın meselesi oluyor.

**Neden görünmüyor:** medeni durum genelde toplamda yayımlanıyor; cinsiyetle kesilince
altı kat fark ortaya çıkıyor.

## 8. Hanehalkı küçülürken hane sayısı artıyor

Ortalama hanehalkı büyüklüğü 4,00 (2008) → **3,08** (2025). Nüfus %22 artarken hane
sayısı çok daha hızlı arttı: aynı nüfus daha çok eve bölünüyor. Konut talebinin nüfus
artışından bağımsız bir bileşeni var ve bu tabloda duruyor.

## 9. Bebek ölümü yarıya indi

Bebek ölüm hızı 13,9‰ (2009) → **7,8‰** (2025), %44 düşüş. 0 yaş ölüm hızı (bin bebek
başına, erkek) 2024'te 10,1 — bütün yaş grupları içinde 55-59'a denk bir risk. Hayatın
ilk yılı hâlâ elli yaşındaki bir insanın riskini taşıyor.

## Rapor sayfaları bu saptamalara göre

Yukarıdakiler "hangi bölüm neden var" sorusunun cevabı:

| Bölüm | Hangi saptamayı gösterir |
|---|---|
| Nüfus ve bileşenleri (doğal artış / göç ayrık) | 5 |
| Yaş yapısı + piramit, 65+ payı | 1, 5 |
| Kaba **ve** standartlaştırılmış ölüm hızı yan yana | 1 |
| Beklenen-gerçekleşen ölüm (fazla ölüm) | 2 |
| Genel doğurganlık hızı, doğum sayısıyla birlikte | 3, 4 |
| Türkiye ve İBBS içinde sıra | 4, 6 |
| Evlenme-boşanma hızı, medeni durum cinsiyetle | 7 |
| Hanehalkı | 8 |
| Bebek ve çocuk ölümlülüğü | 9 |

Her rapor sayfasında bir ilin bu dokuz eksende **nerede durduğu** olacak: kendi serisi,
Türkiye ortalaması, ve İBBS-1 / bölge / ülke içindeki sırası.

# Saptamalar — il düzeyi

Aynı hesaplar seksen bir ile uygulandığında, Türkiye toplamında görünmeyenler.

## 10. Ölüm sıralaması, yaş düzeltilince baştan aşağı değişiyor

2025'in kaba ölüm hızı ile yaşa göre standartlaştırılmış hızı yan yana konunca sıralama
yer değiştiriyor — bazı illerde altmış küsur basamak:

| İl | Kaba (‰) | Standart (‰) | Kaba sıra | Standart sıra |
|---|---|---|---|---|
| **Tunceli** | 8,87 | **3,07** | 12. | **81.** |
| Artvin | 9,90 | 3,83 | 3. | 63. |
| Bayburt | 8,40 | 3,62 | 19. | 75. |
| **Şanlıurfa** | 3,16 | **4,37** | 77. | **8.** |
| Gaziantep | 3,95 | 4,36 | 70. | 10. |
| Kilis | 6,23 | 4,70 | 47. | **1.** |

**Tunceli, Türkiye'nin en düşük ölümlülüğüne sahip ili** — ham sayıya bakan biri onu
en yüksek üçte birde görür. Sebebi ölmek değil yaşlanmak: nüfusu Türkiye'nin en yaşlısı.

**Kilis'te ise gerçek ölümlülük Türkiye'nin en yükseği** ve kaba hız bunu tamamen
gizliyor, çünkü nüfusu genç. Şanlıurfa ve Gaziantep aynı durumda.

**Neden görünmüyor:** yayımlanan tek ölüm hızı kaba hız. Yaş yapısı çok farklı seksen bir
ili aynı sütunda sıralamak, sıralamanın kendisini yaş sıralamasına çeviriyor.

## 11. Gencini en çok kaybeden iller, üniversite illeri

20-29 yaşta yıllık net göç, o yaştaki bin kişiye oranla (2019-2025 ortalaması):

| En çok kaybeden | ‰ | En çok kazanan | ‰ |
|---|---|---|---|
| Gümüşhane | **−86,9** | Tekirdağ | +34,9 |
| Karabük | −60,3 | Kocaeli | +23,6 |
| Isparta | −54,6 | Yalova | +20,3 |
| Kırıkkale | −51,9 | Muğla | +20,1 |
| Bayburt | −51,1 | Antalya | +19,3 |

**Uyarı, ve saptamanın yarısı bu:** ilk dörtten üçü (Gümüşhane, Karabük, Isparta,
Kırıkkale) üniversite illeridir ve ADNKS öğrenciyi kayıtlı adresinde sayar. Brüt akışlara
bakınca durum görünüyor — Gümüşhane 2019-2025 arasında bu yaşta 29.070 kişi almış,
44.933 kişi vermiş. Yani "genç kaçıyor" değil, **gelen öğrenciden çok mezun gidiyor**:
üniversite kontenjanları daralırken il, gelen akışını kaybediyor.

Tekirdağ'ın kazancı ise brüt olarak da net: 116.943 gelmiş, 75.860 gitmiş.

## 12. Gidenin cinsiyeti doğuda erkek, batıda kadın

2019-2025 arasında ilden gidenlerde yüz kadına düşen erkek:

| En erkek | | En kadın | |
|---|---|---|---|
| Hakkari | 121 | Nevşehir | 74 |
| Şırnak | 118 | Uşak | 77 |
| Siirt | 108 | Denizli | 80 |

Doğuda göç eden erkek, batıda kadın. Batıdaki iller için akla gelen ilk açıklama
evlilik göçüdür — kadın evlenip başka ile taşınır — ama bunu doğrulamak evlenme kaydını
göçle eşleştirmeyi gerektirir ve elimizde o yok. Burada söylenen yalnız farkın kendisi.

## 13. Pandemi doğuyu ve İç Anadolu'yu vurdu, Ege'yi az

2019'un yaş-cinsiyet ölümlülüğüne göre 2020-2021 fazla ölümü:

| En ağır | % | En hafif | % |
|---|---|---|---|
| Bayburt | **+35,1** | Kars | **+3,9** |
| Ağrı | +31,9 | Iğdır | +6,6 |
| Diyarbakır | +29,8 | Bartın | +10,6 |
| Mardin | +28,2 | Balıkesir | +10,7 |
| Konya | +28,2 | İzmir | +11,2 |

Aradaki fark **dokuz kat**. İzmir'in %11,2'si 6.464 kişi, Konya'nın %28,2'si 6.917 —
neredeyse aynı sayıda insan, tamamen farklı bir yük.

## 14. Yaşam süresinde 5,4 yıllık il farkı

2023, doğuşta beklenen yaşam süresi:

- **Kadın**: Tunceli 83,6 · Gaziantep 78,7 → **4,9 yıl** fark
- **Erkek**: Tunceli 78,1 · Kilis 73,2 → **4,9 yıl** fark

Kadın-erkek makası her ilde kadın lehine ama genişliği değişiyor: Rize ve Şırnak'ta
**7,4 yıl**, Gaziantep'te 5,1.

Tunceli'nin hem en uzun ömür hem en düşük standartlaştırılmış ölümlülük **hem de** en
küçük hanehalkı (2,49) olması tek bir olguya bakıyor olabilir — ama bu veriden çıkmaz,
o yüzden burada yalnız yan yana duruyorlar.

## 15. Çocuk nüfusu yirmi ilde beşte bir eridi, dört ilde arttı

0-14 nüfusu 2007 → 2025:

| En çok düşen | % | Artan | % |
|---|---|---|---|
| Kars | −37,3 | Tekirdağ | **+47,9** |
| Zonguldak | −35,9 | Yalova | +42,8 |
| Çorum | −35,8 | Şanlıurfa | +28,9 |
| Gümüşhane | −35,7 | Kocaeli | +24,9 |

Şanlıurfa'nın çocuk nüfusu %29 artmış — doğurganlık hızı %31 düşerken. İkisi çelişmiyor:
doğuran kadın sayısı %43 arttı. Bu, saptama 3'ün il düzeyindeki en net örneği.

## 16. Boşanma haritası altı kat açılıyor

2025 kaba boşanma hızı: İzmir 3,28‰, Hakkari 0,51‰ — **altı kat**. Ege ve Akdeniz'in batı
ucu üstte, güneydoğu altta. Aynı harita ilk evlenme yaşında ters duruyor: kadınlar
Kilis'te 23,7, Şanlıurfa'da 23,8 yaşında ilk evliliğini yapıyor.

Eşler arası yaş farkı en büyük Kars ve Muş'ta (3,8 yıl). Bu sayı yalnız bir gelenek
ölçüsü değil: saptama 7'deki dulluk farkının hesabına doğrudan giriyor — kadın hem daha
uzun yaşıyor hem kendinden büyükle evleniyor.

## 17. Hanehalkı büyüklüğü ikiye katlanıyor

Şırnak 4,84 kişi, Tunceli 2,49 — aynı ülkede **iki katı**. Türkiye ortalaması 3,08 ve
düşüyor, ama bu ortalama iki ayrı ülkenin ortalaması gibi duruyor.

## 18. Evlenme, doğru paydayla bakılınca üçte bir düşmüş

Kaba evlenme hızı bütün nüfusu paydaya koyar. Ama evlenme riski yalnız **hiç evlenmemiş**
insanlardadır — çocuklar, evliler ve dullar o paydada işi olmayan kalabalıktır. Payda
düzeltilince Türkiye'nin son on yedi yılı başka görünüyor:

| | 2009 | 2025 | Değişim |
|---|---|---|---|
| Evlenme sayısı | 591.742 | 552.237 | −%6,7 |
| 15+ hiç evlenmemiş kadın | 6.305.001 | 8.639.548 | **+%37** |
| Kaba evlenme hızı (‰) | 8,16 | 6,41 | −%21 |
| **Rafine evlenme hızı (‰)** | **93,85** | **63,92** | **−%32** |

Evlenecek durumda olan kadın sayısı 2,3 milyon **arttığı hâlde** evlenme sayısı düştü.
Kaba hızın gösterdiği %21'lik düşüş, gerçek düşüşün üçte ikisi kadar.

Boşanmada payda evliler:

| | 2009 | 2025 | Değişim |
|---|---|---|---|
| Boşanma sayısı | 114.162 | 193.793 | +%70 |
| **Rafine boşanma hızı (‰)** | **6,63** | **9,41** | **+%42** |
| 100 evlenmeye düşen boşanma | 19,3 | **35,1** | — |

Son satır "evliliklerin üçte biri bitiyor" **değildir** — bu yılın boşanmaları başka
yılların evliliklerinden gelir, ve evlenme düşerken bu oran hiçbir şey değişmeden
yükselir. Ama iki akışın birlikte nereye gittiğini gösterir.

## 19. Paydayı düzeltince sıralama kırk basamak oynuyor

2025, kaba sıradaki yer ile rafine sıradaki yerin farkı:

| Kaba hız yanıltıyor (yukarı) | | Kaba hız yanıltıyor (aşağı) | |
|---|---|---|---|
| Kırklareli | +40 sıra | Batman | **−54 sıra** |
| Ordu | +40 | Mardin | −44 |
| Tekirdağ | +38 | Diyarbakır | −42 |
| **Balıkesir** | +35 (36. → **1.**) | Şırnak | −41 |

**Balıkesir, Türkiye'nin en çok evlenilen ili** — kaba hızda 36. sırada duruyor. Nüfusu
yaşlı, yani paydasının çoğu zaten evlenmiş; evlenmemiş olanlar ise yüksek oranda
evleniyor.

**Batman kaba hızda üst sıralarda, rafine hızda 54 basamak aşağıda.** Sebep aynı olgunun
tersi: nüfusu genç, hiç evlenmemiş kadın sayısı çok, o yüzden her evlenme kaba hızda
büyük görünür.

**Neden görünmüyor:** yayımlanan tek hız kaba hız, ve o hız büyük ölçüde ilin medeni
durum yapısını ölçüyor — evlenme davranışını değil.

## 20. Boşanma artışı en hızlı, boşanmanın en az olduğu yerde

Rafine boşanma hızının 2008-2025 artışı:

| İl | Artış |
|---|---|
| Bitlis | **+%352** |
| Siirt | +%320 |
| Van | +%271 |
| Ağrı | +%260 |
| Hakkari | +%240 |

Bu iller aynı zamanda **bugün hâlâ en düşük boşanma hızına sahip** olanlar (Hakkari
2,71‰, Şırnak 3,02‰ — İzmir 13,33‰). Yani düşük tabandan hızlı artış: makas kapanmıyor
ama yön belli.

Evlenmede tersi: en çok düşen iller Bayburt (−%64), Gümüşhane (−%62), Nevşehir (−%61) —
yani genci giden iller. Rafine evlenme hızı en düşük il de Gümüşhane (37,48‰), en yüksek
Balıkesir'in (85,63‰) yarısından az.

## 21. İlçede yapılamayan hesap

Kaba hız ilçede hesaplanabilir, **rafine hız hesaplanamaz**: TÜİK medeni durumu il
düzeyinden aşağıda yayımlamıyor, yani "hiç evlenmemiş kadın" ve "evli kadın" sayıları
ilçe için yok. Saptama 19 tam olarak kaba hızın ne kadar yanıltabildiğini gösterdiğine
göre, ilçe için yalnız kaba hız yayımlamak bilerek yanıltıcı bir tablo yayımlamak olurdu.

İlçe düzeyinde evlenme-boşanma sayısının kendisi de bu depoda henüz yok; MEDAS'ta olup
olmadığı bir sonraki çekimin sorusu.

# Saptamalar — eğitim

## 22. Eğitim serisinde 2015'te bir yöntem kırığı var

İlk kez evlenen kadınların eğitimi, **sayı olarak**:

| Yıl | Yüksek öğretim | Lise ve dengi | Okuma yazma bilen, okul bitirmeyen | Bilinmeyen | Toplam |
|---|---|---|---|---|---|
| 2013 | 57.370 | 157.852 | 58.449 | 20.321 | 516.635 |
| **2014** | **45.653** | 160.892 | 71.717 | 17.325 | 513.238 |
| **2015** | **173.571** | 110.068 | 43.567 | 7.629 | 512.234 |
| 2016 | 182.793 | 107.770 | 35.480 | 5.636 | 497.722 |

**Bir yılda üniversiteli gelin sayısı 3,8 katına çıkmış, toplam evlenme ise sabit.** Bu
demografik olarak imkânsız: 2015'te evlenen kadınlar 2014'te evlenenlerle aynı kuşak ve
bir yılda 128 bin kişi üniversite bitiremez. Kaybeden satırlar da kazanılanı neredeyse
tam karşılıyor — lise −50.824, ilköğretim −45.175, okuma yazma bilen −28.150, bilinmeyen
−9.696.

Yani 2015'te değişen şey gelinler değil, **eğitim bilgisinin nereden alındığı**. Kayıt
yöntemi değişmiş; bilinmeyenin yarıya inmesi de aynı şeyi söylüyor.

**Sonucu:** 2009 ile 2025'i bu seride karşılaştırmak geçersizdir. Kırığın kendisi bir
bulgudur, üstünden atlayan bir yüzde değil. Kırıktan sonrası kendi içinde tutarlı:
yüksek öğretim payı **%33,9 (2015) → %53,8 (2025)**, ve bu rakam savunulabilir.

**Neden görünmüyor:** bir serideki ani sıçrama her zaman olguya benzer. Yanındaki
satırların aynı anda aynı miktarda düştüğünü ve toplamın kıpırdamadığını fark etmek
gerekiyor. Bu dosyanın ilk hâlinde ben de "%8,4'ten %53,8'e, altı kat" diye yazmıştım;
sayıyı satır satır açınca kırık ortaya çıktı.

## 22b. Aynı tabloda ikinci bir kırık: ilköğretim / ortaokul

| Yıl | İlköğretim (8 yıl) | Ortaokul |
|---|---|---|
| 2014 | **187.769** | 1.908 |
| 2020 | 6.012 | **95.225** |

İlköğretim zaten ilkokul + ortaokuldur; TÜİK 2015-2019 arasında etiketi değiştirmiş ve
aynı insanlar bir satırdan ötekine geçmiş. Doğru okuma ikisinin toplamıdır: %26,3 (2009)
→ %14,8 (2025).

## 23. On altı-on dokuz yaşta ilk evlilik %71 düştü

| Yıl | 16-19 yaşta ilk kez evlenen kadın |
|---|---|
| 2001 | 165.706 |
| 2009 | 142.719 |
| 2015 | 107.665 |
| 2020 | 58.413 |
| 2025 | **40.813** |

2001'den beri **%75**, 2009'dan beri %71 düşüş. Aynı dönemde bütün ilk evlilikler %16
düştü. Yani genç evliliğin düşüşü, evlenmenin genel
düşüşünden **dört kat sert**. Bu, kaba sayının içinde kaybolan bir eğilim: toplam evlenme
grafiğine bakan biri yavaş bir azalma görür, yaşa bakan biri bir kırılma görür.

## 24. Yaş serisi sağlam, eğitim serisi değil

Eğitimde iki kırık bulununca aynı verinin yaş tarafı da denetlendi: 16-19 bandının sayısı
iki ayrı dosyada — il düzeyindeki yaş dosyasında ve Türkiye düzeyindeki eğitim dosyasında
— **on yedi yılın hepsinde birebir aynı**, ve seri hiçbir yerde sıçramıyor: 165.706'dan
40.813'e düzgün bir iniş.

Yani bu veride yaş güvenilir, eğitim değil. İkisi aynı dosyadan gelmesine rağmen: yaş
nikâh kaydından okunuyor ve tanımı hiç değişmemiş, eğitim ise başka bir kaynağa bağlanmış.
