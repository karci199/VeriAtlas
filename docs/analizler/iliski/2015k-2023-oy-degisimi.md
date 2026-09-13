# İlişki: 2015 Kasım → 2023 milletvekili oy değişimi ve mahalle profili

Tarih: 2026-09-14. Betikler: `scripts/analiz/oy_degisim_{endeksa,tuik}_{ittifak,parti}.py`.
Ham çıktılar: `cikti/`.

## Veri

- Seçim: `public/tiles/secim-mv2015k|mv2023-mahalle-TR-*.json` (mahalle, geçerli oy payı).
- Endeksa demografisi (`C:\veri-ham\endeksa\demography`): eğitim, SES, gelir, yaş, kira.
  **Bugünün (2023-24) verisi**, 2015'in değil.
- TÜİK (depo): mahalle nüfusu 0-17 / 18+ 2015 ve 2023, medeni durum; ilçe eğitim düzeyi 2023.
- Eşleşme: ilçe + katlanmış mahalle adı. Endeksa 18.939, TÜİK 15.852 mahalle (her iki seçimde
  ≥300 seçmen); ilçe 968.
- Ortalamalar seçmen sayısıyla ağırlıklı; dilimler 10'luk (1 = en düşük).
- İttifaklar: Cumhur = AKP+MHP+BBP+YRP; Millet = CHP+İYİ+Saadet+DP; Emek = HDP→YSP+TİP.
  2015'te aynı partiler toplanarak karşılaştırıldı.

## Bulgular — ittifak

Genel: Cumhur −13,2 · Millet +9,1 · Emek +0,1.

- **Eğitim/SES:** üniversite oranı en düşük dilimde Cumhur −2,9, en yüksekte −16,3; Millet
  +4,3 → +11,2. İlçe düzeyinde TÜİK eğitimiyle aynı yön (−4,6 → −14,8).
- **Kaleler:** 2015 Cumhur %83-88 olan mahallelerde Cumhur −17,6 (r = −0,46).
- **Genç / çok çocuklu / katılımı düşen mahalleler (çoğu Güneydoğu):** Cumhur ≈ 0,
  Emek −5…−9.

## Bulgular — parti

Genel: AKP −14,2 · CHP −0,3 · MHP −2,7 · HDP→YSP −1,7.

- **AKP kaybı neredeyse her profilde ~−10…−18; asıl belirleyen 2015'teki kendi gücü**
  (r = −0,78 mahalle, −0,85 ilçe): AKP'nin %80 üstü aldığı mahallelerde −29,5.
- **MHP en çok eğitimle ayrışıyor:** az eğitimli / düşük SES mahallelerde +5…+7, eğitimli
  ve varlıklı mahallelerde −6,6 (r = −0,34). Kalelerde +11 (Cumhur içi aktarım, ör. Hasköy).
- **CHP neredeyse sabit:** kentli-eğitimli mahallelerde hafif düşüş (−1,5…−2), genç ve
  çok çocuklu mahallelerde +3…+4,3. Artışın bir kısmı HDP'den taktik oy.
- **HDP→YSP:** genç, çok çocuklu ve katılımı düşen mahallelerde −5…−7 (katılım r = +0,32).

## Yorum

1. Parti bazında "AKP her yerde kaybetti" görünür; kaybın nereye gittiği ancak ittifakla
   görünür: eğitimli-kentli mahallede İYİ ve CHP'ye (Millet), kırsal ve kalelerde MHP ve
   Yeniden Refah'a (Cumhur içinde).
2. CHP'nin sabit görünmesi, Millet artışının İYİ Parti'den geldiğini gösterir; CHP'nin
   kendi oyu yer değiştirdi (kentten Güneydoğu'ya taktik oy).
3. HDP çizgisindeki gerileme başka partiye geçişten çok katılım düşüşüyle birlikte gidiyor.
4. İlişkiler orta düzey; nedensellik değil örüntü. Endeksa demografisi bugüne ait; göç
   eden nüfus 2015 profilini değiştirmiş olabilir. İttifak listeleri (2023) bazı
   mahallelerde parti payını sıfırlar (ör. Aksaray CHP).
