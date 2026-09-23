# Vaka: elektrik kesintileri (EPİAŞ, 21-22 Eylül 2026)

Kaynak: EPİAŞ Şeffaflık, Plansız Kesinti Bilgisi (kaynağı dağıtım şirketleri). Ham:
`C:\veri-ham\epias\outage\Plansiz_Kesinti_Bilgisi-21092026.csv` ve `-22092026.csv`, 5.179 kayıt.
İki günlük örnek — mevsim, hafta içi etkisi ve yıllık düzey bundan çıkarılamaz.

## Kapsam

- Bildiren şirket günden güne değişiyor: 21.09'da 10, 22.09'da 9 (Gediz yalnız 21'inde).
  Görülen: Toroslar, Başkent, Uludağ, Meram, Gediz, CK Boğaziçi (İstanbul Avrupa), CK Akdeniz,
  CK Çamlıbel, AYEDAŞ (İstanbul Anadolu), AKEDAŞ. 21 şirketin 11'i hiç görünmedi → 35 il.
- İstanbul iki "il": İSTANBUL-AVRUPA ve İSTANBUL-ASYA.
- Mahalle metni kayıtların %46'sında "Mah." içeriyor; kalanı ilçe ya da semt adı.

## Neden sınıflaması

Neden metni şirkete göre serbest yazılıyor ("Sigorta Atması", "-Ekonomik Ömür - Sigorta Arıza",
"İç Tesisat"). Anahtar kelimeyle 15 sınıfa indirildi; büyük harf Türkçe kuralla yapılmalı
(`"i".upper()` → "I", "Ekonomik Ömür" eşleşmez).

| Sınıf | Kayıt % | Ortanca dk | Abone-dakika % |
|---|---|---|---|
| Ekipman arızası (sigorta, kablo, iletken, klemens) | 20,9 | 112 | 19,3 |
| Manevra (SCADA) | 15,3 | 9 | 14,8 |
| Koruma açması / geçici / bilinmeyen | 11,9 | 10,5 | 10,3 |
| Eskime ("ekonomik ömür", oksit) | 9,4 | 82 | 12,3 |
| Bakım ihtiyacı | 8,5 | 55 | 9,2 |
| İdari (borçtan kesme, yeni bağlantı, yıkım, OSOS) | 6,4 | 22,5 | 2,1 |
| Abone iç tesisatı (Gediz) | 4,1 | 112 | 0,3 |
| Kuş/hayvan | 3,0 | 68,5 | 9,8 |
| Hava, ağaç/dış etken, 3. şahıs, şebeke çalışması, aşırı yük, diğer | kalan | | |

İdari kesmeler ve iç tesisat arıza değildir; il göstergelerinden çıkarıldı.

## İl göstergesi

Abone başına günlük kesinti dakikası = Σ(etkilenen abone × süre) / EPDK 2025 abone sayısı / 2 gün.
35 ilin ortalaması 2,6 dk/abone/gün (yıla vurulursa ~15 saat — iki günden, kaba).

En yüksek: Hatay 10,9 · Osmaniye 6,1 · Çanakkale 5,4 · Adana 4,2 · Gaziantep 3,7.
En düşük: Tokat 0,2 · İzmir 0,4 · Yozgat 0,4 · Aksaray 0,5 · Yalova 0,5. İstanbul 0,8.

Hatay'da tek kesintinin süresi 31 saate çıkıyor (Defne, Antakya): deprem sonrası şebeke.
Abone-dakikada en ağır tek olay Balıkesir merkezde kuş çarpması (5.908 abone, 6,5 saat).
Günlük dağılım 09:00'da tepe yapıyor (406 kesinti), 04:00'te en düşük (49).
