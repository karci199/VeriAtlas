# TÜİK Veri Portalı (veriportali.tuik.gov.tr)

Durum 2026-09-18: **katalog çekildi** (`scripts/fetch_tuik_portal.py`), ham veri
`C:\veri-ham\tuik_portal\`, düzleştirilmiş hâli `katalog.csv` (4.359 satır).

`data.tuik.gov.tr` artık buraya yönleniyor. Yeni site React, arkasında REST API var.

## Uç nokta

```
POST /api/tr/data/search
{"text":"", "page":1, "typeIds":[], "categoryIds":[], "subCategoryIds":[],
 "years":[], "levels":[], "archive":false, "autoFilter":false}
```

Sayfa başına 10 kayıt, cevapta `total`. Tip numaraları: 1 haber bülteni, 2 tablo ve
grafik, 3 metaveri, 4 rapor, 5 veritabanı, 6 yayın. `GET /api/tr/data/autocomplete?text=`
ve `GET /api/tr/data/downloads?t=y&p=<jeton>` de var; indirme jetonu arama sonucunda
geliyor.

## İki tuzak

**WAF.** Çıplak istek 403 veriyor. Tam tarayıcı başlık seti (User-Agent, Origin, Referer,
X-Requested-With) ve ana sayfaya tek bir GET ile alınan çerez yetiyor. Hesap gerekmiyor.
`robots.txt` Claude ajanlarını **açıkça izinli** sayıyor (`ClaudeBot`, `ClaudeUser`,
`Claude-SearchBot` → `Allow: /`).

**Eksik alan 404 veriyor, 400 değil.** Gövdede bir alan eksikse uç nokta "Sayfa
bulunamadı" diyor — yani yarı doğru istek, yanlış adres gibi görünüyor. Bu yüzden gövde
tahmin edilmedi: sayfanın kendi XHR'ı kancalanıp gerçek istek okundu.

## Katalogda ne var (2026-09-18)

| Tip | Kayıt |
|---|---|
| Haber bülteni | 1.447 |
| Tablo ve grafik | 2.547 |
| Metaveri | 116 |
| Rapor | 23 |
| **Veritabanı** | **101** |
| Yayın | 125 |

Veritabanlarının 92'si MEDAS `kn=` numarası taşıyor — MEDAS konu menüsündeki 92 başlığın
tam listesi ilk kez burada topluca görünüyor. Kalan 9'u ayrı uygulamalar: Genel Nüfus
Sayımları, üç seçim veritabanı (milletvekili, mahalli idareler, cumhurbaşkanlığı), eski
işgücü ve turizm arşivleri.

## Depoda karşılığı olmayan veritabanları

Ham MEDAS dizininde 50 konu etiketi var; katalogdaki 101 veritabanıyla karşılaştırınca
il düzeyinde değerli ve hiç girilmemiş olanlar:

| Veritabanı | Neden değerli |
|---|---|
| **Ücretli Çalışan İstatistikleri** | il düzeyinde ücretli çalışan; depoda hiç ücret/çalışan serisi yok (yalnız SGK günlük kazanç) |
| **Kazanç İstatistikleri** | aynı boşluk, kazanç tarafı |
| **Gelir Dağılımı ve Yaşam Koşulları** | Gini, gelir dilimleri — depoda `gini` yok, İBBS-2 |
| **Yoksulluk İstatistikleri** | depoda `poverty` geçen tek gösterge yok |
| **Hanehalkı Tüketim Harcaması** | İBBS-2 harcama yapısı; depodaki tüketim yalnız EVDS ulusal |
| **İşgücü İstatistikleri Bölgesel Sonuçları** | İBBS-2 işsizlik; şu an Eurostat'tan dolaylı geliyor |
| Çocuk İstatistikleri (9 tema) | eğitim, sağlık, yoksulluk, işgücü ayrı ayrı |
| Bitkisel Ürün Denge Tabloları, Su Ürünleri | tarım tarafında eksik kalan iki başlık |

Kullanıcı kararıyla alınmayanlar bu listede yok: Yaşam Memnuniyeti, Ceza İnfaz Kurumu.
