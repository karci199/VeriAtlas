# SGK istatistikleri — bulgular ve sıradaki iş

Bu dosya, SGK İstatistik Yıllığı'ndan (sgk.gov.tr) elle indirilip depoya henüz
alınmamış verilerle yapılan analizlerin izini tutuyor — hepsi tek oturumda,
`scripts/build_sgk_*.py` betikleriyle üretildi, çıktılar `cikti/analiz-sgk-*.xlsx`.

## Kaynak

SGK İstatistik Yıllıkları, `sgk.gov.tr/Istatistik/Yillik/fcd5e59b-6af9-4d90-a451-ee7500eb1cb4/`.
İndirilen zip'ler yerelde açık duruyor (oturuma özel geçici klasör, kalıcı değil —
tekrar üretmek gerekirse zip'ler aynı sayfadan indirilir, dosya kimlikleri
`f=...&d=...` sorgu parametresiyle dinamik ama sayfa kalıcı).

2025 ve 2014 sürümleri kullanıldı. **2014, cinsiyet kırılımlı karşılaştırma için
erişilebilen en eski yıl** — 2010-2013 arası birleşik format var ama il+cinsiyet+üç
statü bir arada veren temiz tablo (2014'teki Tablo 1.8 karşılığı) yok, 2008-2009
kurumlar hâlâ ayrı dosyalarda. Daha geriye gitmek riskli/emek yoğun, denenmedi.

**İlçe kırılımı hiçbir yerde yok** — ne yıllıklarda ne de SGK Veri Uygulaması'nda
(veri.sgk.gov.tr), oranın en ince coğrafi birimi il.

## Yapılan analizler

| Dosya | Konu | Kaynak tablo |
|---|---|---|
| `analiz-sgk-4a-4b-4c-il-2024.xlsx` | İl başına 4/1-a/b/c sayısı ve payı, 2024 | Tablo 1.7 |
| `analiz-sgk-4a-4b-4c-il-yillara-gore.xlsx` | Aynısı, 2014 vs 2025 fark | Tablo 1.7 |
| `analiz-sgk-formalizasyon-20-64-il-yillara-gore.xlsx` | Zorunlu sigortalılık oranı, 20-64 nüfusa göre, cinsiyet kırılımlı | Tablo 1.8 + nüfus |
| `analiz-sgk-isyeri-buyuklugu-il-2016-2025.xlsx` | İşyeri başına sigortalı (ortalama işletme büyüklüğü) | Tablo 1.10 |
| `analiz-sgk-sektorel-yapi-il-2025.xlsx` | Tarım/Sanayi/İnşaat/Hizmet payı, yalnız 4/1-a | Tablo 1.11 |
| `analiz-sgk-gunluk-kazanc-il-2025.xlsx` | Ortalama günlük kazanç, kamu/özel, kadın/erkek oranı | Tablo 1.17 |
| `analiz-sgk-emekli-aktif-pasif-il-2025.xlsx` | Emekli sayısı, aktif/pasif oranı | Tablo 2.5+2.19+2.32 + Tablo 1.7 |
| `analiz-sgk-emekli-nufus-il-2025.xlsx` | Emekli/nüfus oranı | Tablo 2.5+2.19+2.32 + nüfus |
| `analiz-sgk-sigortali-emekli-nufus-il-2025.xlsx` | Sigortalı/nüfus + Emekli/nüfus + toplamı, kaba nüfus | yukarıdakiler + nüfus |
| `analiz-sgk-sigortali-emekli-nufus18-il-2025.xlsx` | Aynısı, 18+ nüfusa göre | yukarıdakiler + population-age1 |
| `analiz-sgk-nufus-paydasi-karsilastirma-il-2025.xlsx` | Kaba nüfus vs 18+ paydası, sıra farkı | yukarıdakiler |

## Ana bulgular

- **4/1-c (memur) payı** doğuda en yüksek, batı sanayi kuşağında en düşük — Tunceli
  %48,6, İstanbul %7,2 (2025). Bu iller aynı zamanda eğitim analizindeki
  ([dogurganlik-evlilik-notlari.md](dogurganlik-evlilik-notlari.md) değil, ayrı bir
  eğitim analizi) "az öğrenci/az okul" ucuyla örtüşüyor — küçük nüfus + kamu ağırlıklı
  ekonomi aynı profilin iki yüzü.
- **2014→2025 4/1-c payı değişimi iki farklı mekanizma:** doğuda (Hakkari, Şırnak,
  Ağrı, Muş, Siirt) düşüyor çünkü 4/1-a (özel sektör) patlıyor — muhtemelen 6. bölge
  teşvikleri; Karabük/Karaman/Kırklareli/Isparta/Bilecik'te artıyor ama sebep farklı —
  orada 4/1-b (esnaf/çiftçi) çöküyor, boşalan pay a ve c'ye aritmetik olarak kayıyor.
- **Formalizasyon oranı (20-64, zorunlu sigortalı/nüfus):** TR %41,1 (2014) →
  %45,2 (2025). Kadın oranı her ilde erkekten hızlı artıyor — artışın motoru kadın
  istihdamı. Cinsiyet farkı Bolu/Burdur/Antalya/Karadeniz'de en hızlı daralıyor,
  Tunceli/Şırnak/Hatay'da açılıyor.
- **İşyeri büyüklüğü:** TR ortalaması 7,67 (2016) → 7,35 (2025) — küçülüyor, büyüme
  yeni işyeri açılışıyla oluyor. Hakkari/Hatay/Siirt/Bitlis'te büyüyor (mevcut
  işletmeler genişliyor); Karaman/Tekirdağ/Bursa'da küçülüyor.
- **Sektörel yapı (yalnız 4/1-a):** TR %60 hizmet, %26 sanayi, %13 inşaat, %1 tarım.
  Bilecik/Tekirdağ/Yalova/Manisa en sanayi ağırlıklı; Tunceli/Kars/Bayburt/Ardahan/
  Hakkari'de sanayi neredeyse yok.
- **Kamu/özel ücret farkı** — kamu her ilde daha yüksek (tekli sanayi devi olan
  Zonguldak-TTK, Batman-TPAO'da en uçta); Kocaeli/Sakarya/Bursa/Manisa/Tekirdağ'da
  (güçlü özel sanayi) en dengeli.
- **İsteğe bağlı sigortalılık payı** Rize'de %10,1 — diğer illerin 3 katı, muhtemelen
  gemi adamlığı/denizcilik kültürü. Güneydoğu'da (Şırnak %0,09, Hakkari %0,12) en
  düşük. Yurt dışı topluluk sigortalısı beklenenin aksine diaspora göstergesi değil —
  neredeyse tamamen Ankara+İstanbul'da (şirket merkezi kaydı etkisi).
- **Aktif/pasif oranı:** TR 2,12 (resmi rakamla uyumlu, doğrulandı). Şırnak 11,0 (en
  genç sistem), Sinop 1,19 (en yaşlı — muhtemelen TTK erken emekliliği + sahil
  emekliliği).
- **Emekli/nüfus:** TR %14,4 (kaba nüfus), %19,1 (18+ nüfus). 18+'a geçince en çok
  yükselen Hatay (+19 sıra, yüksek çocuk nüfusu yüzünden kaba nüfusta haksız geride
  kalıyordu), en çok düşen Tunceli (−15 sıra, düşük çocuk nüfusu kaba nüfusta yapay
  avantaj sağlıyordu).

## Yöntem notları (tekrar çekimde hataya düşmemek için)

- **Tablo 1.7 sütun düzeni yıla göre değişiyor** — 2014'te 4/1-a toplamı idx2, 4/1-b
  idx13, 4/1-c idx14; 2025'te 4/1-a idx2, 4/1-b idx11, 4/1-c idx17. Her yıl için ayrı
  doğrulama şart, körlemesine aynı indeksi taşımak yanlış sayı üretir (bir kez oldu,
  düzeltildi).
- **Tablo 1.8 (cinsiyet kırılımı) da yıl bazında farklı sütun sırası taşıyor** —
  2014'te Kadın önce, Erkek sonra; 2025'te Erkek önce, Kadın sonra. Bir kez bu yüzden
  kadın oranı %82 gibi imkânsız bir sayı çıktı, kaynağı buydu.
- **Yazdırma sayfası kırılımında başlık satırı tekrarlıyor** (özellikle eski format
  tablolarda) — il kodu sütunu sayıya çevrilemeyen satırlar sessizce atlanmalı,
  atlanmazsa `int()` hatası ya da (daha kötüsü) sessizce yanlış satır okunur.
- **"Genel toplam" satırı** bazı tablolarda (örn. Tablo 1.11) 82. "il" gibi görünüyor
  — filtrelenmezse Türkiye toplamı iki kere sayılır.
- Nüfus paydası için **20-64** (5'lik yaş grubu sınırına tam oturuyor) ya da **18+**
  (tek yaş dosyası gerekiyor, `population-age1.csv.gz`) kullanıldı; **65+ paydası
  bilerek kullanılmadı** — EYT sonrası emeklilik yaşı çok geniş bir banda yayıldı,
  65+ ile sınırlamak emeklilerin çoğunu dışarıda bırakırdı.

## Sıradaki iş (önerilip henüz yapılmayanlar)

- **İş kazası istatistikleri** (Bölüm 3-1/3-2, zip'te indirilmiş, hiç açılmadı) — il
  bazında risk haritası.
- **Primsiz ödemeler** (Tablo 2.38 — 2022 sayılı kanun, hiç prim ödemeden bağlanan
  aylık) — il bazında yoksulluk göstergesi olabilir.
- **Geçici iş göremezlik / hastalık izni** (Bölüm 4, Tablo 4.2) — il ve cinsiyete
  göre, dolaylı çalışma koşulları göstergesi.
- **SGK Mali Bünye** ve **Sağlık** göstergeleri (veri.sgk.gov.tr'de kategori olarak
  var, hiç incelenmedi).
- **Tarımdan çözülme haritası** — 4/1-b'nin 1479 (esnaf) / 2926 (çiftçi) ayrımı,
  önerildi, henüz çekilmedi.
