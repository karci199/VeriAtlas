# SGK istatistik yıllıkları — il tabloları

Kaynak: sgk.gov.tr/Istatistik/Yillik, 2007-2025 yıllık ZIP'leri (Excel).
Ham: `C:\veri-ham\sgk\yillik\<yıl>\`. Akış:

1. `scripts/fetch_sgk_yillik.py` — ZIP'leri indirir, açar.
2. `scripts/extract_sgk_provinces.py` — her il tablosunu hücre hücre
   `sgk/province_cells.parquet`'e döker (başlık metni, sütun başlık yolu, il, değer).
3. `src/veriatlas/adapters/sgk_provinces.py` — başlıkları göstergeye ve kırılıma eşler,
   denetler. 31 gösterge, `sgk_*`, konu `sosyal_guvenlik`.

Tablo numaralarına ve sütun sırasına hiç dayanılmaz: yıllıklar her yıl yeniden
numaralandırıyor. Tablo başlığından konu, sütun başlığındaki kelimelerden kırılım
çıkarılır. Tanınmayan başlık yüklemeyi durdurur.

## Denetimler (yükleme anındaki sonuç, 2026-09-14)

- Her tabloda 81 il (adla eşleşme; plaka yalnız satır işareti).
- Basılı her toplam, altındaki yaprakların toplamıyla karşılaştırılır, sonra atılır (K16).
  Kontrol edilen ~150 bin toplamdan uyuşmayan: aylık alan hak sahibi 155 (2012, iki tablo
  arası), sosyal güvenlik kapsamı 19 (2010 tahmini değerler, 2016 birkaç il).
- Aynı yıllıkta aynı hücre iki tabloda farklı basılmışsa sayılır: 595 hücre, neredeyse
  hepsi 2012 4/b ölüm aylığı hak sahibi (tablo 2.26 ile 2.39, il başına birkaç kişi).
  Sinop 2011 4/b tarım dışı: 6.032 / 6.033. Aynı yılın yıllığındaki ilk tablo tutulur.
- Bir yılın değeri sonraki yıllıkta farklıysa (revizyon) aynı yılın yıllığı tutulur; 678
  hücre.

## Kaynak hataları (düzeltilerek okunur)

- 2010-2016 iş yeri büyüklüğü tablolarında **Kırıkkale 72 numaralı** (Batman da 72).
- 2007-2011: Şanlıurfa "Ş.URFA" / "URFA", Kahramanmaraş "K.MARAŞ", Mersin "İÇEL".
- 2014 tablo 2.35'in başlığı "1479" diyor, içerik 2926 (tarım) gelir tablosu.
- Tabloların sağında başlıksız ara hesap sütunları var (2007-2009 aylıklar, 2010 iş
  yeri); başlığı olmayan ya da solundaki sütunun başlığını tekrarlayan sütun okunmaz.
- "Tablo : 18/1" gibi sayfa işaretleri başlık sayılmaz.

## İl değişiklikleri

2007-2025 arasında il sayısı 81, il ayrılması yok. Tablolar ili SGK il müdürlüğüne /
iş yerinin iline göre verir, **ikamete göre değil**: İstanbul ve Ankara'da genel müdürlüğü
bulunan iş yerlerinin sigortalıları o ilde görünür. 2023 depremi sonrası Hatay,
Kahramanmaraş, Adıyaman, Malatya'da kayıt taşınmaları yıllık sayıları etkiler.

## Kırılım ve tanım değişiklikleri

**Aktif sigortalı (`sgk_active_insured`)**, 2011-:
- 4/a "kısmi süreli çalışan" 2016'ya kadar; 2017'den "stajyer ve kursiyer", "diğer",
  "Ek-9 (ev hizmetleri)" ve "uzun vade" var. 2017'den zorunlu = uzun vade + Ek-9 (zorunlu
  satırı o yıllardan itibaren depolanmaz, iki parçası depolanır).
- 4/b 2011-2018 "bağımsız çalışan (1479)" toplamı + "tarım (2926)"; 2019'dan zorunlu
  (tarım dışı, tarım, muhtar) + isteğe bağlı. "Tarım dışı toplam" 2018'e kadar.
- 4/c 2018'e kadar yalnız toplam, 2019'dan zorunlu / isteğe bağlı.
- 4/b tarım zorunlu 2011'den her yıl düşüp 2024'te 427 bine iner, **2025'te 656 bin**.
  Eşleme hatası değil: 2025 yıllığı üç ayrı tabloda (1.7, 1.8, 1.21) aynı sayıyı doğru
  başlık altında basıyor. Sebebi (mevzuat ya da kayıt değişikliği) araştırılmadı.

**Zorunlu sigortalı (`sgk_compulsory_insured`)**: cinsiyet 2012'den. 4/a toplamı 2010'dan
(iş yeri tablolarından). 4/b 2012-2018 "1479" ve "2926", 2019'dan tarım dışı / tarım /
muhtar ayrı.

**Aktif sigortalı cinsiyete göre (`sgk_active_insured_by_sex`)**: 4/b 2012-, 4/c
2016- (2019 yıllığındaki 2016-2025 çok yıllı tablodan). 2012 tablosunun başlığı "yaş ve
cinsiyet" der, içeriği il × cinsiyet.

**İş yeri (`sgk_workplaces`)**: 2002-2009 eski SSK "aylık bildirgesi alınan iş yeri",
2010- 5510 kapsamında. Kamu/özel, daimi/mevsimlik/geçici 2010-. **Mevsimlik 2015'te biter,
geçici 2016'da başlar**; aynı kavram değil.

**Faaliyet bölümü × il (`sgk_workplaces_by_activity`, `sgk_compulsory_insured_by_activity`)**,
2008-2025, `scripts/extract_sgk_activity.py` (iller sütunda olduğu için ayrı okuyucu). Her tabloda
bölüm toplamları ve il toplamları kaynağın kenar toplamlarıyla birebir; il toplamları öteki
tablolarla sigortalıda birebir, iş yerinde 2023'te 31 ilde küçük fark (en büyük Eskişehir
23.274 / 23.161). 2007 tablosu eski 43 kodlu gruplamada, alınmadı. 2017'den Ek-9 ev
hizmetleri ayrı satır. **2025 NACE Rev.2.1**: 45 kodu yok, bazı bölüm adları (60, 63)
değişti; 2025'i bölüm bazında önceki yıllarla karşılaştırmayın. 2008-2009 sayfa geçişlerinde
kod ve ad sütunları tekrarlanır.

**Büyüklük sınıfları**: 13 sınıf 2010-2025 aynı (1, 2-3, …, 1000+).

**Ortalama günlük kazanç**: cari TL, prime esas (taban-tavan arası), toplanamaz.

**Aylık / gelir alan (`sgk_pension_recipients`)**:
- 2007-2011 yalnız 4/a (SSK) il tabloları; 4/b ve 4/c 2011'den.
- 2007-2013 tek tablo "aylık ve gelir"; 2014'ten aylık ve gelir ayrı tablolar. "Tüm
  aylıklar", "tüm gelirler", "toplam" basıldığı gibi tutulur: iki aylık alan kişi toplamda
  bir kez sayılır, türlerin toplamı değildir.
- Hak sahibi: 2007-2011 eş / çocuk / ana / baba; 2012'den kadın eş / erkek eş / kız çocuk /
  erkek çocuk.
- 4/b 2019'dan tarım dışı / tarım alt kapsamı her tabloda.
- Vatani hizmet (primsiz) 2013-; 2022 sayılı yasa aylıkları 2007-2011.

**Sosyal güvenlik kapsamı**: 2010-2012 iki toplam basılır (yeşil kartlı dahil / hariç;
2012 gelir testi dahil / hariç), dar olan tutulur. **2013'ten toplam, yalnız GSS tescilli
olanları da içerir** (bileşen `gss_registered`). 2010 4/b ve 4/c değerleri ondalıklı: il
dağılımı tahminle yapılmış. 2022 sayılı yasadan yararlananlar toplamın dışında, ayrı
gösterge.

**İş kazası**: 2007-2012 "işlemi tamamlanan" vakalar, 2013'ten yıl içinde bildirilen.
Seri 2013'te kırılır. 4/b iş kazası tabloları 2017'den. Geçici iş göremezlik günleri
2007-; iş kazasında 2013'ten gün sınıfı (1, 2, 3, 4, 5+).

## Bilerek depolanmayanlar

Tabloların kendisi okunabilir Markdown olarak `docs/sgk-dislanan/` altında
(`scripts/sgk_skipped_markdown.py`). İl kırılımı olmayan Türkiye geneli tablolar ve
okunamayan iki il tablosu: `docs/sgk-turkiye-geneli.md`.


- 4/b kazanç aralığı tabloları: aralıklar asgari ücretle her yıl değişir.
- 2007-2009 SSK "kapsamındaki nüfus" ve isteğe bağlı sigortalı tabloları: devamı yok,
  sütunları n' işaretli, tanımsız.
- 2010 "aktif ve pasif sigortalı" tablosu: devrik düzen, sayıları 2010 kapsam tablosunda.
- 2011-2012 4/b meslek kuruluşu tabloları: iki yıl.
- 2012 4/c ölüm aylığının ölenin aylık türüne göre dağılımı: tek yıl.
- Oranlar ve ortalamalar (hastalık olayı başına gün, sigortalıya oran): türetilebilir.
- Yıllığın kendi il nüfusu sütunu: ADNKS zaten depoda.
- 2007-2008 başlıksız çalışma sayfası ("Sayfa2").
