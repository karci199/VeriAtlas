# Soru
İllere göre derslik ve şube başına düşen öğretmen ve öğrenci sayısını hesapla,
en fazla ve en az.

# Yol
Bu gösterge VeriAtlas ambarında/public'te yok. Masaüstü demografi klasöründe
(bkz. [desktop_demografi_kaynak.md] hafıza notu) `Egitim/` alt klasörü değil,
ana klasörün kökünde dört .xls dosyası var:
- `İllere ve Yıllara Göre Eğitim Düzeyi Derslik Sayıları.xls`
- `İllere ve Yıllara Göre Eğitim Düzeyi Şube Sayıları.xls`
- `İllere ve Yıllara Göre Eğitim Düzeyi Öğretmen Sayıları.xls`
- `İllere ve Yıllara Göre Eğitim Düzeyi Öğrenci Sayıları.xls`

Format: gerçek eski-tip `.xls` (CDFV2 Excel), `pandas.read_excel` + `xlrd`
gerekiyor (proje bağımlılığı değil — `uv run --with xlrd --with pandas`).
Her dosya aynı pivot yapısı: satır bloğu = eğitim düzeyi (Okul Öncesi, İlkokul,
Ortaokul, Ortaöğretim, ve Ortaöğretim'in alt kırılımı olarak Genel + Mesleki ve
Teknik — bunlar TOPLAMA DAHİL EDİLMEDİ, sayılırsa çift sayım olur), her blokta
2012-2024 yıl satırları, sütunlar il ("Adana-1" biçiminde ad-plaka kodu, 81 il).

İl toplamı = Okul Öncesi + İlkokul + Ortaokul + Ortaöğretim (bu dördü ayrık,
toplamları il toplamını verir). Yıl 2024 — dört dosyanın da ortak son yılı.

# Sorgu
```python
import pandas as pd

BASE = r"C:\Users\katan\OneDrive\Desktop\demografi"
FILES = {
    'derslik': 'İllere ve Yıllara Göre Eğitim Düzeyi Derslik Sayıları.xls',
    'sube': 'İllere ve Yıllara Göre Eğitim Düzeyi Şube Sayıları.xls',
    'ogretmen': 'İllere ve Yıllara Göre Eğitim Düzeyi Öğretmen Sayıları.xls',
    'ogrenci': 'İllere ve Yıllara Göre Eğitim Düzeyi Öğrenci Sayıları.xls',
}
TOTAL_LEVELS = ['Okul Öncesi', 'İlkokul', 'Ortaokul', 'Ortaöğretim']

def parse_file(path):
    df = pd.read_excel(path, header=None)
    prov_row = df.iloc[1, 3:]  # "Adana-1" gibi hücreler
    provs = {}
    for col, val in prov_row.items():
        if isinstance(val, str) and '-' in val:
            name, code = val.rsplit('-', 1)
            provs[col] = (name.strip(), int(code))
    level_col = df.iloc[:, 1].ffill()  # düzey adı yalnız blok başında yazılı
    year_col = df.iloc[:, 2]
    out = {}
    for i in range(len(df)):
        lvl, yr = level_col.iloc[i], year_col.iloc[i]
        if pd.isna(lvl) or pd.isna(yr):
            continue
        lvl = str(lvl).strip().replace('\t', '')
        out[(lvl, int(yr))] = {code: df.iloc[i, col] for col, (name, code) in provs.items()}
    return out

results = {k: parse_file(BASE + "\\" + fn) for k, fn in FILES.items()}
YEAR = 2024
totals = {}
for key in FILES:
    tot = {}
    for lvl in TOTAL_LEVELS:
        for code, v in results[key][(lvl, YEAR)].items():
            tot[code] = tot.get(code, 0) + (v if pd.notna(v) else 0)
    totals[key] = tot
# oranlar: totals['ogretmen'][code] / totals['derslik'][code], vb.
```

# Sonuç
Şablon: yatay çubuk (PATTERN 2), 4 gösterge × en çok/en az = 8 mini grafik
(her biri 5 il).

**Derslik başına öğretmen:** en çok Mersin (1,88), Eskişehir, İzmir; en az
Ardahan ve Ağrı (1,15).
**Derslik başına öğrenci:** en çok Kilis (32,11), Şanlıurfa, Gaziantep; en az
Ardahan (13,7), Gümüşhane, Tunceli.
**Şube başına öğretmen:** en çok Kırşehir (1,79), Karabük; en az Ağrı (1,05),
Kars.
**Şube başına öğrenci:** en çok Gaziantep (27,97), İstanbul, Şanlıurfa; en az
Ardahan (14,44), Tunceli, Kars.

Örüntü: doğu illerinde (Ağrı, Kars, Ardahan, Bitlis) az öğrenciye çok
derslik/şube düşüyor — küçük, seyrek yerleşim; güneydoğu ve büyükşehirlerde
(Kilis, Şanlıurfa, Gaziantep, İstanbul) tam tersi — sınıf sıkışıklığı.
Dikkat: bu veri warehouse'a alınmadı, yalnız panele işlendi — tekrar
sorulursa aynı .xls dosyalarından aynı yolla hesaplanmalı.
