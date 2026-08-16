# Arayüz planı — OWID Data Explorer modeli

Karar: ekranı gösterge türüne göre bölmüyoruz. OWID'in Data Explorer'ındaki gibi tek bir
çerçeve kuruyoruz; içindeki grafik değişiyor, çerçeve değişmiyor.

## OWID'in ekranı neye bölünmüş

| Bölge | İçerik |
|---|---|
| Sol ray | Başlık + açıklama, "ülke ekle" araması, sıralama, işaretli varlık listesi, "seçimi temizle" |
| Üst şerit | Boyut seçicileri: INDICATOR, SEX, AGE, PROJECTION SCENARIO |
| Orta | Grafik başlığı, **görünüm sekmeleri** (Table · Map · Line · Bar), grafik |
| Grafiğin altı | Zaman kaydırıcısı (oynat düğmesiyle), kaynak satırı, İndir / Paylaş / Tam ekran |

Kritik nokta: **grafik türü bir sekme, göstergenin dayattığı bir şey değil.** Aynı seri
tabloya, haritaya, çizgiye ve sütuna dönüşebiliyor; seçim ve boyutlar korunuyor.

İkinci kritik nokta: **boyutlar birinci sınıf denetim.** "Yaş" ve "cinsiyet" grafiğin
içine gömülü değil, üstte kendi kutusunda; kullanıcı 15-49 yaş kadınları seçip aynı
çizgiyi yeniden çizdirebiliyor.

## Bizim karşılıklarımız

| OWID | Bizde | Durum |
|---|---|---|
| Ülke/bölge listesi | Alan seçimi + Seçtiklerim (sepet) | var |
| INDICATOR açılır kutusu | Sol raydaki gösterge ağacı | var, ağaç kalabilir |
| SEX / AGE / SCENARIO | Olgu tablosundaki `dims` (`age`, `sex`) | **yok — yapılacak** |
| Table/Map/Line/Bar sekmeleri | Rapor Seçenekleri'ndeki "… Oluştur" düğmeleri | var ama yanlış yerde |
| Zaman kaydırıcısı | Başlangıç/Bitiş yılı kutuları | var ama anlık görünümde yanlış |
| Data source satırı | Kalite rozeti + kaynak/sürüm | var, bizimki daha iyi |

## Yapılacak dönüşüm

1. **Görünüm sekmeleri grafiğin üstüne.** Tablo · Harita · Çizgi · Sütun. Göstergenin
   desteklemediği görünüm soluk durur. Hangi göstergenin hangi görünümü desteklediği
   sözlükte yazılı olur (`views = [...]`), koda gömülmez — ağacı ve birimi zaten oradan
   üretiyoruz.

2. **Kırılım denetimleri üst şeride.** Gösterge `dims` ilan ediyorsa (nüfus → `age`,
   `sex`) o boyutlar için seçici çıkar; ilan etmiyorsa (TFH) hiçbir şey çıkmaz. Denetim
   listesi veriden üretilir, elle yazılmaz.

3. **Zaman denetimi görünüme bağlanır.** Çizgi ve sütun bir **aralık** ister, harita ve
   piramit **tek yıl**. Şu anki "Bitiş yılı"nın piramitte yıl anlamına gelmesi kusurdu;
   görünüm seçici bunu kendiliğinden çözer.

4. **Çoklu seçim düzeltmesi.** Tıklama tek seçim, Ctrl+tıklama ekler, Shift+tıklama
   aralık seçer.

## Bizi OWID'den ayıracak olan

Aynısını yapmak amaç değil. Üç yerde bilerek farklılaşıyoruz:

- **Kalite bayrağı görünür.** OWID hesaplanmış değeri ölçülmüş değerden ayırmıyor; bizde
  bölge/İBBS değerleri sarı "tahmin" rozetiyle geliyor.
- **Sürüm (vintage) ekranda.** Hangi yayım sürümüne baktığın yazılı; revizyonlar yan yana
  durabiliyor.
- **Türkiye'nin idari kademeleri.** İl / İBBS-2 / İBBS-1 / coğrafi bölge geçişi ve
  ağırlıklı toplama, OWID'de karşılığı olmayan bir şey.

## Sıra

1. ~~Görünüm sekmeleri + sözlükte `views`~~ — bitti (K10).
2. ~~Kırılım denetimleri~~ — bitti; `dims` denetimi üretiyor, `additive` toplamayı
   yalnız toplanabilir birimlerde açıyor.
3. ~~Zaman denetiminin görünüme bağlanması~~ — bitti; çizgi/tablo aralık, harita/sütun/
   piramit tek yıl.
4. ~~Çoklu seçim düzeltmesi~~ — bitti (2026-08-16). Tıklama ekleyip çıkarıyor,
   **Shift** iki tıklama arasındaki bütün alanları alıyor. Aralık, listenin o anda
   *gösterdiği* sıradan okunuyor — arama ve grup kutusu neyi süzdüyse o; tam listeden
   okunsaydı ekranda görünmeyen alanlar da seçilirdi. Aralık zaten tümüyle seçiliyse
   Shift onu kaldırıyor, yoksa elli satırlık bir uzanışı geri almanın yolu elli tık
   olurdu. **Ctrl** ayrı bir dal istemedi: düz tıklama zaten değiştirmiyor, ekliyor.
   Çapa (son tıklanan alan) `state`'te değil — adres çubuğunun anlattığı şeyin parçası
   değil, ve paylaşılan bir bağlantıda başkasının çapası ilk Shift'i okuyucunun hiç
   tıklamadığı bir yere düşürürdü.

   Haritaya konmadı: harita alanlarının bir sırası yok, "aradakiler" diye bir şey yok.
5. **Harita geometrisi** — `public/areas.geojson` (özellik başına `area_id`, `name_tr`).
   Çizim yazıldı, dosya gelince sekme kendiliğinden açılıyor.
6. ~~Eski `index.html`'in kaldırılması~~ — bitti (2026-08-16). Yanında `app.css` ve
   `scripts/build_page.py` de kalktı: ikisi de yalnız o sayfaya hizmet ediyordu.
   Tek dosyalık `VeriAtlas.html` sürümü de onunla gitti — gezgin veri dilimlerini
   gerektikçe indiriyor, hepsini tek dosyaya gömmek ayrı bir tasarımdır ve istenirse
   yeniden yazılır.

Maket (`web/mock-explorer.html`) 2026-08-16'da kaldırıldı. İşini yapmıştı: düzen gerçek
veriye dokunmadan tartışılsın diye vardı, gezgin yazıldıktan sonra tartışılacak bir şey
kalmadı. Sahte sayılarla duran bir sayfanın depoda beklemesi, bir gün birinin ona
bakmasıyla biter.
