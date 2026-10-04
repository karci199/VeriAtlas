# Kent/kır il kalıbı — ne üretiyor, nasıl okunur

`scripts/analiz/kent_kir_2026_09_27/run_il.py <plaka>` → `C:\veri-ham\analiz\kent_kir\<plaka>\`.
Taban yılı 2024 (Endeksa = ADNKS 2024). Ülke geneli: `run_tr.py`, durum `_durum.csv`.

## Sınıflar (her mahalle tam bir sınıfta)
- **merkez**: 2013 öncesi ilçe belediyesi mahallesi + binalarının ≥%50'si ilçe merkezinin bina lekesinde
  (Microsoft bina, 50 m tampon). İlçe merkezi istisnası: eski ilçe mahallesi, köyden dönme değilse ve
  ≥%20 lekedeyse ya da DEGURBA kent diyorsa merkez.
- **kentsel_belde**: merkezden ayrı yerleşim, ≥5.000 kişi. Kent.
- **kasaba**: ayrı yerleşim, 2.000-5.000 kişi; belde geçmişine bakılmaz. Kır. (Elle kararlarda kasaba sınıfı yok, aşağıya bak.)
- **kirsal_belde**: 2014'e kadar belediyesi olmuş, <2.000. Kır.
- **kir**: köy. **osb**: nüfussuz sanayi bölgesi, kent alanından düşülür.
- Şüphede kır. Elle kararlar `birlestir.py` `ELLE` sözlüğünde, kaynağıyla.

## Dosyalar (il başına)
| Dosya | İçerik |
|---|---|
| `kent_<p>_son.csv` | mahalle × 7 sinyal (bina payı, DEGURBA, kayıt no bloğu, 2007-12 statü, haritatr, parsel, sokak), son sınıf, `arada` gerekçesi, `kurum` |
| `kent_<p>_ikili.csv`, `_ikili_ilce.csv` | kent/kır ve ilçe kentleşme oranı |
| `semt_<p>.csv`, `semt_<p>_profil.csv`, `semt_<p>_mahalle.csv` | semt (PTT semti / eski belde / kentsel belde / kasaba / "İlçe Köyleri"), nüfus, çocuk, yaş, eğitim, seçim |
| `secim_<p>_kentkir.csv`, `_sinif.csv`, `_ilce_kentkir.csv`, `secim_tek_parti_<p>.csv` | 2015-2024 sonuçları sınıfa göre; AK Parti 2002-2024 kent/kır |
| `secmen_oran_*`, `secmen_iliski_*` | kayıtlı / oy / 18+ / nüfus; mahalle tipolojisi (kurum sandığı, seçmen dışı, gurbetçi) |
| `tarihsel_<p>.csv` | sayım 1965-2000 + ADNKS 2007-2012 kent/kır serisi |
| `yas_mc_<p>_ilce.csv`, `_semt.csv`, `_mahalle.csv`, `_holdout.csv`, `_duyarlilik.csv` | ortanca yaş (IPF + 200 tur MC, %90 aralık), gizli test, sınıf/kurum duyarlılığı |
| `sapmalar_<p>.csv` | elle bakılacaklar: merkezsiz ilçe, arada kalan, kurum, kullanıcı listesiyle fark |
| `kullanici_fark_<p>.csv` | yalnız 8 ilde: masaüstü `İLLER 18+ Merkez Çevre` listesiyle farklar |

## Bilinen sınırlar
2002-2011 seçimlerinde kapanan belde mahalleleri bugünkü kimliğe bağlanmıyor (o yıllar kır = köy);
TKGM ad eşleşmesi ~%88; 2023-2024 arasında mahalle sınırı değişen ilçelerde 2023 seçmen/18+ oranı bozuk;
küçük köylerde yaş ortancası ±2 yaş, 2.000+ kırsal beldelerde +3 yaş sapma; PTT sokak adları çoğu yerde kod.

## Elle kent/kır kararları (kullanıcı, Ekim 2026) — kurallar

Karar dosyası: `scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json`, anahtar `area_id`,
değer `{n: gerekçe/kaynak, s: sınıf, y: birleşik belde adı}`. Boru hattı yalnız öneri verir, karar bu dosyadadır.
Kapsam (7.288 karar): Ankara, Bursa, Denizli, İstanbul, Manisa, Sakarya, Uşak, Balıkesir (tüm ilçeler).
Sayfa: `web/kentkir.html` (`scripts/serve.py 8123`), karar yazan: `POST /karar`.

**Sınıflar:** İl Merkezi, İlçe Merkezi (kent) · Kentsel Belde (kent) · Kırsal Belde (kır) · Köy (kır).
Kasaba sınıfı yok. Kentsel belde kırsal beldeden doku ile ayrılır, nüfusla değil.

**Kurallar**
1. **Merkez:** eski ilçe mahallesi, kent dokusuna bitişik, uyduda kesintisiz. Bitişiklik boşluğa bakılarak
   karar verilir (tarla, orman, nehir, otoyol, sanayi şeridi = ayrı); bina lekesi yardımcıdır, karar değil.
2. **Birleşik küme:** bitişik yerleşimler tek belde sayılır; eşik birleşik toplama uygulanır; ad en büyük
   birimden. Sayım iki türlü verilir: birim sayısı ve küme sayısı.
3. **Kırsal belde:** ayrı küme, ~1.950+ kişi (eşik üstü ayrı yerleşim yeter), eski belde olmak şart değil.
   **Eşik altı eski belde:** nüfus azalıyorsa köy (Yüreğil, Göbel, Gölkent), yatay/kararlıysa belde olabilir
   (Büyükyenice, Sarıbeyler, Işıklar). 5.000+ ama müstakil/köy dokulu = yine kırsal belde (Alifuatpaşa, Mende köy kaldı).
4. **Kentsel belde:** ayrı küme, apartman/kent dokusu, tipik ≥5.000; villa/yazlık siteleri ve ada/kıyı
   kümeleri eşik altında da olabilir (Kurtköy, Cunda, Ören, Kırkpınar).
5. **Olabildiğince kır:** nehir/otoyolla şehirden ayrık, müstakil, kendi camisi olan küme köydür, sinyaller
   kent dese de (Adapazarı Karaköy, Rüstemler, Çökekler, Taşlık). Notuna sinyal yazılır.
6. **Kurum nüfusu** (cezaevi, kampüs/yurt, kışla): sınıfı belirlemez, kayda not düşülür; nüfusu şişiren
   birim eşiği aşıyorsa kırsal belde yazılabilir (Ömerli, Börezli, Çağış, Muharremşah). Seri ve oran okurken ayrıca bak.
7. **Büyükşehir illerinde "hafif ihtilaf":** 2013'ten beri TÜİK her köye "mahalle" der, boru hattı bunu
   "TÜİK kent" sayar; AATOPLU, DEGURBA ve bina kır dediği sürece sahte ihtilaftır, köy yazılır.
8. **Resmî karşılaştırma:** büyükşehir illerinde resmî kent %100 çıkar, yapılmaz; Uşak gibi büyükşehir dışında yapılabilir.
9. **Uydu görüntüsü** son sözdür, kullanıcı atar, "tek tek bak" der; atılmazsa boru hattı önerisi + gerekçe sorulur.

**Zaman serisi:** 2013 öncesinde köy olup bugün kent sayılan birimlerin serisi yok: 2013 nüfusunu ilçe toplamıyla
geriye taşı. Bölünen mahalle (parent → child) bölünme yılındaki paya göre geriye dağıtılır. Edremit/Burhaniye
kıyısında 2013→2014 kayıt sıçraması (yalnız yetişkin, +%9) var: karşılaştırmayı 2014'ten başlat.
Kocaali ilçe nüfusu 2018 ve 2023'te, Ferizli Damlık cezaevi 2022-24'te seriyi bozar.

**Bilinen tutarsızlıklar:** 130 belde birimi (Ankara-Manisa) küme adsız; eşik altı eski belde bazen köy bazen belde
(yukarıdaki azalma kuralı); merkez saydığımız yeni apartman kuşaklarının uydu lekesi 0 (yeni yapı eksik).

## Ordu (52) — elle karar notları ve şerhler (2026-10-04)

19 ilçe, 774 birim, kent %60,6 (kırsal belde dahil %63,0), 2013'te %51,3. Kararlar `kullanici_karar.json`.

Şerhler (sonra dönüp bakılacak):
- **Akçatepe** (Altınordu, 1.984): 2013'te 530'du (+%274), artış kurum (üniversite/yurt); kullanıcı kararıyla köy (kurum nüfusu sınıf belirlemez; Efirli ve Yüceler ile tutarlı).
- **Turnasuyu** (Gülyalı) Ordu kıyı şeridine bitişik görünse de kentsel belde yazıldı (kullanıcı kararı); Gülyalı kent oranının %52'si bu tek birimden.
- **Gürgentepe** 6 mahalle merkez (konut/bina 0,7–2,4, boru hattı köy diyordu); **Kale** (Gölköy) merkez, **Karakoca** (Ulubey) köy: ilkinde kasaba dokusu mahalleye giriyor, ikincisinde mahalle boş.
- **Tepealan** (−%28) kırsal belde, **Akpınar** (−%28) köy: ayrım yoğunlaşmış çekirdek var/yok (foto). Eşik altı eski belde: düşüyorsa köy, sabitse belde (Yalıköy −%4 kırsal belde).
- **Bolaman + Güvercinlik** kırsal belde birleşik (2.383); Güvercinlik'in 2013 verisi yok (sonradan mahalle), 2013 karşılaştırması ilçe toplamıyla yapıldı.
- 2013'ten beri 12 kent mahallesi 1,6 ila 4,5 katına çıkmış (Fatsa Ayazlı ×4,5, Altınordu Cumhuriyet ×2,8): yeni yapılaşma ya da adres kaydı; Altınordu 2013→2014 +%5,2 sıçrama (2014 tabanı daha güvenilir olabilir).
- Boru hattı `secim_zaman.py` eski Ordu merkez kodu `x1552` düzeltildi; başka illerde eski `x####` kodları 2007-2011 sınıfsız oy kaybına yol açıyor olabilir.
