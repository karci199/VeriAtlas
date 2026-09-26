# Endeksa — saha notları

Endeksa (endeksa.com) mahalle düzeyinde 2024 ADNKS kesiti, seçim sonuçları, hemşehrilik
ve sınır geometrisi yayımlıyor. TÜİK MEDAS mahalle için yalnız toplam + 18± + cinsiyet
veriyor; Endeksa 5'lik yaş bandı, eğitim, medeni hal, SES, gelir ve yüzölçümü veriyor.
Arayüz bazı alanları "Pro" diye gizliyor, API tamamını gönderiyor.

## Uçlar

Hepsi `https://app.endeksa.com/` altında, sorgu dizisi ortak:

```
countryId=1&cityId=<plaka>&countyId=<Endeksa ilçe kimliği>&districtId=<mahalle kimliği>&level=3
```

| uç | giriş | cevap |
|---|---|---|
| `geo/map` | **gerekmez** | AES şifreli GeoJSON |
| `demography/Values` | gerekir | AES şifreli |
| `demography/FellowCountryman` | gerekir | düz JSON (demografi + hemşehri) |
| `fellowcountryman/Values` | gerekir | düz JSON |

`level` alan kırılımını değil, sorulan düzeyi anlatıyor: 1 il, 2 ilçe, 3 mahalle.
`geo/map` ayrıca `subGeometries=true` istiyor; level 1 ilçeleri (`CountyId`), level 2 o
ilçenin mahallelerini (`DistrictId`) döner.

**Parametre adları tuzak.** `id=<districtId>&level=3` de 200 döner ama gövde
`{"Demography": null, ...}` gelir — hata değil, boş. Dört kimliğin dördü birden
verilmedikçe veri gelmiyor. Şifre çözülmeden bakılırsa fark edilmez: boş cevap 110,
dolu cevap ~8.400 karakter.

## Şifre

`geo/map` ve `demography/Values` gövdesi AES-ECB/PKCS7, base64. Anahtar sayfanın
paketinde açık: `3ND3KS4B4CK3ND24`. `scripts/fetch_endeksa_geo.py:decrypt` bunu yapıyor;
cevap JSON string değilse zaten düz gelmiştir.

## Oturum

`geo/map` girişsiz çalışıyor — sınırların tamamı bu yüzden tarayıcısız çekilebildi
(`public/geo/neighbourhoods/`, 972 ilçe). Demografi ve hemşehri uçları oturum istiyor;
jeton sayfada `localStorage.accessToken`, istekte `Authorization: Bearer`.

Jeton kullanıcının kimlik bilgisi; makineden çıkarılmıyor. Bunun yerine iş bölünüyor
(`raw/endeksa_alici.py`):

- **Python** iş listesini üretir (girişsiz `geo/map`), gelen cevapları çözer ve
  `raw/endeksa/demography/TR-<plaka>-<countyId>.json` olarak yazar.
- **Açık sayfadaki işçi** `/is` ile iş alır, iki authed isteği kendi oturumuyla atar,
  cevabı `/kayit`'a POST eder. Jeton tarayıcıdan hiç çıkmaz.

İstekler arası 2,5–3 sn. Hızlı art arda istek oturumu birkaç dakika kesiyor.

## Veri tuzakları

- Küçük ve eski köylerde demografi boş şablon döner: `HouseholdCount == 0` → veri yok say.
- `DistrictType` her satırda "BELEDİYE MAHALLESİ"; köy/belde ayrımı buradan çıkmaz,
  MEDAS kod sırasından çıkar.
- Yaş bantları toplamı mahalle nüfusunu tutmayabiliyor (Bursa + Ankara dökümünde 2.511
  mahallenin 407'sinde); kullanmadan önce ayıklanmalı.
- Alan doluluğu eşit değil: eğitim %97, SES %99, gelir %60, yaş ve hane %58.
- **Taşıt (2026-09-26, tüm TR dökümü, TÜİK il stoku ile).** `CarCount` = TÜİK **2022 sonu**
  otomobil stoku; plaka 01–54 illerinin çoğunda il toplamı %1 içinde tutuyor. `VehicleCount`
  toplam taşıt **değil**, otomobil dışı taşıt (toplam − otomobil); toplam = ikisinin toplamı.
  Plaka 55–81'de (ve 48'de az) `CarCount` dolgu: aynı ilçede birçok mahalle aynı sayıyı
  taşıyor (Kilis'te 720, Arsin'de 1.168), nüfustan fazla otomobil çıkıyor; il toplamı TÜİK'in
  2–9 katı. 5.803 mahalle. Tanı: ilçe içinde ≥3 mahallede aynı değer (≥50). Bu illerde taşıt
  alanları alınmaz. Hatay, Adıyaman, Gaziantep'te toplam TÜİK'in %80–90'ı —
  2024 nüfus kaybıyla aynı oranda (deprem sonrası nüfusla dağıtılmış olabilir). Niğde %83,
  açıklanamadı.

## Döküm durumu

`raw/endeksa/demography/` — Bursa (17 ilçe) ve Ankara (25 ilçe) tam, 2.511 mahalle.
İstanbul çekiliyor. `raw/` gitignore'da; depoya yalnız bu not girer.

Yayım ve lisans kararı verilmedi; şimdilik araştırma kopyası.

## `ankara-ilceleri-listesi-263f0a` dalından kurtarılan notlar (2026-09-22)

Dal ana dala girmemişti; bölümler orada yazıldı. Çelişen yerde bu dosyanın üst kısmı geçerlidir.

### Ne var

`app.endeksa.com/demography/Values` tek uç nokta; ilçe (`Level=2`) ve mahalle
(`Level=3&DistrictId=`) için aynı ~150 alan:

| Grup | Alanlar | Kaynağı (tahmin) |
|---|---|---|
| Nüfus | toplam, erkek, kadın; 5'lik yaş × cinsiyet (0-4 … 65+) | TÜİK ADNKS |
| Medeni hal | MarriedNever / Married / Divorced / Widow | TÜİK ADNKS |
| Eğitim | 10 kademe (EduNonLiterated … EduDoctorate) | TÜİK ADNKS |
| Hane | HouseholdCount, OwnerShare, RentedShare | TÜİK |
| SES | SesGroupAPlus … SesGroupD, TurkeyIndex/CityIndex etiketi | Endeksa modeli |
| Gelir/harcama | HouseIncome, HouseIncomeTotal, SavingTotal, Expense* (12 kalem) | Endeksa modeli |
| Emlak | HousingCount, CommercialCount, Total_*_Sale_2010-2024, *UnitPrice* | tapu + ilan |
| Coğrafya | Area (km²), PopulationDensity | Endeksa geometrisi |
| Kimlik | DistrictId, DistrictType, VillageName, MunicipalityName | Endeksa |

Ek uç noktalar (önbellek anahtarlarından):

- `app.endeksa.com/fellowcountryman?...&DistrictId=&Level=3` — hemşehri: mahalle
  sakinlerinin nüfusa kayıtlı olduğu ilk 10 il (`CitizenCity`, `CountOf`).
- `app.endeksa.com/geo/map?cityId=&countyId=&districtId=&level=2&subGeometries=true`
  — ilçedeki tüm mahallelerin sınırı, GeoJSON FeatureCollection; `id` =
  DistrictId, `properties.Population`.

Yıl: tek kesit, **2024 ADNKS** (İznik 45.208; Beyler 1.442 = TÜİK 2024 0-17 317
+ 18+ 1.125). İlçe toplamı TÜİK mahalle toplamından 48 fazla — kurumsal nüfus
olabilir, doğrulanmadı.

### Sınırlar

- **Boş şablon kayıtlar.** İznik'te 46 mahallenin 19'u (küçük eski köyler,
  44-244 kişi) `HouseHold=0`, `HouseIncome=4885`, `AgeDensity="0-4"` ile
  geliyor: mahalle düzeyi veri yok, dolgu. Tanı kuralı: `HouseholdCount==0`.
  Bu kayıtlar sayı olarak alınmaz; TÜİK 18± ve cinsiyet ile kalır.
- Zaman serisi yok (emlak satış serileri hariç). Yıllık seri TÜİK/MEDAS'tan.
- "Pro" alanlar (mülk/kiracı, gelir vb.) arayüzde gizli ama API tam gönderiyor.
  **Lisans:** raw/ altında araştırma kopyası tutmak ile VeriAtlas sitesinde
  yayımlamak ayrı konular; yayım kararı verilmedi.

### Nasıl çekiliyor

Yanıt AES-ECB ile şifreli; istemcideki `window.encodeResponse(str)` çözüyor
(anahtar `main.core.min.js` içinde sabit). Sayfa dışından çağırmak yerine
giriş yapılmış Endeksa sekmesinde JS çalıştırılıyor:

1. Tarayıcı panelinde `endeksa.com/tr/analiz/turkiye/<il>/<ilçe>/demografi`
   açık ve oturum girili olmalı. `localStorage.accessToken` kullanılıyor.
2. İlçe: `GET .../demography/Values?CityId=&CountryId=1&CountyId=&Level=2`
   → `SubRegionals[]` mahalle listesi ve `DistrictId`'ler.
3. Her mahalle: `...&DistrictId=<id>&Level=3`, **2,5 sn aralıkla**, hata
   olursa 5 sn bekleyip 3 deneme. Arka arkaya hızlı istek oturumu birkaç
   dakika kesiyor ("Failed to fetch"); bekleyince açılıyor.
4. Sonuçlar `window.__job.out[DistrictId]`'de birikir; bitince parça parça
   okunup `raw/endeksa/<district_id>/<DistrictId>-<ad>.json` yazılır.
5. Geometri: `geo/map?...&level=2&subGeometries=true` tek istek, ilçe başına
   bir `geo.json`.

CityId = plaka kodu. CountyId Endeksa'ya özgü (İznik 1420); ilçe sayfası
açıldığında `geo/coding?countryname=turkiye&cityname=&countyname=` önbellekte
görülüyor, oradan alınır.

### MEDAS eşlemesi

Endeksa `DistrictId` ≠ MEDAS kodu. Ancak İznik'te eski köy mahallelerinin
DistrictId'si (1838xx-1839xx) MEDAS koduyla aynı aralıkta; merkez mahalleler
(11415-11421) farklı. Eşleme ad + ilçe üzerinden, `settlements.csv`'ye
`endeksa_id` sütunu olarak.

### Seçim

`app.endeksa.com/election?CityId=&CountryId=1&CountyId=&DistrictId=&Level=3`
— **şifresiz düz JSON**, mahalle düzeyinde, 17 seçim (2011 genel → 2024
yerel; cumhurbaşkanı turları, 2017 referandum, 2019/2024 yerelde ilçe/meclis/
büyükşehir ayrı). Her kayıt: `SandikSayisi`, `KayitliSecmen`, `KullanilanOy`,
`GecerliOy`, `GecersizOy`, `Secenekler[]` (parti/aday, `OySayisi`). Kayıtlı ve
kullanılan oy var — TÜİK'e gerek yok. `Oran` alanı güvenilmez (2014 yerelde
%34,66 yerine 3466 yazıyor); oran `OySayisi/GecerliOy` ile hesaplanır.
Küçük partiler "Diğer" altında toplanmış; tam liste YSK'dan.

`fellowcountryman` de düz JSON. Yalnız `demography/Values` ve `geo/map`
şifreli; `parse = JSON.parse || encodeResponse` ile ikisi de tek fonksiyonla
okunur.

### İznik dökümü (2026-08-22)

`raw/endeksa/TR-16-006/`: `county.json`, 46 × `<DistrictId>-<ad>.json`,
`geo.json` (47 poligon: 46 mahalle + ilçe), `fellowcountryman.json`,
`election.json`. 46 mahalle adı MEDAS listesiyle birebir eşleşti.
`DistrictType` her mahallede "BELEDİYE MAHALLESİ" — köy/belde ayrımını Endeksa
vermiyor, MEDAS kod sırası (ilk 7 merkez, Boyalıca/Elbeyli belde, kalan köy)
ve elle doğrulamayla yapılacak.

### Adapter (2026-08-22)

`src/veriatlas/adapters/endeksa.py` — `raw/endeksa/<ilçe>/` → olgu tablosu. Bir
gösterge = bir adapter sözleşmesi korunuyor; 23 sınıf `MEASURES` tablosundan
üretiliyor (`ENDEKSA_ADAPTERS`, `load.py endeksa_*` ile çalışır). Sözlük:
`indicators.toml` → yeni konular (eğitim, sosyoekonomik, konut, seçim), kırılımlar
(`education`, `ses`, `expense_item`, `dwelling_type`, `tenure`, `property_type`,
`election`, `option`, `origin`), 20 yeni gösterge.

- TÜİK kökenli sayımlar `measured`; SES/gelir/harcama/mülkiyet `estimated`.
- Placeholder mahalleler (`HouseholdCount == 0`) demografide atlanır, seçim ve
  hemşehride kalır. Ad eşleşmeyen mahalle **reddedilir** (KeyError).
- Seçim: `period_start` = sandık günü; aynı gün üç oylama `election` kırılımıyla
  ayrılır. Oyu `null` gelen seçenek (bağımsızlar, 2015 "Diğer") yazılmaz.
  2019'da mahalle dosyalarında ilçeninkinde olmayan **il genel meclisi** kodu var.
- İlçe satırı: Endeksa'ya özgü göstergelerde yazılır; nüfus/medeni/hane için
  yazılmaz (TÜİK'inki zaten ambarda, 48 kişi fark).
- İznik: 23 adapter, 20.021 satır, `public/fact-endeksa.parquet` (deneme; tam
  `load.py` koşusunda ana `fact.parquet`'e girer).
- `raw/` çalışma ağacında `C:\veri\raw`'a junction.
