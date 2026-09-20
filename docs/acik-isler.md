# Açık işler (2026-09-19, gece güncel)

Çekilip de alınamayan ya da yarım kalanlar, tahmini zorlukla. Yeni oturumda buradan devam.
Keşfedilmiş ama hiç başlanmamış kaynaklar `kaynak-envanteri.md`'de.

## Bu oturumda depoya girenler (2026-09-16/17)

| Kaynak | Gösterge | Kapsam |
|---|---|---|
| Sağlık Bakanlığı yıllığı | `moh_*` 20 gösterge: hastane, yatak, yoğun bakım, müracaat, ameliyat, doluluk, personel, 112 | il, 2012-2016 + 2018-2024 |
| TOBB | `tobb_foreign_*`: yabancı ortaklı kurulan şirket, sermaye, yabancı payı | il × anonim/limited, 2010-2025 |
| TİM | `tim_exports` il ihracatı | il, 2004-2025 |
| İŞKUR | `iskur_*`: başvuru, açık iş, yerleştirme, kayıtlı işgücü/işsiz/iş arayan | il × cinsiyet, 2003-2025 |
| Kültür Turizm | `ktb_*`: geliş, geceleme (il+ilçe), ortalama kalış, doluluk | il 2003-2022 (seçili yıllar), ilçe 2017-2022 |

Web export: 2026-09-17 tam; 8 dosyanın boş olması hata değil (yalnız ilçe düzeyi, satırlar `*-district.csv.gz`'de); MEDAS girişim, bitkisel/hayvansal değer ve EPDK bayiye teslim dahil.

## Yarım kalan çekimler

| Kaynak | Eksik | Neden | Zorluk |
|---|---|---|---|
| ~~İŞKUR~~ | ~~2003-2011~~ | 2026-09-17 yüklendi | — |
| ~~TİM~~ | ~~2004-2009~~ | 2026-09-17 yüklendi | — |
| TİM | ~~il × sektör 2013-2025~~, ~~il × ülke 2013-2025~~ yüklendi 2026-09-17 (`tim_exports_by_sector`, `tim_exports_by_country`); kalan: 2004-2012 (farklı sektör sınıflaması, 2012 dosyası eksik satırlı) | `tim_sectors.py`, `tim_countries.py` | büyük |
| ~~Kültür Turizm~~ | 2026-09-17 kapandı: Bakanlık belgeli 1996, 2000-2021; belediye 2000, 2002-2006, 2008-2022. Kaynakta kullanılamaz: 1997 (il başlıkları kaymış), 1998 (genel toplamı 277 bin yerli eksik), 1999 (genel toplam yok, sayfa geçişinde Ankara başlığı kayıp) | `src/veriatlas/adapters/ktb.py` | — |
| ~~Kültür Turizm~~ | ~~ilçe düzeyi 2017 öncesi~~ | 2026-09-17: kaynak hatası değil, '-' satırlarını atan okuyucuydu; çoğu yıl açıldı | — |
| ~~Sağlık yıllığı 2017~~ | 2026-09-17 yüklendi (kelime konumu + 2018 satır sırası); 2011 il tablosu basmıyor | — |
| ~~Sağlık yıllığı~~ | ~~2010~~ | 2026-09-17 kapandı: PDF indi, il tablosu basmıyor (2011 gibi yalnız bölge grafiği) | — |
| ~~BTK~~ | 2026-09-17 kapandı (kullanıcı kararı): "Gizli — kurum içi" damgalı sayfalar okunmuyor; pazar payı ve AB karşılaştırma tabloları alınmadı | `docs/btk.md` | — |
| EPDK | ~~doğalgaz il tüketimi 2025~~ yüklendi 2026-09-17 (2015-2016 zaten vardı); 2014 yalnız il toplamı (kırılımsız, alınmadı); ~~akaryakıt 2012-2014~~ bayiye teslim (ton, il toplamı) yüklendi 2026-09-17; ~~akaryakıt 2011~~ (Tablo 3.18, ton) 2026-09-17 bayiye teslim serisine eklendi, 2010 raporu il tablosu basmıyor; ürün kırılımı; 2024-2026 aylık kurulu güç | `docs/epdk.md` | orta |
| KGM | kaza özeti PDF tabloları, Trafik ve Ulaşım Bilgileri | `docs/kgm.md` | zor |
| ~~MGM~~ | ~~ilçe iklim normalleri~~ | 2026-09-17 kapandı: MGM yalnız il merkezi istasyonunu yayımlıyor (10 ad biçimi denendi, hepsi boş); ilçe istasyonları yalnız MEVBİS'te (hesap) | — |
| SGK | 2026-09-17 yeniden sayıldı: ulusal tablolarda 2013-2025 açık iş yok. Atlanan: 2010-2012 iş kazası × meslek 4 tablo ve 2013 Tablo 3.8 (başlıkta konu satırı yok, meslekler ISCO-88; yalnız Türkiye, üç yıl — değmez, alınmadı); 2019 Tablo 3.1.17 ve 3.1.21 (kaynak kendi toplamını tutmuyor); çalışma süresi 2022+ (kaynak bozuk, bilerek) | `docs/sgk.md` | kapandı |
| ~~Seçim~~ | ~~yurt dışı seçmen profili~~ | 2026-09-17 kapandı: 1.662 rapor inmişti (çekici 20dfb32'de düzeltilmiş), özet `docs/vaka-secim-disari.md` §4 | — |

## Keşfedildi, başlanmadı (2026-09-17 akşam güncel)

| Kaynak | Ne | Zorluk |
|---|---|---|
| ~~Muhasebat~~ | il genel bütçe gelirleri 2004-2025 yüklendi (`budget_revenue_by_province`) | — |
| ~~BDDK FinTürk~~ | 6 tablo × 7 banka grubu 2007-2025 yüklendi (`bank_group_*`, 545 bin satır) | — |
| ~~VAP (MKK)~~ | il portföy değeri 2005-2025 yüklendi (`investor_portfolio_value`); yatırımcı sayısı panoda yalnız ilk 10 il, alınmadı | — |
| ~~Muhasebat~~ | il merkezi yönetim bütçe geliri ve gideri 2004-2025, mahalli idare bütçe geliri ve gideri 2006-2025 yüklendi (`central_budget_*_by_province`, `local_budget_*_by_province`, 70 bin satır); gideri ekonomik ve fonksiyonel sınıflandırmayla | — |
| OECD bölgesel (SDMX) | ~~keşif ve ilk çekim yapıldı~~ 2026-09-17: `scripts/fetch_oecd_tl3.py`, ham veri `C:\veri-ham\oecd_tl3`. Yüklendi: dış ticaret (2002-2023, ihracat+ithalat), sıcaklık/yağış/iklim gün sayıları (1981-2024), derece-gün (1981-2023). **Diskte hazır, adaptörü yok:** sağlık hizmeti (hekim/yatak/hemşire/taburcu 2000-2023 — Sağlık Bakanlığı yıllığının 2012 öncesini kapatır), sağlık durumu, sağlık riski (PM2,5 maruziyeti — model, ölçüm değil), patent (PCT 1995-2024), göç akımı (2016-2025), DSD_REG_SOC dosyaları (geniş bant, konut, güvenlik, taşıt, seçmen katılımı — beşi de aynı boyutta indi, aynı üst küme olabilir, ölçüleri ayrıştırılmalı). **TL3'te yok (404):** enerji tüketimi, elektrik üretimi, hava kirliliği, atık, turizm, eğitim, istihdam, gelir, verimlilik, kuraklık, yangın, sel. **Alınmadı:** iklim projeksiyonu ve sera gazı (ilki kullanıcı kararı, ikincisi EDGAR ızgara modeli — ölçüm değil) | — |
| TEDAŞ | istatistikkitabi.tedas.gov.tr, il elektrik dağıtım | **üyelik şart** (2026-09-18): kitap listesi bile girişin arkasında, "Kitap Listesini Görmeniz için Lütfen Giriş Yapın". Hesap açmak kullanıcının kararı |
| ~~TKGM MEGSİS~~ | 2026-09-18 yüklendi: `cadastral_parcels`, `..._by_approval`, `..._by_coordinate` (81 il, 2026-09-14 anlık görüntüsü) | — |
| Adalet Bakanlığı | adalet istatistikleri, il/adliye, PDF | zor |
| ETKB | ulusal enerji denge 1972-2024 (il yok) | kolay |
| Erişilemeyen | GİB (IP engeli), MEB ve İBB (robots.txt), TCDD (403), UYAP (kısıtlı), İzmir/Konya açık veri (robots `/api/`), Wikidata SPARQL (robots) | — |

## Keşif turu 2026-09-18 gece (açık veri portalları, EPİAŞ, ölçüm verisi)

**EPİAŞ Şeffaflık — hesap açıldı, uç noktalar çözüldü.** Katalog `menu/get-menu-tree` ile
alındı: 188 veri sayfası. Kural: **uç nokta adı tahmin edilmeyecek**, WAF 403 veriyor; sayfa
menüden açılır (`a[href]` gerçek adresleri taşır), ağ kaydından adres okunur.

| Ne | Uç nokta | Kırılım | Durum |
|---|---|---|---|
| **İl-ilçe serbest tüketici adedi** | `consumption/data/eligible-consumer-count` | **ilçe × profil abone grubu**, aylık (~4.358 satır/ay) | çekilecek — depodaki ilk ilçe düzeyi enerji göstergesi |
| **Baraj aktif doluluk** | `dams/data/active-fullness` + `dams/data/basin-list` | 87 baraj × havza, günlük, kaynak **DSİ** | çekilecek (yıllık ortalama + yıllık en düşük) |
| Santral listesi | `generation/data/powerplant-list-for-date-range` | 1.830 santral, **il alanı yok** | il üretimi için EPDK lisans listesiyle eşleştirme gerekir |
| Gerçek zamanlı üretim | `generation/data/realtime-generation` | ülke geneli × yakıt | il yok |

**Sıklık kararı (kullanıcı, 2026-09-18):** yıllık; gerekirse aylık ortalama. Çok veri varsa
yıllık. Anlık veri yalnız gerektiğinde tek seferlik.

| Kaynak | Ne | Zorluk | Durum |
|---|---|---|---|
| **ULASAV** (`ulasav.csb.gov.tr`) | Çevre Bakanlığı'nın ulusal toplayıcısı, **4.556 veri seti**, belediye verileri tek çatıda (mahalle bağımsız bölüm, cadde-sokak haritaları, hava kalitesi, en kısa yollar) | orta | robots `/api/` kapalı + `Crawl-Delay: 10`; API 403. Sayfa gezilebilir ama 4.556 seti taramak ~12 saat — hedefli arama yapılacak |
| **Belediye CKAN portalları** | 11 çalışan: Ordu 743, Sakarya 307, İzmir 261, Gaziantep 252, Balıkesir 250, Konya 239, Kadıköy 160, Tuzla 97, Nilüfer 65, Sivas 45, Bursa 49 | kolay | robots hepsinde izinli. Tek şehirlik veri — K4 dışı, `ozel-analiz-kalibi` kapsamı |
| **Konya mahalle-cadde-sokak** | resmî numarataj listesi, 59.960 kayıt, ilçe × mahalle × CSBM, 2023/2024/2025 | kolay | CKAN'dan tek CSV ile iniyor; Tuzla ve Kadıköy'de de CSBM listesi var |
| **Ookla Speedtest açık veri** | ölçülmüş sabit/mobil internet hızı, çeyreklik karo (~600 m), S3'te parquet, anahtarsız | kolay | ham depoda 2022Q4 + 2024Q4 (`C:/veri-ham/ookla`); BTK'nın *vaat edilen* hızının karşısına *ölçülen* hızı koyar |
| **OSM Türkiye** | 112 mn öge; sokak adları, arazi örtüsü, POI | orta | ham depoda (`C:/veri-ham/osm`, md5 OK). DuckDB spatial pbf'i doğrudan okuyor. **Sayım için kullanılamaz** (kapsama gönüllüye bağlı), pay/uzunluk göstergeleri için uygun |
| **TÜİK isim portalı** | il × yıl × cinsiyet × ad, ilk 30 ad | kolay | `POST nip.tuik.gov.tr/Home/IlYilToplamIsimForTable`, parametre `ilAdi/cinsiyet/yil`; 2018-2025 |
| Hava Kalitesi (ÇŞB SİM) | istasyon bazlı PM10/SO2/NO2 | bilinmiyor | `/Services/AirQuality?type=0` düz istekte HTML döndü; tarayıcı gerekir |
| Göç İdaresi, OGM, TÜRKPATENT, VGM | ikamet izni; orman/yangın; marka-patent; vakıf | bilinmiyor | hepsi JS uygulaması, tarayıcıyla bakılacak |

### Belediye açık veri portalları — 14 çalışan CKAN (2026-09-18 taraması)

İlk 200 veri seti kaynaklarıyla taranarak sıralandı. "Tablolu" = CSV/XLSX/XLS/JSON kaynağı olan
veri seti sayısı; "ilçe/nüfus" = başlık ya da açıklamasında ilçe, mahalle veya nüfus geçenler.

| Portal | Veri seti | Tablolu | İlçe/nüfus | Baskın biçim | Kolaylık |
|---|---|---|---|---|---|
| Sakarya (`veri.sakarya.bel.tr`) | 307 | 200/200 | 30 | XLSX | **en kolay** |
| Manisa (`acikveri.manisa.bel.tr`) | **1.168** | 180/200 | **130** | XLSX, XLS | **en kolay + en zengin** |
| Konya (`acikveri.konya.bel.tr`) | 239 | 180/200 | 14 | CSV | kolay |
| Balıkesir (`acikveri.balikesir.bel.tr`) | 250 | 171/200 | 27 | XLSX | kolay |
| İzmir (`acikveri.bizizmir.com`) | 261 | 165/200 | 56 | CSV, XLSX | kolay |
| Kadıköy (`acikveri.kadikoy.bel.tr`) | 160 | 116/160 | 49 | CSV | kolay |
| Tuzla (`veri.tuzla.bel.tr`) | 97 | 91/91 | 26 | CSV | kolay |
| Gaziantep (`acikveri.gaziantep.bel.tr`) | 252 | 90/200 | 32 | CSV, PDF | orta |
| Çanakkale (`acikveri.canakkale.bel.tr`) | 119 | 64/119 | 0 | XLSX, PDF | orta |
| Nilüfer (`acikveri.nilufer.bel.tr`) | 65 | 44/65 | 12 | XLSX | orta |
| Ordu (`acikveri.ordu.bel.tr`) | 743 | 58/200 | 114 | **PDF (772)** | zor — içerik zengin ama PDF |
| Sivas (`acikveri.sivas.bel.tr`) | 45 | 32/45 | 2 | SHP, KML | zor (geometri) |
| Bursa (`acikyesil.bursa.bel.tr`) | 49 | 20/49 | 2 | GEOJSON | zor (geometri) |
| B40 (`opendata.b40cities.org`) | 645 | 4/200 | 1 | HTML | zor |

Çalışmayanlar: Antalya (zaman aşımı), YSK açık veri (bağlantı yok), Küçükçekmece ve Kocaeli (502),
Beyoğlu/Eyüpsultan (yok), Kayseri ve Marmara Belediyeler Birliği (CKAN değil), Şeffaf Ankara
(Firebase tabanlı kendi yazılımı), `databook.dataint.net` (Cloudflare), İBB (robots yasak).

**Sıradaki adım:** Manisa ve Sakarya'dan başlanacak — ikisi de tablolu ve Manisa'da 130 veri seti
ilçe/mahalle/nüfus içerikli. Bu veriler tek şehirlik olduğu için K4 dışıdır; `ozel-analiz-kalibi`
kapsamında vaka analizi olarak değerlendirilir.

## Alınmayanlar ve gerekçesi (2026-09-18)

- **NVİ adres (UAVT)**: resmî kaynak captcha arkasında. GitHub'da 1,27 mn sokaklı dökümler var
  (`melihozkara/il-ilce-mahalle-sokak-veritabani`, 12.04.2026) ama derleyen **captcha çözücü**
  kullanmış — o yöntem tekrarlanmaz; lisans da yok.
- **Nişanyan Yeradları** (56.422 güncel + 77.509 eski yer adı): telifli eser, kaynak olarak anılır.
- **Google/Yandex haritalar**: Yandex robots `/maps/business/`, Google `/maps?` kapalı; resmî
  API'ler POI içeriğinin saklanmasını yasaklıyor.
- **TÜİK kütüphanesi** (1965 sayımı ana dil/din ciltleri dahil): `robots.txt` → `Disallow: /`.
- **HGM Atlas API**: kayıt kapalı ("ticarileştirme süreci devam etmektedir").
- **turkiyeapi.com**: ticari (Pro 299 TL/ay); ücretsiz `api.turkiyeapi.dev` zaten kullanılıyor.
- **Veri olmayanlar**: PerkBank (sentetik banka verisi), turkiye-iban (banka kodu, yer boyutu yok),
  ankageo.com (CBS yazılım satıcısı), otomobil fiyat listesi (tarihsiz), genel "veri seti listesi"
  yazıları (upGrad, gencbeyinler, binyaprak — Kaggle/UCI türü, Türkiye il verisi yok).

## 2026-09-18 sabahı eklenenler ve kapananlar

| Kaynak | Ne girdi | Not |
|---|---|---|
| OECD TL3 (ikinci tur) | taburcu 2002-2023, kasten öldürme 2001-2024, araç hırsızlığı 2008-2024, PCT patent 1995-2024 (8 teknoloji alanı) | TÜİK'le çakışan altı ölçü bilerek alınmadı, gerekçe `adapters/oecd_tl3.py` başlığında |
| TÜİK isim portalı | `baby_names`: il × cinsiyet × yıl ilk 30 bebek ismi, 2018-2025, 112 bin satır | tarayıcısız; `POST /Home/IlYilBebekIsimForTable`. Üç bebek eşiği ve ilk 30 kesiği yüzünden toplanmaz |
| TKGM MEGSİS | parsel tablosu üç göstergeye ayrıldı | ham veri 2026-09-14'ten beri bekliyordu |
| TKGM MEGSİS (ilçe + yerleşim) | aynı üç gösterge 2026-09-18 akşamı ilçe (973) ve yerleşim düzeyine indi: 43.184 alan, 345 bin satır | aşağıdaki nota bak |

**TKGM yerleşim düzeyi — kadastro birimi mahalle değildir.** MEGSİS'in en alt kırılımı
"birim", yani kadastro birimi. 50.280 birimin 42.760'ı (%85,0; parselle tartıldığında
%85,7) kayıt defterindeki bir mahalle ya da köye oturuyor; kalanı ada eşleşmiyor ve bu bir
okuma hatası değil:

* Kadastro birimi yerleşimin onlarca yıl önce bıraktığı adı taşıyabiliyor — Elazığ Merkez'de
  `Aşvan`, Keban barajı altında kalmış bir köy.
* Bir yerleşim birden çok birim tutabiliyor: `İskele/karşıyaka`, `İskele/orta`. Bunlar eğik
  çizgiden önceki ada toplanıyor, üst üste yazılmıyor.
* Büyükşehir illerinde 6360 ile kaldırılmış köy kaydına 2026 görüntüsü yazılmıyor: yalnız
  2013 sonrası görülen köyler eşleştirmeye giriyor.
* `Elazığ,Merkez,Adedi` satırı kaynağın kendi tek seferlik saçmalaması (463 parsel), sistemli
  bir ayrıştırma hatası değil.

Eşleşme %75'in altına düşerse adaptör hata veriyor — kayıt defteri değişip sessizce yarım
yüklenmesin diye. İl satırları artık ilçe dosyasından toplanıyor: il tablosu 14.09, ilçe ve
birim dökümü 18.09 görüntüsü ve aradaki dört günde kadastro birkaç bin parsel büyümüş; tek
görüntü tarihi kalsın diye il tablosu yalnız %1 sapma denetimi olarak kullanılıyor.

**EPİAŞ (2026-09-18 sabahı denendi):** `eligible-consumer-count` doğrudan istekte **401**
döndü — TGT, yani kullanıcının hesabıyla giriş gerekiyor. Uç noktalar ve parametreler
belli; eksik olan tek şey oturum. Kullanıcı tarayıcıda giriş yaptığında çekim yapılabilir.

Günün tam dökümü: [oturum-2026-09-19.md](oturum-2026-09-19.md).

## Sıradaki oturumun ilk işi (2026-09-19 gece güncel)

Bugün depoya giren: `cpi_2003_items` (TÜFE kalemleri 2003'e uzadı), `internet_*` dört
gösterge (Ookla mobil+sabit hız), `province_gdp_current` ve `province_gdp_chained` (il
GSYH tutarı), `port_cargo_handled` (liman yükü). Envanter artık depodan üretiliyor:
[envanter.md](envanter.md), `scripts/build_inventory.py`.

**Adaptörü yazılmamış, ham veri diskte bekleyenler:**

| Ne | Nerede | Not |
|---|---|---|
| ~~AVM ciro endeksi~~ | 2026-09-19 akşamı adaptörü yazıldı: `mall_turnover_index`, `mall_visitor_index`, `mall_turnover_per_sqm` | — |
| ~~Telekom IR~~ | 2026-09-19: `telecom_*` altı gösterge (Turkcell + Türk Telekom, çeyreklik). ARPU alınmadı, biri IAS 29'a göre düzeltilmiş | — |
| Denizciliğin kalanı | ham veri diskte | yük ve konteyner adaptöre girdi; gemi, kruvaziyer, Ro-Ro, boğaz geçişleri, filo ve 2020 öncesi liman arşivi duruyor |
| ~~Perakende endeksleri~~ | 2026-09-19: `retail_volume_index`, `retail_turnover_index` (2015=100, 2010-2023). Sanayi, ticaret, inşaat cirosu ve hizmet üretim endeksi hâlâ okunmadı | — |
| Opet akaryakıt | `veri-ham\opet\` | 13 il/139 ilçe kesiti; tur durduruldu |

**Kapanan kapılar (bugün denendi):**

- **DSİ baraj doluluk** — halka açık pano yalnız manşet veriyor (TR geneli üç yıl, dört
  büyükşehir birer değer), ağ kaydında veri isteği yok, ayrıntılı pano robots'ta kapalı.
  Günlük seri yalnız EPİAŞ'ta ve hesap istiyor.
- **marketvisuals.net** — veri kendi Supabase'lerinde, sayfanın anon anahtarıyla geliyor;
  başkasının arka ucundan toplu çekim yapılmadı. Site keşif listesi olarak kullanıldı,
  kaynakların aslına gidildi.
- **MEB okul siteleri** — `robots.txt` ClaudeBot dahil bütün yapay zekâ ve arşiv
  botlarını ad ad engelliyor (2026-09-19 doğrulandı).

**Beşinci yükleme yarıda kesildi** (2026-09-19 gece, kullanıcı kararı: tüm işlemler
durduruldu). Warehouse'ta duran son tam tur dördüncüsü: **880 gösterge, 21,23 mn satır**.
Akşam yazılan on üç gösterge — AVM üçlüsü, liman konteyneri, telekom altılısı, perakende
ikilisi ve liman yükü — **henüz warehouse'ta değil**; yeni oturumun ilk işi tam yükleme.

**Sıradaki:** tam yükleme, envanteri yeniden üret, sonra denizciliğin kalan tabloları ve
TÜİK'in sanayi/ticaret/inşaat ciro endeksleri.

## 2026-09-18 gecesi eklenenler

| Kaynak | Ne girdi | Not |
|---|---|---|
| Zincir mağazalar | `chain_restaurants`: Burger King + McDonald's şube sayısı, ilçe ve il, 18.09.2026 anlık görüntüsü | Yöntem ve bulgular `docs/zincir-magazalar.md`. **Henüz warehouse'a yüklenmedi**, bir sonraki tam yüklemede girer |

**Koordinatı olmayan üç zincir bekliyor.** BİM (13.057), Migros (3.442) ve Starbucks (804)
ham depoda duruyor ama ilçeleri kaynağın kendi etiketinden geliyor; kayıt defteriyle
eşleme yapılmadığı için adaptöre girmediler. PTT'nin 3.295 kaydında koordinat var,
adaptörü yazılabilir.

**TÜİK Veri Portalı dosya indirmesi** 2026-09-18 gecesi bitirildi: 2.247 dosya indi,
15 dosya kaynakta hatalı; dökümü `veri-ham/tuik_portal/basarisiz.csv`.

**PTT posta kodu** 2026-09-18 çekildi ve `postal_codes` göstergesi olarak depoya girdi:
973/973 ilçe, 1.272.201 satır, 72.640 mahalle, 2.777 posta kodu. Yöntem
`scripts/fetch_ptt_postal_codes.py`, doğrulama `docs/semt.md`. Mahalle listesi kayıt
defteri denetimi için duruyor, henüz kullanılmadı.

**bulurum.com kapsama testi (2026-09-18).** Kapsama **kategoriye göre değişiyor**, sitenin
genel bir özelliği değil: eczane 27.458 (gerçeğe çok yakın), banka 10.809'a karşılık
BDDK'nın 31.695 şubesi (%34) — üstelik `/search/` kategori filtresi değil **serbest metin
araması** olduğu için banka sonuçları nakliyat ve temizlik firmalarıyla kirli. Site birkaç
yüz istekten sonra **HTTP 200 ile** doğrulama sayfası döndürüyor; sayı arayan bir okuyucu
bunu sıfır sanır. Kayıt defteri olan kategorilerde kullanılmaz; olmayanlarda (çiğköfteci,
halı yıkama, kuaför) alt sınır ve oran verir — gösterge değil, vaka analizi malzemesi.

**İl Sağlık Müdürlüğü siteleri** (`<il>ism.saglik.gov.tr/TR-<id>/saglik-kurumlari.html`):
hastaneler ilçesiyle tek tek listeleniyor. Depodaki `moh_*` göstergeleri yalnız il
düzeyinde olduğu için bu **ilçe düzeyi sağlık kurumu** verir. 81 il aynı CMS'te ama sayfa
numaraları farklı, önce onların bulunması gerekir. Orta zorluk, başlanmadı.

## Kullanıcı kararı bekleyen

- ~~main birleştirme~~ 2026-09-17 yapıldı; dal ve main aynı noktada.
- ~~EPİAŞ hesabı~~ 2026-09-18 açıldı; uç noktalar yukarıda. Ceza infaz, yaşam memnuniyeti: kararla alınmadı.

## Bilinçli olarak alınmayanlar

MEB (robots.txt), İBB açık veri (robots.txt), TCDD (403), TOBB aylık il tabloları (yıllık depoda).


## Sıradaki işler (2026-09-19 gecesi bırakıldığı yer)

| # | İş | Durum | Not |
|---|---|---|---|
| 1 | **İl Sağlık Müdürlüğü siteleri** | başlanıyor | `<il>ism.saglik.gov.tr/TR-<id>/saglik-kurumlari.html`. Depodaki 20 `moh_*` göstergesi yalnız il düzeyinde; bu siteler hastaneyi **ilçesiyle** listeliyor. 81 il aynı CMS, sayfa numaraları farklı — önce onlar bulunacak |
| 2 | **EPDK şarj istasyonu** | kullanıcıda | Sorgu reCAPTCHA arkasında, kullanıcı indiriyor. 34 sayfanın 8'i indi = **3.500 tekil istasyon** (`C:\veri-ham\epdk1`). Adres alanı "… Beykoz / İSTANBUL" biçiminde, ilçe oradan okunuyor. Tamamlanınca adaptör yazılacak |
| 3 | **Domino's** | bekliyor | 26 ilde 311 şube indi, site IP'yi kapattı (429 sürüyor). Ceza geçince `uv run python scripts/fetch_dominos.py --devam` |
| 4 | **Hakmar Express** | yarım | `/magazalar` gömülü JSON'da ad/adres/il/ilçe/koordinat veriyor ama tek seferde 25 kayıt; site 816 mağaza diyor. Sayfalama çözülmedi |
| 5 | Zincir taraması | sürüyor | Kolay çekilebilen marka arayışı arka planda |

**Perakende zincirlerinde tur kapandı (2026-09-19).** Denenen yedi marka — Bauhaus, Koçtaş,
Watsons, Teknosa, Gratis, Tekzen, Mavi/Boyner türü giyim — hiçbiri tam liste vermedi: çoğu
düz istekte 403, Gratis ve Tekzen erişilebilir ama mağaza listesini sayfaya hiç basmıyor.
Buna karşılık aynı akşam çözülen dört markanın (Oses, Ziyafet, Komagene, Domino's) hepsi
yeme-içme. Desen açık: mağaza listesi perakendeci için rakip istihbaratı, franchise satan
için reklam. Yeni marka denemeden önce bu akılda tutulmalı.


## 2026-09-20: zincir turu ve dorduncu yukleme

**Depo 894 gostergede duruyor. Bu gunun isi henuz icinde degil** — `scripts/load.py`
bastan calistirilmali (901 adaptor). Girecekler: 32 marka / 56.269 magaza,
`fuel_stations`, `operator_dealers`, BIM 13.057, Migros 3.442.

`kgm_vehicle_km` her yuklemede ayni yerde 25-90 dakika tutuyor; profillenmeli.

| # | Is | Durum |
|---|---|---|
| 1 | **Turkcell PDF temizligi** | 3.619 bayi cikti ama hucre kaydirmasi 65 satirin ilini bozmus (`GUMUSHA N`, `1 HAKKARI`) ve `kind`'de bosluk artigi var (`DSNPlu s`). Ilce eslesmesi %93, `MAX_UNPLACED` %3'u asiyor -> adaptore giremez |
| 2 | **Akbank ve diger bankalar** | `Ajax.aspx/SearchBranchAtm` calisiyor, yalniz `searchKeyword` ile (`cityName` 400). Yanit `atmList`/`branchList` ayri. Il kodlari bulunursa Garanti/Is/Ziraat icin ayni kalip. Depoda banka bazinda sube/ATM yok |
| 3 | **KAP** | BIM, Migros, SOK, CarrefourSA, Bizim Toptan borsada — magaza ve calisan sayisi **yillar icinde** oradan alinabilir. Magaza bulucular yalniz bugunu verir. robots 666 donduruyor |
| 4 | Happy Center, Bizim Toptan | esigi asiyor (20/80 ve 15/172), adaptor disinda; birer cekici duzeltmesi uzakta |
| 5 | A101, Hakmar, KFC | sirasiyla konum izgarasi, JS sayfalama, yarim cekim |

**Cekilemeyenler:** Watsons, Teknosa, Koton, LC Waikiki, Mado, Popeyes, Bauhaus (403);
MediaMarkt (robots'ta ClaudeBot kurali); Seyhanlar alindi ama sertifikasi dogrulanmiyor
(kullanici talimatiyla o tek host icin kapatildi).
