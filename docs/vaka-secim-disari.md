# Vaka: yurt dışı ve gümrük kapısı oyları

Kaynak: `public/secim-disari.csv.gz` (`scripts/parse_secim_disari.py`, TÜİK seçim
raporları, 2026-09-13). Sayfa: `web/secim-disari.html`. Bu satırlar harita alanı olmadığı
için (ülke → temsilcilik, il → gümrük kapısı) gösterge deposuna alınmadı; K4 dışı özel
analiz. Yüzdeler geçerli oya göre.

## Veri notu

- Yurt dışı raporlarında "kayıtlı seçmen" sütunu oy kullananla aynı basılmış; buradan
  katılım hesaplanamaz. Sayfa bu durumda katılımı göstermiyor.
- 2023 MV'de bazı temsilcilikler yalnız şehir adıyla (Bremen, Aachen, Regensburg).
- Sandık düzeyi alınmadı.

## 1. Göç türü oy payını belirliyor

2023 CB 2. tur, geçerli oyu 20 binin üstündeki ülkeler, Erdoğan payı:

| Ülke | Geçerli oy | Erdoğan % |
|---|---:|---:|
| ABD | 55.708 | 17,3 |
| Kanada | 22.942 | 19,2 |
| Birleşik Krallık | 67.850 | 19,6 |
| KKTC | 84.057 | 42,2 |
| İsviçre | 65.923 | 43,0 |
| Fransa | 206.112 | 66,8 |
| Almanya | 757.631 | 67,2 |
| Hollanda | 159.983 | 70,6 |
| Avusturya | 67.460 | 73,9 |
| Belçika | 91.222 | 74,7 |

Aynı sıra 2017 halkoylamasında "Evet" için de neredeyse birebir: ABD 16,2 · Birleşik
Krallık 20,3 · İsviçre 38,1 · KKTC 45,2 · Almanya 63,1 · Fransa 64,8 · Hollanda 70,9 ·
Avusturya 73,2 · Belçika 75,0. Altı yıl ve iki farklı oylama türünde ülke sıralaması
değişmiyor: işçi göçüyle oluşmuş Batı Avrupa toplulukları ile eğitim/nitelikli göçle
oluşmuş Anglosakson topluluklar arasında ~4 kat fark.

## 2. Almanya içinde de fark büyük

2023 CB 2. tur, temsilcilik: Essen 78,8 · Münster 74,6 · Düsseldorf 72,8 · Stuttgart 71,3
… Frankfurt 61,4 · Berlin 51,5. Ruhr havzası en yüksek, Berlin başa baş.

## 3. Yurt dışı seçmen büyüyor

Yurt dışında oy kullanan: 2015 Haziran MV 931.646 → 2015 Kasım 1.159.871 → 2017 HO
1.325.682 → 2018 MV 1.357.204 → 2023 MV 1.693.608 → 2023 CB 2. tur 1.782.886. Sekiz yılda
%91 artış.

2023 MV yurt dışı: AK Parti 44,5 · CHP 23,2 · MHP 11,0 · Yeşil Sol 10,3 · İYİ 3,4 · TİP 2,9.

## 4. Gümrük kapıları: kapının bulunduğu il, yolcunun ilini yansıtıyor

2023 CB 2. tur, gümrükte 147.340 kişi oy kullandı (Erdoğan %57,8). Geçerli oyu 2 binin
üstündeki illerde Erdoğan payı: Aydın 24,0 · Muğla 28,8 · Balıkesir 31,1 · Adana 38,7 ·
İzmir 39,1 … Şanlıurfa 79,9 · Trabzon 83,1 · Kayseri 84,6 · Zonguldak 84,8 · Konya 86,6.
Havalimanı kapısında oy veren, çoğunlukla o ilde yaşayan ya da o ile dönen yolcu; sıralama
yurt içi il sonuçlarının kabaca aynısı. İstanbul kapıları başa baş (49,6); Sabiha Gökçen
Erdoğan'a, İstanbul Havalimanı Kılıçdaroğlu'na yakın.

## 4. Yurt dışı seçmen profili (2026-09-17)

Ham: `C:eri-ham\secim\profil\secmen-yurtdisi-{toplam,ulke,temsilcilik}` (1.662 rapor; 2011 kaynakta
yok). Okuyucu `scripts/aday_profili.py` (`read`), yurt içiyle aynı. Toplam raporlarında okunamayan
satır 0; 2023 temsilcilik raporlarında 43 satır (148 ülke toplamı 3.423.191, rapor toplamı 3.423.759).

| Seçim | Seçmen | Kadın % | Ort. yaş | 18-24 % | 65+ % | Eğitimi bilinen % | Yükseköğretim / bilinen % |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015 Haziran | 2.866.979 | 46,9 | 40,4 | 15,1 | 7,7 | 15,6 | 18,5 |
| 2015 Kasım | 2.899.069 | 47,0 | 40,4 | 15,1 | 7,6 | 16,4 | 18,7 |
| 2018 | 3.044.837 | 46,9 | 41,0 | 14,7 | 7,7 | 19,8 | 23,0 |
| 2023 | 3.423.759 | 46,7 | 42,0 | 14,3 | 8,3 | 24,9 | 31,6 |

Yurt dışı seçmenin eğitimi çoğunlukla kayıtsız (2023'te %75 "bilinmeyen"); yükseköğretim payı yalnız
bilinenler içinde ve bilinenler seçkili: eğitimi Türkiye'de kaydedilmiş olanlar. Ülke karşılaştırması
buna dikkatle okunmalı (Almanya'da bilinen %14, İrlanda'da %86).

2023, ülke (≥10.000 seçmen): Almanya 1.504.406 (ort. yaş 43,6), Fransa 397.711 (39,7), Hollanda 287.192
(40,8). En genç Polonya 31,1 (kadın %22), İtalya 36,3; en yaşlı Yunanistan 59,2, Avustralya 45,4. Kadın
payı en düşük Polonya %22, Rusya %24, Azerbaycan %25, Suudi Arabistan %29 — iş göçü. Yükseköğretim
(bilinen ≥3.000): İrlanda %78, BAE %74, İspanya %66, ABD %57, Birleşik Krallık %51; Almanya %24.
Temsilcilik: en yaşlı Melburn 45,5, Hamburg 44,6; en genç Milano 36,3, Gazimağusa 38,9.

## Açık

- Kayıtlı seçmen yurt dışı için YSK'dan ayrıca alınmadıkça katılım yok.
