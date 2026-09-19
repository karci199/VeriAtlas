# UAB denizcilik istatistikleri

`denizcilikistatistikleri.uab.gov.tr` — Ulaştırma Bakanlığı Denizcilik Genel Müdürlüğü.
robots.txt sayfalara izin veriyor, `/api` ve `/web-api`'yi kapatıyor; dosyalar sayfa
bağlantılarından alınıyor, sitenin kendi API'sinden değil. Çekici
`scripts/fetch_uab_denizcilik.py`, ham veri `C:\veri-ham\uab`.

## Ne var

| Bölüm | Kırılım | Yıl |
|---|---|---|
| **Yük elleçleme** | **liman başkanlığı**, kargo tipi, yük grubu, ülke, ay | 2020-2026 |
| Konteyner | liman başkanlığı, ülke, ay | 2020-2026 |
| Gemi | liman, tür, bayrak | 2020-2026 |
| Kruvaziyer | liman, gemi ve yolcu sayısı | 2020-2026 |
| Ro-Ro araç | liman, hat | 2020-2026 |
| Türk Boğazları gemi geçiş | İstanbul ve Çanakkale boğazı, 38 dosya | arşivli |
| Filo, kabotaj, diğer | Türk bayraklı filo, Paris/Akdeniz mutabakatı denetimleri, arama-kurtarma | — |
| Arşiv | bölge ve liman bazında yükleme-boşaltma, 2020 öncesi | — |

Depoya giren: `port_cargo_handled` (il × yön × taşıma türü, ton, yıllık 2021-2025).
Diğerleri diskte, adaptörü yok.

## Sessizce bozan üç şey

1. **Aylık dosyalar birikimli.** Ocak 97,3 mn ton, Şubat 178,0, Mart 276,3 — her biri yıl
   başından o aya kadar. On ikisini toplayan 3.575 mn ton bulur, gerçeğin 6,5 katı.
   Yalnız aralık dosyası okunur.
2. **Sayfa kendi genel toplamını da liman gibi yazıyor.** `Toplam / Total` satırı
   dışlanmazsa ülke iki katına çıkar (1.106 mn ton).
3. **Liman adı dört türlü yazılıyor.** 2020 büyük harf (`İSKENDERUN`,
   `KARADENİZ EREĞLİSİ`), sonraki yıllar başlık düzeni; aynı sütunda dipnot satırları da
   var (`Not:`, `Düzeltme Tarihi: 08.07.2020`). Adlar ASCII iskeletiyle eşleşiyor.

Ayrıca: kaynak `Bandırma`'yı bir yıl `Bandıma` yazmış, `Botaş Liman Başkanlığı`nın adı
sonradan `Ceyhan` olmuş (dosyanın kendi dipnotu), ve Mayıs 2020'de **Ankara** adına 1 ton
yazılmış — denizi olmayan bir il. Kaynağın kendi satırı olduğu için düzeltilmeden
yükleniyor.

**2020 yüklenmiyor:** o yılın aralık dosyası kaynakta yok, son dosya kasım (496,6 mn ton).
Kasımı yıl sanmak "kötü yıl" gibi okunur, eksik ay gibi değil.

## Bulgular (2025)

Toplam elleçleme 553,3 mn ton (2024: 531,7; %+4,1). İlk üç liman yükün %44'ünü taşıyor:
Aliağa 88,7 · Kocaeli 83,9 · İskenderun 70,9 mn ton. Ceyhan %+12,3 ile en hızlı artan —
ham petrol terminali olduğu için boru hattı akışını izler, ticaret hacmini değil.
