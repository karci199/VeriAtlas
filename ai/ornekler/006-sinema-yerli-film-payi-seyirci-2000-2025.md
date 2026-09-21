# Soru
Demografi klasörüne 4 adet sinema dosyası eklendi (Film, Koltuk, Salon, Seyirci
Sayısı) — neler çıkarılabilir?

# Yol
Dört dosya da aynı pivot yapısı: il × yıl (2000-2025). Film ve Seyirci
"1. (Yerli)" / "2. (Yabancı)" kırılımlı; Koltuk ve Salon kırılımsız
("Ölçüm bazında" tek satır). Kişi başına seyirci için VeriAtlas'ın kendi
`public/population.csv.gz` (2025, il toplamı) ile birleştirildi.

# Sorgu
```python
import pandas as pd

BASE = r"C:\Users\katan\OneDrive\Desktop\demografi"
FILES = {
    'film': "İllere Göre Sinema Film Sayısı.xls",
    'koltuk': "İllere Göre Sinema Koltuk Sayısı.xls",
    'salon': "İllere Göre Sinema Salon Sayısı.xls",
    'seyirci': "İllere Göre Sinema Seyirci Sayısı.xls",
}

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
        if pd.isna(yr):
            continue
        lvl = str(lvl).strip() if pd.notna(lvl) else 'toplam'
        out[(lvl, int(yr))] = {code: df.iloc[i, col] for col, (name, code) in provs.items()}
    return out

results = {k: parse_file(BASE + "\\" + fn) for k, fn in FILES.items()}
# yerli pay(il, yıl) = seyirci[('1. (Yerli)', yıl)][code] / (yerli+yabancı)
# sinemasız il(yıl) = salon[('Ölçüm bazında', yıl)][code] == 0 olan iller
```

# Sonuç
Şablon: dumbbell (yerli film payı değişimi, 10 il) + 2 yatay çubuk (kişi başına
seyirci en çok/en az, 5'er il). Kullanıcı "çok kasma, tablo/basit grafik yeter"
dedi — sonraki benzer isteklerde ağır çok-figürlü bölüm yerine tek dumbbell +
küçük bar yeterli, gerekirse düz tablo da kabul.

**Ulusal:** yerli film seyirci payı 2000'de %17 → 2025'te %55; toplam seyirci
17,1M → 27,7M.
**İl bazında yerli pay artışı:** en çok Erzurum (%0,7→%65,4), Amasya, Karabük,
Karaman, Aksaray (dördü 2000'de %0-2'den başlamış). Tek düşen il Van
(%79,1→%62,2) — 2000'de zaten aşırı yüksekti, ortalamaya yakınsadı.
**Sinemasız il:** 2000'de 16 il, 2025'te yalnız Hakkari.
**Salon başına koltuk (multipleks etkisi):** 331 (2000) → 117 (2025) — büyük
tek salonlardan AVM içi çok-salonlu küçük salonlara geçiş.
**Kişi başına seyirci 2025:** en çok Eskişehir (0,60), Ankara, İstanbul,
Yalova, Sakarya; en az Hakkari (0), Bilecik, Tunceli, Kars, Ardahan.

Dikkat: bu veri de warehouse'a alınmadı, yalnız panele işlendi.
