# Soru
sen kayseri yıllara göre kent kır nufusu ve kentlesme oranuı yap ama duzeltmeler yap gecmıste

# Yol
`warehouse.duckdb`, `population`, mahalle ve köy düzeyi; sınıf `kullanici_karar.json`. Kapanan kimlikler eski belediye ve ad bilgisiyle
bugünkü sınıfa bağlanır. Yerel seçim öncesi yıl sonları (2008, 2013, 2018, 2023) ilçe × sınıf bazında komşu yılların ortalamasıyla düzeltilir.

# Sorgu
```bash
python scripts/analiz/kent_kir_2026_09_27/il_kent_kir_seri.py 38
```
```sql
select area_id, year(period_start), dims, sum(value) from fact
where indicator_id='population' and area_id like 'TR-38-%' and area_level in ('neighbourhood','village')
group by 1,2,3;
```

# Sonuç
Çizgi grafik (ham ve düzeltilmiş), yıllık tablo, ilçe tablosu. 2007 %81,1 → 2025 %87,5. Ham seride 2018 ve 2023'te 1,3 ve 1,2 puanlık düşüş düzeltmeyle kalktı.
Sıçramanın seçim kaydı olduğu zamanlamadan çıkarıldı, ayrıca kanıtlanmadı.
