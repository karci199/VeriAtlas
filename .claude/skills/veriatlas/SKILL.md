---
name: veriatlas
description: VeriAtlas analiz paneli — doğal dille sorulan soruyu veriden cevaplar, grafiği/raporu ai/panel.html'e işler. "İstanbul'daki Sivaslılar", "Elazığ raporu çıkar", "evlenme yaşı en hızlı yükselen 5 il" gibi sorular için.
---

# VeriAtlas analiz becerisi

Kullanıcının sorusunu TÜİK verisinden cevapla ve sonucu **ai/panel.html**'e yeni bir
bölüm olarak işle. Panel sabit sayfadır; tarayıcıda açık durur, en yeni cevap en üste.

## Sıra

1. **Örneklere bak.** `ai/ornekler/` içinde benzer soru çözülmüş mü? Varsa aynı yolu izle.
2. **Sözlüğü oku.** `public/meta.json` — göstergeler `tree` altında, kırılımlar
   `dimensions`, türetmeler/oranlar/gruplamalar kendi anahtarlarında. **Sözlükte
   olmayan göstergeyi uydurma; yoksa "bu veri elimizde yok" de ve neyin olduğunu söyle.**
3. **Veriyi çek.** İki kaynak:
   - `warehouse.duckdb` (salt-okunur bağlan!) — tek tablo `fact`:
     `indicator_id, area_id, area_level, period_start(DATE), frequency, dims(JSON metni),
     value, unit, quality_flag, vintage, source_id, retrieved_at`.
     Python: `.venv\Scripts\python.exe` + `duckdb.connect(..., read_only=True)`.
   - `public/*.csv.gz` — sayfanın okuduğu son hal; hızlı bakış için yeterli olabilir.
4. **Çiz.** Kalıplar `ai/sablonlar/grafikler.html` içinde (çizgi, sıralama çubuğu,
   halter, referans çizgisi, olay notu). Rapor istenirse iskelet
   `ai/sablonlar/rapor-iskeleti.html`. Kalıbı kopyala, veriyle doldur; renk ve yazı
   her zaman theme.css belirteçlerinden, asla elle renk yazma.
5. **Panele işle.** `ai/panel.html` içindeki `<!-- ANSWERS:BEGIN -->` satırının hemen
   altına yeni `<section class="answer">` ekle (varsa `#empty` paragrafını kaldır).
   Bölüm başlığı = soru; `.meta` satırına tarih, gösterge, düzey, yıllar.
6. **Örneğe kaydet.** `ai/ornekler/NNN-kisa-ad.md` — biçim `ai/ornekler/README.md`'de.
   Kullanılan SQL'i birebir koy ki tekrar koşulabilsin.
7. Sonucu kullanıcıya bir-iki cümleyle özetle ve paneli tazelemesini söyle.

## Veri kuralları (docs/kararlar.md'nin bu işe düşen özü)

- **Toplama tuzağı:** aynı yılın toplam ve kırılım dosyasını birlikte toplama —
  çift sayarsın. `dims` süzgecini net kur.
- **TÜİK gizli hücreler:** mahalle düzeyinde bastırılmış hücre var; kırılım payı
  hesaplarken payda tam değilse oran verme.
- **Medyanlar toplanmaz:** ortanca yaşta iki cinsiyetin ortalaması alınmaz; toplam
  yoksa yok de.
- **Kaba hızlar (‰) toplanamaz**; il birleştirme gerekiyorsa paydaları topla, yeniden böl.
- **Alan eşleşmesi ada değil kimliğe** (`area_id`) göre — "Merkez"ler birbirini yutar.
- Sayı biçimi: binlik nokta, ondalık virgül, sondaki sıfır yazılmaz (44,5).
- Kaynak satırı her grafikte: "Kaynak: TÜİK MEDAS · VeriAtlas".
- Kod/yorum İngilizce, kullanıcı metni Türkçe (K1). Panele yazılan her şey Türkçe.

## Sınırlar

- Ana sayfaya (`web/`) ve ambara **yazma**; bu beceri yalnız `ai/` altına yazar.
- Alt ajan kullanma (CLAUDE.md kuralı) — her şey ana oturumda.
- Soru arayüzün iki tıkla yaptığı bir şeyse ("Ankara nüfusu haritada") paneli şişirme:
  ana sayfanın URL'ini üret ve ver, istiyorsa yine de panele işle.
