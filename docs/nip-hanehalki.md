# NİP hanehalkı ve eğitim durumu dosyaları

Kaynak: TÜİK Nüfus İstatistikleri Portalı, <https://nip.tuik.gov.tr>. Portal veriyi
HTML tablo olarak, il başına bir istekle veriyor:

```
POST https://nip.tuik.gov.tr/Home/GetInformation
status=1&name=<ölçüm>&value=<İL ADI>
```

`name` sayfanın adresindeki `?value=` ile aynı (`HanehalkiBuyukluguneGoreHs`,
`HanehalkiTipi`). `value` boş bırakılınca Türkiye toplamı gelir; ilçe düzeyi yok.
`status=0` grafik parçasını döndürür ve **daha kaba**: hanehalkı büyüklüğünü 7 kovaya
indirir (1-6 ve "7+"), oysa tablo 10 kova verir. Çekilecek yer tablo ucudur.

Portalın "İndir" düğmesi aynı veriyi 81 ilin tamamı tek dosyada olacak şekilde Excel
verdiği için depoya bu dosyalar alındı; uç yalnızca doğrulama için kayda geçti.

## Dosyalar

`raw/tuik/hanehalki/` altında, ASCII adlarla:

| Dosya | Kapsam | Uzun format satırı |
|---|---|---|
| `household-size.xlsx` | il × 2012-2025 × 1..9, 10+ | 11.340 |
| `household-type.xlsx` | il × 2014-2025 × 4 tip | — (yazılmıyor) |
| `education-attainment.xlsx` | il × 2008-2025 × 9 seviye × (toplam/erkek/kadın) | 39.366 |
| `tenure.xlsx` | il × 2021 × ev sahibi/kiracı/diğer/bilinmeyen | 324 |
| `building-age.xlsx` | il × 2021 × 1980 öncesi/1981-2000/2001+/bilinmeyen | 324 |

Ayrıştırma `src/veriatlas/adapters/tuik_household_excel.py`'de; dört adaptör
(`tuik_household_size`, `tuik_education_attainment`, `tuik_household_tenure`,
`tuik_building_age`) `scripts/load.py` ile ambara yükleniyor:

```bash
uv run python scripts/load.py tuik_household_size tuik_education_attainment tuik_household_tenure tuik_building_age
```

Dikkat: `load.py` `fact` tablosunu baştan yazar, yani yalnız bu dördünü çalıştırmak
ambardaki diğer göstergeleri siler. Tam yükleme için betiği argümansız çalıştır.

`scripts/convert_household_excel.py` aynı ayrıştırıcıyı kullanıp `long/*.csv` dosyalarını
yazar ve yüklenmeyen hanehalkı tipi dosyasını ambardakiyle karşılaştırır.

## Dosyaların kendileri hakkında söylemediği dört şey

**`tenure` ve `building-age` yılsız.** Tek kesit, ama hangi yıl olduğu dosyada yazmıyor.
`Toplam` sütunu 81 ilin tamamında hanehalkı tipi dosyasının **2021** toplamına eşit,
başka hiçbir yıla değil. Betik bunu her çalışmada yeniden sınar — dosya yenilenirse
sayılar eski tarihe yazılmasın diye.

**`education-attainment` her satırı iki kez içeriyor.** 28.367 satır, 14.581 tekil.
Olduğu gibi toplanırsa her rakam ikiye katlanır. Betik yinelenenleri düşürür ve
kalan satır sayısını yıl × il × seviye ile karşılaştırır.

**`TOPLAM` bir seviye değil, satır.** Dokuz gerçek seviyenin toplamı; saklanırsa
kırılım üzerinden alınan her toplam iki katına çıkar. Atılıyor.

**İl adları büyük harfli geliyor** (`AFYONKARAHİSAR`), registry ise değil. Türkçe
büyük harfe çevirme `str.upper` değildir: `Siirt` → `SIIRT` olur ve il eşleşmez.
Registry tarafı `upper_tr` ile çevrilip birebir eşleştiriliyor; eşleşmeyen ad hata
veriyor.

## Hanehalkı tipi neden yazılmıyor

`household_by_type` ambarda zaten var: `adapters/tuik_simple.py` aynı 972 il-yılı
MEDAS'tan yüklüyor. Bu dosya yalnızca okunup o kayıtlarla karşılaştırılıyor, ikinci
bir kopya oluşturulmuyor — iki kopyanın zamanla ayrışması, tek kopyanın eksik
olmasından daha kötü.

İki dosya birbiriyle de tutarlı: büyüklük dosyasının 1-kişilik sütunu tip dosyasının
"Tek Kişilik Hanehalkı" sütununa, on kovanın satır toplamı da "Toplam" sütununa
972 il-yılın tamamında eşit. Dosyadaki 3.888 satır (81 il × 12 yıl × 4 tip; portal
Türkiye satırı vermiyor, ambarda o da var) ambardaki MEDAS kayıtlarıyla birebir aynı —
30 Ağustos 2026'da 0 fark.

## Bilinen sınır

Hepsi il düzeyinde. Portal ilçe vermiyor, dolayısıyla ilçe dosyası sayfasına bu
göstergeler doğrudan bağlanamaz.
