# Türkiye'de idari bölünüş değişiklikleri

Bir zaman serisi, sınırları sabit sanıldığı anda yalan söylemeye başlar. Bu dosya, 1923'ten
bugüne mülki idarede ne değiştiğini ve her değişikliğin bu depodaki veriyi nerede kırdığını
kaydeder. Sınırların bugünkü hâlinin depoda nasıl durduğu ayrı bir karardır (K11,
[kararlar.md](kararlar.md)); burası tarihin kendisi.

## Kaynaklar

1. **İçişleri Bakanlığı, İller İdaresi Genel Müdürlüğü — "Yıllara Göre Kurulan İl/İlçe
   Sayısı ve Adı"** ([PDF](https://www.icisleri.gov.tr/kurumlar/icisleri.gov.tr/IcSite/illeridaresi/%C4%B0statistiki%20Bilgiler/%C4%B0l%20%C4%B0daresi%20ve%20M%C3%BClki%20B%C3%B6l%C3%BCmler/yillara%20gore%20kurulan%20il%20ilce%20sayilari_3.pdf)).
   Kuruluşun resmî kaydı. Her il bu listede bir kez geçer, o yüzden il tarihi buradan
   birebir okunabiliyor. İlçe sütununda yıl hücreleri birleşik olduğu için makine
   okumasında yıl ataması yaklaşık — ilçe sayıları bu dosyada **kesin diye alınmadı**.
2. **Aydınlı, H. İ. ve Çiftçi, S. (2015), "Türkiye'de Kır-Kent Kavramlarının Değişen
   Niteliği ve Mevzuatın Sürece Etkisi", *Elektronik Sosyal Bilimler Dergisi*, 14(54),
   192-200** ([PDF](https://dergipark.org.tr/tr/download/article-file/70613)). 2004
   sonrası yerel yönetim mevzuatının kır-kent oranına etkisi; 1927-2013 kır/kent serisi.
3. **Kendi verimiz.** TÜİK ilçe düzeyinde yayımladığı her yılın listesi, o yılın idari
   haritasıdır. Aşağıdaki "gözlenen" sayılar depodaki `fact.parquet`'ten sayıldı.

## İller: 55 → 81

İçişleri listesinden, illerin kurulduğu yıl:

| Yıl | Kurulan il | Toplam |
|---|---|---|
| 1923 öncesi | 55 il (bugünkü kodlarıyla Adana'dan Zonguldak'a) | 55 |
| 1935-36 | Artvin, Bingöl, Bitlis, Hakkari, Rize, Tunceli | 61 |
| 1939 | Hatay | 62 |
| 1953 | Uşak | 63 |
| 1954 | Adıyaman, Nevşehir, Sakarya | 66 |
| 1957 | Kırşehir | 67 |
| 1989 | Aksaray, Bayburt, Karaman, Kırıkkale | 71 |
| 1990 | Batman, Şırnak | 73 |
| 1991 | Bartın | 74 |
| 1992 | Ardahan, Iğdır | 76 |
| 1995 | Karabük, Kilis, Yalova | 79 |
| 1996 | Osmaniye | 80 |
| 1999 | Düzce | 81 |

Altı ilin 1935 mi 1936 mı olduğu kaynakta birleşik hücrede duruyor; ikisi arasında
kaldıysa "1935-36" yazıldı, bir tarih uydurulmadı.

**Kırşehir iki kez kuruldu.** 1954'te ilçe yapılıp Nevşehir'e bağlandı, 1957'de yeniden
il oldu. İl listesi "hep 67'ydi, sonra arttı" değildir: arada eksilen de var.

**Bu depo için sonucu:** 81 il kümesi ancak **1999'dan** beri sabit. Elimizdeki en eski
seri 2001 (evlenme-boşanma) olduğu için il düzeyinde geriye dönük bir sorun *yok* — ama
genel nüfus sayımlarına (1927-2000) inildiği gün il karşılaştırması ancak "bugünkü
sınırlara taşınmış" hâliyle yapılabilir, ve o taşıma bir hesaptır, veri değildir.

## İlçeler

İlçe sayısı sürekli oynuyor; büyük sıçramaları yasalar yapıyor. Depodaki veriden
**gözlenen** ilçe sayısı (TÜİK'in o yıl veri yayımladığı ilçeler):

| Yıl | Gözlenen ilçe | Ne oldu |
|---|---|---|
| 2007 | 923 | |
| 2008 | 957 | **5747 sayılı kanun** — 34 yeni ilçe (İçişleri listesiyle birebir uyuyor) |
| 2009-2012 | 957 | sabit |
| 2013 | 970 | **6360 sayılı kanun** yürürlüğe giriyor |
| 2017 | 972 | |
| 2018-2025 | 973 | sabit |

6360'ın kurduğu ilçelerin bir kısmı 2013 verisinde, bir kısmı sonrasında görünüyor: kanun
6 Aralık 2012'de yayımlandı ama **2014 yerel seçimlerinden itibaren** yürürlüğe girdi.

**Bu depo için sonucu:** 2012 ile 2013 arasında ilçe düzeyinde "aynı yer" karşılaştırması
kendiliğinden geçerli değil. Bölünen ilçenin serisi kırılır. Ardıllık tablosu (hangi ilçe
hangisinden çıktı) hâlâ yok — K11'in bıraktığı iş.

## Belediye, köy, mahalle: iki büyük silme

**5747 (2008).** 1.145 belde belediyesinin tüzel kişiliği kaldırıldı, köye ya da mahalleye
dönüştürüldü. Belediye sayısı **3.225 → 2.105**. İlk kademe belediyeleri (283 adet)
tamamen kaldırıldı.

**6360 (2012, yürürlük 2014).** Büyükşehir belediyelerinin sınırı **il mülki sınırı**
oldu. 14 yeni büyükşehir kuruldu (16 → 30), 27 yeni ilçe açıldı.

| | 6360 öncesi | sonrası |
|---|---|---|
| Büyükşehir belediyesi | 16 | 30 |
| Büyükşehir ilçe belediyesi | 143 | 500 |
| İl belediyesi | 65 | 51 |
| İlçe belediyesi | 749 | 418 |
| Belde belediyesi | 1.977 | 393 |
| **Toplam belediye** | **2.950** | **1.393** |
| İl özel idaresi | 81 | 51 |
| **Köy** | **34.283** | **18.201** |

16.082 köy ve 1.582 belde mahalleye dönüştü. Bir gecede 16 bin köy kapanmadı — **statüsü
değişti**, insanlar yerinde kaldı.

**Bu depo için sonucu, ölçülmüş hâliyle:** köy verimiz 2013'ten başlıyor ve 18.108 köy
görüyor; 30 büyükşehir ilinde köy **yok** (eksik değil, hukuken yok), o yüzden kır/kent
ayrımı yalnız 51 ilde hesaplanabiliyor (K25).

## Kır-kent tanımı: ölçüt de değişti

- **1965-1985:** 10 binden büyük yerleşim = kent.
- **1982'de DPT'nin 288 yerleşim üzerinde 28 ölçütlü çalışması** sonrası eşik **20 bine**
  çıkarıldı. TÜİK'in yayımladığı bütün kır/kent serileri bu tanımla.
- **İdari tanım (paralel kullanılan):** il ve ilçe merkezleri kent, gerisi köy.
- **2013'ten sonra TÜİK kır/kent ayrımını bıraktı** — 6360 sonrası "kır" hukuken
  büyükşehirlerde kalmadığı için ayrım anlamsızlaştı.

Makaledeki seri, tanım değişikliğinin veriye ne yaptığını çıplak gösteriyor:

| Sayım | Kent nüfusu | Kent % |
|---|---|---|
| 1927 | 3.305.879 | 24,2 |
| 1950 | 5.244.337 | 25,0 |
| 1960 | 8.859.731 | 31,9 |
| 1970 | 13.691.101 | 38,5 |
| 1980 | 19.645.007 | 43,9 |
| 1985 | 26.865.757 | **53,0** |
| 1990 | 33.326.351 | 59,0 |
| 2000 | 44.006.274 | 64,9 |
| 2012 (ADNKS) | 58.448.431 | 77,3 |
| 2013 (ADNKS) | 70.034.413 | **91,3** |

**2012 → 2013'te kent nüfusu 11,6 milyon arttı.** Türkiye'ye 11,6 milyon kentli
taşınmadı; 6360 sayılı kanun köyleri mahalle yaptı. Bir seride bir gecede %14'lük sıçrama
görülüyorsa, önce mevzuata bakılır. Aynı biçimde 1980 → 1985 arasındaki 9 puanlık sıçrama
kentleşmenin hızlanması değil, eşiğin 10 binden 20 bine çıkarılmasıdır.

## Sayım yılları

- **Genel nüfus sayımları:** 1927, 1935, 1940, 1945, 1950, 1955, 1960, 1965, 1970, 1975,
  1980, 1985, 1990, 2000. (1997'de ayrıca nüfus tespiti yapıldı.)
- **ADNKS:** 2007'den itibaren her yıl, 31 Aralık itibarıyla.

İkisi aynı şey değildir: sayım *bulunduğu yerde*, ADNKS *ikamet adresine göre* sayar.
Elimizdeki bütün seriler ADNKS'tir. Sayımlara inersek, 2000 ile 2007 arasındaki fark
kısmen yöntem farkıdır ve öyle işaretlenmelidir.

## Yasa listesi, tarih sırasıyla

| Yıl | Sayı | Ne yaptı |
|---|---|---|
| 1924 | 442 | Köy Kanunu — köyün tüzel kişiliği |
| 1930 | 1580 | Belediye Kanunu |
| 1949 | 5442 | İl İdaresi Kanunu — il/ilçe/bucak/köy basamakları |
| 1984 | 3030 | Büyükşehir belediyesi (İstanbul, Ankara, İzmir) |
| 2004 | 5216 | Büyükşehir Belediyesi Kanunu (3030'un yerine) |
| 2005 | 5302 | İl Özel İdaresi Kanunu |
| 2005 | 5355 | Mahalli İdare Birlikleri |
| 2005 | 5393 | Belediye Kanunu (1580'in yerine) |
| 2008 | 5747 | 1.145 belde kapatıldı, belediye 3.225 → 2.105 |
| 2012 | 6360 | 30 büyükşehir, sınır = il sınırı, 16.082 köy mahalle oldu |

**Bucak** 5442'de hâlâ bir basamak ama pratikte tasfiye oldu; bizim köy verimizde 2017'ye
kadar etiketin içinde görünüyor, sonra yazılmaz oluyor — `tuik_villages` bunu adres
ayrıştırmasında ayrıca ele alıyor.

## Bu dosyanın işi

Otomatik analiz sayfaları yazıldığında her düzeyin altına şu uyarılar konmalı:

- **İlçe sayfası, 2012-2013 aralığı:** ilçe bölündüyse seri kırıktır.
- **Kır/kent gösteren her sayfa:** 2013 sıçraması mevzuattır.
- **Köy sayısı:** 30 büyükşehirde sıfırdır, eksik değildir.
- **2000 öncesine inen her seri:** sayım ile ADNKS aynı ölçü değildir.
