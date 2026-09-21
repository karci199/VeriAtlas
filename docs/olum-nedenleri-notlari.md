# Ölüm nedenleri — 2026-08-17 oturumu

Ölümün *nedeni* bu depoya ilk kez giriyor. Buraya yazılan şey sayıların kendisi değil,
**hangi ölçünün nerede kırıldığı** ve kaynağın nerede durduğu.

## Kaynak: neden MEDAS'ta yok, portalda var

MEDAS'ın 107 konusu tarandı (`raw/medas/probe/02-konu.html`). **Ölüm nedeni diye bir konu
yok.** `Ölüm İstatistikleri` altındaki altı ölçümün hiçbiri nedene bakmıyor; kırılımlar
cinsiyet, ay, medeni durum, yaş grubu ve yaşla sınırlı (`raw/medas/kesif/l-m-statistikleri.json`).

Neden verisi **TÜİK Veri Portalı**'nda, ayrı bir sistemde ve ICD-10 ayrıntısıyla
yayınlanıyor. Yani "TÜİK yayınlamıyor" demek yanlış; **MEDAS yayınlamıyor** demek doğru.
Bu ayrım, bundan sonra bir gösterge aranırken iki yere birden bakmayı gerektiriyor.

MEDAS'tan çekilenler (`fetch_medas_simple.py`'ye eklendi):

| Dosya | Kırılım | Yıllar | Düzey |
|---|---|---|---|
| `nufus-intihar-yas-country.csv` | yaş × cinsiyet | 2002-2025 | ✘ TR |
| `nufus-kaba-intihar-hizi-province.csv` | — | 2002-2025 | 81 il |
| `nufus-trafik-olu-province.csv` | cinsiyet | 2012-2025 | 81 il |

Portaldan gelenler (kullanıcı indirdi, `Desktop/demografi/Ölüm/`): neden × cinsiyet,
neden × cinsiyet × yaş, il × neden, il × cinsiyet intihar (2018-2025), intihar × eğitim ve
× medeni durum (2000-2025).

**Boşluk:** hiçbir kaynakta `il × neden × yaş` yok. Bu kesişim olmadığı için il düzeyinde
yaşa göre standardizasyon yapılamıyor — aşağıdaki düzeltme bu yüzden dolaylı.

## Bulgu — 15-24 erkek ölümünün yarısı dışsal

2025, Türkiye, dışsal yaralanma nedenleri (V01-Y89) toplam ölüm içinde:

| Yaş | Erkek | Kadın |
|---|---|---|
| 15-24 | **%49,9** | %32,5 |
| 25-34 | %44,4 | %22,1 |
| 45-54 | %10,5 | %4,7 |
| 65-74 | %2,2 | %1,6 |
| Tümü | %5,4 | %2,3 |

Bu, "genç erkek ölüm hızı neden düşmedi" sorusunun cevabı: o yaştaki ölümlerin yarısı
tıbbın konusu değil. Sağlık sistemi 65 yaşındaki ölümü erteliyor, 20 yaşındakini
erteleyemiyor.

Ayrıştırma (2009→2025, 20-24 erkek): intihar hızı **+%140**, diğer bütün nedenler
**−%1**. Toplamın sabit görünmesi bir denge değil, bir ikame. Aynı bantta kadında diğer
nedenler −%36 düştü. Makas erkek kötüleştiği için değil, kadın iyileştiği için açıldı.

İntihar 2002→2025: erkek 1.392 → 3.684 (+%165), kadın 909 → 915 (sabit). E/K 1,53 → 4,03.
Cinayet ise 2022→2025 düşüyor: 940 → 714. İkisi zıt yönde — yani artış genel bir şiddet
artışı değil, kendine yönelen şiddete özgü.

## Ölçünün kırıldığı yer: il sıralaması üç ayrı cevap veriyor

`İl ve seçilmiş ölüm nedenlerine göre ölümler.xls`, 2022+2024+2025 havuzlandı
(**2023 dışlandı: deprem dışsal nedene yazılıyor**, TR toplamı 20 binden 66 bine çıkıyor —
bu, deprem yılını dışlama kararının bağımsız doğrulaması).

| Ölçü | Tepe | Dip | 65+ payı ile korelasyon |
|---|---|---|---|
| dışsal / toplam ölüm | Şırnak %7,94 | Giresun %1,61 | **r = −0,69** |
| dışsal / 100 bin nüfus | Burdur 50,1 | İstanbul 11,0 | **r = +0,55** |
| yaş yapısına göre artık | Muğla +2,17 | İstanbul −2,84 | — |

İlk ikisi birbirinin neredeyse tersi: Şırnak payda 1., hızda 73. Pay yaş yapısını ölçüyor
(genç ilde payda küçük olduğu için dışsal otomatik büyük pay alır), hız da ters yönde aynı
hatayı yapıyor. Üçüncüsü `beklenen pay = 7,15 − 0,358 × (65+ payı)` regresyonunun artığı.

**Kural: sayfaya konacaksa üçü birden konmalı.** Tek başına her biri "en tehlikeli il"
sorusuna farklı ve tek başına yanlış bir cevap veriyor.

İki grup ayrışıyor: Güneydoğu (Şırnak, Şanlıurfa, Batman, Diyarbakır) payda yüksek ama
hızda düşük — orada dışsal ölüm az, diğer ölümler daha da az. Batı-güneybatı (Muğla,
Burdur, Antalya, Denizli, Isparta, Uşak) **üç ölçüde de** yüksek; sağlam olan bu.

İstanbul üç ölçüde de en düşük uçta ve yaş yapısı verildiğinde beklenenin yarısı. Bir kısmı
gerçek olabilir (kısa mesafe, toplu taşıma), ama **ikametgah kaydı** da şüpheli: İstanbul'da
çalışıp memleketine kayıtlı biri iş kazasında ölürse ölüm memlekete yazılıyor. Depodaki
kütük–ikamet makası (İstanbul −2.677.994) tam bu mekanizmayı ölçüyor.

## Yan bulgu

Isparta ve Burdur, birbirinden bağımsız iki ölçüde birlikte uçta çıkıyor: 20-24 E/K ölüm
makasında ve dışsal ölüm hızında. Aynı bölgede komşu iki orta ölçekli il. Tesadüf olabilir
ama iki ayrı ölçünün aynı yeri göstermesi mekanizma tezini destekliyor.

## Açık işler

- Trafik ölüsü il × cinsiyet çekildi ama **yaş taşımıyor** — 20-24 bulgusuna bağlanamıyor.
- İntiharın eğitim ve medeni durum kırılımı 2000-2025, hiç bakılmadı (en uzun seri).
- Neden verisi yalnız 2022-2025; eğilim bu dosyayla ölçülemez. Eğilim için tek seri intihar.
