# Yol haritası

Bu dosya "sırada ne var" sorusunun tek cevabı. Kararların gerekçesi
[kararlar.md](kararlar.md)'de; burası yalnızca sıra.

Son güncelleme: 2026-09-12.

## Dal kuralı (2026-09-10) — aynı sorunu tekrar yaşamamak için

Bugün iki kez aynı hata oldu: bir worktree'de (`claude/cekme-islemleri-rapor-8ecaf1`)
başka dallardan (`claude/veri-cekme-devami-de79ac`, `claude/koy-kaydi-ve-semt-duzeltmeleri`)
merge yapılıp asıl işe orada devam edildi, ama fetch komutları hâlâ **ana checkout**
`C:\veri`'de çalıştırılıyordu — o da güncel değildi, eski/hatalı betik sürümüyle veri
kirletti (bkz. aşağıdaki hemşehrilik il-indeks hatası).

**Kural: `C:\veri` tek çalışma kopyası.** Yeni bir worktree açıp oraya merge etmek yerine,
doğrudan `C:\veri`'de `git log --oneline --all` ile hangi `claude/*` dalının en ileride
olduğuna bak, `git merge` ile ana dala al, worktree'yi atla. Oturum başında
`git branch --show-current` ve `git status --short` ile nerede olduğunu doğrula.

## Çözüldü — MEDAS hemşehrilik il-indeks eşleşmesi (2026-09-10)

`fetch_medas_districts.py`'de `--il-no N`, açılır listedeki N'inci satırı seçiyor.
İlk şüphe "plaka koduyla eşleşmiyor" idi (79 = Kilis beklenirken Yalova geldi) ama bu
yanlış alarmdı: **gerçek sıra plaka değil, Türkçe alfabetik sıra** (Ç/Ş/Ğ/İ/Ö/Ü kendi
Türkçe alfabe yerinde) — 79 = Yalova zaten doğruydu.

81 dosyanın tamamı satır içeriğinden (gerçek ilçe adlarından) tek tek doğrulandı:
**79 dosya baştan doğruydu, yalnızca il80 ve il81 yanlıştı** — il80 Yalova'nın
mükerrer bir kopyasıydı (olması gereken Yozgat), il81 Yozgat verisi taşıyordu
(olması gereken Zonguldak); Zonguldak hiç çekilmemişti. İkisi de doğru numarayla
(`--il-no 80`, `--il-no 81`) yeniden çekildi ve içerik doğrulandı (`il: YOZGAT`,
`il: ZONGULDAK`). **81/81 il artık doğru.**

Not: çoğu ilde yalnızca 1-2 yıl dosyası var (İstanbul hariç, o 19 yılın tamamını tek
tek çekiyor) — `--il-no` varsayılan olarak `--tum-yillar` istiyor ama 50.000 sınırı
çoğu ilde tam 19 yılı tek seferde geçirmiyor, sweep de her zaman tamamlamamış
olabilir. İl-bazlı "tamam" ile yıl-bazlı "tamam" farklı şeyler — durum sayfası
yalnızca ili sayıyor, yıl derinliğini değil. Bu ayrı bir iş kalemi.

## Çözüldü — MEDAS tick-toggle hatası ve ilçe ölçümleri (2026-09-11/12)

`fetch_medas_districts.py`, okuma-yazma gibi bazı ölçümlerin kırılım satırlarıyla
**önceden işaretli** gelebildiğini hesaba katmıyordu; `tick()` bir toggle olduğu
için zaten işaretli satırı tekrar tıklamak işareti kaldırıyordu. `is_ticked()` ile
kontrol edilip yalnızca kapalı satırlar tıklanacak şekilde düzeltildi (hem keşif
hem yıl-sekmesi açma aşamasında). Sonuç: **MEDAS ilçe ölçümleri 4/60 → 85/60
(%100)**, **hemşehrilik il-il 80/81 → 81/81 (%100)**. `fetch_medas_simple.py`'ye
`ortanca-yas`, `dogum-yeri-tr`, `dogum-yeri-il` ölçümleri eklendi.

**2007 seçimi de tamamlandı** (`raw/secim`): `mv2007`, `ho2007` 923/923;
`aday2007` 85/85; `cikan2007` 1/1, hepsi "0 eksik".

## Çekim durumu — açık işler

Canlı sayılar `web/durum.html`'de (`scripts/durum_raporu.py` üretiyor, dakikada bir
yenileniyor). Sayfadaki yüzdelerin bir kısmı yakın zamana kadar gerçek durumla
çelişiyordu; yukarıdaki iki kalem düzeldi. Ama sayaç mantığı tam denetlenmedi —
seçim tarafında `fetch_secim.py`'nin kendi defteri "0 eksik" derken sayfanın farklı
bir yüzde göstermesi ihtimaline karşı yeniden kontrol edilmeden yüzdelere körü
körüne güvenilmemeli.

1. **MEDAS hemşehrilik CSV indirme zaman aşımına uğruyor.** `fetch_medas_hemsehrilik.py`
   il01 2023 için iki denemede de `Locator.click` 60 saniyede patlıyor (rapor sayfası
   hazır ama CSV düğmesi görünmüyor/gelmiyor). Tekrar çalıştırmak tek başına çözmedi;
   bekleme süresini uzatmak ya da düğme seçicisini gözden geçirmek gerekiyor.

Ayrıca: Endeksa mahalle demografisi son turda ardışık DNS hatası
(`getaddrinfo failed`) aldı — ağ kesintisi, gerçek veri eksikliği değil; bir
sonraki turda 972/973 ilçe dosyasıyla %100'e ulaştı.

## Nerede duruyoruz

| Gösterge | Düzey | Yıl | Kırılım |
|---|---|---|---|
| Nüfus | Türkiye, il | 2007-2025 | **tek yaş** × cinsiyet (sayfada 5'lik, istenirse tek yaş) |
| Nüfus | ilçe (973) | 2007-2025 | 5'lik yaş × cinsiyet |
| Nüfus | mahalle (Bursa, 1061) | 2013, 2025 | 18 altı / 18 üstü |
| Ortanca yaş | Türkiye, il | 2007-2025 | cinsiyet |
| Toplam doğurganlık hızı | Türkiye, coğrafi bölge, İBBS-1/2, il | 2009-2025 | yok |

Kırılımın üstünde iki katman var (K17): **gruplamalar** (geniş yaş grupları, doğurgan
çağ) ve **karşılaştırmalar** (erkek−kadın farkı, cinsiyet oranı). İkisi de sözlükte
tanımlı, depolanmıyor.

Sözlükte tanımlı ama verisi olmayanlar ekranda gri duruyor: kütük nüfusu, yaş yapısı,
kaba doğum hızı, yapı ruhsatı (bina ve daire).

## Veri — sıra

Bağımlılığa göre sıralı; üsttekiler alttakileri açıyor.

### 1. Mahalle verisini ülkeye yayma

Bursa deseni tuttu, geri kalanı tekrar. İki iş var:

- **Çekici.** `fetch_medas_districts.py`'nin mahalle sürümü: il × yıl döngüsü, MEDAS'ın
  50.000 sınırı yüzünden muhtemelen il başına birkaç yıl. Kırılım kutusu deseni aynı
  (bkz. `medas.md`).
- **İl başına dosya.** K14'ün düzey-başına bölmesi mahallede yetmez — 50.000 mahalle ×
  19 yıl ≈ 1,9 milyon satır. `population-neighbourhood-TR-16.csv.gz` gibi, okuyucu o ile
  bakarken o il iniyor. Sayfa ilçe *sınırlarını* zaten böyle çekiyor.

**İlk çekilecek il büyükşehir olmayan bir il olmalı** — beldelerin etiketin orta
parçasında görünüp görünmediğini ancak orada anlarız (kararlar.md, düzey adları).

### 2. Mahallede cinsiyet kesiti

MEDAS bu düzeyde yaş *ya da* cinsiyet veriyor, ikisini birlikte değil. Ayrı bir çekim,
aynı kayıt, `dims` alanı sayesinde aynı göstergeye ek satır olarak giriyor.

### 3. Ortanca yaşta toplam

Elimizdeki dosyada yalnız erkek/kadın var. Toplam ayrı çekilmeli — iki medyanın
ortalaması medyan değildir, hesaplayamayız.

### 4. Yaş yapısı (bağımlılık oranları)

Sözlükte tanımlı, verisi yok. Aslında nüfustan **türetilebilir**: 0-14 / 15-64 / 65+
payları ve yaşlı-bağımlılık oranı. K12'ye göre türetme olarak mı, ayrı gösterge olarak
mı duracağı kararlaştırılmalı — payda başka bir kırılımdan geldiği için oran kipiyle
(K13) aynı mekanizma değil.

### 5. Kaba doğum hızı, kütük nüfusu

MEDAS'ta ikisi de var, akış bilinen akış. Kaba doğum hızı toplanamaz bir birim (‰).

### 6. Yapı ruhsatı

Yeni konu, yeni MEDAS ağacı. Bina ve daire iki ayrı gösterge — aynı olgunun iki ölçümü
olduğu için tek göstergede kırılım yapmak yanlış olur.

### 7. EVDS ve Dünya Bankası

Adaptör sözleşmesi (K8) bunlar için kuruldu ama ikisi de yazılmadı. EVDS'nin API'si var,
Dünya Bankası SDMX. İkisi de zaman serisi; asıl iş coğrafya değil, dönem eşleme (aylık →
yıllık) ve o da olgu tablosunun `frequency` sütununda zaten karşılanıyor.

### 8. Zamana bağlı coğrafya

Hâlâ açık ve hâlâ zor: ilçelerin geçerlilik aralıkları gözlemden çıkarıldı (K11), ama
**ardıl eşlemesi** yok — bölünen bir ilçenin öncesi ile sonrası nasıl bağlanacak? Bu
olmadan uzun seriler ilçe düzeyinde sessizce yanlış.

## Ekran — OWID'e göre eksikler

OWID Grapher'ı ölçü aldık (K9/K10). Bugün olanlar: tablo (sıralanabilir), harita
(sınıflı renk ekseni, ülke çapı ilçe, ile tıklayınca açılma, pan-zoom), çizgi (eksen
seçimi, imleç okuması), sütun, piramit; mutlak/oran kipi; yedi türetme; düzey ve kırılım
denetimleri; paylaşılabilir bağlantı; CSV indirme; ayarlanabilir tema.

Eksikler, faydasına göre sıralı:

1. **Dağılım grafiği (scatter).** OWID'in en ayırt edici görünümü ve bizde hiç yok: iki
   *farklı* gösterge, biri x biri y, alanlar nokta, yıl kaydırmalı. "Doğurganlık ile
   ortanca yaş ilişkisi" ancak böyle sorulur. Sayfa şu an tek gösterge etrafında kurulu;
   bu, iskeletin en büyük değişikliği olur.
2. **Yıl aralığı seçimi.** Çizgide bütün yıllar çiziliyor, "2015-2025 arasını göster"
   denemiyor. Tek yıllık kaydırıcı var, aralık yok.
3. **Görüntü olarak indirme.** PNG/SVG yok. Bir grafiği rapora koymak için ekran
   görüntüsü almak gerekiyor.
4. **Gömme (embed).** OWID'in her grafiğinin iframe kodu var. Bizde bağlantı var, gömme
   yok.
5. **Kaynaklar sekmesi.** Alt satırda künye var ama OWID'deki gibi "bu göstergenin
   tanımı, kaynağı, sürümü, atıf metni" ayrı bir sekmede değil. Sözlükte bilgi zaten
   duruyor (`definition_tr`, `note_tr`, `sources`), gösterilmiyor.
6. **Yığılmış alan grafiği.** Yaş yapısının zaman içindeki değişimi için doğru görünüm
   bu; piramit tek yıl gösteriyor.
7. **Eğim grafiği (slope).** İki yıl arasında sıralama değişimi. Ucuz ve okunur.
8. **Harita projeksiyonu ve dilim yerleştirme.** Bizimki eşdikdörtgen + enlem düzeltmesi;
   yeterli ama OWID'deki gibi seçilebilir değil.

Ayrıca OWID'de olup bizde **bilinçli olarak olmayan** bir şey: onların "per capita"
düğmesi nüfusa bölüyor. Bizde oran kipi (K13) kırılım payı ya da Türkiye payı veriyor;
kişi başı hesap ayrı bir türetme olarak K12'de sırada duruyor ve nüfusu ikinci bir
gösterge olarak okumayı gerektiriyor — yani aslında 1. maddeyle aynı altyapı.
