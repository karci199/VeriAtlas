# Ulaşım — 2026-08-17 oturumu

İki analiz yapıldı. İkisinin de bulgusundan çok **paydasının nereye baktığı** öğretici.

## Ehliyet / 18+ nüfus (2013-2024)

Payda için tek yaş nüfus şart — beşer yaş bandı 15-19'u bölemiyor, `population-age1`
kullanıldı. Kaynak: `Desktop/demografi/Hanehalkı/Sürücü Belgesi Olan Kişi Sayısı.xls`.

**2025 sütunu bozuk ve kullanılmamalı.** Ehliyet bir stoktur, azalmaz; oysa 2025'te Kars
120.049 → 73.113 (−%39), Kırıkkale −%28, Nevşehir −%21 düşerken Düzce +%15 fırlıyor. On iki
yıl düzgün artan seri tek yılda çöküyor — tanım ya da kapsam değişikliği (muhtemelen süresi
dolmuş belgelerin düşülmesi). Bir sonraki vintage'da kontrol edilmeli.

Türkiye 46,0 → 56,5 (yüz yetişkine ehliyet). **81 ilin hepsinde arttı.** En yüksek:
Kırıkkale 68,6 · Nevşehir 67,9 · Isparta 67,4. En düşük: Ardahan 37,9 · Tunceli 40,1 ·
Yalova 40,4. En çok artan: Kilis +20,9 · Hatay +18,6 · Adıyaman +18,3.

Sıralamanın tepesi zengin iller değil, İç Anadolu'nun orta ölçekli illeri. **Ehliyet bir
refah değil zorunluluk göstergesi**: metro ve otobüsün olduğu yerde insan ehliyetsiz
yaşayabiliyor.

Kayıt sapması araştırıldı: ehliyet verildiği ilde sayılır, taşınan kişinin belgesi
memlekette kalabilir. En çok göç alan iki il (Tekirdağ, Yalova) en düşük 10'da, en çok göç
veren Kars ve Erzurum yüksekte — sapma bu yönde. **Ama 81 ilde korelasyon r = −0,04**, yani
genel bir bozulma yok. Sıralama atılmıyor, yalnız hızlı büyüyen illerde düşük okunuyor.

## Ehliyetli başına trafik ölüsü (2019-2024 havuzlanmış)

Kaynak: `nufus-trafik-olu-province.csv` (MEDAS, il × cinsiyet, 2012-2025).
Türkiye **17,2 / 100 bin ehliyetli-yıl**. Çankırı 52,1 ile İstanbul 5,2 arasında on kat fark.

**Ölçü kırık ve kırıklığın yeri bulgunun kendisi:** trafik ölüsü *kazanın olduğu* ilde,
ehliyet *verildiği* ilde sayılıyor. En yüksek on ilin çoğu ana güzergâh üstünde (Çankırı,
Bolu, Düzce, Aksaray, Afyon, Niğde) — ölenlerin çoğu o ilin sürücüsü değil, transit geçen
sürücü. Yani ölçülen şey "hangi ilin sürücüsü tehlikeli" değil, **"hangi ilin yolundan kaç
kişi geçiyor"**.

Düzeltme yolu ölümü ikametgaha göre almak. `İl ve seçilmiş ölüm nedenlerine göre ölümler`
dosyası ikametgaha göre ama taşıma kazasını ayrı satır olarak vermiyor, yalnız "dışsal
toplam" var. **Şu an düzeltilemiyor.**

TÜİK'in kendi "milyon araç başına ölü" göstergesi de aynı hatayı taşıyor; buradaki paydanın
tek üstünlüğü araç yerine sürücü sayması.

## Hane başına otomobil (2012-2025)

Stok yeniden kuruldu: MEDAS "bin kişi başına otomobil" oranı × nüfus. Ham stok ölçümü
(`Motorlu Kara Taşıt Sayısı`) çekilemedi — tarayıcıya düzey ve yıl listesi boş dönüyor,
kırılımı önce çözülmesi gerekiyor.

Türkiye **0,436 → 0,644**. Otomobil 8,65M → 17,38M, hane 19,84M → 26,98M.

En yüksek: Ankara 1,092 · İstanbul 0,827 · Antalya 0,822. En düşük: Hakkari 0,055 ·
Şırnak 0,081 · Ağrı 0,101.

**Ankara'nın 1,09'u hane tüketimi değil kayıt olgusu**: kamu kurumu, bakanlık, şirket
merkezi ve kiralama filoları Ankara'ya kayıtlı. Bu göstergede uç değer olarak işaretlenmeli.

**Ehliyette yakınsama var, arabada yok.** Ağrı ehliyette 35 → 52 çıkarken hane başına
otomobilde 0,112 → 0,101'e düştü. Doğuda insanlar ehliyet alıyor, araba alamıyor: ehliyet
bir yetenek, araba bir varlık, ve ikisi ayrışıyor.

Şanlıurfa 81 ilin en çok düşeni: 0,308 → 0,245 (−%20), çünkü hane sayısı araba sayısından
hızlı arttı. Trabzon (+%90) ve Malatya (+%73) ise sıralamanın değil **hareketin** tepesinde.

## Ders

Muş, ehliyetli başına trafik ölüsünde İstanbul'dan sonra en düşük ikinci il. Yolları güvenli
olduğu için değil, kimse araba kullanmadığı için. **En güvenli görünen yer çoğu zaman en az
hareket eden yerdir** — trafik güvenliği ölçüsü maruziyetle düzeltilmeden okunamaz, ve
gerçek maruziyet (araç-km) TÜİK'te yok.
