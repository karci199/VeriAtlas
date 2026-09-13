# Yol haritası

Bu dosya "sırada ne var" sorusunun tek cevabı. Kararların gerekçesi
[kararlar.md](kararlar.md)'de; burası yalnızca sıra.

Son güncelleme: 2026-09-13.

## Dal kuralı (2026-09-10, `koy-kaydi` dalından)

Bir worktree'de başka dallar birleştirilip iş orada sürdürülürken çekim komutları güncel
olmayan ana checkout `C:eri`'de çalıştırıldı ve eski betik sürümü veri kirletti. Kural:
oturum başında `git branch --show-current` ve `git status --short` ile nerede olunduğu
doğrulanır; çekim, kodu güncel olan kopyada çalışır.

2026-09-13'te `durum-ozeti-plan` ve `koy-kaydi-ve-semt-duzeltmeleri` birleştirildi (K32):
iki dal 2007-2012 yerleşim geriye doldurmasını ayrı ayrı yapmıştı.

## Nerede duruyoruz

Depoda **74 gösterge, 5,78 milyon satır**. Altı depolanan düzey: ülke, İBBS-2 (göç
matrisi), il, ilçe, mahalle, köy.

| Gösterge | Düzey | Yıl | Kırılım |
|---|---|---|---|
| Nüfus | Türkiye, il | 2007-2025 | tek yaş × cinsiyet |
| Nüfus | **ilçe (998)** | 2007-2025 | 5'lik yaş × cinsiyet |
| Nüfus | mahalle (38.408) | 2007-2025 | 0-17 / 18+ |
| Nüfus | köy (35.345) | 2007-2025 | yok |
| Hemşehrilik, diaspora, doğum yeri | **ilçe × 81 il** | 3 kesit | K30 — tam kare depoda, ekrana özet |
| Medeni durum | Türkiye, il, ilçe (989) | 2008-2025 | medeni durum × cinsiyet × yaş |
| Hanehalkı sayısı / büyüklüğü / tipi | Türkiye, il, **ilçe** | 2008-2025 | tip |
| Doğum | Türkiye, il | 2009-2025 | annenin yaş grubu |
| Doğum, ölüm, evlenme, boşanma | ilçe | 2009/2014-2025 | cinsiyet (ölüm) |
| Ölüm | Türkiye, il | 2009-2025 | yaş grubu × cinsiyet; Türkiye'de tek yaş; neden (2022+) |
| Evlenme | Türkiye, il | 2001-2025 | **kadın yaşı × erkek yaşı** |
| Boşanma | Türkiye, il | 2001-2025 | yok |
| Göç | il; İBBS-2 matrisi | 2008-2025 | — |
| Kütük nüfusu | il | 2007-2025 | ilinde / il dışında |
| **Belediye su, atıksu, atık** (33 ölçü) | Türkiye, il | 2001-2024 | kaynak, arıtma, alıcı ortam, bertaraf |
| **Elektrik** tüketimi / üretimi / kurulu güç | il; üretim yalnız Türkiye | 2000-2024; 1970-2024 | tüketici grubu, kaynak |
| Ortanca yaş, TFH, yaşam süresi, yabancı uyruklu | Türkiye, il | değişken | değişken |

Seçim arşivi ayrı hatta (`C:\veri-ham\secim`, tablolar `public/tiles/secim-*.json`):
yurt içi sonuçlar sandık hariç en alt kırılımda tam. 2026-09-13'te yurt dışı ve gümrük
sonuç raporları ile yurt dışı seçmen profili (1.662 rapor) **indi, ayrıştırılmadı**.

Mahalle ve köy serileri 2013'ten **2007'ye** indi. İkisi birbirini doğruluyor: 2012'de
34.292 köy varken 2013'te 18.108 kalıyor, aynı geçişte mahalle 18.883'ten 31.653'e
çıkıyor — 6360 sayılı yasanın dönüşümü iki taraftan birden görünüyor.

## Sıra

İlçe yaş × cinsiyet, kütük 2007-2009 ve ölenin tek yaşı 2026-09-12'de yüklendi; bu
bölümden çıktılar.

### 1. Seçim: yurt dışı ve gümrük raporlarının ayrıştırılması

1.662 yurt dışı seçmen profili (ülke ve temsilcilik düzeyi) ile MV/CB/halkoylaması yurt
dışı, gümrük ve ülke geneli raporları ham HTML olarak duruyor. `aday_profili.py` ve
`parse_secim.py` kalıplarıyla okunacak. Çekici hatası: `fetch_secim_profil.fetch_one` yurt
dışı dosyasını yanlış klasöre yazıyor — kuyruk (`C:\veri-ham\secim_eksik_kuyruk.py`)
bunu atladı, repo dosyası düzeltilmeli.

### 2. Ekran: yeni göstergelerin sayfada görünmesi

Hanehalkı ilçe, evlenme yaş × yaş, belediye/elektrik dosyaları yazıldı, sayfada gözle
bakılmadı. İlçe kareleri için özet dosyasını okuyan bir görünüm yok.

### 3. Çekici yolları

Çekiciler ham veriyi worktree içindeki `raw/`a yazıyor, `C:\veri-ham`'a değil;
2026-09-13 çekimleri elle aynalandı. `config.RAW` ortam değişkenine bağlanmalı.
`fetch_medas_simple.build_query` bölünmez boşlukta eşleşemiyor (atık konusu).

### 4. Kent / kır ayrımının yeniden kurulması

Bugünkü ayrım yalnız yerleşim türünden çıkıyor (belediye mahallesi = kent, köy = kır) ve
yalnız 51 ilde işliyor, çünkü 6360 büyükşehirlerde köy bırakmadı. Elimizdeki mahalle ve
köy serileri artık 2007'ye kadar indiği için ayrımı yerleşimin gerçek karakterine göre
kurmanın veri tabanı var. Kaynak seçenekleri kararlar.md'de (Wikipedia ilçe sayfaları,
TÜİK'in üçlü sınıflaması, seçim verisindeki kent-kır etiketi).

### 5. Evlenme ve boşanmanın kalan kırılımları

Kadın × erkek yaş grubu yüklendi (`marriages_by_age`). Eğitim ve önceki medeni durum MEDAS'ta
alınamıyor. Kalan ve alınabilen: boşanmada bitiş nedeni, evlilik süresi, dava süresi —
kullanıcı kararıyla (2026-09-13) şimdilik gerek görülmedi.

### 6. Mahallede cinsiyet kesiti

MEDAS bu düzeyde yaş *ya da* cinsiyet veriyor, ikisini birlikte değil. Ayrı bir çekim,
aynı kayıt, `dims` sayesinde aynı göstergeye ek satır.

### 7. Ortanca yaşta toplam

Elimizdeki dosyada yalnız erkek/kadın var; iki medyanın ortalaması medyan değildir.

### 8. EVDS ve Dünya Bankası

Adaptör sözleşmesi (K8) bunlar için kuruldu, ikisi de yazılmadı.

### 9. Zamana bağlı coğrafya

Hâlâ açık ve hâlâ zor. İlçelerin geçerlilik aralıkları gözlemden çıkarıldı (K11), ama
**ardıl eşlemesi** yok. 2007-2012 geriye doldurması bunun beş vakasını görünür kıldı
(Akköy → Pamukkale gibi) ve köy defterine takma ad olarak yazıldı; ilçe düzeyinde aynı
iş yapılmadı. Bu olmadan uzun ilçe serileri sessizce yanlış: 2014'ün Aksaray Merkez'i ile
2020'ninki aynı alan değil.

## Kaynak kısıtları

MEDAS'ın vermedikleri kararlar.md'de ayrı başlıkta: ölüm × medeni durum (düğme
kayboluyor), ölenin tek yaşı il düzeyinde, ilçede bebek ölümü, sektörel GSYİH, ilçe TFH.

## Ekran — OWID'e göre eksikler

Sıralama değişmedi: dağılım grafiği (scatter) · yıl aralığı seçimi · görüntü olarak
indirme · gömme (embed) · kaynaklar sekmesi · yığılmış alan · eğim grafiği · harita
projeksiyonu.
