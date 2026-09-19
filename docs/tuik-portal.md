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

## Dosya indirme (2026-09-18)

`scripts/fetch_tuik_portal_files.py` katalogdaki 2.262 indirme bağlantısını geziyor.
**1.406 dosya indi (%62), 178 MB** — oturum burada durduruldu, çekici kaldığı yerden
devam eder (inen dosya atlanıyor).

**Kısıtlama tuzağı:** uç nokta hızlı istekte dosya yerine 200 + küçük HTML döndürüyor.
İlk tur saniyede beş istekle 2.262'den yalnız 78 dosya aldı ve gerisini "bozuk" saydı;
aynı jeton tek başına istendiğinde 104 KB'lık Excel geldi. İstek arası 1,2 sn ve HTML
cevabın artan beklemeyle beş kez denenmesiyle başarı oranı %3,5'ten **%96'ya** çıktı.

Dosyalar eski BIFF `.xls` (openpyxl açamaz, `xlrd` açıyor).

### MEDAS'ta olmayıp buradan çıkanlar

İnen 1.406 dosyanın 143'ü coğrafi kırılımlı (%10). MEDAS'ın 92 veritabanında karşılığı
olmayanlar:

| Ne | Düzey | Not |
|---|---|---|
| **İl düzeyinde işsizlik / istihdam / işgücüne katılma oranı** | 81 il, 2022-2025 | MEDAS'ta en alt İBBS2'ydi; depoda işsizlik Eurostat'tan dolaylı geliyordu. Güven aralıklarıyla |
| İBBS-3 suç türüne göre ceza infazına giren/çıkan hükümlü | il | suçun işlendiği il **ve** daimi ikametgâh ayrı |
| Cumhuriyet Başsavcılıkları soruşturma iş durumu | il, 2006-2013 | güncel yıllar yok |
| Okul, şube, öğrenci, öğretmen, derslik sayısı | İBBS 1-2-3 | MEB robots engelinin kapattığı boşluk |
| Okullaşma oranı, kurs ve kursiyer sayısı | il | |
| Bölgesel fiyat düzeyi endeksi ve satınalma gücü paritesi | 26 bölge | gelir karşılaştırmalarını düzeltir |
| Göç etme **nedenine** göre illerin aldığı/verdiği göç | il | depoda göç var, nedeni yok |
| Aile Yapısı Araştırması (akraba evliliği, başlık parası, nikah türü) | İBBS1 + üç büyük il | |
| İllere göre kamu hizmetlerinden memnuniyet, belediye hizmetleri | il | |

## Ortalama madde fiyatları (2026-09-19)

`average_item_price` — TÜFE madde sepetindeki **409 maddenin Türkiye ortalama fiyatı, TL,
aylık, 2003-01 ile 2022-04 arası**; 84.290 satır. Endeks değil gerçek fiyat: ekmek 2003
Ocak'ta 1,03 TL, 2022 Nisan'da 13,74 TL. Kaynak portalın `01839` numaralı dosyası, dün
gece indirilen 2.247 dosyadan biri — kazıma yok, dosya zaten depoda.

İl kırılımı yok ve olmayacak: TÜİK madde fiyatlarını yalnız Türkiye geneli yayımlıyor.

Üç tuzak, üçü de sessiz:

1. **Yıl sütunu tip değiştiriyor.** 2008 Aralık'a kadar sayı (`2008.0`, üstünde YTL),
   2009 Ocak'tan sonra metin (`"2009"`, üstünde TL). `isinstance(year, float)` diyen bir
   okuyucu 2003-2008 ile 2016-2022'yi alıp **aradaki 84 ayı düşürüyor** — ve sonuç sağlıklı
   görünüyor, çünkü kalan aylar iki uçta da kesintisiz. İlk sürümümüz tam bunu yaptı.
2. **Aynı satırda iki para birimi.** 2005 başında liradan altı sıfır atıldı; pirinç Aralık
   2004'te 2.545.872, Ocak 2005'te 2,55. 2005 öncesi milyona bölünüyor, yoksa seri tek ayda
   milyon kat çöküyor.
3. **Uzantı yalan söylüyor.** Portal her şeye `.xls` adı veriyor; bu dosya gerçek BIFF, ama
   kardeşi (`seçilmiş maddelere ait ortalama fiyatlar`) `.xls` adlı bir **xlsx**. Biçim ilk
   iki bayttan (`PK`) anlaşılmalı, addan değil.

**Otomobil de sepette.** Dizel otomobil Nisan 2022'de ortalama 715.454 TL, benzinli
523.209 TL — "yıllara göre araba fiyatı" sorusu için Wayback'e gerek yok.
