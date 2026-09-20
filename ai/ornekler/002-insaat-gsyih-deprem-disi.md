# Soru
İnşaat GSYH grafiği yap, deprem bölgesi dışındaki tüm TR, yıllık.

# Yol
`warehouse.duckdb` (salt-okunur) · `province_gdp_chained`, kırılım `gdp_sector=f`
(NACE F, inşaat), `area_level='province'`, zincirlenmiş hacim. Seri 2000–2024;
il × sektör GSYH'si TÜİK'te iki yıl gecikmeli yayımlandığı için 2025 yok.

Deprem illeri il adından değil `area_id`'den süzülür (K: alan eşleşmesi kimliğe göre).
6 Şubat 2023 OHAL kapsamındaki 11 il: Adana, Adıyaman, Diyarbakır, Elazığ, Gaziantep,
Hatay, Kahramanmaraş, Kilis, Malatya, Osmaniye, Şanlıurfa. `areas_tr.csv`'den ad ile
kimliğe çevrilir ve 11 tane bulunduğu doğrulanır — bulunamayan ad sessizce düşmesin diye
`assert len(eq_ids)==11`.

# Sorgu
```sql
select area_id, year(period_start) y, value v
from fact
where indicator_id = 'province_gdp_chained'
  and dims = 'gdp_sector=f'
  and area_level = 'province'
```

Sonra Python tarafında iki gruba ayrılıp toplanır:

```python
grp = 'eq' if area_id in eq_ids else 'rest'
# yıl × grup toplamı; 'tr' = eq + rest
```

Toplam için `dims='gdp_sector=gdp'` ya da `total_sectors` satırı **kullanılmaz** —
sektör satırıyla birlikte toplanırsa çift sayım olur (toplama tuzağı).

# Sonuç
PATTERN 1 (çizgi grafik) + PATTERN 5 (2023 deprem işareti). İki seri: deprem bölgesi
dışı 70 il (düz, series-1) ve Türkiye toplamı (kesikli, series-2). Y ekseni milyar TL,
0–140 arası beş kademe; değerler ambarda bin TL olduğu için 1e6'ya bölünür.

Bulgu: 70 il 2017'de 116,1 milyar TL ile zirve yapıp 2024'te 95,2'ye inmiş (−%18,1).
Türkiye toplamının 2023 sonrası yükselişinin tamamı deprem illerinden geliyor:
2022→2024 deprem illeri +%126,4, diğer 70 il +%5,1. Deprem illerinin ülke inşaatındaki
payı %10,6'dan %20,4'e çıkmış.
