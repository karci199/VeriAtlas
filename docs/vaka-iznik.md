# Vaka: İznik Anadolu Lisesi — okul ve YKS analizi

Özel analiz kalıbı (K4 dışı, tek-yere-özel). Ana MEDAS/MEB veri hattıyla
karıştırılmaz; bu belge 2026-09-12 oturumunda yapılan keşif ve bulguların
kaydıdır. Yöntem docs/cekiciler.md'ye taşınabilir, sayılar buraya kalır.

## Kaynaklar

1. **MEDAS "Bitirilen Eğitim Düzeyi"** (ilçe, TÜİK/ADNKS) — İznik'in kayıtlı
   nüfusunun eğitim düzeyi, 2008-2025, `raw/medas/ilce/egitim-duzeyi-il21-*`.
2. **İznik ilçe MEB sitesi** (`iznik.meb.gov.tr`) — ilçenin kendi ilan ettiği
   toplam: 44 kurum, 406 derslik, 528 öğretmen, 7.307 öğrenci (2026 anlık).
3. **32+ okulun kendi web sitesi** (`<okul>.meb.k12.tr`) — derslik/öğretmen/
   öğrenci/branş, okul bazında.
4. **İznik Anadolu Lisesi'nin mezun listeleri** (2013-2024, 2021-22 hariç —
   o yıl sayfası hiç yayınlanmamış) — isim var ama biz isim çekmedik, yalnız
   yıl/bölüm/üniversite sayıldı.
5. **Üçüncü parti YKS istatistik siteleri**: sorubak.com, sinavizcisi.com
   (en zengini), liseradar.com, fevkal.com — hepsi ÖSYM/YÖK Atlas verisini
   kaynak gösteriyor.

## Okul sitesi şablonları (4 farklı kalıp çözüldü)

Aynı MEB CMS'i (meb.k12.tr) kullanan okullar bile farklı temalar kullanıyor:

1. `<td class="mavi_yazi">Derslik Sayısı</td><td>:</td><td>16</td>`
2. `<p class="okulumuz-baslik">Derslik Sayısı</p><p class="okulumuz-sayi">10</p>`
3. `<li>Derslik Sayısı: 3</li>`
4. `Derslik:<strong>8</strong>`

`/tema/teskilat.php` sayfası ise **tüm okul tiplerinde aynı yapıda** —
`title='<branş>'` özniteliğiyle personel-branş dökümü veriyor, homepage'in
4 şablonundan bağımsız. Genellenebilir tek yöntem bu.

İlçe menüsündeki bazı okul linkleri **bayat/yanlış** çıktı (Cumhuriyet
İlkokulu, Elbeyli İlkokulu) — doğru adres web aramasıyla bulundu. İlçe
menüsü ayrıca 44 kurumun tamamını listelemiyor (yalnız 32), eksik ~12'si
muhtemelen 2 imam hatip ortaokulu + 8 özel okul + öğretmenevi.

## İznik Anadolu Lisesi — genel sayılar (2026)

16 derslik, 25 öğretmen (kadro; teşkilat şemasında 22 branş öğretmeni + 1
müdür + 1 müdür yrd. + 1 memur + 1 yardımcı personel = 27 kişi), 345-348
öğrenci (kaynağa göre küçük fark), 1 fen laboratuvarı, 1 kütüphane (3.270
kitap), 2 yemekhane, normal öğretim (tek oturum).

Ders saatleri (01.09.2025): toplanma 08:30, 8 ders, öğle arası 12:45-13:30,
günün sonu 15:50.

**Sınıf-şube (2026 kaydı):** 9-12. sınıf toplam 13 şube, 348 öğrenci (138
erkek, 210 kız). Bu okulda MF/TM/TS/Dil alan ayrımı şube etiketinde
görünmüyor ("ALANI YOK") — alan bilgisi yalnız öğretmen ders programındaki
SAY/DİL/EA kısaltmalarında var.

## Mezun analizi (2013-2024, isim yok)

- **Toplam yerleşen, yıllara göre:** 2013-14: 95 → düşe düşe 2023-24: 76.
  2013-2017 arası ~95 civarında sabit, sonra kademeli düşüş.
- **Nitelik (prestijli alan payı — Tıp/Hukuk/Mühendislik/Mimarlık/Diş):**
  en yüksek 2015-16 (%52,9), en düşük 2023-24 (%17,1) — düşüş nicelikten
  daha keskin.
- **Sağlık alanına yerleşen (Tıp+Diş+Eczacılık+Ebelik+Hemşirelik+Odyoloji+
  Fizyoterapi+Veterinerlik+Beslenme-Diyetetik vb.), 2013-2024 toplam 144**
  kişi; zirve 2016-2019 (yılda 19-21), 2022-2024'te 7-10'a inmiş. Mezunun
  kendi anlatımı: bir fizik öğretmeni o dönem kız öğrencileri sağlığa
  yönlendirmiş, mezuniyet yılları yüksek sağlık ataması dönemine denk
  gelmiş — veri bunu doğruluyor ama gerçek sebep ancak canlı tanıklıkla
  netleşti.
- **Hukuk toplam 26** (11 kız, 6 erkek, geri kalan isimden cinsiyet
  çıkarılamadı); **Öğretmenlik toplam 45** (22 kız, 4 erkek — en keskin
  cinsiyet eğilimi); **Mimarlık toplam 57** (23 kız, 16 erkek — dengeli);
  **Mühendislik toplam 243** (50 kız, 108 erkek — en büyük hacim, erkek
  ağırlıklı, ama 2013'ten 2024'e 35'ten 9'a düşmüş).
- **Elit üniversite (ODTÜ/Boğaziçi/İTÜ/YTÜ/Koç/Sabancı/Bilkent/TOBB):**
  33/864 (%3,8) — çoğunluk İTÜ ve YTÜ; Koç'a yalnız 1 kişi (Hukuk,
  2018-19); Sabancı/Bilkent/TOBB'a hiç kimse gitmemiş.
- **LGS etkisi test edilemedi** — ilk LGS kohortu (2017-18 8. sınıf) tam
  2021-22'de mezun olurdu, o yıl sayfası okulun kendi arşivinde de yok.
  Gördüğümüz düşüş (2019-2021) LGS öncesi TEOG kohortlarına ait, LGS'yle
  ilişkilendirilemez.

## Üçüncü parti YKS siteleri — sinavizcisi.com bulguları

- **Şampiyonlar:** 4 puan türünde (SAY/SÖZ/EA/DİL) 2022-2025'in en iyi tek
  yerleşmesi + her yılın (2019-2025) ayrı şampiyonu + okul birincisinin
  yerleştiği bölüm (isim yok, yalnız unvan).
- **İlçe/il karşılaştırma:** Bursa'nın 17 ilçesi ve Türkiye'nin 81 ili,
  SAY/EA ortalama sıraya göre sıralanabiliyor (2020-2026 ortalaması).
  - Bursa'da İznik 11./17 (Mudanya 1., ama Keles/Harmancık/Büyükorhan gibi
    örneklemi çok küçük ilçeler üstte görünüyor — güvenilmez).
  - Türkiye'de Bursa 81 il içinde 17.; **en başarılı il Kırıkkale**
    (128.242), **en başarısız Hakkari** (259.337); **İstanbul 3. en kötü**
    (221.228) — en çok liseye (2.165) sahip il olmasına rağmen.
- **Göç analizi:** İznik mezunları en çok İstanbul (%24), Eskişehir
  (%14,1), Bursa'nın kendisi (%12) yönüne yerleşiyor.

## Veri kalitesi uyarıları

- **sinavizcisi.com kendi içinde tutarsız:** "İlçe Kıyas" aracı 2022-2025
  (4 yıl) kullanırken "İlçe profili" sayfası 2020-2026 (7 yıl) kullanıyor
  — aynı ilçe için farklı sayfalar farklı ortalama veriyor. Sayfanın
  kendisi bu kapsamı açıkça yazıyor, çelişki değil kapsam farkı — ama
  fark edilmezse yanlış yorumlanır.
- **"Tesis ve Kapasite Bilgileri" kutusu yanlış çıktı:** derslik/öğretmen/
  kütüphane kitap sayısı okulun kendi sitesiyle birebir örtüşürken,
  öğrenci sayısı (261) hem 345'ten hem 348'den farklı — kaynağı belirsiz,
  güvenilmez.
- **SEO şablon hatası:** İznik Anadolu Lisesi sayfasının alt açıklama
  metninde yanlışlıkla "Nuh Mehmet Baldöktü Anadolu Lisesi" / "Kayseri"
  yazıyor — sitenin otomatik ürettiği metinlerin düzgün kontrol
  edilmediğinin kanıtı.
- **Genel ilke:** üçüncü parti YKS siteleri hızlı ve zengin ama hiçbir
  rakamına tek başına güvenilmez — resmi kaynakla (okul sitesi, MEDAS,
  MEB) çapraz doğrulama şart. [[cekim-kurallari]]

## Açık işler

- 2021-2022 mezun sayfası eksik (okulun kendi arşivinde de yok) — LGS
  etkisini test etmek için gerekli, bulunamadı.
- İznik'in eksik ~12 kurumu (44 ilan - 32 bulunan) tamamlanmadı.
- Diğer İznik okullarının (32 tanesi) `teskilat.php` üzerinden branş
  dökümü henüz sistematik toplanmadı — yalnız 4 okul (Alparslan Ortaokulu,
  Göllüce İlkokulu, Kılıçaslan İlkokulu, İznik MTAL) pilot olarak
  denendi, hepsi başarılı.
- Bursa dışı illerin ilçe-bazlı YKS karşılaştırması yapılmadı (yalnız
  81 il listesi çıkarıldı, il-içi ilçe kırılımı yalnız Bursa için).
