# Kararlar

Verilen kararların kaydı. Yeni karar en alta eklenir; eskisi değişirse üstü çizilir,
silinmez — sonradan "neden böyle yapmışız" sorusunun cevabı burada durur.

## K1 — Kod İngilizce, etiket Türkçe (2026-08-13)

Modül, sınıf, fonksiyon, değişken, klasör ve tablo/sütun adları İngilizce.
Kullanıcının gördüğü her şey (gösterge adı, birim, eksen etiketi, rapor metni,
hata mesajı) Türkçe — ve veri modelinde ayrı bir alan olarak tutulur, koda gömülmez.

Gerekçe: veri modeli SDMX ve Dünya Bankası / OWID sözlükleriyle hizalanacak, onlar
İngilizce. Etiketi ayrı alanda tutmak ileride İngilizce arayüz eklemeyi de serbest
bırakıyor.

Sonuç: gösterge sözlüğünde her kayıt en az `label_tr` + `label_en` taşır.

Mevcut kodun docstring'leri ve yorumları Türkçe; henüz çevrilmedi. Veri hattı
yazılırken dönüştürülecek (bkz. açık işler).

## K2 — Paket adı `veriatlas` (2026-08-13)

`src/veri/` → `src/veriatlas/`, dağıtım adı `veriatlas`, konsol komutu `veriatlas`.
Depo klasörü `C:\veri` olarak kaldı (yol her yere gömülü, taşımanın getirisi yok).

## K3 — Arayüz web olacak (2026-08-13)

Observable Framework + Plot + MapLibre + DuckDB-WASM. Veri hattı Python; yayınlanan
parquet dilimleri doğrudan tarayıcıya gider, arada sunucu yok.

Değerlendirilen alternatif: WPF masaüstü + `C:\DesignKit` (DesignKit.Wpf.dll, net48).
Reddedildi — Python veri hattıyla WPF arasına köprü gerekirdi, ayrıca harita ve
etkileşimli grafik tarafı WPF'te zayıf.

Tema: DesignKit'in Win11 / WinUI 3 koyu paleti taşınacak, ama **sadece renkler**
(`src/DesignKit.Wpf/Themes/Fluent/Fluent.Colors.Dark.xaml` — `#202020` taban, katman /
kart / kontrol dolguları, odak halkası) CSS özel değişkeni olarak. Kontrol stilleri
XAML, taşınmıyor; web tarafında yeniden yazılacak.

## K4 — İlk tema: nüfus ve doğurganlık (2026-08-13)

Ön çalışmadaki 6 doğrulanmış dosya bu temada; ilk veri hattı sentetik veriyle değil,
kaynağı belli gerçek veriyle test edilebiliyor. İlk ekran: toplam doğurganlık hızı,
81 il × 2009-2025.

## K5 — Ekran düzeni onaylandı, tema değiştirilebilir olacak (2026-08-13)

Onaylanan düzen: solda gösterge ağacı + arama · üstte filtre çubuğu (düzey, alan
seçimi, yıl aralığı) · ortada grafik · altında kaynak/kalite rozetleri ve tablo.

Renk hiçbir yere sabit yazılmaz. Her renk CSS özel değişkeni üzerinden gelir; koyu
tema kanonik (DesignKit ile aynı kural), açık tema aynı değişken kümesini yeniden
tanımlar. Grafik renkleri de aynı kümeden okunur — Plot çağrılarına hex gömülmez.

Sonuç: değişken kümesi tek dosyada toplanır ve palet değiştirmek o dosyayı
değiştirmek demektir; bileşenlere dokunulmaz.

## K6 — Kanonik olgu tablosu (2026-08-13)

Bir ölçüm = bir satır. Çeşitlilik sütuna değil satıra gider: yeni bir coğrafi düzey ya
da yeni bir gösterge, yeni bir **değerdir**, yeni bir sütun değil. Bütün göstergeler
tek tabloda. Kod: `src/veriatlas/schema.py`.

| Sütun | Ne tutar |
|---|---|
| `indicator_id` | hangi gösterge (`tfr`) |
| `area_id` | hangi alan (`TR-16`) |
| `area_level` | alanın düzeyi (`province`) |
| `period_start` | dönemin başladığı gün |
| `frequency` | dönemin uzunluğu (`annual` … `daily`) |
| `dims` | esnek kırılım (`age=0-14;place=rural`, yoksa boş) |
| `value` | ölçülen sayı |
| `unit` | birim — koda gömülmez, satırda durur |
| `quality_flag` | `measured` / `estimated` / `interpolated` |
| `vintage` | kaynağın kendi sürümü (`2026-03`) |
| `source_id` | nereden geldi |
| `retrieved_at` | ne zaman çekildi |

**Tekillik anahtarı:** `indicator_id` + `area_id` + `period_start` + `frequency` +
`dims` + `vintage`. Aynı anahtar ikinci kez yüklenirse hata verir — bir içe aktarmayı
yeniden çalıştırmak sayıyı sessizce ikiye katlayamaz.

`frequency` anahtarda, çünkü yıllık 2009 ile 2009-Ç1 aynı `period_start`'a sahip.
`vintage` anahtarda, çünkü revizyonu üstüne yazmıyoruz — iki sürüm yan yana durur ve
verinin hangi tarihe ait olduğu satırdan okunur (ön çalışmadaki 1. sorun).

Kırılımlar için üç yol değerlendirildi: tek esnek alan · her kırılıma ayrı sütun · her
göstergeye ayrı tablo. **Tek esnek alan seçildi** — hangi kırılımların geleceğini
bilmiyoruz (uyruk, sektör, yapı türü…), arayüz tek ve genel olduğu için filtre
kutularını çalışma anında üretmesi gerekiyor, ayrı tablo ise platformun "tek kanonik
model" amacını bozardı. Serbestlik değil esneklik: bir göstergenin hangi kırılım
anahtarlarını kullanabileceği gösterge sözlüğünde tanımlanacak, tanımsız anahtar
yüklemede hata verir.

`dims` kanonik metin olarak tutulur (`age=0-14;place=rural`, anahtarlar sıralı) —
tekillik karşılaştırması metin üzerinden yapıldığı için aynı kırılım her zaman aynı
biçimde yazılmak zorunda.

## K7 — Gösterge sözlüğü depoda dosya (2026-08-13)

`src/veriatlas/data/indicators.toml`, TOML. Gerekçe: gösterge tanımı veri değil,
karardır — "bina" ile "daire"nin farklı şeyler olduğunu TÜİK söylemiyor, biz
söylüyoruz. Kararlar git'te durmalı, değişiklik geçmişi görünsün. TOML seçildi çünkü
yorum satırı kabul ediyor (JSON etmiyor) ve Python 3.13 okuyucusu gömülü geliyor.

Üç bölüm: `[topic.*]` (sol ağaç, sırasıyla), `[unit.*]` (etiket + ondalık basamak),
`[indicator.*]` (etiket, konu, birim, sıklık, izin verilen `dims` anahtarları, tanım).

Bağladıkları:

- **Olgu tablosundaki `unit` artık kimlik** (`children_per_woman`), Türkçe metin değil.
  K1'in gereği: Türkçe yalnızca etikettir, veriye gömülmez.
- **`dims` bekçisi burada.** Gösterge hangi kırılım anahtarlarını taşıyabileceğini
  ilan eder; `check_dims` gerisini reddeder. `age` yerine `yas` yazmak sessizce ikinci
  bir paralel seri yaratamaz.
- **Sol ağaç sözlükten üretiliyor**, HTML'e yazılmıyor. Verisi olmayan gösterge ağaçta
  soluk duruyor: ağaç envanter kadar plandır, soluk madde "henüz değil" der, olmayan
  madde "hiç" derdi.
- **Ondalık basamak birimin özelliği.** Doğurganlık iki basamak, daire sayısı sıfır.

Bina ve daire ayrı gösterge olarak tanımlandı — ön çalışmada karışan tam bu ikisiydi
(2025'te 146.553 bina = 1,19 milyon daire).

## K9 — Arayüz iskeleti: OWID Data Explorer modeli (2026-08-13)

Ekranı gösterge türüne göre bölmüyoruz. Tek çerçeve: solda alan seçimi ve sepet, üstte
boyut seçicileri, ortada görünüm sekmeleriyle (Tablo · Harita · Çizgi · Sütun) grafik,
altında zaman denetimi ve kaynak satırı.

Değerlendirilen alternatif: türe göre ayrı ekranlar (zaman serisi / nüfus yapısı /
harita). Reddedildi — seçimler ekranlar arasında taşınmıyor ve üç ayrı arayüz bakımı
çıkıyor.

İki ilke:

- **Grafik türü bir sekmedir**, göstergenin dayattığı bir şey değil. Aynı gösterge
  tabloya, haritaya, çizgiye dönüşebilir; seçim ve boyutlar korunur.
- **Kırılımlar birinci sınıf denetimdir.** OWID'in SEX/AGE kutuları bizim `dims`
  alanımızın karşılığı. Gösterge hangi kırılımı ilan ettiyse denetimi çıkar; sözlük
  neyi ilan ettiyse arayüz onu gösterir.

Ayrıntı ve yapılacaklar sırası: [arayuz.md](arayuz.md).

## K10 — Tek iskelet, sözlükten sürülen içerik (2026-08-13)

K9'un iskeleti kuruldu: `web/explorer.html` + `explorer.css` + `explorer.js`. Kural,
iskeletin sabit, konuya göre değişen her şeyin sözlükten gelmesi:

- **`views` sözlükte.** Gösterge hangi görünümlere izin veriyorsa sekme o kadar. Sayfada
  "bu gösterge nüfussa piramit çiz" diye bir dallanma yok; `indicators.toml` ne yazdıysa
  o. Bilinmeyen görünüm adı yükleme anında reddediliyor (`VIEWS`), yoksa hiçbir şey
  çizmeyen bir sekme olarak ortaya çıkardı.
- **`dims` denetimi üretiyor.** Üst şeritteki kutular ilan edilen kırılımlardan, değerleri
  de veriden çıkıyor. TFH kırılım ilan etmiyor, şerit kendiliğinden inceliyor.
- **`additive` birimin özelliği.** "Tümü (topla)" seçeneği yalnız toplanabilir birimlerde
  çıkıyor: kişi toplanır, doğurganlık hızı toplanmaz. Bu olmadan arayüz kırılımları
  toplayıp sessizce yanlış sayı üretebilirdi.
- **Zaman denetimi görünüme bağlı.** Çizgi ve tablo bütün aralığı gösterdiği için denetim
  gizleniyor; harita, sütun ve piramit tek yılda duruyor.
- **Harita gerçek, geometri yok.** Görünüm yazıldı (`public/areas.geojson`, özellik başına
  `area_id`); dosya yokken sekme sebebini söyleyerek soluk duruyor.

Tema ayarlanabilir (K5'in devamı): koyu/açık, yazı ölçeği, yoğunluk, vurgu rengi.
`--font-scale` ve `--density` tek kaynak; bütün ölçüler bunlardan türüyor, sayfada
sabit piksel yok. Seçim `localStorage`'da. Ekranın durumu adres çubuğunda (`#i=…&v=…`),
"Bağlantı" düğmesi onu kopyalıyor.

Eski `web/index.html` şimdilik duruyor; gezgin olgunlaşınca kaldırılacak.
## K11 — Harita katmanları ve ilçe tarihçesi (2026-08-13)

Sınırlar `public/` altında, çizim anında dışarıya çıkılmıyor:

- **İl** — `public/areas.geojson`, 81 il, kayıttaki `area_id`'ye bağlanmış
  (`scripts/fetch_geometry.py`). Eşleşmeyen tek il kalırsa betik duruyor.
- **İlçe** — `public/geo/districts/TR-XX.geojson`, il başına bir dosya, 973 ilçe
  (`scripts/fetch_districts.py`). Kaynak tek parça 14,7 MB; ile bölünüp ~100 m
  toleransla sadeleştirilince 2,5 MB'a iniyor ve tarayıcı yalnız açılan ili indiriyor.
  Kaynak: HDX COD-AB-TUR (OCHA), CC BY-IGO — ttezer/turkiye-harita-verisi anlık kopyası.
- **İBBS / bölge** — ayrı dosya değil; illerin birleştirilmesiyle üretilecek (`parents`
  tablosu üyeliği zaten tutuyor). Poligon birleştirme bağımlılığı gerekiyor, o yüzden
  harita sekmesi şimdilik yalnız il düzeyinde açık, diğer düzeylerde sebebini söyleyerek
  soluk duruyor.

Etkileşim: ülke haritasında bir ile tıklanınca o ilin ilçeleri açılıyor, çerçeve
kendiliğinden o ile yakınlaşıyor, "← Türkiye" ile çıkılıyor. Alan adları haritaya
yazılmıyor — sınır yeter, ad imleç kutusunda.

**Zaman meselesi, dürüst hâliyle:** eldeki bütün sınır kaynakları *bugünün* idari
haritasının anlık kopyası. 6360 sayılı yasa (2014 yerel seçimlerinden itibaren yürürlük)
ilçe kurdu, köyleri mahalleye çevirdi, büyükşehir sınırlarını il sınırına genişletti;
bunların hiçbiri kaynakta yok. Kaynak deponun `districts.crosswalk.json` dosyası boş —
yani hazır bir ardıllık tablosu ortalıkta yok.

Bu yüzden `areas_tr_districts.csv` içindeki `valid_from` / `valid_to` **boş yazılıyor**.
Boş, "hep vardı" değil, "henüz doğrulanmadı" demek; uydurulmuş bir tarih, olmayan bir
veriden daha kötüdür çünkü sorgulanmaz.

Doldurma yolu, tercih sırasına göre:

1. **Gözlemden** — TÜİK ilçe düzeyinde veri yayımladığında her yılın ilçe listesi o yılın
   idari haritasıdır. İlk görüldüğü yıl `valid_from`, son görüldüğü yıl `valid_to`
   adayıdır. Bu hukuki değil gözlemsel bir tarihtir ve öyle işaretlenir.
2. **Elle doğrulanmış mevzuat** — 6360 gibi tek tek Resmî Gazete'ye bakılarak, satır
   başına kaynak yazılarak.

Ardıllık (hangi ilçe hangisinden çıktı) ayrı bir tablo olacak: bir ilçenin bölünmesi,
zaman serisini kırar ve toplama kuralı olmadan 2013 ile 2014 karşılaştırılamaz.

## K12 — Türetilmiş seriler: sözlükte tanımlı, depolanmaz (2026-08-14)

Endeks, yıllık değişim, ileride kişi başı ve ara değer — bunlar arayüz numarası değil,
ölçümün üstünde ayrı bir katman. Üç kural:

1. **Sözlükte tanımlı** (`[derivation.*]`): ürettiği birim, kalite bayrağı, tek yılda
   anlamı olup olmadığı (`needs_span`). Sayfa nasıl böleceğini bilir, sonuca ne diyeceğini
   bilmez — o sözlükten gelir (K1, K7).
2. **Depolanmaz, hesaplanır.** Olgu tablosuna yazılsa hangi sürümden türediği kaybolur;
   yeniden hesaplamak bedava. Künyede kaynak yine ölçümün künyesidir.
3. **Kalite bayrağı zorunlu.** Endeks ve yıllık değişim ölçümden birebir çıktığı için
   `measured`; ara değer `interpolated`, ileriye uzatma ise ayrı bir bayrak (`projected`)
   isteyecek ve ölçümle aynı çizgide gösterilmeyecek.

İlk ikisi kuruldu: **endeks (ilk yıl = 100)** ve **yıllık değişim (%)**. İkisi de
büyüklüğü değil hareketi çizdiği için İstanbul'un her grafiği bastırması sorununu da
çözüyor. Tek yıl gösteren görünümlerde (harita, sütun, piramit) denetim kendiliğinden
kayboluyor: bir yılın "önceki yıla göre değişimi" o görünümde yalan olurdu.

Sıradakiler: ara değer (eksik yıl), kişi başı, ve ileriye uzatma — sonuncusu muhtemelen
türetme değil, ayrı bir "projeksiyon" göstergesi olarak.

## K13 — Oran kipi: mutlak sayının yanına payı (2026-08-14)

Mutlak ve göreli aynı soruyu sormuyor. Şanlıurfa'nın çocuk nüfusu kişi sayısında
Ankara'dan küçük, oranda çok daha büyük — ve haritada asıl anlatan ikincisi.

Kırılım denetimlerinin yanında **Değer: Mutlak sayı / Toplamın %'si** var. Payda, o
alan-yılın kırılım seçiminden bağımsız toplamı: seçili dilimi kendine bölmek her yerde
%100 verirdi. Bu yüzden yalnızca toplanabilir birimlerde ve kırılımı olan göstergelerde
açılıyor (`canShare`) — oranların toplamının payı diye bir sayı yok.

Türetmeden (K12) ayrı bir denetim: türetmeler zaman içindeki hareketle ilgili, oran aynı
yılın başka bir okuması, ve ikisi birleşiyor — bir payın endeksi alınabiliyor. Haritada
oran kipinde log ramp sunulmuyor: log, üç büyüklük mertebesine yayılan sayımlar için
vardı, sınırlı bir oran için değil.

## K14 — Ağır düzeyler ayrı dosyada, istendiğinde iniyor (2026-08-14)

İlçe nüfusunun yaş × cinsiyet kırılımı 973 × 38 × 19 yıl — yaklaşık 700.000 satır,
50 MB. Ana dosyaya konsaydı il çizgi grafiği için gelen herkes bunu indirirdi.

Kural: **bir düzeyin satırları tamamen tek dosyada durur.** İlçe toplamı bir dosyada,
ilçe kırılımı ötekinde olsaydı kırılım üstünden toplayan her şey — "Tümü (topla)",
oran kipinin paydası — o ilçeleri iki kez sayardı. Bu yüzden ilçe düzeyinin tamamı
`public/population-district.csv` içinde ve sayfa onu ancak okuyucu ilçe düzeyini
gerçekten istediğinde çekiyor.

Düzey menüsü artık elde duran satırlardan değil sözlükten kuruluyor (`levels`,
`parts`): yoksa dosyayı indirmesi gereken menüde o düzey hiç görünmezdi. Sayfa ilçe
*sınırlarını* zaten il il, istendiğinde çekiyordu (K11) — bu onun veri tarafındaki eşi.

**Ek (2026-08-14 akşam): veri dosyaları gzip'li çıkıyor.** 53,6 MB → **3,9 MB**.
Sıkıştırma sunucuya bırakılmıyor, dışa aktarımda yapılıyor ve sayfa `DecompressionStream`
ile kendisi açıyor: ekran `python -m http.server` üstünde çalışmak zorunda ve o hiçbir
şey pazarlık etmiyor — sayfanın kendi ayarladığı kodlama, nerede barındığına bağlı
değil.

Dosya içinde sabit olan dört sütun (düzey, kalite bayrağı, sürüm, kaynak) atılsaydı
*düz* baytların yarısı giderdi ama gzip'ten sonra kazanç 3,9 → 3,6 MB. O yüzden
duruyorlar: künye, tarif ettiği satırlarla birlikte yolculuk etmeye devam ediyor —
zaten orada olmasının sebebi bu.

## 2026-08-14 oturumu — kapanan altı madde

Önceki oturumun listesi bitti:

1. ~~**İlçe yaş × cinsiyet kırılımı.**~~ Kutular aslında işaretleniyormuş; eksik olan
   `Tamam`'dan sonra açılan değer listelerindeki `<Hepsi>` idi (bkz. `medas.md`).
   19 yılın tamamı çekildi ve her yıl ilçe ilçe toplam dosyasıyla birebir tutuyor
   (ülke toplamları da ADNKS'nin yayımladığı sayılar). 696.900 satır olgu tablosunda.
2. ~~**Oran (%) kipi.**~~ K13.
3. ~~**Yıl aralığı seyrek.**~~ Örnekleme kalktı; tablo bütün yılları gösteriyor, kendi
   kutusunda iki yönde kayıyor, alan sütunu ve başlık satırı sabit.
4. ~~**"Tümünü seç" kaydırıyor.**~~ Liste yeniden çizilirken `scrollTop` korunuyor.
5. ~~**Denetim adları.**~~ `Ortak eksen / Panel bazlı`; harita ikilisi iki etiketli gruba
   ayrıldı: `Renk: Log / Doğrusal`, `Uçlar: Tüm yıllar / Bu yıl`.
6. ~~**Harita ilçe kipinde kırılım denetimleri.**~~ Üç parçası vardı: veri (1), şeridin
   ekrandaki *gerçek* düzeyi izlemesi (`effectiveLevel` — harita bir il açıkken ilçe
   çiziyor ama şerit ilin bantlarını sunuyordu), ve yaş bantlarının düzeye göre farklı
   olması (il 75+, ilçe 90+). Menü artık düzeye göre süzülüyor, düzey değişince seçim
   geçerli bir değere çekiliyor.

Kalan pürüz: `population-district.csv` 53 MB. Düzey başına ayrı dosya (K14) ana sayfayı
kurtardı ama ilçeye geçen okuyucu 53 MB indiriyor. Satırların üçte biri her satırda
tekrarlanan künye (`quality_flag,vintage,source_id`); sıkıştırma ya da yıl başına dosya
sıradaki iş.

## K15 — MEDAS etiketleri adla değil koduyla eşleşir (2026-08-14)

MEDAS her etikete kodunu iliştiriyor: il için plaka (`Adana-1`), İBBS için `TR62`,
ülke için `TR`, ilçe için MEDAS kodu (`-1757`). Plaka zaten kayıttaki il kimliğinin
kendisi (`TR-01`, ISO 3166-2:TR), yani eşleşme için katlama, ad değişikliği takibi,
`Şanlıurfa`/`Urfa` tahmini gerekmiyor.

Bunu ortanca yaş adaptöründe kurduk çünkü orada ad eşleşmesi sessizce yanlış cevap
veriyordu: dosyada 81 değil **78 il** var. Ankara ve İzmir yalnız tek-il İBBS-2
satırı olarak (`Ankara-TR51`, `İzmir-TR31`), İstanbul ise İBBS-**1** satırı olarak
(`İstanbul-TR1`) geçiyor — MEDAS aynı insan kümesini gösteren düzeyleri tek satıra
indirmiş. Adla okunsa bu üç il haritanın tam ortasında "veri yok" olurdu.

Kural: **tek il içeren İBBS bölgesi o ildir.** Hangi bölgelerin böyle olduğu kayıttaki
üyelik tablosundan, ataların tamamı yürünerek çıkarılıyor (`single_province_regions`) —
elle yazılmış bir liste değil, çünkü İstanbul'un İBBS-1'e kadar çıkması "hangi düzeye
bakayım" sorusunu kuralla çözülmesi gereken bir şey yapıyor. TÜİK birini bölerse kural
kendiliğinden doğru kalır.

Yanına ikinci bir emniyet konuldu: adaptör 81 ilin tamamını bulamazsa yükleme
**durur**. Eksik il, haritada gerçek bir boşluktan ayırt edilemez (K6).

İBBS-1 ve çok illi İBBS-2 satırları alınmıyor: ekran ülke / il / ilçe düzeyinde
çalışıyor, kimsenin istemediği bir düzey bakılacak bir şey değil bakımı yapılacak bir
şeydir. İhtiyaç olursa eklenir.

## Düzey adları: İBBS üçte biter, altı LAU'dur (2026-08-14)

Sık yapılan bir hata, kendi kayıt yapımızı da bozabilirdi: **İBBS'nin dördüncü ve
beşinci düzeyi yok.** Türkiye'de İBBS üç düzeydir — Düzey 1 (12 bölge), Düzey 2 (26 alt
bölge), Düzey 3 (81 il) — ve 2002/4720 sayılı Bakanlar Kurulu kararıyla böyle
tanımlanmıştır. AB sisteminde bir zamanlar NUTS-4 ve NUTS-5 vardı; 1059/2003 sayılı
tüzük bunları kaldırıp **LAU-1 / LAU-2** (yerel idari birimler) adını verdi, Eurostat
2017'den beri tek bir **LAU** düzeyi kullanıyor. Yani ilçe ve mahalle İBBS değil LAU'dur.

Bunun veri modeline üç sonucu var:

1. **İl iki şey birden:** hem idari il hem İBBS-3. Kayıt bunu zaten iki ayrı hiyerarşi
   olarak tutuyor (`area_parents_tr.csv`, `hierarchy` sütunu: `nuts` ve `geographic`) —
   tek bir üst-alan sütunu olsaydı birini atmak zorunda kalırdık (K6).
2. **Tek il içeren bölgeler var ve tam üç tane:** Düzey-2'de TR10 (İstanbul), TR51
   (Ankara), TR31 (İzmir). Düzey-1'de yalnızca **TR1 = İstanbul** tek illidir; kalan on
   bir bölge 3-10 il içerir. İstanbul her iki düzeyde de tek olduğu için TR1 = TR10 =
   TR-34 aynı insan kümesinin üç kodudur — MEDAS'ın ortanca yaş dosyasında bu üç ili
   yalnız bölge satırı olarak vermesinin sebebi bu (K15).
3. **Beldeler LAU'dur, ilçenin altındadır** — köylerle aynı basamakta. 6360 sayılı kanun
   (2012, Mart 2014 seçimleriyle yürürlükte) 30 büyükşehir ilinde belde belediyelerini ve
   köyleri kaldırıp mahalleye çevirdi; 16.000'den fazla köy, 1.000'den fazla belde
   etkilendi. Yani belde bugün yalnızca **büyükşehir olmayan 51 ilde** var.

Elimizdeki Bursa dosyası (büyükşehir) bunu doğruluyor ama tamamlamıyor: etiketin orta
parçası hem 2013'te hem 2025'te 17 çeşit, ilçe başına bir tane, hepsi `<İlçe> Bel.`.
Yani bu dosyada belde ayrı bir basamak olarak hiç görünmüyor. Büyükşehir olmayan bir ilin
dosyasında o parçanın belde adı taşıyıp taşımadığı **açık soru** — ikinci il çekilirken
bakılacak ilk şey bu.

## K16 — En ince taneyi depola, kabasını türet (2026-08-14)

Nüfus hem tek yaş hem beşli bant olarak yayımlanıyor. Kural: **olgu tablosu yayımlananın
en incesini tutar, kabası hesaplanır.** Tek yaştan beşliğe toplamak tam ve kayıpsız;
tersi imkânsız. Aynı gerekçe K12'nin (türetme depolanmaz) kırılım eksenindeki karşılığı.

Sınır dışa aktarımdadır: depo 236.816 satır tek yaş tutuyor, sayfanın her ziyaretçinin
indirdiği temel dosyası beşli bant (49.856 satır, 0,33 MB). Tek yaş isteyen okuyucu için
ayrı bir dosya var (`population-age1.csv.gz`, 1,4 MB) ve o **yerine geçer, eklenmez** —
ikisi birden elde tutulsa kırılım üstünden toplamak herkesi iki kez sayardı, K14'ün
düzeyler için koyduğu kuralın bir eksen ötesi.

İki tuzak yaşandı ve ikisi de kurala dönüştü:

- Tek yaş dosyası `^\d+$` ile süzülünce kapanış bandı ("75+", sayı değil) düştü ve
  çözünürlük İstanbul'da kendi toplamından 496.393 kişi eksik kaldı. **Bir çözünürlük
  dağılımın tamamını taşımak zorundadır**; seçim satırın yaşına değil düzeyine göre.
- Gruplama `group_by` sıralamayı bozduğu için gzip kötüleşti, ilçe dosyası 3,9 → 8,9 MB
  oldu. Toplama işleminden **sonra** yeniden sıralanıyor.

Dosya güvenilmeden önce bağımsız kaynakla sınandı: il toplamları MEDAS ilçe ihracatının
toplamıyla, ortak 1.539 il-yılın hepsinde birebir aynı.

## K17 — Gruplama ve karşılaştırma sözlükte (2026-08-14)

"0-14 / 15-64 / 65+" ne ayrı bir gösterge ne de sayfada bir dal. Sözlükte iki yeni bölüm:

**`[grouping.*]`** — bir kırılımın kaba okuması: hangi değerler hangi grubu oluşturur.
Bir değer iki gruba giremez (yükleyici reddediyor), ve bir gruplama ancak o düzeydeki
**her bandı** kapsıyorsa sunulur. İkinci kural ilçede 90+'a kadar giden kuyruğu ve
mahalledeki 0-17/18+ bölmesini birlikte doğru yönetiyor: mahallede "15-64" sormak insan
düşürürdü, orada hiç sunulmuyor.

**`[comparison.*]`** — bir kırılımın iki değerini karşı karşıya koyar: `Erkek − Kadın
(fark)` ve `Cinsiyet oranı (E/K × 100)`. Dilim iki kez alınıp birleştiriliyor. Farkın
birimi göstergenin kendi birimi (kişi, yaş), oranınki ayrı.

İkisi de kırılım kutusunun içinde duruyor — "hangi yaş", "hangi yaş bölmesi" ve "hangi
iki değer" aynı sorunun üç hâli, üç ayrı köşeye dağıtılmamalı.

## K18 — Düzey kutusu listeyi seçer, seçimi değil (2026-08-14)

Türkiye'nin 0-4 oranını Bursa'nınkiyle, onu da bir ilçesininkiyle karşılaştırmak
sorulmaya değer bir soru; oysa sayfa bunu **soramıyordu**. Düzeyi değiştirmek seçimi
siliyor ve yeni düzeyin en büyük beşini yerine koyuyordu, yani karşılaştırmayı kurmanın
her adımı bir öncekini çöpe atıyordu.

Kutu artık **hangi listenin sunulduğunu** söylüyor, ne çizileceğini değil. Seçim düzey
değişince yerinde kalıyor, ve seçilenler bloğu her alanı nereden geldiğiyle etiketliyor
("Aladağ · İlçe") — çünkü "Merkez" tek başına ilçe mi mahalle mi olduğunu söylemez.
Tohumlama yazıldığı hâl için duruyor: hiçbir şey seçili değilse boş sayfa açılmasın.

Sonuç olarak her grafik alanı **kendi düzeyine** göre çözüyor (`levelOfArea`, satırlardan
okunuyor — kimliğin biçimi dışa aktarıcının işi). Ad araması da düzey kapsamından çıktı,
yoksa Türkiye'nin çizgisi "TR" diye etiketleniyordu.

Harita ve tablo tek düzeylidir, öyle kalıyor: bir haritada mahalleyle ili yan yana
boyamak alan yarışması olur, karşılaştırma değil.

## K19 — Doğum ve ölüm: sayı depolanır, hız türetilir (2026-08-14)

MEDAS'ın altı hayati ölçüsünden **dördü** yüklendi: doğum sayısı, ölüm sayısı (cinsiyet
kırılımıyla), bebek ölüm hızı, beş yaş altı ölüm hızı. Kaba doğum hızı ve kaba ölüm hızı
**yüklenmedi** — ikisi de elimizdeki iki sayının bölümüdür (olay ÷ nüfus) ve K12'ye göre
böyle bir sayı türetmedir, ikinci bir indirme değil. Sayfadaki "Alan nüfusunun %'si" kipi
onları zaten çiziyor. Yayımlanmışları `raw/`'da denetim olarak duruyor ve denetim geçti:
1.394 il-yılda ortalama mutlak fark doğumda 0,10‰, ölümde 0,05‰ — kalan fark TÜİK'in yıl
ortası nüfus kullanmasından, bizim yıl sonu ADNKS'sinden.

**Ay kırılımı saklanmadı.** Kaynak doğumu aya, ölümü cinsiyet × aya bölüyor; ikisi de yıla
toplanarak duruyor. Mevsimlilik gerçek bir soru ama bu ekranın sorusu değil; ham dosya
kırılımı koruduğu için sorulduğunda yeni indirme değil, yeni bir dim gerekiyor.

**Doğal nüfus artışı** (doğum − ölüm) `derived.py`'de, ortanca yaş toplamı gibi: iki
göstergeyi birlikte okuduğu için sayfanın türetmeleri bunu yapamaz. İki tarafın da
bulunduğu alan-yıllarda üretiliyor — yalnız doğumu olan bir yıl, doğumu kadar artış
göstermesin diye. Türkiye 2009'da 897.048, 2025'te 403.690; 2017'den beri 85 il-yıl eksi,
2025'te 19 il (Balıkesir −2.535 en düşük).

Doğrulama: 2009-2024'ün on altı yılının doğum, ölüm ve doğal artış sayıları Wikipedia'nın
"Demographics of Turkey" tablosuyla (kaynağı TÜİK) **birebir** tutuyor.

Dosya biçimi tuzağı: bu çekimde MEDAS tabloyu **devirmiş** — alanlar sütunlarda, yıllar
satırlarda. `tuik_simple` okuyamaz, o yüzden `tuik_vital` ayrı bir okuyucu. İkinci tuzak,
kırılım etiketinin bloğun yalnız ilk satırında yazılması: harfiyen okununca ölüm on yedi
yıl yerine tek yıl olarak yüklendi ve hata vermedi. Etiket blok boyunca taşınıyor,
`tests/test_vital.py` bunu tutuyor.

## K20 — Evlenme ve boşanma; toplamın ne zaman hesaplanabildiği (2026-08-14)

Evlenme sayısı, boşanma sayısı (2001-2025) ve dört yaş ölçüsü yüklendi. Kaba evlenme ve
kaba boşanma hızı yine yüklenmedi — K19'un kuralı. Yayımlanmışlarıyla denetlendi:
1.558 il-yılda ortalama mutlak fark evlenmede 0,05‰, boşanmada 0,01‰.

**Kırılımlar kapalı çekildi.** İkisinin de altında on kadar kırılım var (eşlerin yaş
grubu, eğitim durumu, evliliğin süresi, velayet). Açıkken ölçü 121 göstergeye çıkıyor ve
indirme iki yılda bir sorguya iniyor; kapalıyken 25 yıl tek sorgu. Ham dosya duruyor.

**Ortalama evlenme yaşında "Toplam" hesaplanıyor, ilk evlenme yaşında hesaplanmıyor.**
Ayrım ağırlıklarda: her nikâhta bir damat ve bir gelin vardır, yani iki ortalamanın
ağırlığı tanım gereği eşittir ve (e+k)/2 tam sonucu verir. İlk evlenmede öyle değil — bir
evlilik erkeğin ilki, kadının ikincisi olabilir, ilk kez evlenen erkek ve kadın sayısı
eşit değildir. Ortanca yaşta olduğu gibi, elde olmayan ağırlık uydurulmuyor.

## K23 — Kütük nüfusu: yılı elle seç, ekseni doğru oku (2026-08-14)

Otomatik dilimleme çalışmadı, çünkü MEDAS'ın alan sayacı iş sürerken tırmanıyor
(33 → 39 → 82) ve dilim boyu üçte bir eksik hesaplanıyordu. Çözüm sayaçtan kurtulmak:
`--yil=2019` ile yıl elle seçiliyor, tek yıl 6.642 hücre, sınırın çok altında. **2007-2025
tamam.** Düzey kutusu bu ölçüde hiçbir şey yapmıyor — Türkiye ve İl bayt bayt aynı dosyayı
indiriyor, ikisi de 82 alan — o yüzden yalnız il kopyası saklanıyor; ikisini birden
yüklemek her alanı iki kez toplardı.

## K24 — Kütük nüfusu tek gösterge, iki kırılım (2026-08-14)

Önce iki ayrı gösterge yazıldı: kütük nüfusu (sütun toplamı) ve ilinde yaşayan kendi
kütüklüleri (köşegen). Yanlış şekildi. Doğrusu **tek gösterge, `residence` kırılımı**:
`İlinde` köşegen, `İl dışında` sütunun geri kalanı, ikisi toplanınca kütüğün tamamı.

Fark, sayfanın hazır makinesinin çalışıp çalışmaması: kırılım olunca "Tümü (topla)"
toplamı, "Nerede yaşıyor içinde %" kütüğün yüzde kaçının hâlâ ilde olduğunu, herhangi bir
türetme de o parçanın kendi artış hızını veriyor — ildeki ve dışarıdaki için ayrı ayrı.
İki gösterge olarak ise toplanamayan iki tablo, ağaçta iki satır ve aralarındaki oranı
sormanın hiçbir yolu yoktu.

Rakamlar: İstanbul kütüğü 2007'de 2,44 milyon → 2025'te 2,60 milyon, ama ildeki kısmı
2,16'dan 2,12 milyona *düşerken* dışarıdaki 282 binden 481 bine çıkmış. Kütüğü en dağınık
il Ardahan (%13,7'si ilde), en toplu il Antalya (%88).

Yan etki: kırılım değerleri artık **sözlükteki sırayla** sunuluyor, alfabetik değil. Her
listeli boyut şimdiye kadar zaten alfabetikti, o yüzden fark etmiyordu; "İlinde / İl
dışında"da fark etti — kalan, kalanı olduğu şeyden önce geliyordu. Medeni durum da bu
sayede mantıklı sırasına oturdu (hiç evlenmedi → evli → boşandı → eşi öldü).

**Asıl tuzak eksendeydi.** Ölçünün adı satırların kütük olduğunu düşündürüyor; değil.
Satır ikamet edilen il, sütun nüfusa kayıtlı olunan il. Satır toplamı zaten elimizde olan
ikamet nüfusudur; kütük nüfusu **sütun toplamıdır**. Yanlış eksen hata vermiyordu: ülke
toplamı tutuyordu (iki okuma da aynı ülkeye toplanır) ve her ilin oranı 1,00 çıkıyordu.
Yakalatan şey, Ardahan ile Sivas'ın da 1,00 çıkmasıydı — kütüğünün yarısı yıllar önce
göçmüş iller. Doğru eksende 2019'da Ardahan 5,53, İstanbul 0,16.

Denetim: kütük toplamı 2019'da 81,62 milyon, ADNKS nüfusu 83,15 milyon; aradaki 1,53
milyon yabancı uyruklu nüfusa denk geliyor (kütüğü olmayanlar). 2009'da fark 168 bin,
o yılın yabancı nüfusu kadar.

## K21 — Sayfada bulunan üç mantık hatası (2026-08-14)

Üçü de sessizdi: yanlış sayı üretmiyor, doğru seçeneği ortadan kaldırıyor ya da anlamsız
olanı sunuyorlardı.

1. **Nüfusa oranlama birimin Türkçe etiketine bakıyordu** (`unit === "kişi"`). Sayılan şey
   insan olduğu sürece çalıştı; doğum "doğum", ölüm "ölüm", evlenme "evlenme" birimiyle
   gelince kip sessizce kayboldu — yani kaba doğum/ölüm/evlenme hızı, o sayıların en
   standart okuması, hiç sunulmadı. Ölçüt artık **toplanabilirlik**: sözlüğün birim
   hakkında söylediği bir olgu, bir dildeki kelime değil (K1).
2. **Yüzde türetmeleri eksi tabanda ters işaret veriyordu.** Doğal artışı −1.000'den
   −500'e çıkan bir il "yüzde 50 düştü" diye yazılıyordu; tersi doğru. Eksi tabanlı
   yüzde artık üretilmiyor, ve şeridin kendisi bu türetmeleri o göstergede soluk
   gösteriyor. Net göçte bu hata en baştan beri vardı. Sıfır ayrı iş: tek bir noktayı
   tanımsız yapar, o nokta düşer — bütün seri kapanmaz (yabancı uyruklu nüfus 2.952
   satırda beş sıfır yüzünden kapanıyordu).
3. **Oran tipi karşılaştırma her birimde sunuluyordu.** İki değerin *farkı* her birimde
   anlamlıdır (erkekler üç yıl geç evleniyor); *oranı* yalnız sayımlarda. Ortalama evlenme
   yaşının "cinsiyet oranı" 28,5 ÷ 26,0 = 110 diye bir sayı veriyordu. Ortanca yaş bu boş
   seçeneği uzun süredir taşıyordu.

## K22 — Az seçenek buton, çok seçenek açılır kutu (2026-08-14)

Eşik OWID'in kendi gezgininden ölçüldü: orada cinsiyet (3) ve senaryo (4) buton, gösterge
(10) ve yaş (25) açılır kutu. Bizde sınır beş. Tek bir `chooser()` iki biçimi de üretiyor;
butonlar gerçek radio olduğu için klavyeyle geziliyor ve `<select>` ile aynı `change`
olayını yolluyor — şeridin tek yakalayıcısı hangi biçimi aldığını bilmiyor. `<optgroup>`
gerektiren kutular (karşılaştırma, oran) buton olmuyor: aralarında ayrım olmayan bir
düğme dizisi, son ikisinin bambaşka bir şey yaptığını gizlerdi.

## K25 — Köy ayrı bir düzeydir (2026-08-15)

`village`, şemadaki altıncı alan düzeyi. Köy, mahallenin küçüğü değil: öteki yerleşim
türü, ve ikisinin toplamı ilçeyi verir. Ayrı tutulmasının iki sebebi var — TÜİK mahallede
yaş ayrımı yayımlıyor, köyde yayımlamıyor (MEDAS'ta yaş işaretlenince Köy düzeyi
seçeneklerden kayboluyor); ve ikisinin toplamı, hâlâ ikisi birden olan 51 ilde "kent/kır"
denen şeyin ta kendisi.

18.402 köy, 2013-2025, 51 il. 6360 sayılı yasa 2014'te büyükşehirlerdeki bütün köyleri
mahalleye çevirdi, o illerde köy **yok** — eksik değil. Denetim: köy + mahalle, her ilin
yayımlanan nüfusunun %99,8-100'ünü veriyor.

Kayıt yine gözlemden kuruldu (K11) ve kimlik yine MEDAS kodu (K15). Buna en çok burada
ihtiyaç var: etiket 2017'den itibaren bucağı yazmayı bırakıyor
(`Sivas(Akıncılar/Merkez Bucağı/Abdurrahman Köy.)` → `Sivas(Akıncılar/Abdurrahman Köy.)`),
yani o tarihten sonra ad tek başına hiçbir şeyi tanımlamıyor — bir ilçede birkaç tane
`Yeni Köy.` var. Üç parça bekleyen ilk ayrıştırıcı dokuz yılı sessizce düşürmüştü.
1.058 ad değişikliği `docs/koy-adlari.md` dosyasında.

## Oturum notu — 2026-08-14/15

Bir oturumda yapılanlar, sıradaki oturum buradan devam etsin diye.

**Yüklenen veri.** Doğum, ölüm (cinsiyet), bebek ve beş yaş altı ölüm hızı (2009-2025) ·
doğal nüfus artışı (türetme) · evlenme, boşanma (2001-2025) · ortalama evlenme yaşı ve
ilk evlenme yaşı (cinsiyet; evlenme yaşında toplam türetiliyor) · kütük nüfusu
(2007-2025, İlinde / İl dışında kırılımıyla) · mahalle nüfusu 81 ilin tamamı (12.750
mahalleden 32.681'e). Depo 1,97 milyon satır, 25 gösterge. Kararlar K19-K24.

**Doğrulama.** Doğum, ölüm ve doğal artış Wikipedia'nın TÜİK tablosuyla on altı yılda
birebir. Evlenme/boşanma ve doğum/ölüm sayıları, yüklemediğimiz kaba hızlara karşı
sınandı: 1.394-1.558 il-yılda ortalama mutlak fark 0,01‰ ile 0,10‰ arasında. Kütük
toplamı ile ADNKS nüfusu arasındaki fark, o yılın yabancı uyruklu nüfusu kadar.

**Bulunan on bir mantık hatası.** Hepsi sessizdi — yanlış sayı üretiyor ya da doğru
seçeneği ortadan kaldırıyorlardı, hiçbiri hata vermiyordu. K21 üçünü, K23 eksen hatasını,
K19 ölüm yükleme hatasını anlatıyor. Kalanlar: masaüstü kaynağı taşınınca bütün yükleme
çöküyordu (artık `raw/` kopyası kullanılıyor) · aynı yıl iki dosyada gelince çift anahtar
· köy etiketi 2017'den itibaren bucağı yazmayı bırakıyor ve üç parça bekleyen ayrıştırıcı
dokuz yılı düşürüyordu · nüfusa oran, nüfus dosyası gelmeden hesaplanıp boş sonucu
belleğe yazıyordu · tek kırılımlı göstergede iki ayrı ada sahip aynı yüzde · nüfusa oran
kipinde alt başlık başka bir kipin adını yazıyordu. Çekicide üç hata daha: yıl listesinin
altı ekrandan taşıyor, `has_text` gevşek eşleşiyor, MEDAS'ın alan sayacı iş sürerken
tırmanıyor (33 → 39 → 82) ve dilim boyu ona göre yanlış hesaplanıyordu.

**Arayüz.** OWID'in eşiği ölçüldü ve uygulandı (K22). Kırılım değerleri artık sözlükteki
sırayla. 18+ gruplaması eklendi: mahallede yerli, il ve Türkiye'de tek yaş tablosundan
(`needs_fine`), ilçede sunulmuyor çünkü 15-19 bandı onsekizin iki yanına düşüyor.

**Geliştirme sunucusu.** `scripts/serve.py`, `no-store` gönderiyor. Tarayıcı bir gün
boyunca eski `explorer.js`'i çalıştırdı ve düzeltilmiş üç hatayı düzelmemiş gösterdi;
`python -m http.server` bu iş için yeterli değil.

**Excel.** `scripts/build_settlement_excel.py` → `cikti/mahalle-nufus.xlsx`. Sayfalar:
Özet, Mahalleler, Köyler, İlçeler, İller, Yıllar, Notlar. Kapsam sütunu kritik: mahalle
verisi belediye mahalleleridir, Türkiye'nin %95'i ama Ardahan'ın %47'si. Kent/kır ayrımı
yalnız 51 ilde hesaplanabiliyor — 6360 sayılı yasa büyükşehirlerde köy bırakmadı.

**Köy verisi depoya alındı** (K25): kayıt, adaptör, yeni `village` düzeyi, sayfaya tembel
yüklenen `population-village.csv.gz`.

**Kent/kır için iki kaynak notu, sıradaki oturuma.** Şu an ayrım yalnız yerleşim türünden
çıkıyor (belediye mahallesi = kent, köy = kır) ve yalnız 51 ilde işliyor. İki kaynak daha
var:

* **Wikipedia'nın ilçe sayfaları** mahalleleri "Merkez" ve "Kırsal" diye ayırıyor
  (Akhisar'ın mahalleleri kutusu böyle; Kalecik'te Gölköyü "kırsal mahalle" olarak
  geçiyor). Büyük oranda doğru ve büyükşehirleri de kapsıyor — bizim kaynağımızın
  yapamadığı tam olarak orası. Eşleştirme ad üzerinden olacağı için dikkat ister.
* **TÜİK'in yeni sınıflaması üçe ayırıyor** (ikiye değil). Hangi tanımı esas alacağımız
  bir karar: iki kaynağa göre iki ayrı sütun tutmak, hangisinin ne dediğini görünür
  bıraktığı için tek bir "doğru" ayrımdan iyi olabilir.
* Seçim verisindeki (7H) kent-kır etiketi üçüncü kaynak; mahalle düzeyinde ve 2015 için.

## Sıradaki oturum — açık maddeler (2026-08-14, akşam)

0. **Kütük karesinin tamamı: kim nerede yaşıyor.** İndirdiğimiz dosya 81×81'lik bir kare
   ve şu an ondan yalnız iki sayı okuyoruz — sütun toplamı (kütük nüfusu) ve köşegen
   (ilinde yaşayan kendi kütüklüleri). Kare olduğu gibi saklanırsa iki soru daha
   açılıyor: "İstanbul kütüklüleri hangi illerde yaşıyor" (sütunun dağılımı) ve "bu ilde
   yaşayanlar hangi ilin kütüğünde" (satırın dağılımı — İstanbul'da en çok hangi
   memleketten insan var). Veri zaten elimizde, maliyeti yalnız 81 değerli bir kırılım
   saklamak: 81 il × 81 kütük × 19 yıl = 124.659 satır, bugünkü ilçe dosyasının beşte
   biri. Pahalı değil ama şimdilik gerekmiyor; not olarak duruyor.

1. **Bursa dışındaki iller için mahalle verisi.** Tek dosya ikinci ilde şişer; K14'ün
   düzey-başına bölmesi mahallede il-başına bölmeye dönüşecek (ilçe sınırlarının zaten
   yaptığı gibi). Mahalle sınır geometrisi yok, o yüzden mahallede harita açılmıyor —
   ve bulunmazsa açılmayacak.
2. **Haritada varsayılan ölçek.** Ortanca yaş 35-45 aralığında; log ramp orada bir işe
   yaramıyor. Varsayılan, göstergenin birimine göre seçilebilir (sayım → log,
   sınırlı/oransal → doğrusal) — şimdilik okuyucu tek tıkla değiştiriyor.
3. **Ortanca yaşta toplam yok.** Kaynak dosya yalnız erkek/kadın veriyor. Toplam
   isteniyorsa MEDAS'tan ayrı çekilmeli — iki medyanın ortalaması medyan değildir.
4. **Mahallede cinsiyet kırılımı.** MEDAS bu düzeyde yaş *ya da* cinsiyet veriyor,
   ikisini birlikte değil. Cinsiyet kesiti ayrı bir çekim.

## Açık işler

Sıra, birbirine bağımlılığa göre:

1. ~~Kanonik olgu tablosu şeması~~ — bitti, bkz. K6.
2. ~~Gösterge sözlüğü~~ — bitti, bkz. K7.
3. **Zamana bağlı coğrafya kaydı** — ülke / 7 bölge / 81 il yapıldı (`src/veriatlas/data/areas_tr.csv`,
   81 il + ülke, ISO 3166-2:TR). İlçelerin *bugünkü* listesi ve sınırları da geldi
   (`areas_tr_districts.csv`, 973 ilçe, bkz. K11). Kalan zor yarı aynen duruyor:
   geçerlilik aralıkları ve ardıl eşlemesi — kaynağı yok, gözlemden ya da elle
   doğrulanarak kurulacak.
4. **Adaptör sözleşmesi** — kuruldu, bkz. K8. Sıradaki adaptörler: EVDS3 (API var),
   MEDAS (Playwright), Dünya Bankası (SDMX).
5. **Kalite kuralları** — pandera şemaları, yükleme sırasında çalışır.
6. **Arayüz dönüşümü** — iskelet kuruldu, bkz. K10. Kalan: harita geometrisi (il/İBBS
   sınırları), çoklu seçim kısayolları (Ctrl/Shift), eski `index.html`'in kaldırılması.
7. **MEDAS adaptörü** — akışın ilk yarısı çalışıyor (bkz. medas.md); kalan: Zaman →
   Düzey → Rapor Oluştur → sayfalı tablo.
8. **Kod dili geçişi** — mevcut `config.py` ve `scripts/` Türkçe docstring'li;
   K1'e göre İngilizceye çevrilecek.

## İlk yükleme — TFH (2026-08-13)

`scripts/load_tfr.py`, 81 il × 17 yıl = 1.377 satır, `public/fact_tfr.parquet` ve
`warehouse.duckdb` içindeki `fact` tablosu. Şema gerçek veriyle sınandı ve tuttu.

Yüklenen veri ön çalışmanın bulgularıyla karşılaştırıldı, hepsi tutuyor: 2025'te
1,30 altı 38 il, 2,10 üstü 5 il, Bursa 1,78 → 1,32, en düşük Bartın 1,09. İki görünür
sapmanın ikisi de eşik sorunu çıktı — Nevşehir 2009'da tam 2,10 (yani "2,10 üstü 31
il" aslında "2,10 ve üstü"), ve 2025'te Ankara/Eskişehir/Zonguldak 1,11'de eşit.

Yükleme sırasında öğrenilenler:

- **Hiçbir kaynak dosyada alan kodu yok**, sadece Türkçe il adı. Ad eşleşmesi bu yüzden
  içe aktarmanın en sessiz hata yolu; `areas.resolve` tanımadığı adı boş kimliğe
  çevirmek yerine hata veriyor.
- **Plaka kodları 1989'daki adlara göre alfabetik.** Mersin (İçel), Şanlıurfa (Urfa) ve
  Kahramanmaraş (Maraş) sonradan adlandığı için bugünkü adla sıralama yanlış kod verir.
- **Dosyada sürüm bilgisi yok.** TÜİK'in bu sayıları ne zaman yayımladığı yazmıyor;
  `vintage` şimdilik çekim ayıyla (`2026-08`) dolduruldu. MEDAS adaptörü rapor başlığını
  okuyunca gerçek yayım tarihiyle değişecek. Bilinen açık.
- **Birim gösterge sözlüğü gelene kadar betiğe gömülü** (`çocuk/kadın`). Sözlük
  yazılınca oradan okunacak.

## Bölge düzeyi ve ağırlıklı toplama (2026-08-13)

Coğrafya kaydı `scripts/fetch_areas.py` ile üretiliyor: ülke, 7 coğrafi bölge,
**12 İBBS-1 bölge**, **26 İBBS-2 alt bölge**, 81 il. İl listesi ve nüfuslar
TurkiyeAPI'den; İBBS eşleşmesi elle tutulan `data/nuts_tr.csv`'den (TurkiyeAPI İBBS
taşımıyor, TÜİK ise o düzeylerde yayımlıyor).

**Üyelik ayrı tabloda** (`data/area_parents_tr.csv`): bir il aynı anda iki hiyerarşiye
bağlı — coğrafi (Marmara) ve istatistiki (TR41). Tek `parent_id` sütunu birini seçip
diğerini kaybetmeye zorlardı.

İBBS-1 değeri illerden doğrudan toplanıyor, İBBS-2 üzerinden değil: ortalamanın
ortalaması ağırlığı bozar.

Çalışma anında dış servise bağlanmıyoruz: veri bir kez çekilip kendi kaydımıza yazılıyor,
kaynak ve çekim tarihi kayıtta duruyor.

**Bölge değeri ağırlıklı ortalamayla hesaplanıyor** (`src/veriatlas/aggregate.py`).
Toplamlar toplanır, oranlar toplanmaz: doğurganlık bir orandır, yedi ilin düz ortalaması
o bölgenin doğurganlığı değildir — 90 bin nüfuslu il İstanbul kadar sayılırdı. Nüfusla
ağırlıklandırmak bunun en kötü kısmını düzeltiyor.

Yine de yaklaşık: doğru ağırlık doğurgan çağdaki kadın nüfusu, toplam nüfus değil. Bu
yüzden üretilen her satır `estimated` işaretli — grafikte sarı "tahmin" rozetiyle
görünüyor. Kalite bayrağı makinesinin ilk gerçek kullanımı bu oldu.

Ağırlıklar `src/veriatlas/data/area_weights_tr.csv`'de, kayıttan ayrı tutuluyor: ad
kalıcıdır, nüfus ise tarihi olan bir gözlemdir.

## K8 — Adaptör sözleşmesi (2026-08-13)

`src/veriatlas/adapters/`. Sözleşme kasıtlı olarak küçük, çünkü kaynaklar birbirine hiç
benzemiyor (EVDS bir REST API, MEDAS bir tarayıcı oturumu, ilkimiz diskteki bir dosya):

- `fetch()` — ham baytları `raw/` altına getirir, dokunmadan saklar
- `parse()` — o baytları olgu tablosu satırlarına çevirir
- manifest — çalıştırmanın kaydı, `raw/manifests.jsonl`'a eklenir

Ayrım önemli: **hatayı ayrıştırmada yaparız.** Ham kopya durduğu için ayrıştırma
hatası düzeltilip yeniden oynatılabilir — kaynağa dönmek gerekmez, ki kaynak o zamana
kadar veriyi revize etmiş, adını değiştirmiş ya da kaldırmış olabilir.

Manifest ham baytların sağlamasını (SHA-256, kısa) tutuyor: "bu dosya geçen seferkinden
farklı mı" sorusu diff almadan, "şu grafiği hangi veri sürümü üretti" sorusu kaynak
değiştikten sonra da cevaplanabiliyor. Dosya ekleme-only, üzerine yazılmıyor.

**Doğrulama adaptörün işi değil.** `ingest()` her kaynağı aynı şemadan ve aynı kırılım
denetiminden geçiriyor; ayrıca gösterge kimliği ile birimin sözlükle uyuştuğunu
sınıyor. Yani yeni bir adaptör olgu tablosunun kabul ettiği şeyi sessizce genişletemez.

İlk adaptör (`TuikTfr`) bilerek en garip vaka seçildi: servis değil, elle indirilmiş
bir dosya. Sözleşme hem onu hem REST API'yi bükülmeden taşıyabiliyorsa doğru şekildedir.
`scripts/load_tfr.py` kalktı, yerine `scripts/load.py` geldi.

## Kaynak kısıtları (değişmedi)

- Sektörel GSYİH: MEDAS'ta `FAALİYET A10` sunucu tarafında kilitli, çekilemiyor
- İlçe düzeyi TFH: TÜİK yayınlamıyor
- 2013+ kent/kır: TÜİK'te yok, IPF ile tahmin edildi — kalite bayrağı "tahmin"
- Yabancı uyruklu nüfus: henüz çekilmedi

Ayrıntı: [oturum-2026-08-13.md](oturum-2026-08-13.md)
