# Veri kaynakları

Adaptör yazılabilecek kaynakların dökümü. Sıra, "bize ne kadar lazım" değil "ne kadar
kolay bağlanır"a göre: API'si olanlar önce.

**Doğrulama durumu** sütunu önemli. `✔` = bu oturumda belgesine bakıldı. `?` = varlığı
biliniyor ama uç noktası/koşulları teyit edilmedi; adaptör yazmadan önce bakılacak.

## Türkiye — programlı erişimi olanlar

| Kaynak | Kapsam | Erişim | Anahtar | D |
|---|---|---|---|---|
| **TCMB EVDS3** | Faiz, kur, enflasyon, ödemeler dengesi, parasal veriler; 154 kategori | REST/JSON, `evds3.tcmb.gov.tr/igmevdsms-dis` | var (HTTP `key:` başlığı) | ✔ |
| **EPİAŞ Şeffaflık 2.0** | Elektrik ve doğal gaz piyasası: üretim, tüketim, fiyat, kapasite; saatlik | REST, ayrı elektrik / doğal gaz servisleri, teknik doküman yayında | ücretsiz, kayıt | ✔ |
| **AFAD deprem servisi** | Son depremler + arşiv; TADAS'ta ivme kayıtları | REST/JSON; Kandilli ile birleştiren üçüncü taraf API'ler de var | yok | ✔ |
| **Dünya Bankası** | Kalkınma göstergeleri (WDI), ülke × yıl | REST v2 + SDMX | yok | ✔ |
| **IMF** | Ödemeler dengesi, DOTS, WEO, mali istatistikler | Yeni portal `data.imf.org`, SDMX 3.0 REST; eski `sdmxcentral` uçları da ayakta | yok | ✔ |
| **Eurostat** | AB istatistikleri; Türkiye aday ülke olarak birçok seride var | SDMX 3.0 REST | yok | ✔ |
| **UNICEF** | Çocuk sağlığı, eğitim, beslenme; MICS göstergeleri | SDMX REST, CSV/JSON | yok | ✔ |
| **WHO GHO** | Sağlık göstergeleri, ülke × yıl | OData | yok | ✔ |
| **OWID** | Derlenmiş uluslararası seriler (nüfus, enerji, sağlık, iklim) | Charts / Tables / Indicators / Search API; `owid-catalog` Python kütüphanesi | yok | ✔ |
| **CIA World Factbook** | Ülke profilleri, kaba demografik ve ekonomik göstergeler | `factbook.json` deposu, haftalık güncellenen JSON; kamu malı | yok | ✔ |
| **DBnomics** | 93 sağlayıcıyı tek arayüzde toplayan toplayıcı; TCMB dahil (TÜİK yok). Kodlar ve sağlayıcı yapısı korunuyor | REST, `api.db.nomics.world/v22`, OpenAPI belgesi var; Python/R/Stata istemcileri | yok | ✔ |
| **OECD** | Ulusal hesaplar, işgücü, eğitim; Türkiye üye | SDMX REST | yok | ? |
| **ILOSTAT** | İşgücü istatistikleri | SDMX + toplu dosya | yok | ? |
| **UN Comtrade** | İkili dış ticaret, ürün kırılımlı | REST | ücretsiz kotalı, anahtar ister | ? |
| **FAOSTAT** | Tarım, gıda, arazi kullanımı | REST + toplu dosya | yok | ? |

## Türkiye — API yok, kazıma ya da dosya

| Kaynak | Kapsam | Erişim | D |
|---|---|---|---|
| **TÜİK MEDAS** | Neredeyse bütün resmi istatistik; il/ilçe kırılımı | Playwright; sunucu turlu ZK arayüzü. Bazı kırılımlar sunucuda kilitli | ✔ |
| **TÜİK Veri Portalı** (`data.tuik.gov.tr`) | Haber bültenleri, dinamik sorgulama | İndirilebilir dosya; kurumlara sözleşmeyle web servisi verildiği belirtiliyor, kamuya açık uç nokta görünmüyor | ✔ |
| **TÜİK Coğrafi İstatistik Portalı** (`cip.tuik.gov.tr`) | Harita üzerinde il/ilçe/mahalle göstergeleri | Portal; sınır geometrisi için değerli | ? |
| **TÜİK mikro veri** | Anket ham verisi (hanehalkı işgücü, gelir yaşam koşulları) | Başvuru + sözleşme, ücretli olabiliyor | ? |
| **MGM / MEVBİS** | Meteoroloji: sıcaklık, yağış, istasyon bazlı | Satış/başvuru sistemi; günlük tahmin uçları gayriresmî kullanılıyor | ✔ |
| **YSK** | Seçim sonuçları, sandık düzeyinde | Portal + indirilebilir dosya; sandık verisi için üçüncü taraf derlemeler daha kullanışlı | ? |
| **Sağlık Bakanlığı** | Sağlık istatistik yıllığı, pilot açık veri | PDF/Excel ağırlıklı | ? |
| **Ulusal Coğrafi Bilgi Portalı** | İdari sınırlar, mekânsal katmanlar | WMS/WFS servisleri | ? |
| **Borsa İstanbul Veri Mağazası** | Hisse, endeks, tahvil | Ücretli abonelik | ? |

## Coğrafya

| Kaynak | Kapsam | Erişim | D |
|---|---|---|---|
| **TurkiyeAPI** (`api.turkiyeapi.dev/v2`) | 81 il · 973 ilçe · 1.377 belediye · 32.254 mahalle · 18.183 köy. Nüfus, yüzölçümü, rakım, koordinat, posta kodu, alan kodu, bölge | REST, anahtarsız, OpenAPI; MIT lisans, kaynak veri TÜİK MEDAS + PTT + HGM + OSM | ✔ |
| **TÜİK Coğrafi İstatistik Portalı** (`cip.tuik.gov.tr`) | Harita üzerinde il/ilçe/mahalle göstergeleri | Portal | ? |
| **Ulusal Coğrafi Bilgi Portalı** (`atlas.gov.tr`) | İdari sınırlar, mekânsal katmanlar | WMS/WFS | ? |
| **TÜCBS Açık Veri** (`tucbskontrol.csb.gov.tr`) | Ulusal coğrafi açık veri | Portal | ? |

TurkiyeAPI bizim için doğrudan işe yarıyor ama **sınırı bilinmeli: bugünkü durumu
veriyor, tarihini değil.** 6360 öncesi ilçeler, kapanmış köyler, ad değişiklikleri yok;
"İznik 2009'da neydi" sorusunu cevaplamıyor. Yani ilçe kaydının *listesini* oradan
alabiliriz, *geçerlilik aralığı ve ardıl eşlemesini* yine kendimiz kurmamız gerekiyor.

Kullanım biçimi: çalışma anında API'ye bağlanmak yerine, veriyi bir kez çekip kendi
kaydımıza yazmak — kaynak ve çekim tarihi kayıtta dursun. Dış servis çökerse ya da
numaralandırmasını değiştirirse verimiz etkilenmesin.

## Türkiye — yerel yönetim ve diğer

| Kaynak | Kapsam | Not |
|---|---|---|
| **İBB Açık Veri** | İstanbul: ulaşım, nüfus, çevre, sosyal yardım | En zengin belediye portalı; CKAN tabanlı, API'si var |
| **Resmi İstatistik Portalı** (`resmiistatistik.gov.tr`) | Resmi istatistik programındaki bütün kurumların yayın takvimi ve dağıtımı | Hangi kurumun neyi yayımladığını bulmak için giriş noktası |
| **YSK Açık Veri Portalı** (`acikveri.ysk.gov.tr`) | Seçim sonuçları | Portal; sandık düzeyi için üçüncü taraf derlemeler daha kullanışlı |
| **Ankara / İzmir / Bursa / Kayseri açık veri** | Kent ölçeği | Kapsam ve süreklilik değişken |
| **ULAKBİM Veri Portalı** | Akademik araştırma veri setleri | TÜBİTAK altyapısı |
| **Hava kalitesi izleme** (`sim.csb.gov.tr`) | İstasyon bazlı PM10/PM2.5/NO2, saatlik | Uzun geriye dönük seri var |
| **Üniversite veri setleri** | NLP, büyük veri (İTÜ, Bilkent, YTÜ, Fırat) | Konumuz dışı ama derlemede geçiyor |

## Akademik ve anket kaynakları

Bunlar "resmi istatistik" değil ama TÜİK'in vermediği kırılımları veriyorlar —
özellikle doğurganlık, göç ve sağlık davranışı için.

| Kaynak | Neden önemli |
|---|---|
| **TNSA — Türkiye Nüfus ve Sağlık Araştırması** (Hacettepe HÜNEE) | 1968'den beri beş yılda bir. Doğurganlık, evlilik, çocuk sağlığı; TÜİK'in yayımlamadığı davranışsal kırılımlar burada. Mikro veri başvuruyla. En son ana rapor 2018; 2023 dalgasının veri durumu teyit edilmeli |
| **DHS Program** | TNSA'nın uluslararası ailesi; karşılaştırılabilir gösterge tanımları ve mikro veri erişim usulü |
| **Türkiye Gençlik Araştırması** (HÜNEE) | Genç nüfusun eğitim/istihdam/göç eğilimleri |
| **DergiPark** | Türkçe akademik yayın dizini. "Nüfusbilim Dergisi" gibi doğrudan konuya değen dergiler burada; TNSA'nın yeniden hesaplanmış göstergeleri gibi metodoloji makaleleri var |
| **Human Mortality Database** | Ölümlülük tabloları, uluslararası karşılaştırmalı |
| **IPUMS International** | Nüfus sayımı mikro örneklemleri, ülkeler arası uyumlaştırılmış |

## Makale / metin tarafı

"Veri" yerine "yorum" arayan tarafta iş görecekler:

- **TÜİK haber bültenleri** — her yayımın yanında tanım ve metodoloji notu; tanım
  kaymasını yakalamak için birincil kaynak
- **TCMB Enflasyon Raporu, Finansal İstikrar Raporu** — seri kırılmalarının
  gerekçesi çoğu zaman burada açıklanıyor
- **Betam, TEPAV** araştırma notları — işgücü ve büyüme verisine hızlı yorum
- **Nüfusbilim Dergisi / DergiPark** — demografik yöntem makaleleri
- **OWID yazıları** — gösterge tanımı ve karşılaştırma kurgusu açısından örnek alınacak
  iyi bir referans

## Sıradaki adım için öneri

Adaptör sözleşmesi yazılırken ilk üç aday: **EVDS3** (anahtar var, REST, en kolay),
**Dünya Bankası** (anahtarsız, uluslararası karşılaştırma açar), **MEDAS** (en zor ama
projenin asıl kaynağı). Üçü birbirinden yeterince farklı ki sözleşmenin doğru soyutlama
olup olmadığı hemen anlaşılır.

DBnomics'i tek başına bir kestirme gibi görmemek lazım: TÜİK'i taşımıyor, yani asıl
ihtiyacımız olan il/ilçe kırılımlı veri orada yok. Ama uluslararası tarafta tek adaptörle
onlarca sağlayıcı açtığı için Dünya Bankası'na alternatif olarak değerlendirilebilir.
