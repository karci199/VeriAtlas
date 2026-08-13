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

**Pasif düğme.** Birden çok "Tamam" var; `.last` pasif olana denk gelebiliyor. Etkin
olanı seçmek gerekiyor.

**Sunucu turu.** Her tıklamadan sonra `networkidle` + ~1 sn beklemek gerekiyor; adımları
zincirlemek çalışmıyor.

## Çalışan akış (Göstergeler sekmesi)

1. Konu = `Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları`
2. Ölçüm satırı = `İBBS-Düzey1, İBBS-Düzey2, İl ve İlçe Nüfusları`
3. Kırılım: `Cinsiyet` ve `Yaş Grubu` işaretle (Köy/Şehir işaretlenmiyor — kapsam dışı)
4. `Tamam`
5. `Göstergeleri Ekle` → "Seçili göstergelerle devam etmek için ileri butonuna basınız"

## Sırada

6. `İleri` → **Zaman** sekmesi: periyot ve yıllar
7. `İleri` → **Düzey** sekmesi: İl + Türkiye (ilçe kapsam dışı)
8. **Rapor Oluştur** → tablo. Rapor sayfalı gelebiliyor; tek sayfadan okumak eksik veri
   verir (ön çalışmada yaşandı).

## Kapsam kararı

İl ve Türkiye düzeyi, 5'lik yaş grupları × cinsiyet, 2007'den itibaren. Kent/kır
alınmıyor. Hedef: nüfus piramidi ve harita için gereken temel.

Elde hazır bir dosya da var (`Desktop/demografi/demografi2/il tek yaş ve cinsiyete göre
nüfus.xls`, 2007-2023, tek yaş × cinsiyet) ama 2024-2025 eksik; MEDAS'tan çekmek hem
güncel veriyi hem tekrarlanabilir bir yolu getiriyor.
