# Zincir mağazalar — çekim yöntemi ve depoya giren

Hiçbir zincir il/ilçe tablosu yayımlamıyor. Hepsi kendi "mağaza bulucu"sundan okundu
(2026-09-18). Ham dosyalar `C:\veri-ham\<marka>\`, repo dışında.

## Depoya giren

`chain_restaurants` — Burger King ve McDonald's şube sayısı, ilçe ve il düzeyinde,
18.09.2026 anlık görüntüsü. Adaptör `src/veriatlas/adapters/chain_stores.py`.

**Seri değil.** Mağaza bulucular yalnız bugün açık olanı gösteriyor, geçmişini tutmuyor.
Yeniden çekildiğinde satırlar eklenmez, değiştirilir — TKGM MEGSİS anlık görüntüsüyle
aynı kural.

**İlçe adresten değil koordinattan belirleniyor.** İkisinin de her şubede koordinatı var;
`public/geo/districts/*.geojson` sınırlarına nokta-poligon testiyle düşürülüyor. Adres
metnine güvenilmemesinin nedeni:

- Burger King'in adresindeki il/ilçe kendi pazarlama coğrafyası. Ataşehir etiketli şube
  Ümraniye sınırında çıkabiliyor; ayrıca URL parçaları `ç/ş/ı`'yı düşürdüğü için
  `Çukurova` ile `Cukurova` çakışıyor.
- McDonald's yanıtında `city` ve `town` alanları **var ama 335 satırın hepsinde boş**.

Koordinatı hiçbir ilçeye düşmeyen şube tahmin edilmiyor, düşürülüyor: BK 847'de 12,
McDonald's 335'te 1 — hepsi kıyı şeridinde, sınırın sahilin gerisinden geçtiği yerlerde
(marina, plaj tesisi, iskele). Kayıp %3'ü aşarsa adaptör hata veriyor; sınır dosyası
değişip sayı sessizce küçülmesin diye.

İl satırı ilçelerin toplamı olarak adaptörün kendisinde yazılıyor. `aggregate` ile
yapılsaydı `estimated` damgası yerdi; oysa bu bir sayımın birebir toplamı.

## Marka marka çekim yöntemleri

| Marka | Kayıt | Koordinat | Yöntem |
|---|---|---|---|
| **McDonald's** | 335 | %100 | `POST /restaurants/getstores`, gövde `cityId=0&subcity=&avm=false` → tüm Türkiye tek istekte. Ek alanlar: McDrive, McCafe, kiosk, kahvaltı, 24 saat, AVM içi |
| **Burger King** | 847 | %98,8 | robots.txt'teki `restaurants_tr.xml` → 847 şube sayfası; her sayfada `data-location="[lat,lng]"`. **httpx çalışmıyor** (çift `Transfer-Encoding` başlığı, h11 reddediyor) → `urllib` |
| **PTT** | 3.295 | %100 | `POST enyakinptt.ptt.gov.tr/api/Isyerleri`, gövde `ilID=<plaka>&ilceID=0&mahKoyID=0`. Yanıt **Base64'lü JSON** |
| **BİM** | 13.057 | yok | PRG deseni: `GET magazalar.aspx?CityKey=<plaka>&CountyKey=<id>&firin=0`. İlçe id'leri `?CityKey=<n>` sayfasındaki select'ten. **İl tek başına sonuç vermiyor, ilçe şart.** Sayı BİM + FİLE karışık, marka ayrımı yapılmadı |
| **Migros** | 3.442 | yok | Angular `mat-select`, JSON API yok → Playwright. Panelin `.cdk-overlay-container input`'una yazılır, `mat-option` `get_by_text(exact=True)` ile tıklanır; `text-is()` ve regex filtre çalışmıyor |
| **Starbucks** | 804 | kısmi | 804'ü tek sayfada düz metin. Koordinat yalnız "yol tarifi" düğmesinin `window.open(.../dir/?api=1&destination=lat,lng)` çağrısında — tek tek tetiklemek gerekiyor, otomatikleştirilemedi |
| A101 | — | — | **Çekilemedi**: il/ilçe seçici yok (yalnız IP konumu), Cloudflare koruması |
| ŞOK | — | — | Sitesinde mağaza bulucu sayfası **yok** |

Koordinatı olmayan üçü (BİM, Migros, Starbucks) henüz adaptöre girmedi: ilçesi kaynağın
kendi etiketinden geliyor, o etiketin kayıt defteriyle eşlenmesi ayrı iş.

## OSM neden kullanılamadı

`C:\veri-ham\osm\turkey-latest.osm.pbf` DuckDB spatial ile 103 saniyede taranıyor
(`OSM_CONFIG_FILE` elle yazıldı). Marka kapsaması: BİM %21,6 · Migros %32,8 ·
Starbucks %45,9 · Burger King %41 · **PTT %0,9**. Kapsama gönüllüye bağlı olduğu için
**sayım göstergesi üretilemez**; yalnız alt sınır verir.

## İlk bulgular (2026-09-18)

- Burger King 835 şube / **257 ilçe**; McDonald's 334 şube / **134 ilçe**. BK, McDonald's'ın
  iki katı ilçede var. 973 ilçenin %73'ünde ikisi de yok.
- En çok şube: Ankara Çankaya 50 (30 BK + 20 McDonald's), Antalya Muratpaşa 24,
  İstanbul Pendik 21, Kadıköy 19.
- Kişi başına en yoğun (nüfus ≥50 bin): İzmir Balçova 10.820 kişi/şube, İstanbul Beşiktaş
  12.761, Bakırköy 12.836, Muğla Dalaman 17.776, Bodrum 18.836. Liste iki desenden ibaret:
  üst gelir merkezleri ve turistik kıyı. Migros yoğunluğunda görülen "kayıtlı nüfus gerçek
  talebi göstermiyor" bulgusunun aynısı — `docs/gosterge-notlari.md`'deki kayıtlı nüfus
  uyarısıyla birlikte okunmalı.
- Marka ayrışması: BK'nin tek başına olduğu ilçeler Anadolu ve çeper kentleri (Şahinbey,
  Kocasinan, Haliliye, Diyarbakır Yenişehir, Sancaktepe — her birinde 4-5 BK, hiç
  McDonald's yok). McDonald's'ın tek başına olduğu 8 ilçenin çoğu transit/turist noktası
  (Selçuk 2, Avanos, Pozantı, Aksu). McDonald's merkezde yoğunlaşıyor, BK yayılıyor.

## Çiğ köfte zincirleri (2026-09-18)

Çiğ köftenin **kayıt defteri yok**. TESK esnafı sayıyor, TOBB şirketi; ikisi de çiğköfteciyi
kuaförden ayırmıyor. Rehberler eksik sayıyor (bulurum Türkiye geneli 3.485 diyor, oysa Oses
tek başına 1.670). Ama her zincir franchise satmak için kendi şube listesini yayımlıyor —
yani esnaf sayılamıyor, zincir sayılabiliyor.

| Marka | Şube | Koordinat | Yöntem |
|---|---|---|---|
| **Oses** | 1.670 | %100 | Tüm ülke tek sayfada, `gMaps.locations = [...]` JSON dizisi. İlçe, il, adres, telefon, koordinat. Tek istek |
| **Ziyafet** | 459 | %100 | Bayi haritası **Google My Maps** gömülü; Google robots'u `/maps/d/`'yi açıkça izinli sayıyor, markanın kendi haritası `?mid=<id>&forcekml=1` ile KML iniyor. İl/ilçe alanı yok, koordinat var |
| **Komagene** | **3.814** | %100 | SPA, `gateway.komagene.com.tr`. İki uç nokta sayfanın kendi XHR'ından okundu: `b2c/site/getwebportalilceler` `{"IlId":n}` ve `b2c/site/getsubebilgileri` `{"IlceId":"n"}`. Tarayıcısız çalışıyor, kimlikler markanın kendi kimlikleri (164 = Adana) |

**Dolaşan rakamlar pazarlama.** Bir yapay zekâ özeti Komagene'yi "~3.050", Ziyafet'i "~700"
şube diye verdi; Ziyafet'in kendi sayfası "Ağustos 2026 itibarıyla 57 ilde 455 bayi" diyor.
Depoya yalnızca kendi çektiğimiz girer.

**Bu sayılar markaların sayısıdır, sektörün değil.** `chain_restaurants` göstergesi "kaç
çiğköfteci var" sorusunun cevabı değildir ve markalar önceden toplanmaz.

### Depoya giren sayılar (2026-09-18 anlık görüntüsü)

İlçe sınırına düşürüldükten sonra `chain_restaurants` göstergesindeki hâlleri:

| Marka | Şube | İlçe |
|---|---|---|
| Komagene | 3.805 | 608 |
| Oses | 1.629 | 416 |
| Burger King | 835 | 257 |
| Ziyafet | 459 | 170 |
| McDonald's | 334 | 134 |

Komagene, iki küresel hamburger zincirinin toplamının üç katı şubeye ve iki katından
fazla ilçeye ulaşıyor: 973 ilçenin 608'inde Komagene var, 257'sinde Burger King.

Sınır dışına düşen satırlar atılıyor: kıyı şeridi (Komagene 9, BK 12, McDonald's 1) ve
**yurt dışı şubeler** — Oses 1.670 satırının 33'ünü `Yurtdışı` diye etiketliyor, koordinatları
Avrupa'da. Oses bu yüzden %2,5 kaybediyor, adaptörün %3'lük eşiğine yakın.

## Sektör toplamları — kazımanın ölçütü

Ortakalan'ın 265 market zincirini kapsayan "Perakende Raporu 2025"inden (CNBC-e, 20.02.2025):
organize gıda perakendesinde toplam market sayısı 2024 başında **52.259**, yıl sonunda
**55.737**; indirim marketleri 40.530 → **42.782**; ulusal ölçekli zincirlerin şube sayısı
%15 artışla **1.088**.

Bu sayılar depoya **girmez** (rapor ücretli, ikinci elden alıntı) ama kazıdığımız marka
sayılarının ne kadarını yakaladığını ölçmek için tutulur — BDDK'nın banka şubesi sayısını
bulurum'un karşısına koyduğumuz gibi. Aynı haberdeki "7 yılda 25 bin yeni market" rakamı
projeksiyondur, `projeksiyon-alinmaz` kuralı gereği not bile düşülmez, burada yalnızca
gerçekleşmiş sayılarla karıştırılmasın diye anılıyor.

## 2026-09-19 gecesi bakılan, alınamayanlar

| Marka | Durum |
|---|---|
| **Domino's** | Çözüldü, çekici yazıldı (`scripts/fetch_dominos.py`). 26 ilde 311 şube indi, sonra **HTTP 429**; site bir süre IP'yi tümden kapattı. `--devam` ile kaldığı yerden sürer |
| **Gratis** | İl sayfaları var (`/magazalarimiz/<il>`) ama mağaza listesi ne HTML'de ne hidrasyon sonrası görünüyor; sayfa gövdesi 6.800 karakter ve tamamı menü |
| **Hakmar Express** | Doğru alan adı `hakmarexpress.com.tr` (hakmar.com.tr başka bir şirket). `/magazalar` sayfası gömülü JSON'da mağaza taşıyor — ad, adres, il, **ilçe**, koordinat — ama tek seferde yalnız 25 kayıt (İstanbul). Sayfalama/şehir filtresi çözülmedi. Sitenin kendi başlığı **816 mağaza** diyor |
| **Watsons** | Mağaza bulucusu tarayıcıda çalışıyor, düz istekte **403** |
| **Teknosa** | Doğru adres `/magaza-bul`, tarayıcıda çalışıyor, düz istekte **403** (Cloudflare) |

**Hız sınırı dersi.** Üç sitede üç farklı eşik çıktı: Komagene 0,3 saniyeyle 1.000+ istekte
hiç şikâyet etmedi, PTT 0,4 saniyeyle 973 istekte 429 vermeye başladı, Domino's 0,3 saniyeyle
26 ilde IP'yi kapattı. Eşik önceden bilinemiyor, o yüzden **her çekiciye baştan `--devam`
modu** konuyor: yarıda kalan çekimi baştan almak, sınırı aşmanın en hızlı yolu.

## Perakende zincirleri (2026-09-19)

Tek sayfada tüm listeyi veren sekiz marka bulundu; `scripts/fetch_marketler.py` hepsini
tek istekle çekiyor. Verinin nerede durduğu her markada farklı, o yüzden marka başına
ayrı ayrıştırıcı var.

| Marka | Mağaza | Koordinat | Verinin yeri |
|---|---|---|---|
| **Gratis** | 899 | 899 | Next.js yükünde **çift kaçışlı** JSON (`\"storeId\"`) |
| **Madame Coco** | 719 | 709 | `{"count":719,...,"results":[…]}`, ilçe `township.name` |
| **Rossmann** | 211 | 211 | `var locations = [...]`; ilçe alanının adı `distinct` |
| Happy Center | 194 | — | kart başlığı `İlçe / Mağaza adı`, **il yok** |
| Bizim Toptan | 172 | — | `<li data-city="34" data-county="1447" data-search="istanbul, zeytinburnu">` |
| **Karaca** | 171 | 171 | kart başına JSON; **geçersiz JSON** (`mail` alanında kaçışsız `<a href="…">`), alan alan okunuyor |
| Onur Market | 154 | — | adres kuyruğunda `İlçe / İl` |
| **Vatan Bilgisayar** | 150 | 150 | `data-x`/`data-y`, **virgüllü ondalık** (`36,993773`) |

**Gratis'te bir ders var.** Önce "mağaza listesi hiç yüklenmiyor" diye kapatılmıştı: tarayıcıda
liste görünmüyordu ve ham gövdede `latitude` araması boş dönüyordu. Oysa 2.430 adres
sayfadaydı — veri, içinde her tırnağı ters bölüyle kaçırılmış bir JSON metniydi. Sayfanın
*görüntüsüne* bakıp "veri yok" demek yetmiyor; ham gövdede alan adı aranmalı, hem de
kaçışlı biçimiyle.

### Depoya giren: `chain_stores`

Koordinatı olan beş marka `chain_stores` göstergesine girdi (1.263 satır, ilçe + il):

| Marka | Mağaza | İlçe |
|---|---|---|
| Gratis | 897 | 312 |
| Madame Coco | 660 | 310 |
| Rossmann | 209 | 101 |
| Karaca | 167 | 111 |
| Vatan Bilgisayar | 150 | 113 |

Zincir restoranlardan ayrı bir gösterge: kozmetik mağazası ile hamburgerci farklı sorulara
cevap verir, toplamı bir şey ifade etmez.

**Yurt dışı mağazalar artık ayrı ayıklanıyor.** Madame Coco Moskova, Almatı, Beyrut,
Brüksel ve Astana'yı Adana ile aynı dosyada listeliyor — 719 mağazanın 59'u yurt dışı.
Bunlar hiçbir ilçeye düşmediği için eski kural %3'lük eşiği aştırıp yüklemeyi çökertiyordu.
Çözüm eşiği yükseltmek değil: Türkiye'nin sınırlayıcı kutusu (`TURKEY`) dışındaki nokta
**yurt dışı** sayılıp paydadan çıkarılıyor. Eşik, sınır dosyasının bozulmasını yakalamak
için var; Kazakistan'daki bir mağaza sınır dosyası hakkında hiçbir şey söylemez.

**Koordinatsız üçü alınmadı** (Happy Center, Bizim Toptan, Onur Market). İlçeleri
kaynağın kendi etiketinden gelir, kayıt defteriyle eşlenmesi ayrı iş; Happy Center ayrıca
il bilgisi hiç vermiyor. Ham verileri `C:\veri-ham\marketler` altında bekliyor.

## Kahve zincirleri (2026-09-19)

| Marka | Şube | Yurt dışı | Depoya giren | İlçe |
|---|---|---|---|---|
| **Starbucks** | 804 | — | 795 | 184 |
| **EspressoLab** | 421 | **102** | 310 | 119 |

İkisi de Gratis'le aynı kalıbı kullanıyor: Next.js yükünde çift kaçışlı JSON. Starbucks'ta
ilçe alanının adı `county` ve koordinat bir düzey aşağıda, `"location":{"lon":…,"lat":…}`
biçiminde — üstelik tırnaksız sayı olarak, diğer bütün alanların aksine.

Starbucks daha önceki bir oturumda "804 kayıt, koordinat yalnız yol tarifi düğmesinde,
otomatikleştirilemedi" diye bırakılmıştı. Doğru sayfada koordinat hazır duruyor; aynı
sayı, bu kez tam.

**EspressoLab'ın 421 şubesinin 102'si yurt dışında** — Kazablanka 14, Kahire 12, Amman 6,
Bavyera 6, Dubai 5. Yurt içi 319 şubenin 310'u ilçeye düştü. Yurt dışı ayıklaması olmasa
bu marka %26 kayıpla eşiği aşar ve yüklemeyi çökertirdi.

## ŞOK Market (2026-09-19)

11.274 mağaza çekildi, 11.220'si ilçeye düştü — **809 ilçe**, yani Türkiye'nin 973 ilçesinin
%83'ünde ŞOK var. Depodaki en geniş zincir katmanı.

Önceki bir oturumda "ŞOK'un sitesinde mağaza bulucu sayfası yok" diye kapatılmıştı; o
bakılan yer alışveriş sitesiydi. Bulucu kurumsal sitede ve iki düz GET ucu var:
`kurumsal.sokmarket.com.tr/ajax/servis/ilceler?city=…` ve `…/magazalarimiz?city=…&district=…`.

**Koordinat alanlarının adları ters.** Gemlik'teki bir mağaza `"lng":"40,4714","ltd":"29,0999"`
diye geliyor — 40,47 enlem, 29,10 boylam. Adına güvenilseydi bütün ŞOK'lar Somali açıklarına
düşer ve nokta-poligon testi hepsini sessizce elerdi. Alanlar konuma göre okunuyor ve çekici
sonucun Türkiye kutusuna düştüğünü doğruluyor.

Tek tek bozuk koordinatlar da var — ŞOK ÇANKAYA PARK 83,8 boylamında (Çin) kayıtlı. Bunlar
düşürülmüyor, koordinatı boşaltılıyor: mağaza gerçek ve sayıma girmeli, yanlış olan yalnız
koordinatı. Oran %5'i aşarsa çekici hata veriyor — sistematik bir alan takası olsaydı
*bütün* satırlar dışarı düşerdi.

## robots kararı yol bazında verilir (2026-09-19 düzeltmesi)

Daha önceki bir tarama Teknosa, MediaMarkt, Mavi, Gratis, Vatan ve Watsons'ı **"YASAK"**
diye işaretlemiş ve altı zincir bu yüzden hiç denenmemişti. Yanlıştı: o tarama robots
dosyasında `Disallow` satırı görünce siteyi kapalı saymış, oysa o satırlar sepet, hesap ve
arama yolları için.

Doğrusu `urllib.robotparser` ile **istenecek yol** için sormaktır:

| Zincir | `/magazalarimiz` ClaudeBot | genel kural |
|---|---|---|
| Teknosa, MediaMarkt, Mavi, Gratis | izinli | izinli |
| Koçtaş, Bauhaus, Tekzen, ŞOK | izinli | izinli |
| Kahve Dünyası, A101 | izinli | izinli |

Gerçekten kapalı olanlar: **FLO** (ClaudeBot adıyla yazılmış, `Disallow: /`) ve robots'a
erişim bile vermeyen (403) **sahibinden, CarrefourSA, Watsons, Boyner, DeFacto, Decathlon,
BP**. Bir de **arabam.com**: site açık ama `/ikinci-el/arama*` açıkça yasak, yani ilan
sayımı yapılamaz.

## Petrol Ofisi (2026-09-19)

2.631 istasyon, 81 il, 756 ilçe — `scripts/fetch_petrol_ofisi.py`, tek istek.
Sayfa listeyi üç kez taşıyor: `stations` düz liste, `cities` ve `districts` aynı listenin
açılır kutular için gruplanmışı. Bir alanı sayfa genelinde saymak bu yüzden üçe katlıyor
(`CityName` 7.893 kez geçiyor, istasyon 2.631). Çekici düz listeyi okuyor ve il
gruplamasının toplamıyla karşılaştırıyor; tutmazsa duruyor.

**A101'in tam listesi yok.** `/magazalarimiz` 404; çalışan sayfa `/en-yakin-magazalar` ve
yalnız tarayıcının konumuna en yakın mağazaları veriyor. Tamamı için koordinat ızgarası
taraması gerekir — ayrı bir iş.


## A101: konum taraması gerekiyor (kurulmadı)

`/en-yakin-magazalar` sayfası listeyi **tarayıcının konum iznine göre** veriyor. URL'ye
`?lat=&lng=` yazmak işe yaramıyor: sayfa parametreyi kendi yol durumuna yazıyor ama
mağazaları yine tarayıcının verdiği konuma göre çiziyor (Üsküdar'dan sorulduğunda hep
Üsküdar mağazaları geldi). Sunucu tarafında sayfayı çekmek de boş dönüyor — 5,6 KB, tek
bir adres yok.

Tam listenin tek yolu tarayıcıda konumu sahte konumlandırıp ızgara taraması yapmak:
973 ilçe merkezinin koordinatıyla (kapsam.json'daki sınır kutularının ortası) tek tek
sormak, dönen mağazaları kimliğe göre tekilleştirmek. Yaklaşık 13.000 mağaza için
973 sorgu yeter gibi görünüyor ama kapsama boşluğu kalırsa ızgara sıklaştırılmalı.

Bu iş **kurulmadı**: tarayıcı otomasyonu ve konum sahteleme gerektiriyor, yarım kurulmuş
bir tarayıcı sessizce eksik veri toplar. Ayrı bir oturumda, doğrulamasıyla birlikte
yapılmalı — kontrol ölçütü: BİM'in 13.057 mağazasına yakın bir sayı ve 81 ilin tamamı.

### A101: uç nokta bulundu (2026-09-20)

Yukarıdaki "konum taraması gerekiyor" notu yanlış yere bakıyordu. Sayfa mağazaları kendi
içinde tutmuyor, ayrı bir konağa soruyor ve **konumu argüman olarak** geçiyor:

    GET rio.a101.com.tr/dbmk89vnr/CALL/StoreContentManager/nearestStores/default
        ?__culture=tr-TR&__platform=web&__isbase64=true
        &data=<base64 of {"geoHash":"<9 karakter geohash>"}>

Konum iki kez kodlanmış — önce geohash, sonra base64 — bu yüzden `?lat=&lng=` denemesinde
görünmüyordu. Tarayıcı konumu sahtelemeye gerek yok; `rio` konağı `www` gibi Cloudflare
sayfa korumasının arkasında değil. Yanıt tam kayıt veriyor: `id, name, city, townShip,
plateCode, address, lat, lng, distance`.

**Yarıçap yok, sayfa var: her zaman en yakın 20.** Kırıkkale'nin boş bir noktasından
sorulduğunda da 20 geliyor, en uzağı 49 km. Yani bir sorgu yalnız 20'nci mağazanın
mesafesi kadar yeri ispatlar. Çekici (`scripts/fetch_a101.py`) bu yüzden sabit ızgara
değil **dörtlü ağaç**: hücrenin merkezinden sorar, kanıtlanan yarıçap hücrenin yarı
köşegenini kapsamıyorsa hücreyi dörde böler. Kadıköy derinleşir, Tunceli derinleşmez —
ve tarama kendi kapsamasını kendi bildirir.

**Hız sınırı sert.** ~30 sorgudan sonra IP hem tarayıcıda hem Python'da `403`'e düştü;
Domino's deseninin aynısı. Önceden istenmiş bir geohash kenar önbellekten döndüğü için
engel bir süre "bazı sorgular çalışıyor" gibi görünüyor — bu yanıltıcı, yeni koordinat
denenmeden açık sayılmamalı. Tarama bu yüzden 1,5 sn gecikmeyle ve engelde 20 dk bekleyip
`--devam` ile süren bir sürücüyle çalıştırılıyor.

Doğrulama ölçütü: BİM 13.057, ŞOK 11.220. A101 bu büyüklüğe ve 81 ile ulaşmazsa çekim
eksiktir; çekici 81 ilden azını görürse uyarı basar.

## BİM ve Migros depoya girdi (2026-09-20)

İkisi de şube listesi değil **ilçe başına sayı** yayımlıyor, koordinat vermiyor. Bu yüzden
ilçe kaynağın kendi etiketinden geliyor ve o etiket kayıt defterine üç kuralla bağlanıyor:

1. **`Merkez` → ilin kendi adı.** Kayıt defterinde `Merkez` diye bir ilçe yok; Bolu'nun
   merkez ilçesi `Bolu`. Kural güvenli, çünkü adıyla aynı ilçesi olmayan 30 il tam olarak
   30 büyükşehir ve onlarda da `Merkez` geçmiyor.
2. **Dört il takma adı**: `Afyon`, `Agri`, `İçel` (Mersin'in 2002 öncesi adı), `K.Maraş`.
3. **On ilçe yazımı**: şapkanın düştüğü dördü (`Kâhta`, `Lâpseki`, `Devrekâni`, `Lâçin`)
   ve boşluğun kapandığı altısı (`Gazi Osmanpaşa`, `Marmara Ereğlisi`, `Oniki Şubat`,
   `19 Mayıs`, `Mustafakemalpaşa`, `Bahşili`).

Üçü de tek tek yazıldı, genel bir "aksanı at, küçült, boşlukları sil" normalleştirmesi
yapılmadı: o yol iki ayrı yeri sessizce birleştirir, oysa buradaki fark kapalı ve sayılı.

**Eşleşmeyen ad yüklemeyi durduruyor.** Koordinat sınıra düşmediğinde görünür bir kayıp
olur, sayılır ve eşiği aşarsa hata verir; ad tutmadığında ise kayıp **görünmez** — ilçe
"BİM yok" diye çıkar ve bu ülkeye dair bir bilgi gibi okunur. O yüzden buradaki ölçüt
%95 değil, **tamamı**: 13.057 BİM ve 3.442 Migros'un hepsi yerine oturuyor.

| Marka | Mağaza | İlçe |
|---|---|---|
| BİM (+FİLE) | 13.057 | **916** |
| ŞOK | 11.220 | 809 |
| Migros | 3.442 | 528 |

BİM 973 ilçenin **916'sında** var — depodaki en geniş zincir. ŞOK'u 107 ilçede geçiyor.

**BİM sayısı FİLE'yi de içeriyor.** Bulucuda fırın için kutu var, marka için yok; ikisi
ayrılamıyor ve ayrıldığı iddia edilmiyor.

## Tarım Kredi Kooperatif Marketleri (2026-09-20)

**2.348 mağaza, 640 ilçe**, hepsi koordinatlı ve hepsi Türkiye kutusunda.

Kooperatifin kendi sitesinde (tarimkredi.org.tr) mağaza bulucu yok — orası ana kuruluşun
sitesi ve yalnız iki genel müdürlük adresi taşıyor. Market zinciri ayrı alan adında ve
listeyi bütün hâlde veriyor:

    GET tkkoop.com.tr/json/magazalar?sehir=<il adı>

**Boş filtre hata değil, tüm ülke.** Sayfadaki açılır kutu hep tek il sorduğu için adres
il istiyormuş gibi duruyor; `?sehir=` boş bırakıldığında 2.348 mağazanın tamamı tek
istekte geliyor. İl yerine plaka yazmak (`?sehir=6`) **HTTP 500** veriyor — bu bozuk
istektir, "06'da mağaza yok" değil.

İlçe kaynağın etiketinden değil koordinattan alınıyor: ad (`ANKARA - AHİMESUT`) markanın
kendi etiketi, adres ise serbest metin ve ilçe içine gömülü — art arda iki Ankara satırı
`ETİMESGUT / ANKARA` ve `KEÇİÖEREN/ ANKARA` yazıyor, ikincisi hem yanlış hem bitişik.

Dolaşan rakam yine eski: bir haber "1.665 mağaza" diyor, çektiğimiz 2.348.

### Zincirlerin ilçe kapsaması (2026-09-20 itibarıyla depoda)

| Marka | Mağaza | İlçe | 973 ilçenin |
|---|---|---|---|
| BİM (+FİLE) | 13.057 | 916 | %94 |
| ŞOK | 11.220 | 809 | %83 |
| Komagene | 3.805 | 608 | %62 |
| Migros | 3.442 | 528 | %54 |
| **Tarım Kredi** | **2.348** | **640** | **%66** |

Tarım Kredi mağaza sayısında Migros'un altında ama **ilçe sayısında üstünde**: 2.348
mağazayla 640 ilçeye giriyor, Migros 3.442 mağazayla 528'e. Kooperatif yapısının kırsala
yayıldığı, özel zincirin kente yığıldığı buradan okunuyor — ama okunmadan önce mağaza
başına düşen nüfusa bakılmalı, `docs/gosterge-notlari.md`'deki kayıtlı nüfus uyarısıyla.

## Teknoloji ve beyaz eşya (2026-09-20)

**Vestel girdi: 1.158 satış noktası, 489 ilçe** — `scripts/fetch_vestel.py`. Ayrıca
**359 yetkili servis (79 il)** ham depoda; mağazayla aynı sayıya katılmıyor, çamaşır
makinesi satan dükkânla onu tamir eden atölye aynı şey değil.

Vestel'in ağı diğerlerinden farklı: şirketin kendi mağazaları değil, **bayiler**. Tabela
Vestel, arkadaki şirket yerel — Ankara'daki ilk kayıt `GÖKTAŞLAR İÇ DIŞ TİCARET ...
KIZLARPINARI` diye geçiyor. Ad kaynağın yazdığı gibi bırakılıyor.

Uç nokta sayfanın kendi `storeAndServices({...})` çağrısında yazılı:
`POST /lookup/offlinestores` gövde `cityID=<plaka>&districtID=`. Boş ilçe **ilin tamamı**
demek; "tüm iller" değeri yok, `cityID=0` boş liste veriyor — bu geçerli bir soruya boş
cevap, hata değil. 81 istek.

### robots kararı yol bazında değil, artık dosya bazında da verilmeli

2026-09-19'daki düzeltme "Teknosa, MediaMarkt, Gratis izinli" demişti. Bugün bakıldığında
**Teknosa'nın robots.txt'i HTTP 403 veriyor** — dosyanın kendisi okunamıyor. Standart
gereği okunamayan robots "tamamı yasak" sayılır, o yüzden Teknosa'ya gidilmedi. Mağaza
bulucusunun adresi de değişmiş: `/magazalarimiz` değil `/magaza-bul`, ve o yol açıkça
ClaudeBot'a kapalı.

| Marka | robots.txt | Durum |
|---|---|---|
| **Vestel** | 200, `/lookup/` serbest | **çekildi: 1.158 nokta + 359 servis** |
| Koçtaş | 200, serbest | uç nokta bulundu (`/store-finder/findPOSByCity`), çekilmedi |
| MediaMarkt | 200, serbest | sayfa kabuk, uç nokta aranacak |
| Bauhaus | 200 ama sayfa 403 | mağaza sayfası Cloudflare'de |
| Tekzen | 200, serbest | sayfa kabuk, uç nokta aranacak |
| Teknosa | **403 (okunamıyor)** | kapalı sayıldı |
| **Arçelik, Beko, Altus** | **403** | üçü de aynı grup, üçü de kapalı |
| **Bosch, Siemens, Profilo** | **403** | BSH grubunun üçü de kapalı |
| Watsons | **403** | kapalı |

Beyaz eşyada tek açık kapı Vestel çıktı. Arçelik ve BSH (Bosch/Siemens/Profilo) grupları
robots dosyasını bile vermiyor; bayi ağları bu yüzden sayılamıyor ve "bayisi yok" diye
değil, **bakılamadı** diye kaydediliyor.

## Koçtaş (2026-09-20) — ve iki sahte alan

**134 mağaza, 108 ilçe, 38 il.** 55'i büyük format (`KOCTAS_STORE`), 79'u mahalle
formatı (`KOCTAS_FIX`). Uç nokta sayfanın formunun kendi hedefi:
`GET /store-finder/findPOSByCity?addressCity=<plaka>`. Parametrenin adı `city` değil
`addressCity`; `?city=06` **HTTP 400** veriyor — reddedilmiş istek, boş il değil.

Bu kaynakta bilgi veriyormuş gibi duran ama vermeyen iki alan var:

**`storeContent` kapanış bildirmiyor.** 134 mağazanın 58'inde
`"Mağazamız geçici olarak kapalıdır."` yazıyor — Ankara Eryaman, Ankamall ve Panora
dahil, yani zincirin amiral mağazaları. Hepsinde `storeOpenStatus: OPEN`. Cümle bir
içerik alanına düşmüş kalıp metin; kapanış işareti sayılsaydı zincirin **%43'ü kapalı**
görünecekti. Okunan alan `storeOpenStatus`.

**`addressTown` ilçeyi yanlış veriyor.** Yenimahalle'deki Ankamall AVM mağazası
`HAMAMÖZÜ` diye kayıtlı — üstelik ilçe kodu `K0503`, yani Amasya'nın plakası. Çankaya'daki
Gordion AVM `HAYMANA` yazıyor. Alan dosyaya kaynaktaki hâliyle yazılıyor ama ilçe, her
zincirde olduğu gibi, koordinattan belirleniyor. Bu tabloyu adres etiketiyle kuran biri
Hamamözü'ne AVM mağazası açardı.

## MediaMarkt: robots açık, kapı kapalı (2026-09-20)

robots.txt izin veriyor ve mağaza listesini çeken sorgunun adı bile açıkta —
`query AllStores { stores(states: [ACTIVE, PARTIALLY_ACTIVE]) {...} }`, sayfanın kendi
`StoreFinder` paketinin içinde yazılı. Ama `/api/v1/graphql` uygulamanın kendi kimliğini
istiyor: aynı sorgu tarayıcıdan gönderildiğinde de **403**. Sayfa mağazaları sunucuda
basmıyor, yani HTML'de de yok. Kapalı sayıldı — "mağazası yok" değil, **alınamadı**.

## Eczaneler: markanın değil mesleğin sayımı (2026-09-20)

**31.451 eczane, 81 il, 967 ilçe.** Depodaki ilk *sayım* niteliğindeki dükkân göstergesi:
eczane açmak ruhsat gerektiriyor ve TİTCK ruhsat kaydını tutuyor. Bu yüzden `pharmacies`,
"bu ilçede kaç eczane var" sorusuna `population`'ın "kaç kişi var"a cevap verdiği gibi
cevap veriyor; `chain_stores`'daki hiçbir satır böyle okunamaz.

Kaynak TEB değil. TEB'in sitesinde istatistik yok, `tebeczane.net` şifreli bir doküman
sistemi. Kayıt, ruhsatı veren kurumda: `ebs.titck.gov.tr`, Kendo ızgarası,
`POST /Ecza/Eczane/grdEczaneListesi_Read`, il zorunlu.

**`pageSize=5000` istendiğinde sunucu `{"Total":0,"Data":[]}` dönüyor.** HTTP 200, hata
yok. İlk çekim bu yüzden 80 il ve 25.605 eczane yazdı: **İstanbul'un 5.846 eczanesi
"eczane yok" olarak kaydedilmişti.** `pageSize=1000` ile aynı il sorunsuz cevap veriyor.
Çekici artık bin bin sayfalıyor ve her ilin sayfaları o ilin kendi `Total`'ine eşit
değilse duruyor.

**`id` alanı kimlik değil**, ızgaranın sayfa içi satır numarası — dört sayfada okunan bir
ilde dört tane `1` var. Tekilleştirme yapılmıyor; sayım satır sayısıdır ve eksik/çift
olmadığının güvencesi `Total` karşılaştırmasıdır.

### Üç kaynak, aynı on istisna

Eczane kaydının ilçe adları, BİM ve Migros'unkiyle **birebir aynı üç sapmayı** gösteriyor:
`Merkez`, dört il takma adı, on ilçe yazımı. Tek bir yeni istisna çıkmadı. Ortak hiçbir
yazılımı, ortak hiçbir sağlayıcısı olmayan iki zincir bulucusu ile bir devlet kaydı aynı
on yerde kayıt defterinden ayrılıyor — bu yüzden eşleme artık adaptörlerde değil, kayıt
defterinin yanında: `veriatlas.areas.resolve_district`.
