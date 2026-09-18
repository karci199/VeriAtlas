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
