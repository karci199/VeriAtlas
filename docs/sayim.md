# Genel nüfus sayımları 1965-2000 (TÜİK biruni uygulamaları)

TÜİK her sayımı ayrı bir ZK uygulaması olarak sunuyor; menü
`https://biruni.tuik.gov.tr/nufusmenuapp/`:

| Sayım | Uygulama | Sekmeler |
|---|---|---|
| 2000 | `nufusapp/idari.zul` | İdari bölünüş, Sosyal ve demografik, Ekonomik, Hanehalkı ve konut |
| 1990 | `nufus90app/idari.zul` | aynı dört sekme |
| 1985 | `nufus85app/idari.zul` | aynı dört sekme |
| 1980, 1975, 1970, 1965 | `nufus80app/idari.zul?yil=…` (ZK 2.3) | **yalnız İdari bölünüş** |

1927-1960 bu uygulamalarda yok; yalnız basılı ciltlerde (TÜİK kütüphanesi, robots
`Disallow: /` — elle indirme gerekir). 1965-1980 için yaş ya da nitelik tablosu yok,
yalnız yerleşim nüfusları.

## Ne çekiliyor

- **İdari sekme, 1965-2000:** her il için "Tüm idari birimler" = ilçe merkezi (Şehir),
  belde ve köy nüfusu, erkek/kadın. 489 rapor, **tamam**.
- **Sosyal sekme, 1985/1990/2000, ilçe düzeyi:** cinsiyet, tek yaş, beşerli yaş, onarlı yaş,
  0-14/15-64/65+, okuryazarlık, eğitim durumu, doğum yeri, medeni durum, canlı doğan
  çocuk; ilçe toplamı, şehir, belde-köy ayrıntısı.
- **Ekonomik sekme:** işgücü, işgücünde olmayanlar, ekonomik faaliyet, son haftada tutulan
  iş, esas meslek, işteki durum. **Hanehalkı sekmesi:** hanehalkı büyüklüğü, yerleşik nüfus.
- **Belde ve köy düzeyi (bucak bucak):** 9 değişken (tek yaş ve doğum yeri bu düzeyde yok).

Çekici: [`scripts/fetch_census_districts.py`](../scripts/fetch_census_districts.py)
(`zk_client.py` üstünde, tarayıcısız). `--kuyruk` bütün işi sırayla yürütür (küçük ve
önemli önce, köy düzeyi sonda; sıra kodda `QUEUE`). Çıktı
`C:\veri-ham\tuik_sayim\<yıl>\[idari-|eko-|hane-]<il>-<değişken>-<ayrıntı>.html`, köy düzeyi
`<yıl>\koy\`. Günlük `cekim.log`. Aynı komut kaldığı yerden sürer (1 KB'den büyük dosya
atlanır). Başlatma (C:\veri'den, ayrık süreç):

    Start-Process -WindowStyle Hidden -WorkingDirectory 'C:\veri' -FilePath 'C:\veri\.venv\Scripts\python.exe' `
      -ArgumentList '-u','scripts\fetch_census_districts.py','--kuyruk' `
      -RedirectStandardOutput 'C:\veri-ham\tuik_sayim\cekim.log' -RedirectStandardError 'C:\veri-ham\tuik_sayim\cekim.err'

Tempo: rapor arası 6 sn (`SAYIM_BEKLE`), rapor başına ~12-15 sn. MEDAS da aynı sunucuda
çalıştığı için aynı anda ikinci oturum açılmaz (bir kez açıldı, istekler zaman aşımına düştü).

## Uygulamanın söylemediği (çekicide çözüldü)

- **Rapor düğmesi seçili sekmeyi sunucuda okur.** Önce Tabbox'a `onSelect` gönderilmezse
  cevap "İdari birim seçiniz".
- **Her sekmede aynı "Türkiye/İl/İlçe/Belde ve Köyler" kutusu var.** Belge sırasıyla
  sekmenin kendi kutusu alınır; en yenisini almak hanehalkı sekmesinin değişkenlerine düşer.
- Değişken kutusu çoklu seçim gibi görünür ama rapor **yalnız ilk değişkeni** kullanır.
- 1965-1980 uygulamasında ilçe kutusu yok; il seçmek yeter.
- Sunucu arada bağlantıyı koparır (WinError 10054) ya da zaman aşımına düşer: oturum
  açma ve her adım beklemeli yeniden denemeli (`open_census`, `run_queue`).
- Robots.txt 503 döner (bilinmiyor); seçim uygulaması da aynı sunucudan çekilmişti.

## Rapor okumada sessizce bozanlar (hepsi yaşandı)

- **Boş hücre = 0**, ama boş hücreyi atınca sütunlar kayar: Hakkari 73 yaş "1 | 1 | boş"
  → 73 = 1 + 1; okuryazarlıkta Erkek satırının "bilinmeyen"i boş. Denetim satır toplamıyla
  yapılır, hücre hücre yalnız eşit uzunlukta satırlarda.
- **İl adı yalnız ilin ilk ilçesinin satırında basılır**; sonraki ilçelerde son görülen il taşınır.
- **Büyükşehirlerde şehir iki kez basılır:** il merkezinin parçaları, sonra "Şehir" toplamı.
  1965-1985 parçalar "(*)", 1990+ "(1)" işaretli; 1965 İstanbul/Ankara/İzmir'de işaretsiz ve
  bloğun "Şehir" satırından hemen önce. Parçalar atlanır (ilk sürümde 2000'de +7,7 mn).
- **"Bucak toplamı" satırın ikinci hücresinde** olabilir; her hücrede toplam etiketi aranır.
- **"Toplamalar" bir toplam değildir:** köye bağlı olmayan dağınık yerleşim (Nurdağı ~500).
- **(B) = belde**, (Bm) bucak merkezi, (Ptt) postane.
- Yıllar arası köy eşleştirmesi ad + il + **ilçe** ile (İzmir'in 1965 kentsel "Gültepe"si ≠
  Bergama köyü).

## Doğrulama

- İdari: 489 raporun hepsinde yerleşimlerin toplamı raporun "İl toplamı"na birebir; Türkiye
  toplamları resmi sonuçla aynı (1965: 31.391.421 … 2000: 67.803.927).
- İlçe beşerli yaş 2000: 81 ilin ilçe toplamı TÜİK'in ayrı yayımladığı il nüfusuna (portal
  tablosu 00898) birebir, 923 ilçe toplamı 67.803.927.
- Tek yaş toplamı beşerliden "yaşı bilinmeyen" kadar küçük (Adana 376).
- Her raporda Toplam = Erkek + Kadın denetimi (`check_report`); sayısal satırı olmayan
  cevap hata sayfasıdır, kaydedilmez, yeniden istenir.

## Adaptör

Henüz yok. Okuma kalıpları analiz betiklerinde denendi (ilçe yaş, köy nüfusları, eğitim);
adaptör yazılırken yukarıdaki kurallar uygulanacak.
