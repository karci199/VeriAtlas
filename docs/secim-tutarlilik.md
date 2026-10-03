# Seçim tablolarında tutarlılık (2026-10-02)

Mahalle tabloları (`public/tiles/secim-<oy>-mahalle-TR-XX.json`) ilçe tablosuna (`secim-<oy>-ilce.json`)
toplanmalı. Toplanmıyorsa ayrıştırıcı satır düşürmüştür; satır düşünce kalan satırların hepsi geçerli
görünür, `tile_denetim.py` bunu yakalayamaz. Yeni denetim: `scripts/tile_toplam_denetim.py`.

## Bulunan ve düzeltilen iki hata (`scripts/parse_secim.py`)

1. **Tam sayı katılım.** Katılım oranı yuvarlak çıkınca (%87, %97, %100, %101) satıra bir sayı daha
   giriyordu (width+2), kod yalnız width ve width+1'i okuyup fazlasını sessizce atıyordu.
   2017 halkoylaması Bursa+Ankara'da %9,5 eksikti (İznik: Eşrefzade ve beş köy). Düzeltme:
   `width + 2` için `numbers[:3] + numbers[5:]`. Etki yalnız ho2017'de görüldü.
2. **Eski ad, eski ilçe kodu.** 2015 raporları ilçeyi "Kazan" yazıyor; kayıt defteri bunu eski koda
   (`TR-06-x1815`) bağlıyor, mahalleler haritadaki Kahramankazan'ın altında aranmıyordu. Kahramankazan'ın
   2015 mahalle verisi bütünüyle yoktu. Düzeltme: eski ilçenin halefinde (`successors()`) ada bakılır,
   yalnız tek halefte bulunursa alınır.

Düzeltme sonrası Bursa ve Ankara için ilçe toplamı = mahalle toplamı: mv2015h, mv2015k, mv2018, mv2023, ho2017.

## Düzelmeyen: bağlanamayan yerleşim (anahtarı `~` içerenler)

Rapor mahalleyi harita dizininde olmayan adla yazıyorsa satır oyunu korur ama kimliğini kaybeder
(`TR-06-002~aktas`). Kent/kır kararı kimliğe bağlı olduğundan bu oylar iki tarafa da girmiyor.
Bursa+Ankara, bağlanamayan oyun ilçe payı (geçerli oy):

| Seçim | Altındağ | Ayaş | Haymana | Bala | Mamak | Diğer ≥%1 |
|---|---|---|---|---|---|---|
| 2015 Kasım | %24,8 | %17,4 | %8,5 | %4,8 | %3,4 | Orhaneli, Orhangazi, Gürsu, İnegöl, Çankaya |
| 2018 | %24,9 | %17,5 | %7,2 | | | Orhaneli, Çankaya |
| 2023 | | | | | | Çamlıdere %1,7 |
| 2017 halkoylaması | %25,0 | %17,1 | %7,0 | | %3,4 | Orhaneli, Çankaya |

Nedeni çoğunlukla 2013-2014 mahalle birleştirmesi: Altındağ merkezinde Aktaş, Altınpark, Ali Ersoy,
Anafartalar, Bağlariçi, Çamlık, Doğu, Gülpınar, Plevne, Sakarya, Yıldırım Beyazıt, Ziraat 2015-2017
raporlarında eski adlarıyla duruyor, bugünkü kayıt defterinde yok. Ad benzerliği çözmüyor.
**Sonuç:** 2015K, 2017 ve 2018 için Altındağ, Ayaş, Haymana kent/kır payları yanlı. 2023 temiz.
2018-2023 değişim tablolarında bu üç ilçe için sapma, 2015K-2023 tablolarında Altındağ/Ayaş/Haymana/Bala/Mamak.

## Kalan ulusal sapmalar (ölçüldü, nedeni aranmadı)

Ülke genelinde mahalle toplamı ilçe toplamından eksik: 2014-2023 modern seçimlerde %0,1 (Bayburt %6-7,
Uşak %3,5, Artvin %2-3, Sinop %2), ho2007 %0,56 (İzmir %4,4; `mahalle-içi tutarsız` 1.911 satır),
mv1991 Uşak %5,8, **mv1995 %13, mv1999 %19,5, mv2002 %21,2** (Eskişehir ve yeni iller dahil birçok ilde
%60-78). 1995-2002 milletvekili mahalle tabloları kullanılmaz.

## Yöntem

`uv run python scripts/tile_toplam_denetim.py` her seçim için en kötü illeri ve bağlanamayan oyu yazar.
Yeni bir seçim ayrıştırıldığında ve her ayrıştırıcı değişikliğinden sonra çalıştır. Bir hatayı elle
bulunca kaç seçimde olduğunu say (bu rapor: ikisi de tek tek bulundu, ikincisi ancak ilçe düzeyinde
karşılaştırınca göründü).
