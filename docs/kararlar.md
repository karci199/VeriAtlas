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

## Açık işler

Sıra, birbirine bağımlılığa göre:

1. **Kanonik olgu tablosu şeması** — SDMX'ten sadeleştirilmiş. Vintage (veri sürümü)
   ve kalite bayrağı ilk sınıf alan olacak; ön çalışmadaki 1. ve 5. sorunun cevabı bu.
2. **Gösterge sözlüğü** — konu ağacı, birim, frekans, `label_tr` / `label_en`.
   Tanım kaymasını (bina ≠ daire) burada yakalıyoruz.
3. **Zamana bağlı coğrafya kaydı** — 6360 sayılı yasa, 2013 kırılması, sonradan
   kurulan ilçeler. Kod → geçerlilik aralığı → ardıl eşlemesi.
4. **Adaptör sözleşmesi** — fetch / parse / metadata + manifest. İlk iki adaptör:
   EVDS3 (API var) ve MEDAS (Playwright).
5. **Kalite kuralları** — pandera şemaları, yükleme sırasında çalışır.
6. **Kod dili geçişi** — mevcut `config.py` ve `scripts/` Türkçe docstring'li;
   K1'e göre İngilizceye çevrilecek.

## Kaynak kısıtları (değişmedi)

- Sektörel GSYİH: MEDAS'ta `FAALİYET A10` sunucu tarafında kilitli, çekilemiyor
- İlçe düzeyi TFH: TÜİK yayınlamıyor
- 2013+ kent/kır: TÜİK'te yok, IPF ile tahmin edildi — kalite bayrağı "tahmin"
- Yabancı uyruklu nüfus: henüz çekilmedi

Ayrıntı: [oturum-2026-08-13.md](oturum-2026-08-13.md)
