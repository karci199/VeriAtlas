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
