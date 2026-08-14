# MEDAS otomasyonu — saha notları

TÜİK MEDAS bir ZK (Java) uygulaması. Kimlikler oturuma göre üretiliyor, her tıklamadan
sonra sayfa sunucuda yeniden kuruluyor, hiçbir şeye sabit CSS kimliğiyle tutunulamıyor.
Aşağıdakiler `scripts/probe_medas.py` ile bulundu; adaptör bunların üstüne yazılacak.

## Tutunma noktaları

| Ne | Nasıl bulunur |
|---|---|
| Konu | Sayfadaki ilk `select`, 92 seçenek, etiketle seçiliyor |
| Ölçüm listesi | `.z-listitem` satırları |
| Kırılım listesi | `.z-listitem:has(.z-listitem-checkbox)` |
| Onay kutusu | Gerçek `input` **değil**: `.z-listitem-checkbox` sınıflı `span` |
| Düğmeler | Metinle (`Tamam`, `Yenile`, `İleri`, `Göstergeleri Ekle`) |

## Tuzaklar

**Kodlama.** MEDAS sayfayı ISO-8859-9 veriyor ama başlıkta başka bir şey söylüyor;
Türkçe karakterler bozuk geliyor (`K�r�l�m`). Bu yüzden tam metin eşleşmesi çalışmaz —
etiketlerin ascii'ye güvenli parçasıyla eşleştirmek gerekiyor (`BBS-D`, `Grubu`).

**Aynı kelime iki listede.** "Cinsiyet" hem kırılım listesinde hem ölçüm listesinde
("Cinsiyet oranı") geçiyor. Aramayı bütün sayfada yaparsan yanlışlıkla ölçümü
değiştiriyorsun ve kırılım paneli sessizce boşalıyor — hata vermiyor, sadece sonraki
adımda "Tamam" düğmesi pasif kalıyor. Aramayı onay kutusu olan satırlarla sınırla.

**Kırılım iki adım.** Kırılım listesinde `Cinsiyet` / `Yaş Grubu` satırını işaretlemek
yalnızca yarısı. `Tamam`'a basınca her boyut için bir **değer listesi** açılıyor
(`<Hepsi>`, Erkek, Kadın, 0-4, 5-9 …) ve asıl işaretlenmesi gereken oradaki `<Hepsi>`.
Atlanırsa MEDAS hata vermiyor, kırılımsız ölçümü ekliyor — indirilen dosya toplamla
birebir aynı çıkıyor. Sayfa bunu altta "Lütfen alt kırılım seçiniz!" diye söylüyor;
işaretlendiğinde `Seçilen gösterge adedi` 0 → 38 oluyor (19 yaş bandı × 2 cinsiyet).
Tek doğrulama bu sayaç: dosya boyutuna bakmak yetmez.

**Onay kutusu = seçim.** Listbox checkmark kipinde çalışıyor: `<i class="z-icon-check">`
her zaman markup'ta duruyor, CSS satır seçiliyken gösteriyor. Yani hiçbir sınıf
değişmiyor, durum ZK'nın kendi nesnesinden okunuyor: `zk.Widget.$(el).isSelected()`.

**Pasif düğme.** Birden çok "Tamam" var; `.last` pasif olana denk gelebiliyor. Etkin
olanı seçmek gerekiyor.

**Sunucu turu.** Her tıklamadan sonra `networkidle` + ~1 sn beklemek gerekiyor; adımları
zincirlemek çalışmıyor.

**Onay kutusu indeksi.** İki ayrı numaralandırma var ve karıştırılıyor: `visible_rows`
*kutusu olan* satırları sayıyor (`.z-listitem:has(.z-listitem-checkbox)`), oysa
`.z-listitem-checkbox` doğrudan kutuları sayıyor. İkisi ayrışır ayrışmaz yanlış satıra
tıklanıyor. Tek doğru yol `tick(page, index)`, çünkü o `visible_rows` ile aynı listeyi
indeksliyor. Medeni durum ölçümünde bu yüzden üç boyuttan ikisi seçiliyordu.

**Zorunlu kırılım zaten işaretli gelir.** MEDAS kırmızı yazdığı kırılımı (medeni durumda
`Medeni Durum`) ölçüm seçilir seçilmez işaretliyor. İşaret bir *anahtar*, tıklamak onu
**kapatıyor**. Kapanınca ölçüm eksik boyutla ekleniyor, hiçbir hata çıkmıyor, yalnız
`gösterge adedi` 0 dönüyor. Kural: tıklamadan önce `is_ticked` sor.

**CSV düğmesi rapor bitince belirir.** Sabit süre beklemek yanlış: küçük il saniyeler
sürerken İstanbul/Ankara/İzmir/Konya 60 sn'yi aşıyor. Mahalle çekiminde 13 il tam olarak
bu yüzden düştü — veri yok diye değil, beklemek yetmediği için. Düğmeyi `wait_for` ile
bekle, süreyi istenen hücre sayısıyla ölçekle.

**Kodlama ölçüme göre değişiyor.** İlçe ve mahalle indirmeleri ISO-8859-9; medeni durum
indirmesi **BOM'lu UTF-8**. Varsayma, tespit et.

## Çalışan akış (Göstergeler sekmesi)

1. Konu = `Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları`
2. Ölçüm satırı = `İBBS-Düzey1, İBBS-Düzey2, İl ve İlçe Nüfusları`
3. Kırılım: `Cinsiyet` ve `Yaş Grubu` işaretle (Köy/Şehir işaretlenmiyor — kapsam dışı)
4. `Tamam`
5. `Göstergeleri Ekle` → "Seçili göstergelerle devam etmek için ileri butonuna basınız"

4b. `Tamam`'dan sonra açılan değer listelerinde her boyutun `<Hepsi>`'sini işaretle
5. `Göstergeleri Ekle` → "Seçili göstergelerle devam etmek için ileri butonuna basınız"
6. `İleri` → **Zaman** sekmesi: periyot ve yıllar
7. `İleri` → **Düzey** sekmesi: İlçe Düzeyi + il HEPSİ + başlıktaki kutuyla tümünü seç
8. **Rapor Oluştur** → CSV düğmesi. Tablo sayfalı geliyor; tek sayfadan okumak eksik veri
   verir (ön çalışmada yaşandı), bu yüzden tablo değil CSV indiriliyor.

Kırılımlı ilçe sorgusu 38 × 973 × 1 yıl = 36.974 — 50.000 sınırının altında, ama ancak
yılda bir sorgu sığıyor.

## Mahalle akışı (2026-08-14)

Ölçüm `Belediye, köy ve mahalle nüfusları` — MEDAS'ın listesinde **küçük harfle**, dosya
başlığındaki Başlık Biçimi'yle değil. Tek kırılımı `18 yaş ve üzeri`, yani 2 gösterge; o
yüzden burada dar olan ölçüm, geniş olan düzey listesi. Çekim parçası **il**, ve iki
göstergeyle 13 yılın tamamı çoğu ile tek sorguda sığıyor.

Düzey sekmesindeki kutular zincirleme doluyor: Mahalle → il → `TÜM İLÇELER` → liste
başlığından tümünü seç. Biri atlanırsa sonraki hiç belirmiyor.

**Kırılım işaretliyken düzey kutusunda yalnız `Mahalle` kalıyor**; `Köy` ve `Belediye`
düşüyor. Yani 18 yaş bölmesi köyler için yayımlanmıyor. Sonucu: 6360 sayılı yasayla
köyleri mahalleye dönüşen 30 büyükşehirde kapsam tam (Bursa %99,3-99,8), kalan 51 ilde
ilin dörtte biri eksik (Yozgat %75-78). Bu bir çekim hatası değil, kaynağın kapsamı.

## Medeni durum akışı (2026-08-14)

Ölçüm `Medeni Duruma Göre Nüfus Bilgileri (15 Yaş üstü)`, üç kırılım birlikte: medeni
durum (5) × cinsiyet (2) × yaş grubu (17) = **151 gösterge**. Yıllar 2008-2025. Düzey
kutusu beş seçenek veriyor: Türkiye, İBBS1, İBBS2 (26 Bölge), İBBS3 (İl Düzeyi), İlçe.

Yaş 15'ten başlıyor — medeni durum yalnız 15 yaş üstü için yayımlanıyor, 0-14 eksik değil
yok.

Sütun başlığı üç boyutu tek hücreye paketliyor: `Erkek ve 15-19 ve Bilinmeyen`.

## Kapsam kararı

İl ve Türkiye düzeyi, 5'lik yaş grupları × cinsiyet, 2007'den itibaren. Kent/kır
alınmıyor. Hedef: nüfus piramidi ve harita için gereken temel.

Elde hazır bir dosya da var (`Desktop/demografi/demografi2/il tek yaş ve cinsiyete göre
nüfus.xls`, 2007-2023, tek yaş × cinsiyet) ama 2024-2025 eksik; MEDAS'tan çekmek hem
güncel veriyi hem tekrarlanabilir bir yolu getiriyor.
