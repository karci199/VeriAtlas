# Ookla Speedtest — ölçülen internet hızı

BTK'nın verdiği sayı, abonelere **satılan** hızdır. Bu kaynak, telefonun sokakta
**ölçtüğü** hızı verir; ikisi aynı şey değildir ve farkın kendisi bir göstergedir.

## Kaynak

Ookla her çeyreği ~600 m'lik karolar hâlinde açık yayımlıyor: `quadkey`, karo poligonu,
ortalama indirme/yükleme hızı (kbit/s), gecikme (ms), test ve cihaz sayısı. Anahtarsız,
S3'te parquet. Ham depoda iki çeyrek var:

    C:\veri-ham\ookla\2022q4_mobile.parquet
    C:\veri-ham\ookla\2024q4_mobile.parquet

Dört dosya: mobil ve sabit genişbant, iki çeyrek. Mobil, telefonun dışarıda ölçtüğü;
sabit, evdeki ya da işyerindeki hattın ölçtüğü hız. İkisi `connection_type` boyutunda ayrı
durur — toplanmaz, ortalamaları alınmaz; farklı şeylerin ölçümü.

## Yöntem

`scripts/build_ookla_speed.py` karoyu ilçe poligonuna oturtur
(`public/geo/districts/*.geojson`, atlasın çizdiği sınırların aynısı), sonra ilçe ve il
için **test sayısıyla ağırlıklı** ortalama alır. Çıktı tek dosya:
`C:\veri-ham\ookla\hiz_ilce.csv`. Adaptör (`ookla_speed.py`) bunu dört göstergeye yazar:
`internet_download_speed`, `internet_upload_speed`, `internet_latency`,
`internet_speedtests` — her biri mobil ve sabit kırılımıyla.

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

Sabit hat mobilden çok daha kalabalık ölçülüyor: 2024Q4'te 1,17 mn sabit teste karşılık
137 bin mobil test. Türkiye ortalaması (il satırları, test ağırlıklı) sabit hatta 2022Q4'te
53,1 Mbit/s iken 2024Q4'te 115,4; mobilde 41,5'ten 60,4'e. İki yılda sabit iki kattan fazla
hızlanmış, mobil %46.

Sabitte ilçeler arası uçurum mobilden büyük: Gazi Osmanpaşa 245,7 ve Buca 217,7 Mbit/s'e
karşılık Samandağ 19,2, Altınözü 20,2, Türkoğlu 22,4 — on iki kat fark. Alt uçtaki üç
ilçenin ikisi Hatay'da; 2023 depreminin ardından altyapının hâlâ toparlanmadığı okunuyor,
ama bunu bu veriyle söylemek değil, sormak doğru olur.

2024Q4 mobil ilk bakış (en az 300 testli ilçeler): Arnavutköy 207,6 Mbit/s ile açık ara önde —
İstanbul Havalimanı orada ve havalimanı testleri karoları yukarı çekiyor, yani bu bir
"ilçe hızı" değil bir tesis etkisi. Onu saymazsak Kartal 93,8, Gaziemir 93,6, Üsküdar
84,3; alt uçta Niğde 36,9, Başiskele 39,1, Antakya 39,7. Aradaki fark iki buçuk kat.

## `ne-durumdayiz-b7162a` dalından kurtarılan notlar (2026-09-22)

Dal ana dala girmemişti; bölümler orada yazıldı. Çelişen yerde bu dosyanın üst kısmı geçerlidir.

### Kullanım kuralı — kaç teste dayanıyor

Bu kaynakta güvenilirlik göstergeden göstergeye değil, **satırdan satıra** değişir. Aynı
çeyrekte bir ilçenin hızı 7.176 teste, komşusununki 1 teste dayanabiliyor; ikisi tabloda
yan yana ve aynı görünüyor. Bu yüzden hız okunmadan önce `internet_speedtests` bakılır —
aynı alan, aynı dönem, aynı `connection_type` ile.

2024Q4'te ilçe başına test sayısı:

| Kırılım | Ölçüm alan ilçe | 100 testin altında | Medyan test |
|---|---|---|---|
| Sabit genişbant | 959 | 445 | 126 |
| Mobil | 930 | 657 | 30 |

Kural:

1. **İlçe düzeyi sabit hat: 100 testin altı gösterilmez.** Değer silinmez, "yetersiz
   ölçüm" diye işaretlenir — yokluğu da bilgidir.
2. **İlçe düzeyi mobil kullanılmaz.** İlçelerin üçte ikisi eşiğin altında; kalan üçte
   birle çizilen harita Türkiye haritası değil, kalabalık ilçeler haritasıdır. Mobil
   yalnız il düzeyinde okunur.
3. **Sıralama tek başına yayımlanmaz**; hızın yanında test sayısı da durur. 2024Q4 sabit
   hattın tepesindeki Kocaköy'ün (439 Mbit/s) arkasında **bir** test var, Güce'nin (359)
   arkasında dört.
4. **İl düzeyi eşiksiz kullanılabilir** — sabit hatta en küçük ilde bile binlerce test
   var. Tek istisna mobilde Tunceli (52) ve Bayburt (53), 2024Q4; bu iki hücre ilçe
   kuralına tabidir.
5. **Tesis etkisine dikkat.** Havalimanı, üniversite yerleşkesi ya da veri merkezi olan
   ilçede karolar yukarı çekilir; Arnavutköy'ün mobilde açık ara önde olması İstanbul
   Havalimanı'dır, ilçenin hızı değildir. Yüksek testli ama tek noktada yığılmış ilçe,
   az testli ilçe kadar yanıltır.

Eşik, kaynağın kendi yanlılığını çözmez: testi çalıştıran kendini seçiyor. Eşiğin
çözdüğü, **az sayıda ölçümün gürültüsüdür**. Düzey yanlılığı için hâlâ "ilçeler arası
fark" ve "aynı yerin iki çeyreği" kullanılır.
