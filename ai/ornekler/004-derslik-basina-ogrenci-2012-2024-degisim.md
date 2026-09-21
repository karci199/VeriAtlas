# Soru
Derslik başına öğrenci sayısı illere göre en eskiden en yeniye değişim.

# Yol
Aynı kaynak: [003-derslik-sube-basina-ogretmen-ogrenci.md](003-derslik-sube-basina-ogretmen-ogrenci.md)'teki
Derslik ve Öğrenci `.xls` dosyaları, ama bu kez tek yıl (2024) yerine tüm
yıllar (2012-2024) parse edildi. Değişim = 2024 oranı − 2012 oranı (dosyaların
kapsadığı ilk ve son yıl).

# Sorgu
```python
import pandas as pd

BASE = r"C:\Users\katan\OneDrive\Desktop\demografi"
FILES = {
    'derslik': 'İllere ve Yıllara Göre Eğitim Düzeyi Derslik Sayıları.xls',
    'ogrenci': 'İllere ve Yıllara Göre Eğitim Düzeyi Öğrenci Sayıları.xls',
}
TOTAL_LEVELS = ['Okul Öncesi', 'İlkokul', 'Ortaokul', 'Ortaöğretim']

def parse_file(path):
    df = pd.read_excel(path, header=None)
    prov_row = df.iloc[1, 3:]
    provs = {}
    for col, val in prov_row.items():
        if isinstance(val, str) and '-' in val:
            name, code = val.rsplit('-', 1)
            provs[col] = (name.strip(), int(code))
    level_col = df.iloc[:, 1].ffill()
    year_col = df.iloc[:, 2]
    out = {}
    for i in range(len(df)):
        lvl, yr = level_col.iloc[i], year_col.iloc[i]
        if pd.isna(lvl) or pd.isna(yr):
            continue
        lvl = str(lvl).strip().replace('\t', '')
        out[(lvl, int(yr))] = {code: df.iloc[i, col] for col, (name, code) in provs.items()}
    return out, provs

results, provs = {}, {}
for key, fn in FILES.items():
    data, p = parse_file(BASE + "\\" + fn)
    results[key] = data
    provs.update(p)

years = sorted(set(y for (l, y) in results['derslik'].keys()))
y0, y1 = years[0], years[-1]  # 2012, 2024

def totals_for(key, yr):
    tot = {}
    for lvl in TOTAL_LEVELS:
        for code, v in results[key][(lvl, yr)].items():
            tot[code] = tot.get(code, 0) + (v if pd.notna(v) else 0)
    return tot

d0, o0 = totals_for('derslik', y0), totals_for('ogrenci', y0)
d1, o1 = totals_for('derslik', y1), totals_for('ogrenci', y1)
# oran(code, yıl) = o[code] / d[code]; fark = oran(y1) - oran(y0)
```

# Sonuç
Şablon: dumbbell (PATTERN 3), 10 il (üstte 5 en çok düşen, altta 5 en az
değişen — biri artan, seri-3 renkli).

81 ilin 80'inde derslik başına öğrenci düştü. En sert düşüş Van (44,84→23,89,
−20,96), Batman, Ağrı, Şanlıurfa, Diyarbakır — 2012'de en kalabalık
dersliklere sahip iller. En az değişen Burdur (−1,09, neredeyse sabit),
Tunceli, Uşak, Muğla, Çanakkale. **Tek istisna Kilis**: 29,08→32,11 (+3,03) —
2012 sonrası sınır bölgesindeki nüfus hareketiyle örtüşüyor, ayrıca not
edildi.

Dikkat: bu veri de warehouse'a alınmadı, panele işlendi. Yıl aralığı dosyaya
bağlı (2012-2024) — "en eski/en yeni" ifadesi dosyanın kapsadığı aralıkla
sınırlı, TÜİK/MEB'in daha eski verisi varsa dahil değil.
