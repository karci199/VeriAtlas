# Ulaşım — bulgular ve durum

Yeni konu (`topic.ulasim`). Kaynak: masaüstünde yeni bulunan `Ulaşım/` klasörü, TÜİK
"İllere göre motorlu kara taşıtları sayısı" (Temmuz 2026, 81 il). Adaptör yazıldı
(`tuik_vehicles`), gösterge sözlükte (`vehicles`, birim `vehicle`, kırılım
`vehicle_type`: otomobil, minibüs, otobüs, kamyonet, kamyon, motosiklet, özel amaçlı,
traktör), depoya alındı ve ekrana eklendi.

**Tek kesit — zaman serisi yok.** Dosya yalnızca Temmuz 2026'nın fotoğrafı; önceki
yılların verisi masaüstünde yok.

**per_capita ekranda kasıtlı kapalı, ama `base` mekanizması açık.** Proje kuralı
"İl nüfusunun %'si" kipini (per_capita) yalnız insan ve insanların başına gelen
olayları (doğum, ölüm, evlenme, boşanma) nüfusa bölmeye izin veriyor
(`tests/test_indicators.py`, `test_only_people_and_their_events_may_be_divided_by_the_population`) —
taşıt insan değil, o kip ona kapalı. Ama sözlükteki genel `base` mekanizması (GDH'nin
doğurgan kadın 15-49 paydası için zaten vardı) herhangi bir göstergenin dilimine
bölünmeyi destekliyor; iki yeni taban eklendi: `base.population_total` (Bin kişi
başına) ve `base.household_count` (Hane başına), ikisi de `applies_to = ["vehicles"]`.
Ekranda DEĞER listesinde görünüyorlar.

Bir gerçek sorun çıktı ve düzeltildi: taşıt verisi tek kesit 2026 (Temmuz), nüfus ve
hane sayısı en son 2025'te bitiyor — yıl birebir eşleşmediği için oran hep "—"
dönüyordu. `web/explorer.js`'e `nearestDenominator` eklendi: tam yıl yoksa paydanın o
alan için en yakın yılı kullanılıyor. Bu, gelecekte tek-kesit bir gösterge eklenirse
tekrar karşılaşılacak bir durum — çözüm genel, yalnız taşıta özel değil.

## Bulgu 10 — motorlu taşıt/nüfus oranı, kıyı-iç ayrımını değil turizm/tarım ekseni gösteriyor

TR ortalaması: bin kişi başına 403,6 taşıt (34,7 milyon taşıt / 86,1 milyon nüfus, 2025).

En yüksek: Muğla 719, Burdur 691, Antalya 625, Çanakkale 613, Aydın 589, Manisa 589,
Isparta 571, Denizli 569, Nevşehir 563, Ankara 528 — turizm ve sera tarımı yoğun iller,
kişi başı 0,5-0,7 taşıt gibi mantıksız yüksek bir seviyede. İki olası mekanizma:
mevsimlik/ikinci konut sahiplerinin aracı o ile kayıtlı ama ADNKS nüfusuna girmiyor;
tarım işletmelerinin (özellikle sera) filosu kişi başına değil işletme başına.

En düşük: hep güneydoğu — Hakkari 44, Şırnak 73, Ağrı 79, Bitlis 87, Van 89, Bingöl 95,
Siirt 95, Diyarbakır 107, Batman 109, Muş 113. Aynı coğrafya önceki bulgularla
(akraba evliliği, kütük yerlilik oranı, evlenme yaşı) örtüşüyor — demografik davranışın
yanına maddi refah farkı da aynı haritaya düşüyor.

## Bulgu 11 — traktör: mutlak sayı ile pay farklı şeyler söylüyor

TR toplamı: 2.333.356 traktör, filonun %6,72'si.

**Mutlak sayıda en çok:** Manisa 113.060, Konya 105.456, İzmir 88.298, Bursa 82.007,
Ankara 76.299 — nüfusu/filosu zaten büyük iller, traktör sayısı büyük ama filo içindeki
payı düşük (Manisa %13, Ankara yalnızca %2,4).

**Payda en yüksek:** Ardahan %49,6 (filonun neredeyse yarısı traktör), Kars %38,3,
Muş %33,2, Yozgat %27,6, Ağrı %24,0, Çankırı %23,0, Kastamonu %21,9. Küçük illerde
traktör filonun baskın parçası — tarım dışında neredeyse başka taşıt yok demek.

**İkisi birlikte okunmalı:** Ardahan payda birinci ama mutlak sayıda (11.330) listenin
çok gerisinde; Manisa mutlakta birinci ama payda görece düşük. Tek sayı yanıltıyor.

## Bulgu 12 — hane başına taşıt, nüfus oranındaki turizm çarpıtmasını kısmen düzeltiyor

TR ortalaması hesaplanmadı ayrı (bkz. Excel), il uçları:

En yüksek: Muğla 2,02 taşıt/hane, Burdur 1,98, Antalya 1,89, Manisa 1,76, Nevşehir 1,74
— nüfus oranındaki aynı turizm/tarım illeri, ama sıralama hafif değişiyor (Manisa öne
çıkıyor, Manisa hanede yüksek çünkü traktör filosu aile işletmesi hanesine düşüyor).

En düşük: Hakkari 0,20 taşıt/hane (5 hanede 1 taşıt), Bingöl 0,32, Ağrı 0,35, Bitlis
0,36, Şırnak 0,37 — güneydoğu, nüfus oranıyla aynı sırada.

Hane başına oran nüfus oranındaki turizm çarpıtmasını **tam düzeltmiyor** (ikinci
konutlar MEDAS'ta ayrı hane sayılmıyor), ama doğu-batı ailesi büyüklüğü farkını devre
dışı bırakıyor — iki oran birlikte okunmalı, ikisi de tek başına yeterli değil.

## Durum

- ✔ Adaptör: `src/veriatlas/adapters/tuik_vehicles.py`
- ✔ Sözlük: `topic.ulasim`, `unit.vehicle`, `dim.vehicle_type`, `indicator.vehicles`
- ✔ Ekran: `scripts/export_web.py` içine `DATASETS`, `BROKEN_DOWN`, `fine` eklendi
- ✔ Ekranda oran kipleri: "Bin kişi başına" ve "Hane başına" (`base.population_total`,
  `base.household_count`, DEĞER listesinde) — `web/explorer.js`'e yıl-eşleşmesi yoksa
  en yakın yılı kullanan `nearestDenominator` genel düzeltmesiyle birlikte
- ✔ Excel: `scripts/build_vehicle_excel.py` → `cikti/tasit-analizi.xlsx` (İller + Notlar)
- Sıradaki iş: `Ulaşım/` klasöründeki diğer dosyalar henüz bakılmadı — marka dağılımı,
  yakıt cinsi, silindir hacmi (bunlar TR toplamı, il kırılımı yok), aylık kayıt/silinme
  sayıları (zaman serisi olabilir, kontrol edilmeli).
