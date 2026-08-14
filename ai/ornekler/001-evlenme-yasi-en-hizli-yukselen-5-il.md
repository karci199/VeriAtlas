# Soru
Ortalama evlenme yaşının en hızlı yükseldiği 5 il, çizgi grafik.

# Yol
warehouse.duckdb → `fact`, `indicator_id='mean_marriage_age'`, `dims='sex=total'`,
`area_level='province'`. Değişim = son yıl − ilk yıl (2001→2025). Türkiye serisi
(`area_level='country'`) referans çizgisi olarak eklendi.

# Sorgu
```sql
with base as (
    select area_id, extract(year from period_start) as yr, value
    from fact
    where indicator_id = 'mean_marriage_age'
      and area_level = 'province'
      and dims = 'sex=total'
),
span as (select min(yr) as y0, max(yr) as y1 from base),
delta as (
    select b0.area_id, b0.value as v0, b1.value as v1, b1.value - b0.value as diff
    from base b0
    join span s on b0.yr = s.y0
    join base b1 on b1.area_id = b0.area_id and b1.yr = s.y1
)
select area_id, v0, v1, diff from delta order by diff desc limit 5
```

# Sonuç
Bartın +8,2 · Tunceli +7,8 · Sinop +7,1 · Çorum +7,0 · Giresun +6,6 yıl.
Şablon: çizgi (PATTERN 1) + Türkiye referans çizgisi (PATTERN 4) + özet tablo.
Dikkat: çizgi sonu etiketleri son değerler kümelenince çakışıyor — y'leri elle
aralamak gerekti (≥14px aralık, gerekirse çizgiden uzaklaştır).
Eksen 22–36 sabitlendi ki dört tick (24/28/32/36) temiz otursun.
