# Soru

"gdh ort anne yaşı ilk olma yaşı doğum arası süre" — dördünü tablo olarak
(grafik değil, telefonda görünmüyor). Ayrıca doğum aralığı süresi neyi açıklıyor,
ilişki nasıl kuruluyor?

# Yol

Dört gösterge, iki kaynak. Ambarda yalnız ilk gösterge var:

- **GDH (genel doğurganlık hızı)** — ambarda hazır gösterge yok, türetildi:
  `births` / `population(sex=female, age 15-49)` × 1000, il ve ülke, 2019 & 2025.
- **Doğum aralığı** — `İllere ve Annenin Doğum Sırasına Göre Son İki Doğumu
  Arasındaki Ortalama Süre.xls` (masaüstü, henüz `raw/`e alınmadı), 2019-2025.
- **İlk doğumda ort. anne yaşı** — `İllere Göre İlk Doğumdaki Ortalama Anne Yaşı.xls`.
- **Ort. anne yaşı (tüm doğumlar)** — `İllere Göre Annenin Ortalama Yaşı
  (TR,DF_DOGUM_ANNE_ORTYAS_C,1.0).xlsx`.

Pencere 2019-2025: doğum aralığı serisi 2019'da başlıyor, ortak pencere o.

## Okuma tuzakları (ikisine de düşüldü, düzeltildi)

- Aralık dosyasında yıl sütunu blok başında **bir kez** dolu ve tipi karışık:
  `2025.0` sayı ama `2024(r)` metin. Yalnız `isinstance(float)` ile okuyunca ara
  bloklar sessizce 2025'e yazıldı ve TR 2025 değeri 4,76 yerine 4,60 çıktı.
  Rakam süzen `year_of()` ile düzeltildi — düzeltince TR 4,62→4,76 ve r=0,64
  `docs/dogurganlik-evlilik-notlari.md` Bulgu 6/8 ile birebir tuttu (doğrulama).
- `.xlsx` dosyası `openpyxl` ile **`read_only=False`** açılmalı; `read_only=True`
  bu dosyada 1 satır döndürüyor (not zaten Bulgu 4'te vardı).
- İl adı → `area_id` eşlemesi `src/veriatlas/data/areas_tr.csv` üzerinden;
  `meta.json`'daki `area_labels` yalnız bölgeleri tutuyor, il yok.

# Sorgu

```sql
-- GDH: 1.000 kadın (15-49) başına canlı doğum
with w as (
  select area_id, year(period_start) y, sum(value) women from fact
  where indicator_id='population' and dims like '%sex=female%'
    and cast(regexp_extract(dims,'age=([0-9]+)',1) as int) between 15 and 49
    and area_level in ('province','country') and year(period_start) in (2019,2025)
  group by 1,2),
b as (
  select area_id, year(period_start) y, sum(value) births from fact
  where indicator_id='births' and area_level in ('province','country')
    and year(period_start) in (2019,2025) group by 1,2)
select b.area_id, b.y, b.births*1000.0/w.women from b join w using(area_id,y)
```

xls/xlsx okuma ve tablo üretimi: scratchpad'deki `build.py` + `render.py`
(bu dosyadaki tuzak notları o iki betiğin özeti).

# Sonuç

81 il + Türkiye satırı, GDH'ye göre azalan sıralı tek tablo; sütunlar: GDH ‰ 2025,
ilk doğum yaşı 2025, ort. anne yaşı 2025, doğum aralığı 2025, aralık değişimi
2019→2025. Şablon kullanılmadı — grafik istenmedi, düz `<table>`. Türkiye satırı
`tr.tr-row` ile koyulaştırıldı (panel CSS'ine eklendi).

Korelasyonlar (81 il, 2025 kesiti):

| İlişki | r |
|---|---|
| GDH ~ doğum aralığı | −0,96 |
| GDH ~ ilk doğum yaşı | −0,74 |
| GDH ~ ort. anne yaşı | −0,48 |
| GDH düşüşü % ~ aralık değişimi (2019→2025) | +0,64 |

**Yeni bulgu:** kesitteki r = −0,96 not dosyasında yoktu; Bulgu 8 yalnız
*değişim* ilişkisini (r=0,64) kaydetmişti. Seviye ilişkisi neredeyse mekanik —
doğum aralığı tek başına il GDH'sinin dağılımını açıklıyor.

Mekanizma anlatısı Bulgu 6-8 ile aynı: doğurganlık düşüşü evlenmeyi/ilk doğumu
ertelemekten değil, ilk çocuktan sonraki aralığın açılmasından geliyor.
