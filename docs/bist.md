# Borsa İstanbul — ne var, ne alındı (2026-09-26)

Karar: **şimdilik alınmadı.** Kullanıcıyla bakıldı, "burayı geçelim" denildi. İl eksenine
katkısı küçük; asıl değer Türkiye geneli finans serisi. Aşağıdaki not, dönülürse
yeniden keşif yapılmasın diye.

Depoda BIST'e yakın tek gösterge MKK/VAP'tan `investor_portfolio_value` (il, 2005-2025).

## Açık dosyalar (www.borsaistanbul.com, robots serbest)

Dosya adresleri `https://www.borsaistanbul.com/files/DataFilePaths.zip` içindeki
`VerilerDosyaIsimleri.xlsx`'te; kopyası `C:\veri-ham\bist\DataFilePaths`.

| Dosya | İçerik | Durum |
|---|---|---|
| `/datum/toppiydeg.zip` | pay piyasası piyasa değeri, pazar bazında, TL ve $ | aylık 1986-01 → **2014-03'te donmuş** |
| `/datum/tophacmiksoz.zip` | işlem hacmi, miktar, sözleşme | aynı, 2014-03'te biter |
| `/datum/islgorsirsay.zip` | işlem gören şirket sayısı, pazara giren/çıkan şirket | yıllık/aylık, 2014-03'te biter |
| `/datum/hisse_endeks_ds.csv` | her payın bulunduğu endeksler, **güncel** (indirme günü) | 14 şehir endeksi (Adana, Ankara, Antalya, Aydın, Balıkesir, Bursa, Denizli, İstanbul, İzmir, Kayseri, Kocaeli, Konya, Manisa, Tekirdağ) → il başına borsa şirketi; yalnız bugünün kesiti, mali sektör ve perakende kapsam dışı |
| `/datum/IslemSirasiKapananSirketler.xls` | kotasyondan kalıcı çıkan şirketler | liste |
| `/datum/PayEndeksleri.zip`, TLREF | endeks ve TLREF günlük | güncel gün |

2014-03 donması BISTECH geçişiyle (30.11.2015) ilgili görünüyor; sonrası açık dosyada yok.
Ham: `C:\veri-ham\bist\`.

## DataStore (datastore.borsaistanbul.com)

SPA; ürün kataloğu `GET /api/category` ve `GET /api/product-type?category=<PPB|KMTPB|BAPB|EVB|VIPB|HAVB>`
ile anahtarsız okunuyor. Ürünlerin çoğu **ücretsiz** (fiyat 0 ya da %100 indirim);
ücretli olanlar gün içi emir/işlem defteri (850) ve ITCH (1.700). İndirme **üyelik ve
sepet** üzerinden: hesap açma ve sözleşme kabulü kullanıcıya ait, Claude yapmaz.

İşe yarayacak ücretsiz ürünler (günlük → aylık toplanır):

| Kod | Ürün |
|---|---|
| 3180 | Fiyat endeksleri (pay endeksleri), şehir endeksleri dahil |
| 3190 | Birincil halka arzlar (paylar): hasılat, fiyat, **satın alan yatırımcı sayısı** |
| 3152 / 3131 | İşlem hacmi, miktar, sözleşme sayısı |
| 100465 | Değerleme oranları (aylık F/K, PD/DD) |
| 3184 | 2000'den beri BIST 30/50/100 endekslerindeki şirketler |
| 100462 / 100461 | Temettü ödemeleri, sermaye artırımları |
| 3202 / 100580 | Şirket yıllıkları 1998-2008, bilanço ve gelir tabloları 2000-2009 |

Önce EVDS'e bakılmalı: BIST 100 ve piyasa değeri EVDS'te varsa DataStore gerekmez.

## Aynı gün bakılan Ticaret Bakanlığı PDF'leri

`ticaret.gov.tr/istatistikler/bakanlik-istatistikleri/ic-ticaret-ve-tuketici-istatistikleri`
altında tek sayfalık, her dönem aynı adrese yazılan PDF'ler. robots.txt 200 koduyla bir
"Internal Server Error" sayfası dönüyor: izin durumu **bilinmiyor**, toplu tarama yapılmadı.

| PDF | Durum |
|---|---|
| MERSİS Verileri | **depoda** (`mersis_active_businesses`, `mersis_business_flows`; Wayback kopyalarıyla) |
| Oda ve Borsa Sayıları | bakılmadı |
| Lisanslı Depoculuk Verileri | bakılmadı |
| Taşınır Rehin Sicil Sistemi (TARES) | bakılmadı |
| Sektörel Ticaret Verileri | bakılmadı |
| Elektronik Genel Kurul Verileri | ilgisiz |
