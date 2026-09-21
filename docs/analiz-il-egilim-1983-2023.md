# İl ve ilçelerin Türkiye'ye göre eğilimi, 1983–2023

Soru: son kırk yılda hangi il ülke ortalamasına **göre** sola, hangisi sağa kaydı?
Ham sol blok payı işe yaramaz — bir il ülkeyle birlikte sağa gitmiş olabilir. Burada
bakılan, ilin sol blok payının aynı seçimdeki ülke payından **farkı** ve bu farkın
zaman içindeki hareketi.

Üretim: `uv run python scripts/analyze_province_lean.py` (il) ve
`uv run python scripts/analyze_province_lean.py --level ilce --start 1995` (ilçe);
veri `public/elections/`.

## Yöntem ve kapsam dışı bırakılanlar

- **Seçimler:** 1983–2023, **12 seçim**. 1961–1977 kapsam dışı (pencere 1983'te başlıyor;
  ayrıca 1977'ye çıpalamak yanıltıcı olurdu, solun tavan yaptığı seçim).
- **2007 ve 2011 içeride, bağımsız sütunu Kürt/sol sayılarak.** O iki seçimde Kürt
  siyaseti bağımsız adaylarla girdi, oylar "BĞMZ" havuzunda duruyor. Havuzu o iki yılda
  Kürt/sol saymak, Kürt olmayan bağımsızın çıktığı yerde bir miktar fazla sayar — ama
  ülke genelinde sütun 2007'de %5,2, 2011'de %6,6 ve güneydoğuda yoğun; iki seçimi
  tamamen atmak dönemin altıda birini kaybettiriyordu. `--drop-0711` eski, katı okumayı
  geri getiriyor. **Kayma rakamları iki okumada aynı** (pencereler 1983–91 ve 2018–23,
  o yılları içermiyor); değişen, eğim ve ayrışma serisi.
- **CHP listesi olmayan il-seçimler atlandı** (2023'te Bitlis, Gümüşhane, Muş, Yozgat,
  Çankırı). Olmayan liste bir tercih değil.
- **1989 sonrası kurulan 14 il** çıktıkları ile katlandı; karşılaştırmanın iki ucu aynı
  toprağı kapsıyor. Kalan: **67 il**.
- **Kayma** = 2018–2023 ortalama farkı − 1983–1991 ortalama farkı (puan). **Eğilim** =
  aynı farkın en küçük kareler eğimi (puan / 10 yıl, 12 seçimin hepsi kullanılır). İkisi de aynı hikâyeyi anlatıyor;
  kayma daha okunur, eğilim tek bir seçime bağlı değil.
- İki okuma yan yana: **Kürt partileri solda** ve **Kürt partileri hariç**. Anlaşmadıkları
  yer bulgunun kendisi.

Ülke sol blok payı bu dönemde %30,4 → %37,4 (Kürt partileri hariç %30,4 → %28,5).
Yani aşağıdaki hareketler ulusal bir salınım değil, **yeniden dağılım**.

## 1. Kürt partileri solda sayılınca

| En çok sola | kayma | | En çok sağa | kayma |
|---|---|---|---|---|
| Ağrı | **+36,3** | | Sivas | **−19,4** |
| Van | +35,5 | | Niğde | −17,5 |
| Hakkari | +29,2 | | Sinop | −16,7 |
| Siirt | +27,8 | | Zonguldak | −14,2 |
| Bitlis | +27,3 | | Yozgat | −13,8 |
| Muş | +26,3 | | Tokat | −13,4 |
| Diyarbakır | +23,0 | | Ordu / Trabzon | −12,9 |
| Mardin | +22,1 | | Gümüşhane | −12,9 |

Sola kayan ilk sekizin hepsi Kürt illeri. Ağrı 1983–91'de ülkenin 4,8 puan sağındayken
2018–23'te 31,5 puan solunda: **kırk yılda 36 puan**, listenin açık ara birincisi.
Karşı uçta İç Anadolu ve Batı Karadeniz: Sivas 1983'te ülkeyle aynı yerdeyken bugün
18,6 puan sağında.

## 2. Kürt partileri hariç tutulunca eksen değişiyor

| En çok sola | kayma | | En çok sağa | kayma |
|---|---|---|---|---|
| Muğla | **+16,8** | | Diyarbakır | **−31,8** |
| Antalya | +13,9 | | Tunceli | −29,4 |
| Kırklareli | +13,2 | | Hakkari | −28,7 |
| Aydın | +11,8 | | Mardin | −26,2 |
| Çanakkale | +11,3 | | Siirt | −23,4 |
| Isparta | +10,9 | | Kars | −22,4 |
| İzmir | +9,5 | | Muş | −17,9 |

Aynı iller iki listede ters uçlarda: Diyarbakır bir okumada +23,0, diğerinde −31,8.
Sebep basit ve önemli — güneydoğuda CHP tipi sol **yok olmadı, yerini Kürt partilerine
bıraktı**. Hangi listeyi okuduğunuz, o oyları nasıl saydığınıza bağlı.

Kürt partileri dışarıda bırakıldığında geriye kalan asıl hareket **kıyı–iç ayrışması**:
Ege, Batı Akdeniz ve Trakya sola; İç Anadolu, Karadeniz ve güneydoğu sağa.

## 3. Parti tanımından bağımsız olan hareket

İki okumada da aynı yöne kayan iller — sonuç blok tanımına bağlı değil:

- **Sola:** Muğla (+11,4 / +16,8), Antalya (+9,6 / +13,9), Aydın (+9,8 / +11,8),
  Kırklareli (+5,3 / +13,2), İzmir (+8,7 / +9,5), Çanakkale, Isparta, Eskişehir,
  Balıkesir, Artvin.
- **Sağa:** Sivas (−19,4 / −10,3), Niğde (−17,5 / −8,1), Sinop (−16,7 / −7,4),
  Zonguldak (−14,2 / −4,8), Gaziantep (−11,5 / −11,1), Kocaeli, Tokat, Yozgat,
  Trabzon, Ordu.

Not: Isparta ve Bolu "sola kaydı" derken hâlâ ülkenin sağında (−5,5 ve −4,9); kayma
yönü söyler, konumu değil.

## 4. İki okumanın en çok ayrıldığı iller

Fark, Kürt partilerinin o ildeki katkısının büyüklüğü:

| il | kürtlü | kürtsüz | fark |
|---|---|---|---|
| Hakkari | +29,2 | −28,7 | 57,9 |
| Diyarbakır | +23,0 | −31,8 | 54,8 |
| Siirt | +27,8 | −23,4 | 51,2 |
| Ağrı | +36,3 | −13,5 | 49,7 |
| Mardin | +22,1 | −26,2 | 48,3 |
| Van | +35,5 | −12,0 | 47,5 |
| Muş | +26,3 | −17,9 | 44,1 |
| Tunceli | +8,4 | −29,4 | 37,9 |
| Kars | +1,3 | −22,4 | 23,7 |

Tunceli ilginç: iki okumada da ülkenin solunda (bugün +42,6 / +4,7), ama Kürt partileri
sayılmazsa 1983'teki +34,2'lik solculuğunun neredeyse tamamını kaybetmiş görünüyor.

## 5. İlçe düzeyi (1995–2023)

`--level ilce --start 1995`. **750 ilçe**, 7 seçim. 1995'ten başlıyor çünkü 1983–87
raporlarında ilçelerin çoğu hâlâ "Merkez" diye geçiyor. İki ek eleme var, ikisi de
sessiz bozulmayı kesmek için:

- **Sınırı değişmiş sayılanlar (38 ilçe):** seçmeni ülkenin 0,45–2,5 katı dışında
  hareket eden ilçe fikir değil şekil değiştirmiştir. En uçtakiler Battalgazi ×9,0,
  Edremit (Van) ×7,2, Yeşilyurt ×7,0, Etimesgut ×3,6, Nilüfer ×2,5 — hepsi 2013
  büyükşehir düzenlemesinin ya da merkez bölünmelerinin ürünü.
- **5.000 seçmenin altındakiler** dışarıda: birkaç bin seçmen eğilimle değil gürültüyle
  salınıyor (bu eleme olmadan listenin tepesine Yedisu, Bozcaada gibi yerler çıkıyor).

**Kürt partileri solda — en çok sola:** Güçlükonak (Şırnak) **+49,1**, Patnos (Ağrı)
+45,4, Muradiye (Van) +39,1, İdil (Şırnak) +36,8, Mazıdağı (Mardin) +35,2, Hamur (Ağrı)
+34,5, Taşlıçay +33,7, Dargeçit +33,4.

**En çok sağa:** Akkuş (Ordu) **−21,8**, Ayvacık (Samsun) −19,3, Eflani (Karabük) −18,6,
Erfelek (Sinop) −17,7, Kumru (Ordu) −17,7, Ulus (Bartın) −17,6, Şenkaya (Erzurum) −17,6,
Çarşamba (Samsun) −17,4. **Liste neredeyse tamamen Karadeniz kırsalı.**

**Kürt partileri hariç — en çok sola:** Datça (Muğla) **+17,6**, Fındıklı (Rize) +16,3,
Şavşat (Artvin) +15,8, Bodrum +15,8, Fethiye +15,3, Karşıyaka +15,1, Hacıbektaş +14,9,
Güzelbahçe +14,6, Beşiktaş +14,5, Karaburun +14,2, Dikili +14,1. **En çok sağa:** Eruh
(Siirt) −24,6, Şenkaya −20,5, Adaklı (Bingöl) −16,9, Akkuş −14,1, Iğdır Merkez −14,0.

İl düzeyindeki resim ilçede de aynı, daha keskin hâliyle çıkıyor:

- İki okumada da sola gidenler **turizm kıyısı ve büyük şehrin eğitimli merkezi**:
  Datça (+19,8 / +17,6), Bodrum, Adalar (+22,0 / +12,6), Beşiktaş (+17,5 / +14,5).
- İki okumada da sağa gidenlerin hepsi **Orta ve Doğu Karadeniz kırsalı**: Akkuş,
  Ayvacık, Eflani, Erfelek, Kumru, Ulus, Çarşamba, Gökçebey.
- Fındıklı ve Şavşat ilginç istisna: Rize ve Artvin'in içinde, ülkeye göre sola giden
  iki ilçe.

40 yıllık uzun pencere (`--start 1983`) yalnız **486 ilçe** bırakıyor — 230'u sınır
değişikliği elemesine takılıyor — ama sıralamanın tepesi aynı yöne bakıyor: Karayazı
(Erzurum) **+59,5**, Başkale (Van) +52,0, Bulanık (Muş) +51,2.

## 6. Ayrışma, oynaklık ve göç (`--dispersion`)

### Ülke coğrafi olarak ayrıştı, 2015'te tepe yaptı

Her seçimde illerin ülkeden sapmasının standart sapması:

| seçim | il sd | seçmen ağırlıklı | kürtsüz sd |
|---|---|---|---|
| 1983 | 8,77 | 6,09 | 8,77 |
| 1995 | 10,45 | 8,33 | 10,73 |
| 2002 | 12,47 | 10,20 | 8,49 |
| 2011 | 16,41 | 12,54 | 13,74 |
| **2015 Haz** | **20,09** | **15,49** | 13,85 |
| 2018 | 17,28 | 13,72 | 11,83 |
| 2023 | 15,54 | 12,62 | 10,81 |

İller 40 yılda birbirinden **iki kattan fazla uzaklaştı** (8,8 → 20,1), zirve 2015
Haziran; 2015'ten beri makas bir miktar kapanıyor. Kürt partileri hariç okumada da
artıyor (8,8 → 14,4 → 10,8), yani ayrışma yalnız Kürt oyunun hikâyesi değil. İlçe
düzeyinde aynı eğri, daha yüksek seviyede: 12,25 (1995) → 22,00 (2015 Haz) → 17,77 (2023).

### Oynaklık ≠ kayma

Eğilim çıkarıldıktan sonra kalan artık standart sapma, "yerinde durmayan" yerleri verir.
En oynak iller **Tunceli 12,7 · Hakkari 12,0 · Ağrı 10,4 · Mardin 9,4 · Rize 8,2**;
en durağanlar **İstanbul 1,3 · Adana 1,3 · Mersin 1,5 · Samsun 1,6 · Balıkesir 1,7**.
Büyük iller hem az kayıyor hem az sallanıyor: ülke ortalamasını onlar tanımlıyor.
Rize istisna — kaymadı (−5,3) ama seçimden seçime çok sallanıyor.

### Göç sorusunun cevabı: kısmen evet, ama sandığın kadar değil

Seçmen artışını ülkeye oranladım (1'in altı = ülkeden yavaş büyüyen, boşalan yer).

| kapsam | n | r (kürtlü) | r (kürtsüz) |
|---|---|---|---|
| tüm iller | 67 | **+0,51** | −0,24 |
| Kürt partisi payı hep %10 altında kalan iller | 44 | **+0,39** | +0,23 |
| tüm ilçeler | 750 | +0,37 | +0,06 |
| Kürt partisi payı düşük ilçeler | 531 | +0,26 | +0,14 |

En çok boşalan 15 il, senin tahminini birebir doğruluyor — **İç Anadolu ve Karadeniz**:
Afyonkarahisar 0,45 · Tunceli 0,46 · Artvin 0,48 · Çankırı 0,52 · Kastamonu 0,52 ·
Sinop 0,53 · Gümüşhane 0,57 · Erzincan 0,58 · Kars 0,58 · Yozgat 0,59 · Sivas 0,59 ·
Tokat 0,60 · Amasya 0,61 · Rize 0,61 · Çorum 0,61.

Bunların kayması çoğunlukla sağa: Sivas −19,4, Sinop −16,7, Yozgat −13,8, Tokat −13,4,
Çankırı −11,9, Kastamonu −9,3.

**Ama üçüncü sütuna bak.** Aynı illerin Kürt partileri hariç okumadaki kayması sıfıra
yakın: Afyon +1,0, Kastamonu +0,6, Çankırı −0,8, Yozgat −2,9, Rize +4,3. Korelasyon da
+0,39'dan +0,23'e düşüyor. Yani boşalan illerin "sağa kayması"nın büyük kısmı kendi
seçmenlerinin değiştiğinden değil, **ülke ortalamasının Kürt oyuyla sola gitmesinden**
kaynaklanıyor: yerinde duran yer, hareket eden bir ortalamaya göre geriye düşmüş görünür.

Geriye kalan +0,23'lük ilişki gerçek ama zayıf — boşalmanın kaymayı açıklayan payı
%5 civarı. Ve yön bile kesin değil: aynı listede Artvin (+7,6 kürtsüz) ve Rize (+4,3)
boşalırken sola gitmiş. **Göç bir faktör, tek faktör değil.**

## 7. Ülkeye göre değil, kendine göre

"TR'ye göre fark"ın iki ucu da hareket ediyor. Referansı bırakıp her yeri **kendi
geçmişiyle** karşılaştırınca resim netleşiyor. Ülke sol blok payı 1983–91'de %31,9,
2018–23'te %36,1 — yani **+4,2 puan**.

**İl düzeyi.** Kendi sol payı gerçekten düşen: **31/67**. Sol payı *arttığı hâlde*
ülkeye göre geri düşen: **11 il** — bunlar sağa dönmedi, ülke onlardan hızlı sola gitti.

| il | bugünkü sol % | kendi değişimi | TR'ye göre | fark |
|---|---|---|---|---|
| Sivas | 17,5 | **−15,2** | −19,4 | 4,2 |
| Niğde | 14,7 | −13,2 | −17,5 | 4,3 |
| Sinop | 27,6 | −12,5 | −16,7 | 4,2 |
| Yozgat | 12,6 | −10,8 | −13,8 | 3,0 |
| Zonguldak | 30,3 | −10,0 | −14,2 | 4,2 |
| Trabzon | 17,9 | −8,7 | −12,9 | 4,2 |
| Çankırı | 7,2 | −8,9 | −11,9 | 3,0 |

Yani listenin tepesindeki iller **gerçekten sağa gitti** — Sivas'ın kendi sol payı 15
puan düşmüş. Referans etkisi sabit ve küçük: her yerde ~4 puan, ülkenin kendi
hareketi kadar. Önceki bölümlerdeki −19,4 rakamının yaklaşık **dörtte biri** ülke
ortalamasının kaymasından, **dörtte üçü** ilin kendi değişiminden geliyor.

**İlçe düzeyi.** Kendi sol payı düşen: **319/750**. Artmasına rağmen ülkeye göre geri
düşen: **172 ilçe** — bu grup ilde olduğundan çok daha kalabalık. En sert gerçek
düşüşler yine Karadeniz: Akkuş −17,8 (bugün %15,6), Ayvacık (Samsun) −15,3 (%6,5),
Eflani −14,5, Erfelek −13,7, Kumru −13,6 (%8,9).

Kürt ilçelerinde ise "kendi" ve "kürtsüz kendi" sütunları taban tabana zıt: Güçlükonak
kendi sol payını +53,2 artırmış, Kürt partileri sayılmazsa yalnız +2,0. Diyarbakır'da
il düzeyinde kendi payı +27,3, kürtsüz **−37,8**. Aynı seçmen, iki farklı sorunun
cevabı.

## 8. Bileşim mi, fikir mi? (shift-share)

Ülke sol payı, yerel payların nüfusla ağırlıklı ortalaması. İki sebeple değişebilir:
insanlar farklı oy verdiği için (**within**) ya da büyüyen yerler ile küçülen yerler
farklı oy verdiği için (**between** — kimse fikrini değiştirmeden ortalama kayar).

| bileşen | il | ilçe |
|---|---|---|
| toplam değişim | +4,38 | +3,39 |
| yerinde fikir değişimi | +2,30 | +2,59 |
| **nüfus kayması** | **+0,66** | **+0,44** |
| etkileşim | +1,42 | +0,36 |
| nüfus kaymasının payı | **%15** | **%13** |

**Göç ülke sonucunu tek başına taşımıyor.** Kırk yıllık nüfus kayması ülke sol payına
yarım puandan biraz fazla katmış; değişimin %85'i insanların bulundukları yerde farklı
oy vermesinden geliyor. İl düzeyindeki büyük etkileşim terimi (+1,42) tek bir olguyu
gösteriyor: hem hızlı büyüyen hem çok sola giden yerler, yani Kürt illeri.

## 9. Yerin kaderi ne kadar sabit?

Birimlerin ülkeden sapmasının ilk ve son pencerede sıralaması ne kadar aynı kalıyor
(Spearman):

| pencere | il | ilçe |
|---|---|---|
| 1995 → 2023 (28 yıl) | 0,91 / 0,95 | 0,88 / 0,91 |
| 1983 → 2023 (40 yıl) | 0,64 / 0,51 | 0,61 / 0,46 |

(kürtlü / kürtsüz). İl ve ilçe aynı sonucu veriyor — fark düzeyden değil **pencere
uzunluğundan**. Bir kuşak boyunca coğrafya neredeyse kader (0,9); kırk yılda ciddi bir
yeniden dizilim var (0,5–0,6). 1980'lerin siyasi haritası bugünün haritası değil.

## 10. Kenarda duran birkaç şey

- **2015'in iki seçimi arasında beş ay var, bazı yerlerde 26 puan.** Kendi sol payı
  Haziran'dan Kasım'a en çok düşen ilçeler: Köprüköy (Erzurum) −26,5, Eleşkirt (Ağrı)
  −24,2, Hamur −19,1, Arıcak (Elazığ) −16,7, Gürpınar (Van) −16,0 — hepsi doğuda.
  Aynı beş ayda Trakya ters yöne gitti: Hanak +8,4, Babaeski +8,3, Saray (Tekirdağ)
  +8,1, Kırklareli Merkez +7,4. İl düzeyinde de aynı: Şanlıurfa −11,3 ↔ Kırklareli +5,1.
- **Kürt partileri hariç bugünün en sol ilçeleri** neredeyse tek bir koridor: Karşıyaka
  %62,5, Beşiktaş %60,3, Narlıdere %59,9, Güzelbahçe %59,7, **Divriği (Sivas) %58,7**,
  Urla %57,7, Babaeski %56,6, Dikili %55,9. Divriği bu listede tek başına ayrık duruyor
  — Sivas'ın Alevi ilçesi, ilin geri kalanı %17,5'te.
- **En düşükler tek bir ilde kümeleniyor:** Muş'un beş ilçesi ilk sekizde (Korkut %1,5,
  Bulanık %1,5, Malazgirt %1,6, Hasköy %1,6, Muş Merkez %1,9). Kürt partisi çıkarılınca
  bu ilçelerde sol pratikte yok.
- **Kırklareli, kürtsüz okumada Türkiye'nin en sol ili** (%49,0) — İzmir'i (%44,3) ve
  Muğla'yı (%43,9) geçiyor. Edirne ikinci (%44,6).

## 11. Ülkede sol ne zaman düştü?

Sol blok payı, ülke geneli, 17 seçim:

| seçim | sol | kürtsüz | önceki seçime göre |
|---|---|---|---|
| 1961 | 36,8 | 36,8 | |
| 1965 | 31,8 | 31,8 | −5,0 |
| 1969 | 32,9 | 32,9 | +1,1 |
| 1973 | 34,6 | 34,6 | +1,6 |
| **1977** | **42,0** | 42,0 | +7,4 |
| 1983 | 30,4 | 30,4 | **−11,5** |
| 1987 | 33,2 | 33,2 | +2,8 |
| 1991 | 32,0 | 32,0 | −1,2 |
| 1995 | 29,8 | 25,6 | −2,2 |
| 1999 | 37,5 | 32,1 | +7,7 |
| 2002 | 28,9 | 22,8 | −8,5 |
| **2007** | **27,0** | **21,7** | −2,0 |
| 2011 | 33,0 | 26,5 | +6,1 |
| 2015 Haz | 38,8 | 25,8 | +5,7 |
| 2015 Kas | 36,7 | 26,2 | −2,1 |
| 2018 | 34,8 | 23,1 | −1,9 |
| 2023 | 37,4 | 28,5 | +2,6 |

- **Tek seferde en büyük düşüş 1977 → 1983: −11,5 puan.** Askerî darbe ve parti
  kapatmaları; CHP 1983'te sandıkta yok.
- **1977 → 1995 aralığı gerçekten dönemin adı:** 42,0 → 29,8, on sekiz yılda −12,2 puan
  ve dört seçim üst üste düşüş (1983, 1991, 1995). Sezgi doğru.
- Ama dip 1995 değil: sol blok en düşük seviyesini **2007'de (%27,0)** gördü. 1999'un
  +7,7'lik DSP sıçraması geçici çıktı, 2002'de −8,5 ile fazlasıyla geri verildi.
- **Kürt partileri hariç okumada dip daha geç ve daha derin: 2007'de %21,7**, ve o seri
  bugün bile (%28,5) 1977'nin 13 puan altında. 1977'nin seviyesine hiçbir zaman
  dönülmedi; sol blok payındaki son toparlanma büyük ölçüde Kürt oyunun eklenmesiyle.

Kısacası: düşüş 1977'de başladı, 1983'te bir defada koptu, 1995'e kadar sürdü,
1999'da sahte bir sıçrama yaptı ve asıl dibi 2000'lerin ortasında gördü.

## Ne söylemiyor

- Bu bir **oy oranı** analizi değil, **göreli konum** analizi. "Sola kaydı", "sol
  partiler oyunu artırdı" demek değil; "ülkeye göre solda kalan mesafesi arttı" demek.
- Blok ayrımı bir yorumdur; parti listesi `scripts/build_election_series.py` içinde
  açıkça duruyor ve tartışmaya açıktır. YTP yıla göre çözülüyor (1961–69 sağ, 2002 sol).
- 1977'ye çıpalanmadı; 1977 solun tavan yaptığı seçim, oraya göre ölçünce her yer sağa
  kaymış görünür.
- Göç ilişkisi korelasyondur, mekanizma değil: kimin gittiği (genç, eğitimli, seçici göç) bu veriden görünmez.
- Nüfus hareketi doğrudan ölçülmedi; seçmen artışı vekil ölçüt olarak kullanıldı. Alevi yoğun ilçelerde daha önce görülen "sağa dönmedi,
  boşaldı" bulgusu il düzeyinde de geçerli olabilir; bu analiz onu ayırt etmiyor.
