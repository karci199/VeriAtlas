# Sağlık İstatistikleri Yıllığı (Sağlık Bakanlığı)

Kaynak: sbsgm.saglik.gov.tr → Sağlık İstatistikleri Yıllığı (TR-93566), yıl başına bir sayfa, her
sayfada Türkçe PDF (dosyamerkez.saglik.gov.tr). Site düz HTTP istemcisine boş JS kabuğu döndürüyor;
bağlantılar 2026-09-16'da tarayıcıyla okundu ve `scripts/fetch_saglik_yearbooks.py` içine yazıldı.
Ham veri `C:\veri-ham\saglik` (8 PDF, ~245 MB; sayfa metinleri `siy<yıl>_text.json`).

Adaptör `src/veriatlas/adapters/saglik_yearbook.py`, 20 `moh_*` gösterge, 2012-2016 ve 2018-2024, il + Türkiye.

2011-2016 yıllıkları yalnız www.saglik.gov.tr/TR-84930 listesinde (sbsgm listesi 2017'de başlıyor),
dosyalar dosyasb.saglik.gov.tr'de. 2010 sayfası (TR-84952) HTML değil, PDF'in kendisini döndürüyor; `C:eri-ham\saglik\siy2010.pdf` olarak indi (172 sayfa) ama il tablosu basmıyor: göstergeler İBBS-1 grafiği, illere göre yalnız ambulans helikopteri. 2011 yıllığı il tablosu basmıyor (yalnız
İBBS-1 grafikleri).

## Ne alındı

Her yıllıkta dört-beş "İllere Göre Bazı Sağlık Göstergeleri" tablosu, metin katmanından:

| Tablo (2024 no.) | Göstergeler |
|---|---|
| 7.20 hastane | hastane, yatak, nitelikli yatak, yoğun bakım yatağı, nitelikli yatak oranı, aile hekimliği birimi |
| 8.26 kullanım | müracaat (birinci / ikinci-üçüncü basamak), diş hekimi müracaatı, yatan hasta, yatılan gün, ameliyat, doluluk, ortalama kalış, yatak devir hızı ve aralığı |
| 10.12 personel | uzman, pratisyen, asistan hekim, diş hekimi, eczacı, hemşire, ebe, diğer |
| 12.4 acil | 112 istasyonu, ambulans, asılsız ihbar oranı |

2012-2014'te hastane tablosu aile hekimliği ve 112 sütunlarını da taşır (11 sütun), başvuru ile
yatan hasta tek tabloda (13 sütun). 2015-2018'de aile hekimliği ve 112 ayrı bir tabloda, acil tablosu 2019'da başlıyor; 2012-2019'da
yatan hasta tablosunda "kaba ölüm hızı" sütunu var. Yıl başına tablo sırası `LAYOUTS`'ta.

Alınmayanlar: "10.000 kişiye düşen", "birim başına nüfus", "kişi başı müracaat" — bakanlığın
nüfus rakamına bağlı, depodaki sayım ve nüfustan yeniden kurulabilir. Bölüm 1 demografi tablosu
(TÜİK'ten zaten depoda). İl haritaları yalnız renk sınıfı taşıyor, değer yok.

## Denetimler

- Her tablo 81 il; her sayım sütununun il toplamı basılı Türkiye satırını tutmak zorunda.
- 2019-2024 hastane ve yatak Türkiye toplamları TÜİK/MEDAS `hospitals`, `hospital_beds` il
  toplamlarıyla birebir aynı (TÜİK kaynağı da Bakanlık).
- Nitelikli yatak oranı = nitelikli ÷ (toplam − yoğun bakım) (tablo dipnotu); 2024 Adana
  4.642 ÷ (7.203 − 1.551) = %82,1.

## Tuzaklar

- Tablolar başlıktan değil satırlardan bulunuyor: il adı + sayılar, aynı hücre sayısındaki
  bitişik sayfalar bir tablo. 2018'de başvuru tablosu yatan hasta sayfalarında tekrar basılı;
  hücre sayısına göre ayırmak bunu çözüyor.
- **2017 alınmadı.** Metin katmanı bozuk: rakamlar 29 aşağı kaymış denetim karakteri
  (`\x14` = 1, `\x11` = nokta), ı/ğ/ş/ö/Ç başka glifler — bunlar `repair` ile çözülüyor — ama satırlar
  ortadan kırılıyor ve personel tablosunda il adları tamamen karışık. 2017 için sayfaları görüntüye
  çevirip okumak (BTK yöntem 4) gerekir, ~10 sayfa.
- 2016: "Türkiye"nin i'si ve "Bartın"ın tı'sı U+FFFE olarak basılı; 2012-2013 "Kahraman￾maraş";
  2014 "Kahraman-" / "-maraş" iki satır. `GLYPHS` + `NAME_FIXES`.
- 2012 hastane tablosunun Türkiye satırı adsız basılı: aynı sayfada aynı genişlikte adsız sayı
  satırı toplam sayılır, toplam denetimi yanlış eşleşmeyi yakalar.
- Tablo sayısı yıl başına sabit beklenir; bir tablo kaçarsa yükleme durur.
