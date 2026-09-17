# Açık işler (2026-09-17, akşam güncel)

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
| Muhasebat | il merkezi yönetim bütçesi (2004-2026) ve mahalli idareler bütçesi (2006-2026); aynı portal API'si, `scripts/fetch_muhasebat.py`'ye slug eklemek yeter | kolay |
| OECD bölgesel (SDMX) | TL3 = il düzeyinde iklim, arazi örtüsü, hava kirliliği, kentleşme | orta |
| TEDAŞ | istatistikkitabi.tedas.gov.tr, il elektrik dağıtım | bilinmiyor (zaman aşımı) |
| TKGM MEGSİS | tapu/kadastro, ham veri diskte, adaptör yok | orta |
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
| **Ookla Speedtest açık veri** | ölçülmüş sabit/mobil internet hızı, çeyreklik karo (~600 m), S3'te parquet, anahtarsız | kolay | ham depoda 2022Q4 + 2024Q4 (`C:eri-ham\ookla`); BTK'nın *vaat edilen* hızının karşısına *ölçülen* hızı koyar |
| **OSM Türkiye** | 112 mn öge; sokak adları, arazi örtüsü, POI | orta | ham depoda (`C:eri-ham\osm`, md5 OK). DuckDB spatial pbf'i doğrudan okuyor. **Sayım için kullanılamaz** (kapsama gönüllüye bağlı), pay/uzunluk göstergeleri için uygun |
| **TÜİK isim portalı** | il × yıl × cinsiyet × ad, ilk 30 ad | kolay | `POST nip.tuik.gov.tr/Home/IlYilToplamIsimForTable`, parametre `ilAdi/cinsiyet/yil`; 2018-2025 |
| Hava Kalitesi (ÇŞB SİM) | istasyon bazlı PM10/SO2/NO2 | bilinmiyor | `/Services/AirQuality?type=0` düz istekte HTML döndü; tarayıcı gerekir |
| Göç İdaresi, OGM, TÜRKPATENT, VGM | ikamet izni; orman/yangın; marka-patent; vakıf | bilinmiyor | hepsi JS uygulaması, tarayıcıyla bakılacak |

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

## Kullanıcı kararı bekleyen

- ~~main birleştirme~~ 2026-09-17 yapıldı; dal ve main aynı noktada.
- ~~EPİAŞ hesabı~~ 2026-09-18 açıldı; uç noktalar yukarıda. Ceza infaz, yaşam memnuniyeti: kararla alınmadı.

## Bilinçli olarak alınmayanlar

MEB (robots.txt), İBB açık veri (robots.txt), TCDD (403), TOBB aylık il tabloları (yıllık depoda).
