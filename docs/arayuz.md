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

Yeni oturumda: (1) görünüm sekmeleri + sözlükte `views`, (2) kırılım denetimleri,
(3) zaman denetiminin görünüme bağlanması, (4) çoklu seçim düzeltmesi. Harita için
sınır geometrisi gerekiyor, o ayrı bir iş.
