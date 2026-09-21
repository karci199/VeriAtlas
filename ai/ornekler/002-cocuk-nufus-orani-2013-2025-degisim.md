# Soru
2013 vs 2025 karşılaştırması: çocuk nüfus oranı en fazla değişen oran olarak iller
az ve çok. Kent-kır ayrımı yapılabilir mi?

# Yol
public/population.csv.gz (warehouse.duckdb bu worktree'de yok — public CSV'den
hesaplandı). Kırılım `age`+`sex`, `level='province'`. Çocuk oranı = (0-4 + 5-9 +
10-14 nüfus toplamı) / (ilin toplam nüfusu, tüm yaş grupları) × 100, yıl 2013 ve
2025 için ayrı ayrı; fark = 2025 oranı − 2013 oranı.

Kent-kır kırılımı **yok**: `public/meta.json` → `dimensions` içinde yalnız `sex`,
`age`, `household_type`, `marital`, `residence` (residence = ilinde/il dışında
yaşıyor, kent/kır değil). En ince coğrafi kırılım il→ilçe→mahalle/köy; mahalle
"kent", köy "kır" sayılıp kaba bir vekil kurulabilir ama bu sözlükte tanımlı bir
gösterge değil, ayrı soru olarak ele alınmalı.

# Sorgu
```python
import gzip, csv
from collections import defaultdict

child_ages = {'0-4', '5-9', '10-14'}
data = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # area -> year -> [child, total]
names = {}
with gzip.open('public/population.csv.gz', 'rt', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        if row['level'] != 'province':
            continue
        yr = int(row['year'])
        if yr not in (2013, 2025):
            continue
        v = int(row['value'])
        area = row['area_id']
        names[area] = row['area']
        data[area][yr][1] += v
        if row['age'] in child_ages:
            data[area][yr][0] += v

rows = []
for area, byyear in data.items():
    if 2013 not in byyear or 2025 not in byyear:
        continue
    c13, t13 = byyear[2013]
    c25, t25 = byyear[2025]
    rows.append((area, names[area], c13/t13*100, c25/t25*100, c25/t25*100 - c13/t13*100))

rows.sort(key=lambda x: x[4])
```

# Sonuç
81 ilin hepsinde 0-14 yaş oranı düştü — artan tek il yok. En sert düşüş Van
(−9,17 puan), Ağrı, Hakkari, Şırnak, Siirt (hepsi 2013'te en genç nüfuslu doğu
illeri). En az değişenler Tunceli (−1,39), Çanakkale, Yalova, Tekirdağ,
Kırklareli — hepsi zaten düşük çocuk oranıyla başlayan batı illeri.
Şablon: dumbbell (PATTERN 3), 10 satır (üstte 5 en çok düşen, altta 5 en az
değişen, aralarında 20px boşluk). Dikkat: dar aralıklı satırlarda (batı illeri)
iki etiket üst üste bindiği için label'ları çizginin üstüne/altına ayırdım
(gap<35px koşulu).
