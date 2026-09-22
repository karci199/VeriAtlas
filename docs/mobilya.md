# Mobilya mağazaları (2026-09-22)

Gösterge `furniture_stores`, adaptör `networks.FurnitureStores`. Beş marka, 2.082 mağaza.

| Marka | Mağaza | Kaynak | Uç |
| --- | ---: | --- | --- |
| İstikbal | 657 | Boydak grubu marka API'si | `brandapi.erciyes.com/api/FirmApi/GetProvinceBrandFirms?Brand=İSTİKBAL&Code=<plaka>` |
| Bellona | 613 | aynı | `Brand=BELLONA` |
| Mondi | 329 | aynı | `Brand=MONDİ` |
| Doğtaş | 248 | Doğtaş-Kelebek ortak paneli | `services.dmgpanel.com/ajax/new-shops?mark=dogtas` |
| Kelebek | 235 | aynı | `mark=kelebek` |

Boydak API'si `istikbal.com.tr/sayfa/magazalarimiz` sayfasının arkasında, boş `Bearer`
başlığıyla açık, robots.txt'si yok (404). Sunucu yavaş (sorgu başına ~5 sn); 243 sorgu
yaklaşık 40 dakika. Çekici `C:\veri-ham\mobilya\erciyes_cek.py`. Enza Home, Yataş ve
Kilim aynı API'de marka adıyla sonuç vermedi. Bellona'nın kendi sitesinin robots.txt'si
genel ajanlara açık (`Crawl-delay: 30`).

## Tuzaklar

- **Git Bash "İ"yi bozar.** `curl --data-urlencode "Brand=İSTİKBAL"` sıfır kayıt döndürür,
  Bellona (ASCII) döndürür. Harf elle kodlanmalı (`%C4%B0`) ya da çekici Python'da yazılmalı.
- **Doğtaş/Kelebek'te koordinat metin alanında:** `google_maps_link` çoğu zaman
  `"41.0885, 29.0059"`; Kelebek'in 15 mağazasında kısa link, adres ya da boş. Bunlar
  panelin kendi ilçesiyle yerleşir (`Point.named_district`); panel merkez ilçeyi
  "Artvin Merkez" diye yazar.
- **Panelin kendi etiketi de yanılır:** "Kelebek Mobilya - Van Merkez" Van'da olmayan
  Yenimahalle ilçesine kayıtlı. Tahmin edilmedi, yerleşmemiş sayıldı.

## Bayi mi, kendi mağazası mı

Doğtaş ve Kelebek her mağazayı `Bayi`, `Perakende` (firmanın kendi mağazası) ya da
`Outlet` diye işaretliyor. Bu alanlar göstergeye girmedi (tek kırılım marka), ham
dosyada duruyor.

| | Doğtaş | Kelebek |
| --- | ---: | ---: |
| Bayi | 217 | 203 |
| Kendi mağazası | 24 | 26 |
| Outlet | 7 | 6 |
| Bayi payı, İstanbul + Ankara + İzmir | %68 | %64 |
| Bayi payı, diğer iller | %98 | %99 |
| Medyan mağaza alanı | 1.300 m² | 1.100 m² |
| Toplam satış alanı | 350.867 m² | 282.630 m² |
| 2021 ve sonrası açılan (bugün açık olanlar içinde) | %64 | %77 |

**Okuma.** Markanın kendi mağazası neredeyse yalnız üç büyük ildedir; taşrada mobilya
ağı tamamen bayidir. Açılış tarihleri bugün açık mağazalara aittir — kapananlar listede
yok — bu yüzden "son beş yılda ağ büyüdü" değil, "bugünkü ağın çoğu son beş yılda
açılmış" okunur (hayatta kalan yanlılığı).
