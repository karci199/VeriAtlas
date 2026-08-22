# Endeksa — mahalle düzeyi kesit verisi

İlk deneme: İznik (TR-16-006), 2026-08-22. Ham yanıtlar `C:eriawendeksa<district_id>` (raw/ depo dışı, gitignore).

## Ne var

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

## Sınırlar

- **Boş şablon kayıtlar.** İznik'te 46 mahallenin 19'u (küçük eski köyler,
  44-244 kişi) `HouseHold=0`, `HouseIncome=4885`, `AgeDensity="0-4"` ile
  geliyor: mahalle düzeyi veri yok, dolgu. Tanı kuralı: `HouseholdCount==0`.
  Bu kayıtlar sayı olarak alınmaz; TÜİK 18± ve cinsiyet ile kalır.
- Zaman serisi yok (emlak satış serileri hariç). Yıllık seri TÜİK/MEDAS'tan.
- "Pro" alanlar (mülk/kiracı, gelir vb.) arayüzde gizli ama API tam gönderiyor.
  **Lisans:** raw/ altında araştırma kopyası tutmak ile VeriAtlas sitesinde
  yayımlamak ayrı konular; yayım kararı verilmedi.

## Nasıl çekiliyor

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

## MEDAS eşlemesi

Endeksa `DistrictId` ≠ MEDAS kodu. Ancak İznik'te eski köy mahallelerinin
DistrictId'si (1838xx-1839xx) MEDAS koduyla aynı aralıkta; merkez mahalleler
(11415-11421) farklı. Eşleme ad + ilçe üzerinden, `settlements.csv`'ye
`endeksa_id` sütunu olarak.

## Seçim

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

## İznik dökümü (2026-08-22)

`raw/endeksa/TR-16-006/`: `county.json`, 46 × `<DistrictId>-<ad>.json`,
`geo.json` (47 poligon: 46 mahalle + ilçe), `fellowcountryman.json`,
`election.json`. 46 mahalle adı MEDAS listesiyle birebir eşleşti.
`DistrictType` her mahallede "BELEDİYE MAHALLESİ" — köy/belde ayrımını Endeksa
vermiyor, MEDAS kod sırası (ilk 7 merkez, Boyalıca/Elbeyli belde, kalan köy)
ve elle doğrulamayla yapılacak.
