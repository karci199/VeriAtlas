# EPDK — enerji piyasası il verisi

Durum 2026-09-15: 2025 Excel ekleri ve 2015-2024 Word raporları **depoda** (`adapters/epdk.py`,
`adapters/epdk_history.py`, 7 gösterge).

## Akış

1. `raw/epdk/envanter.tsv` — elektrik, doğalgaz, petrol, LPG, enerji dönüşümü, şarj rapor
   sayfalarındaki 507 belge bağlantısı (sayfalar düz HTML, `curl`/`httpx` yeter).
2. `scripts/fetch_epdk_documents.py` — hepsini `raw/epdk/files/<piyasa>/<id>.<uzantı>` olarak
   indirir (492 belge, 1,25 GB): Excel eki, Word ve PDF raporlar, aylık resmi istatistikler.

## Depoda

| Gösterge | Kapsam | Denetim |
|---|---|---|
| `epdk_electricity_consumption`, `_consumers` | il × tüketici türü, 2024-2025 | tür → il toplamı, il → genel toplam |
| `epdk_natural_gas_sales` | il × sektör (Sm3), 2025 | şirket satırları → il TOPLAM |
| `epdk_natural_gas_subscribers` | il, abone / serbest tüketici, 2025 | şirketler → il, iller → genel toplam |
| `epdk_fuel_sales` | il × ürün (ton), 2025 | ürünler → il toplamı, iller → Türkiye |
| `epdk_lpg_sales` | il × tüplü/dökme/otogaz (ton), 2025 | türler → il, iller → Türkiye |

## Tuzaklar

- Genel toplam satırının il hücresi boş; il adını aşağı taşıyan okuyucu onu son ile (Bayburt)
  yazar — Bayburt Türkiye kadar elektrik tüketir görünür (test: `test_epdk.py`).
- Doğalgaz Tablo-13'ün son bloğu `DİĞER`: iletim şebekesi ve depolamada kullanılan gaz, il yok.
- Elektrik Excel'i ile PDF il tablosu 66/69 ilde aynı. Yalova: Excel yalnız dağıtım (iletim
  bağlantılı 44 GWh yok). Yozgat: Excel 876, PDF dağıtım 832 + iletim 1.059 GWh — tutmuyor.
- TÜİK il elektrik tüketimi ile oran ortancası 1,07; Çanakkale 2,17, Karabük 1,73, Yalova 1,60
  (iletim bağlantılı sanayi/santral farklı sayılıyor). Ayrı gösterge, karıştırma.
- Faturalanan tüketim: Şırnak mesken 2023→2025 %80 artış, abone %5 — faturalamanın sıkılaşması.

## Geçmiş yıllar (Word raporları)

`scripts/extract_epdk_docx_tables.py` bütün Word raporlarının tablolarını başlıklarıyla
`raw/epdk/docx_cells.parquet`'e yazar (1,9 mn hücre). Türkçe başlıkla seçildiği için İngilizce
kopyalar okunmaz. Rapor yılı raporun kendi başlıklarından ("2019 Yılı Sonu") alınır.

| Gösterge | Yıllar |
|---|---|
| elektrik tüketimi (il × tür) | 2017-2025 |
| elektrik abone (il × tür) | 2021-2025 |
| doğalgaz tüketimi (il × temin şekli) | 2017-2024 |
| doğalgaz abone / serbest tüketici | 2017-2025 |
| akaryakıt satışı (il × ürün) | 2015-2025 |
| LPG satışı (il × tür) | 2016-2025 |

Tuzaklar (hepsi denetim yakaladı):

- İstanbul 2017-2021 tablolarında Avrupa ve Anadolu iki satır: ile göre yazan okuyucu ikincisini
  birincinin üstüne yazıyor, İstanbul'un yarısı (13,4 TWh) kayboluyordu. Yakalar toplanıyor.
- 2017-2021 elektrik türleri eski tarife grupları (Ticarethane, Tarımsal Sulama): 2022 kırılması.
- 2024 raporu tüketici tablosunu "2023" diye başlıklandırmış; yıl tablo başlığından alınmaz.
- Doğalgaz sütun adları yıldan yıla değişiyor (CNG Diğer / CNG OTOGAZ / Oto CNG / Oto LNG),
  sütun sırası da (2023'te CNG ilk sütun).
- Yuvarlanmış tablolar (milyon Sm3 üç ondalık, tam ton/MWh): toplam denetimi yuvarlama payıyla.
- 2017'de 77 ilde doğalgaz dağıtımı var; eksik iller şebekesiz iller.
- **Revizyon:** 2024 elektrik 2024 raporunda ve 2025 ekinde 50 hücrede farklı; 49'u <%2,4.
  Mardin tarımsal 2024: 222,0 → 253,7 GWh (+%14), revizyon olarak kabul edildi. Yeni değer tutulur;
  başka hücrede %5'i aşan fark yüklemeyi durdurur.

## Sıradaki

Aylık resmi istatistik Excel'leri (2024-2026: il × kaynak kurulu güç, iletim-dağıtım kırılımlı
tüketim, serbest tüketici) ; 2014 ve öncesi PDF raporlar; kurulu güç il tabloları (Word'de var, gösterge yok).

## Kurulu güç (2026-09-15)

| Gösterge | Kapsam | Kaynak |
|---|---|---|
| `epdk_unlicensed_capacity` | il × kaynak (güneş, rüzgâr, hidro, biyokütle, doğalgaz, linyit), 2016-2025 yıl sonu | aylık raporların Aralık sayıları (`docx_resmi_cells.parquet`) |
| `epdk_licensed_capacity` | il toplamı, 2017-2024 | yıllık rapor Tablo 1.3 |

Tuzaklar: Aralık 2021 tablosunda "Küthahya" (119 MW) — tanınmayan ad artık yüklemeyi durdurur;
2019 lisanslı tabloda AYDIN iki kez (1.194,9 ve 44,0 MW), ikisi Türkiye toplamında, 44 MW ile
atanmadı; Kilis'te lisanslı santral yok; santrali olmayan iller lisanssız tabloda listelenmiyor
(2016: 63 il); güneş fotovoltaik ve yoğunlaştırılmış 2016-2019 ayrı sütun, toplandı. İl × kaynak
lisanslı kurulu güç yalnız 2026 aylık Excel'lerinde var (yıllık kural gereği alınmadı).

## LPG 2006-2015, PDF raporlar (2026-09-15)

`LPG_PDFS`: 10 rapor, il × tüplü/dökme/otogaz; yıl kapak ve lisans tablolarından, sıra otogazın
2009-2016 kesintisiz artışıyla doğrulandı. Her yıl il satırı toplamı ve Türkiye toplamı tutuyor.
Tuzaklar: 2009-2010 yazı tipinde İ → Đ; "Malataya" (2007); "İçel" (2009-2010); 2013'te
KAHRAMANMAR / sayılar / AŞ üç satıra bölünmüş.

Alınmayanlar: doğalgaz 2014-2016 il tüketimi (PDF'te boş hücreler kayboluyor, sütun ayrılamıyor;
2014 Word'de yalnız il toplamı); akaryakıt 2011-2014 (litre, bayi pompa satışı — 2015 sonrası ton
serisiyle aynı ölçü değil); şarj hizmeti (il kırılımı yok, Türkiye grafikleri).

## Şarj istasyonları (2026-09-19)

`charging_stations` — EPDK lisans veritabanındaki elektrikli araç şarj istasyonu sayısı,
**728 ilçe ve 81 il**, 16.376 tekil istasyon. Kazıma değil **lisans kaydı**: mağaza
bulucularından farklı olarak sayım tamdır, eksik kalan bir kayıt görünmez değildir.

**Sorgu reCAPTCHA arkasında.** `lisans.epdk.gov.tr/epvys-web/.../sarjIstasyonuOzetSorgula.xhtml`
ekranında Sorgula'ya basmak "Ben robot değilim" işaretlemeyi gerektiriyor, o yüzden
sayfalar elle indirildi: sayfa boyutu 500, her sayfa için Raporla, 34 dosya
(`C:\veri-ham\epdk\sarj_istasyonu\`).

Üç tuzak:

* **Sayfalar çakışıyor.** `ŞRJ/9055` birden çok dosyada geçiyor; satır saymak yerine
  istasyon numarasıyla tekilleştiriliyor. İlk sekiz dosyadaki 4.154 satır 3.500 tekil
  istasyondu.
* **İl sütunu yok.** İl ve ilçe serbest metin adresin sonunda: `… Beykoz / İSTANBUL`.
  16.376 kaydın 16.345'i çözülüyor; kalan 31'i adres yer adı söylemeden bitiyor, tahmin
  edilmiyor.
* **Her istasyonun altında soket tablosu var**, o yüzden dosyanın satır sayısı istasyon
  sayısı değil. Soketler alınmadı: kapasite ölçüsü, varlık ölçüsü değil.

Kayıt defterinin tanımadığı ilçe adları il düzeyinde tutuluyor — istasyon gerçek, il kesin,
yalnız ilçe belirsiz. Bu yüzden il toplamı ilçelerinin toplamından büyük olabilir (16.345'e
karşı 16.247).

**İlk bulgu:** İstanbul 4.118 istasyonla ülkenin dörtte birini barındırıyor; Ankara 2.065,
Antalya 928, İzmir 747, Bursa 707. Muğla'nın 469 ile yedinci sırada olması nüfusuyla
orantısız — turistik kıyı deseni, `chain_restaurants` yoğunluk analizinde de çıkmıştı.
Depodaki `vehicles-by-fuel` ile birlikte okunursa "araç var ama istasyon yok" sorusu
cevaplanabilir.
