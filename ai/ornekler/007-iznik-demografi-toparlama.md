# Soru
İznik için yaptıklarımızı hatırla, demografi klasöründeki ve arayüzden (endeksa.com)
toplanan tüm İznik verisini (yaş grubu, cinsiyet, 18+/-, medeni hal, eğitim, gelir vb.)
toparla — ne çıkıyor, sur içi/sur dışı, toplam kent-kır.

# Yol
Üç kaynak birleştirildi:
1. **Önceki oturum** (`docs/oturum-2026-08-13.md`, İznik demografisi 1935-2025 bölümü)
   — kent payı, ortanca yaş farkı, doğal artış.
2. **Masaüstü demografi klasöründeki dört .xls** (uzun/pivot format, `pd.read_excel`):
   - `iznikfull.xls` — ilçe geneli, yaş×cinsiyet×köy/şehir, 2007-2025 (78 sütun, uzun
     kategori adları `"Erkek ve 0-4 ve Köy"` biçiminde)
   - `iznik.xls` / `iznik_18.xls` — mahalle bazında toplam nüfus / 18+-18- (LONG format:
     col0=yıl(ffill), col1=mahalle adı-kod, col2..=değer — province dosyalarındaki WIDE
     formattan farklı, dikkat)
   - `hanehalkı tipleri iznik.xls` — ilçe geneli hanehalkı tipi, 2014-2025
3. **Kullanıcının endeksa.com'dan ekran görüntüsüyle attığı mahalle verisi** (üçüncü
   taraf, TÜİK değil) — hane halkı büyüklüğü, kişi başı/hane geliri, konut/işyeri/yazlık
   sayısı, medeni hal, eğitim düzeyi — 7 mahalle (Selçuk, Yeşilçami, Eşrefzade, Mustafa
   Kemal Paşa, Beyler, Mahmut Çelebi, Yeni).

# Sorgu
```python
import pandas as pd

BASE = r"C:\Users\katan\OneDrive\Desktop\demografi"

# iznikfull.xls: WIDE format, kategori basligi = "Erkek ve 0-4 ve Köy" gibi
df = pd.read_excel(BASE + "\\iznikfull.xls", header=None)
headers = df.iloc[2, 2:].tolist()
data = df.iloc[5:].reset_index(drop=True)
year_col = data.iloc[:, 0].astype(str)

def row_for_year(yr):
    idx = data.index[year_col == str(yr)][0]
    return dict(zip(headers, data.iloc[idx, 2:]))

def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0

def sum_by(d, cond):
    return sum(num(v) for k, v in d.items() if cond(k))

def age_of(k):
    parts = k.split(" ve ")
    return parts[1] if len(parts) > 1 else None

CHILD, OLD = {"0-4","5-9","10-14"}, {"65-69","70-74","75+","75-79","80-84","85-89","90+"}
r07, r12 = row_for_year(2007), row_for_year(2012)  # 2012 = 6360 oncesi son yil
koy07 = sum_by(r07, lambda k: "Köy" in k)
child07_koy = sum_by(r07, lambda k: age_of(k) in CHILD and "Köy" in k)
# ... (koy/sehir ayri 0-14 ve 65+ paylari boyle kurulur)

# iznik.xls / iznik_18.xls: LONG format
def load_long(fn, value_cols):
    df = pd.read_excel(BASE + "\\" + fn, header=None)
    body = df.iloc[5:].reset_index(drop=True)
    yr_col = body.iloc[:, 0].ffill().astype(int)
    out = {}
    for i in range(len(body)):
        mahalle = body.iloc[i, 1]
        if not isinstance(mahalle, str):
            continue
        name, _, _code = mahalle.rpartition("-")
        out.setdefault(yr_col.iloc[i], {})[name.strip()] = [num(body.iloc[i, c]) for c in value_cols]
    return out

pop18 = load_long("iznik_18.xls", [2, 3])  # [18+, 18-]
```

# Sonuç
Şablon: dumbbell (0-14 vs 65+ payı, ilçe geneli, 2007→2025) + üç metin bloğu +
mahalle tablosu (endeksa verisi, kaynağı üçüncü taraf diye işaretlendi).

**Ana bulgular:**
- 6360 kanunu İznik'te de ulusal örüntüyle örtüşüyor: köy nüfusu 2012'de %48,2,
  2013'te tam sıfır (Bursa büyükşehir olduğu için ilçe geneli "şehir" sayılmış).
- Kırsal her zaman şehirden daha yaşlı ve daha hızlı yaşlanıyor (köy 65+ payı
  2007→2012 %12,9→%14,6 vs şehir %9,2→%10,2).
- İlçe geneli 0-14 payı %21,5→%15,6, 65+ payı %11,1→%17,9 (2007→2025) — ulusal
  trendden daha keskin bir yaşlanma.
- Mahalle bazında merkez de yaşlanıyor (Selçuk 18+ payı %74,2→%79,3) ama en sert
  yaşlanma eski köylerde (Derbent, Gürmüzlü, Mustafalı: 18+ payı %93-100, neredeyse
  çocuk yok).
- Hanehalkı fragmantasyonu: tek kişilik hane %9,0→%12,5 (2014-2025).
- Mahalle geliri Selçuk'ta en yüksek (28.799 ₺ kişi başı), en kalabalık hanede
  (Yeşilçami/Eşrefzade ~3,2 kişi/hane) en düşük — klasik ters ilişki.

**"Sur içi / sur dışı" notu:** bu bir TÜİK kategorisi değil, sohbette bir öneri
olarak ortaya atıldı ama hiç hesaplanmadı — ne bu oturumda ne 13 Ağustos
oturumunda. Kaydedilirken bu ayrım "yapıldı" diye YAZILMADI, yalnızca not
düşüldü ki ileride karıştırılmasın.

Dikkat: `iznik.xls`/`iznik_18.xls` 2007'de yalnız 3 beldenin (İznik/Elbeyli/
Boyalıca) mahallelerini içeriyor, köy nüfusu bu dosyada hiç yok — MEDAS'ın köyde
yaş kırılımı sunmama sınırı burada da geçerli (bkz. [006 ve önceki kent-kır
notu](005-kent-kir-nufusu-2007-2025-kentlesme.md)).
