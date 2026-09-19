# Ookla Speedtest — ölçülen internet hızı

BTK'nın verdiği sayı, abonelere **satılan** hızdır. Bu kaynak, telefonun sokakta
**ölçtüğü** hızı verir; ikisi aynı şey değildir ve farkın kendisi bir göstergedir.

## Kaynak

Ookla her çeyreği ~600 m'lik karolar hâlinde açık yayımlıyor: `quadkey`, karo poligonu,
ortalama indirme/yükleme hızı (kbit/s), gecikme (ms), test ve cihaz sayısı. Anahtarsız,
S3'te parquet. Ham depoda iki çeyrek var:

    C:\veri-ham\ookla\2022q4_mobile.parquet
    C:\veri-ham\ookla\2024q4_mobile.parquet

**Yalnız mobil.** Ookla aynı biçimde sabit genişbant seti de yayımlıyor; henüz indirilmedi.

## Yöntem

`scripts/build_ookla_speed.py` karoyu ilçe poligonuna oturtur
(`public/geo/districts/*.geojson`, atlasın çizdiği sınırların aynısı), sonra ilçe ve il
için **test sayısıyla ağırlıklı** ortalama alır. Çıktı tek dosya:
`C:\veri-ham\ookla\hiz_ilce.csv`. Adaptör (`ookla_speed.py`) bunu dört göstergeye yazar:
`mobile_download_speed`, `mobile_upload_speed`, `mobile_latency`, `mobile_speedtests`.

Dört tuzak, dördü de sessiz:

1. **Dosya küresel.** Türkiye'ye çizilen kutu Tiflis, Erivan ve Batum'u da içeriyor:
   2024Q4'te kutuya düşen 229.721 testin 90.712'si yurt dışı. Poligon dışında kalan karo
   atılır; "%40 kayıp" diye okunacak şey aslında komşu ülkelerdir.
2. **Ortalama karoya göre alınırsa yanlış çıkar.** Bir testlik boş yamaç ile dört yüz
   testlik şehir merkezi eşit ağırlık alır. Ağırlık test sayısıdır, karo sayısı değil.
3. **Karo düşmeyen ilçeye sıfır yazılmaz.** 2024Q4'te 973 ilçenin 930'u ölçüm aldı; kalan
   43'ü seyrek nüfuslu ve satırsız kalır. Ölçüm yokluğu, sıfır ölçüm değildir.
4. **Birim kbit/s.** Mbit/s'e çevrilmezse sayı bin kat büyür ve sıralama yine doğru
   görünür — testler fiziksel aralığı denetliyor.

## Ne diyebilir, ne diyemez

Testi çalıştıranlar kendilerini seçiyor: bağlantısından şüphelenen ve telefonu çok olan
yerler fazla temsil ediliyor. **Düzey** bu yanlılığı taşır; **ilçeler arası fark** ve
**aynı ilçenin iki çeyreği** sağlam kullanımlardır.

2024Q4 ilk bakış (en az 300 testli ilçeler): Arnavutköy 207,6 Mbit/s ile açık ara önde —
İstanbul Havalimanı orada ve havalimanı testleri karoları yukarı çekiyor, yani bu bir
"ilçe hızı" değil bir tesis etkisi. Onu saymazsak Kartal 93,8, Gaziemir 93,6, Üsküdar
84,3; alt uçta Niğde 36,9, Başiskele 39,1, Antakya 39,7. Aradaki fark iki buçuk kat.
