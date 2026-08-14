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

## Sıradaki oturum — açık maddeler (2026-08-14, akşam)

1. **Ortanca yaş göstergesi.** Elde MEDAS çıktısı var (`OrtancaYas.csv`, 2007-2025,
   cinsiyete göre, ülke + İBBS-1 + İBBS-2 + il). Toplanamaz bir birim, yani oran kipi
   (K13) kendiliğinden kapanacak — sözlüğe girip adaptörü yazılacak.

   **Tuzak:** dosyada 81 değil 78 il var. Ankara, İstanbul ve İzmir yalnız tek-il İBBS-2
   satırı olarak geçiyor (`Ankara-TR51`), MEDAS ikisini tek satırda birleştirmiş. Ad
   eşleşmesiyle içe aktarılırsa bu üç il il düzeyinde sessizce eksik kalır ve haritada
   "veri yok" gibi görünür — K6'daki tanınmayan-ad kuralının tam da önlemek istediği şey.
2. **Etiket kodları kaynak olarak.** MEDAS etiketleri kodu içinde taşıyor: il için plaka
   (`Adana-1`), İBBS için `TR62`, ilçe için MEDAS kodu (`-1757`). Ad yerine bunlarla
   eşleşmek yukarıdaki tuzağı da, ad değişikliklerini de kökten çözer.

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
