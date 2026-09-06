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

## Döküm durumu

`raw/endeksa/demography/` — Bursa (17 ilçe) ve Ankara (25 ilçe) tam, 2.511 mahalle.
İstanbul çekiliyor. `raw/` gitignore'da; depoya yalnız bu not girer.

Yayım ve lisans kararı verilmedi; şimdilik araştırma kopyası.
