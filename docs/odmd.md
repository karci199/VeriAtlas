# ODMD — otomotiv satış verisi

Otomotiv Distribütörleri ve Mobilite Derneği (odmd.org.tr). Robots.txt yok. İlk çekim
2026-09-26; ham `C:\veri-ham\odmd\` (`perakende/`, `pazar/`, liste başlıkları `liste.json`).

## İndirme

Önce liste sayfası (`web_2837_1/neuralnetwork.aspx?type=<liste>`) açılır — ASP.NET oturum
çerezi gelir. Sonra `wf_docudownload.aspx?primary_id=<id>&type=<liste>&...` dosyaya
yönlenir; çerezsiz aynı adres boş HTML döndürür (hata değil, boş). Liste sayfaları
`sortial.aspx?linkpos=<n>&type=<liste>`. Simge adı `icon_excel` ama `icon-pdf`.

## Depoda

| Gösterge | Kaynak | Kapsam |
|---|---|---|
| `odmd_retail_sales` | Perakende Satışlar (type 36) Excel + PDF | aylık 2014-01 → 2026-08; 2012-13 kısmi |
| `odmd_retail_sales_annual` | aynı, yıllık dosyalar | 2005-2009, 2013-2025 |
| `odmd_car_sales_by_segment_body` | Pazar Değerlendirme (type 35) PDF, Ek 4 | 2020-2025 |
| `odmd_car_sales_by_powertrain` | Ek 5 | 2020-2025 |
| `odmd_car_sales_by_co2` | Ek 7 | 2019-2025 |
| `odmd_car_sales_automatic` | Ek 8 | 2019-2025 |
| `odmd_lcv_sales_by_body` | Ek 9 | 2020-2025 |
| `odmd_lcv_sales_by_powertrain` | Ek 10 | 2023-2025 |

Perakende: marka × otomobil/hafif ticari × yerli üretim/ithal. Sütunlar YERLİ/İTHAL/TOPLAM
başlığından konumla okunur (sıfırlar bazen boş ya da `-`). "2016 Yılı (Ocak)" gibi başlıklar
aydır, yıllık değil; yıllık yalnız "Ocak-…" ya da ay adı geçmeyen başlıktır ve yalnız yıl
tamamsa alınır. Tesla satırı ODMD tahmini → `estimated`.

Pazar tabloları: Aralık raporunun "Ocak-Aralık" bölümünden, eksik tablo bir sonraki Aralık
raporunun geçen yıl sütunundan. Tablo bulucu değil metin okunur (çizgisiz tablolar). Bazı
raporlarda tablo resim; OCR yok, o tablo o yıl yok. Toplam satırı ve otomobil toplamları
(segment = motor tipi = CO2) tutmazsa yükleme durur; 2020-2025 toplamları Excel perakende
ile birebir.

## Alınmayanlar

- Perakende PDF'lerinden 23'ü (2010-2012 çoğu, 2013 Mayıs, 2004): boş hücreler yazılmamış ya da
  tablo metin katmanında eksik; sütuna yerleştirilemiyor (`UNREADABLE_PDFS`). Kalan 21 PDF
  sözcük konumuyla okunur ve toplam denetiminden geçer.
- Pazar raporları 2006-2019: tablo yok, yalnız yazı. Aylık Ek tabloları: raporların
  yarısında bir kısmı resim; aylık seri kurulmadı.
- Ek 6 motor hacmi: bantlar ÖTV dilimine göre yıldan yıla değişiyor.
- Avrupa/dünya pazarı (ACEA), kredi, sigorta, sahibinden "enleri" raporları.
- Model kırılımı ODMD'de yok.

## Kullanım kaydı

Her perakende dosyasının altında: bilgiler haksız rekabete yol açacak şekilde kullanılamaz;
ODMD kaynak gösterilerek Rekabet Kanunu'na aykırı yorum, sıralama ve açıklama yapılamaz.
Depoda tutmak sorun değil; sitede marka sıralaması yayımlanmadan önce bu kayıt gözetilmeli.
