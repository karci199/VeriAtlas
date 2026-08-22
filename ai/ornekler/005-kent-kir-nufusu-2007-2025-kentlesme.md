# Soru
2007'den bugüne iller için 18+/18- ve toplam mahalle nüfusları, kent-kır ayrımı
yapılabilir mi. ("AATOPLU 7H.xlsx"tan 2012 sonrası için yardım alınabilir; ya da
MEDAS'tan indir dendi — çok veri olduğu için.)

# Yol
MEDAS'a gitmeye gerek kalmadı: masaüstünde zaten `İllere Göre Kent Kır Nüfusu.xls`
duruyordu (81 il × 2007-2025, köy/şehir nüfusu ayrı sütun). `İlçelere Göre Kent Kır
Nüfusu.xls` de var (ilçe düzeyi, kullanılmadı).

**Kritik sınır — 6360 sayılı kanun:** 2013 verisinde tam 30 büyükşehir ilinde köy
hücresi boş — 2012'de büyükşehir belediye sınırı il sınırına genişletildi, köy/belde
tüzel kişiliği kalktı, tüm il nüfusu "şehir" sayıldı. Bu 30 ilde kentleşme sıçraması
gerçek değil, hukuki. Değişim analizi bu yüzden yalnız büyükşehir olmayan 51 ile
uygulandı.

**18+/18- kırılımı için MEDAS'ın kendi sınırı:** `scripts/fetch_medas_settlement_totals.py`
docstring'i zaten belgeliyor — MEDAS'a 18+ kırılımı sorulduğunda "Köy" ve "Belediye"
düzey kutusundan tamamen düşüyor, yalnız "Mahalle" kalıyor. Yani sunucu köy nüfusunu
yaşa göre hiç kırmıyor; bu AATOPLU'dan da çıkmaz, farklı bir MEDAS sorgusuyla da
çözülmez. Mahalle (kent) tarafı için 18+/0-17 zaten ambarda:
`public/population-neighbourhood.csv.gz` (2013-2025, `TR-NN-...` id'siyle il'e
bağlanabilir).

# Sorgu
```python
import pandas as pd

fn = r"C:\Users\katan\OneDrive\Desktop\demografi\İllere Göre Kent Kır Nüfusu.xls"
df = pd.read_excel(fn, header=None)

year_col = df.iloc[:, 0].ffill()
data, names = {}, {}
for i in range(5, len(df)):
    yr = year_col.iloc[i]
    prov = df.iloc[i, 1]
    koy, sehir = df.iloc[i, 2], df.iloc[i, 3]
    if pd.isna(yr) or not isinstance(prov, str) or '-' not in prov:
        continue
    name, code = prov.rsplit('-', 1)
    code = int(code)
    names[code] = name.strip()
    data.setdefault(int(yr), {})[code] = (
        int(koy) if pd.notna(koy) else None,
        int(sehir) if pd.notna(sehir) else None,
    )

# 2013'te koy is None olan 30 il = buyuksehir; degisim analizini disinda tut
metro30 = {code for code, (koy, sehir) in data[2013].items() if koy is None}

rows = []
for code, name in names.items():
    if code in metro30:
        continue
    k07, s07 = data[2007][code]
    k25, s25 = data[2025][code]
    if k07 is None or k25 is None:
        continue
    o07 = s07 / (s07 + k07) * 100
    o25 = s25 / (s25 + k25) * 100
    rows.append((name, o07, o25, o25 - o07))
rows.sort(key=lambda r: r[3])
```

# Sonuç
Şablon: dumbbell (PATTERN 3), 10 il (5 en çok kentleşen + 5 en az değişen).

51 büyükşehir-dışı ilin hepsinde 2007→2025 arası şehir nüfus oranı arttı —
kırsallaşan tek il yok. En hızlı kentleşenler Erzincan (%53,6→%76, +22,4 puan),
Düzce, Zonguldak, Aksaray, Niğde. En az değişenler Tunceli (+2,3, zaten 2007'de
%65 kentli), Karabük, Yalova, Rize, Kırıkkale — hepsi 2007'de zaten yüksek şehir
oranıyla başlamış.

Dikkat: bu tablo da warehouse'a alınmadı, yalnız panele işlendi. Kullanıcıya
mahalle (kent) 18+/18- toplamının il bazına indirgenip ayrı bölüm olarak
eklenebileceği teklif edildi — ambarda zaten var, MEDAS'a gitmeye gerek yok.
