# Yol haritası

Bu dosya "sırada ne var" sorusunun tek cevabı. Kararların gerekçesi
[kararlar.md](kararlar.md)'de; burası yalnızca sıra.

Son güncelleme: 2026-08-14.

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
