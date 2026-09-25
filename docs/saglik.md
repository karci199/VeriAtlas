# Sağlık İstatistikleri Yıllığı (Sağlık Bakanlığı)

Kaynak: sbsgm.saglik.gov.tr → Sağlık İstatistikleri Yıllığı (TR-93566), yıl başına bir sayfa, her
sayfada Türkçe PDF (dosyamerkez.saglik.gov.tr). Site düz HTTP istemcisine boş JS kabuğu döndürüyor;
bağlantılar 2026-09-16'da tarayıcıyla okundu ve `scripts/fetch_saglik_yearbooks.py` içine yazıldı.
Ham veri `C:\veri-ham\saglik` (8 PDF, ~245 MB; sayfa metinleri `siy<yıl>_text.json`).

Adaptör `src/veriatlas/adapters/saglik_yearbook.py`, 20 `moh_*` gösterge, 2012-2016 ve 2018-2024, il + Türkiye.

2011-2016 yıllıkları yalnız www.saglik.gov.tr/TR-84930 listesinde (sbsgm listesi 2017'de başlıyor),
dosyalar dosyasb.saglik.gov.tr'de. 2010 sayfası (TR-84952) HTML değil, PDF'in kendisini döndürüyor; `C:\veri-ham\saglik\siy2010.pdf` olarak indi (172 sayfa) ama il tablosu basmıyor: göstergeler İBBS-1 grafiği, illere göre yalnız ambulans helikopteri. 2011 yıllığı il tablosu basmıyor (yalnız
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


## İlçe düzeyi sağlık: denendi, olmuyor (2026-09-19)

Depodaki 20 `moh_*` göstergesinin hepsi il düzeyinde, çünkü Sağlık İstatistikleri Yıllığı
ilçe kırılımı basmıyor. İlçeye inmek için üç yol denendi, üçü de kapandı:

**1. İl Sağlık Müdürlüğü siteleri** (`<il>ism.saglik.gov.tr`). 81 ilin tamamı aynı CMS'i
kullanıyor ve hastanelerini adıyla linkliyor. `scripts/fetch_ism_hospitals.py` keşif turu
78 ilde 1.031 hastane sayfası buldu — ama sayı **hastane sayısı değil, menü derinliği**:
Düzce 60, Aydın 49, Konya 43 sayfa çıkarken Çanakkale, Edirne ve Kahramanmaraş 1, üç il
hiç. 115 sayfa da tekil hastane değil kategori sayfası ("Devlet Hastanelerimiz").
Her müdürlük ana sayfasını farklı kurduğu için ülke çapında tutarlı sayım vermiyor.

**2. ASM listeleri.** 81 il tarandı: 70 ilin aile hekimliğiyle ilgili sayfası var, ama
Bolu'daki gibi ilçe sütunlu gerçek liste yayımlayan **8 il** — Adana, Balıkesir, Bolu,
Edirne, Erzincan, Kahramanmaraş, Mardin, Tekirdağ. Envanter
`C:eri-ham\ismsm_tarama.csv`. Diğer illerin dosyaları ASM listesi değil (genelge,
"bebek dostu AHB", emzirme politikası, denetim tarihleri). 8 il K4'ü karşılamaz.

**3. MHRS.** Randevu sisteminin kurum listesi ideal kaynak olurdu — tüm hastaneler, il ve
ilçesiyle. `robots.txt` **`Disallow: /api/`** diyor, kullanılmadı.

Ayrıca Bakanlığın dosya sunucuları `dosyaism.saglik.gov.tr` ve `dosyamerkez.saglik.gov.tr`
robots'ta **`Disallow: /`** taşıyor; ekli belgeler otomatik indirilmiyor.

**Karar:** ilçe düzeyi sağlık şimdilik kapalı. Bakanlık ilçe kırılımı yayımlarsa yeniden
bakılır; yarım kapsamayla gösterge üretilmez.

## İlçe düzeyi sağlık: SKRS ile açıldı (2026-09-25)

Yukarıdaki üç yolun dördüncüsü çıktı: Sağlık Bakanlığı'nın kod sunucusu SKRS
(`skrs.saglik.gov.tr`, robots.txt boş) aktif kurum kaydını il başına tek POST'la veriyor —
ad, kurum kodu, il, ilçe, tür. `scripts/fetch_skrs_institutions.py`, ham
`C:\veri-ham\skrs\`, adaptör `src/veriatlas/adapters/skrs_facilities.py`, gösterge
`health_facility_register` (il + ilçe, 25.09.2026 anlık görüntüsü, seri değil).

- Uç nokta `/Anasayfa/KurumIslemleriDetay/482` arayüzde bağlı değil; okul listesinin
  (`EgitimKurumIslemleriDetay`, arayüzde bağlı) adından tahminle bulundu.
- 147.616 aktif kayıt. Hastaneler TÜİK 2024 sektör sayılarıyla: Bakanlık 930/941,
  üniversite 72/69, özel 510/552; illerin 59'unda Bakanlık ve özel birebir. Özel farkın
  33'ü İstanbul'da, açıklanamadı.
- Şehir hastanesi yerleşkesindeki ayrı kodlu binalar (`EĞİTİM HASTANESİ`) ve diş
  hastaneleri hastane sayılmaz; SUAM'ların diş uygulama merkezleri de.
- Aile hekimliği birimi (31.221) = aile hekimi kadrosu, dolu ya da boş; ASM (8.406)
  birimleri barındıran bina, eski "sağlık ocağı". Ülke ortalaması ASM başına 3,7 birim.
- Muayenehane kayıtları kişi adı taşır; depoya yalnız sayı girer.
- Aynı sunucudaki MEB okul listesi 2017 anlık görüntüsü → `schools_2017`
  (`skrs_schools.py`); okul öncesinde kapsama %51.
