# İlçe ardılları — bölünen ilçeler ve karşılaştırılabilir gruplar

Bir ilçenin nüfus serisi kendisiyle karşılaştırılabilir değil: Denizli'nin Merkez
ilçesi 2013'te bölündü ve zaten var olan Pamukkale beş bin kişiden üç yüz bine
çıktı. Bu %+5.677'lik artış demografi değil, sınır değişikliği.

Bölünmenin insanları nasıl paylaştırdığını nüfus dosyası söylemiyor — ama
söylemesi de gerekmiyor. Karşılaştırmayı mümkün kılan şey, **pencerenin tamamında
sabit kalan bir grup**: bölünen ilçeyi ve ondan çıkan her şeyi aynı torbaya koy,
torbanın toprağı 2007'de de 2025'te de aynı olsun. Pay tahmini yok, aritmetik tam.

Gözlenen olay: **23**. Birden çok ilçe içeren grup: **23**.
Doğrulama: hiçbir grup ardışık iki yılda hem %25'ten çok hem
15.000 kişiden çok oynamıyor — ikisi birden olsaydı grup bir üyesini
kaçırmış olurdu ve dosya yazılmazdı. İki koşul birden, çünkü tek başına her biri
gürültü: Çamlıdere üç bin kişiyle ikiye katlanıp yarılanıyor (2018 adres denetimi,
2023 depremi), kaçan bir bölünme üyesi ise asla küçük olmuyor.

| il | yıl | ayrılan | gelen | toprak alan/veren |
|---|---|---|---|---|
| Adana | 2008 | — | Çukurova, Sarıçam | Seyhan |
| Antalya | 2008 | Merkez | Aksu, Döşemealtı, Kepez, Konyaaltı, Muratpaşa | — |
| Balıkesir | 2013 | Merkez | Altıeylül, Karesi | — |
| Denizli | 2013 | Merkez | Merkezefendi | Pamukkale |
| Diyarbakır | 2008 | Merkez | Bağlar, Kayapınar, Sur, Yenişehir | — |
| Erzurum | 2008 | Merkez | Palandöken, Yakutiye | Aziziye |
| Eskişehir | 2008 | Merkez | Odunpazarı, Tepebaşı | — |
| Hakkari | 2018 | — | Derecik | Şemdinli |
| Hatay | 2013 | Merkez | Antakya, Arsuz, Defne, Payas | — |
| Mersin | 2008 | Merkez | Akdeniz, Mezitli, Toroslar, Yenişehir | — |
| İstanbul | 2008 | Eminönü | Arnavutköy, Ataşehir, Başakşehir, Beylikdüzü, Çekmeköy, Esenyurt, Sancaktepe, Sultangazi | Büyükçekmece, Çatalca, Gazi Osmanpaşa, Kadıköy, Ümraniye |
| İzmir | 2008 | — | Bayraklı, Karabağlar | Karşıyaka, Konak |
| Kocaeli | 2008 | Merkez | Başiskele, Çayırova, Darıca, Dilovası, İzmit, Kartepe | Gebze |
| Malatya | 2013 | Merkez | — | Battalgazi, Yeşilyurt |
| Manisa | 2013 | Merkez | Şehzadeler, Yunusemre | — |
| Kahramanmaraş | 2013 | Merkez | Dulkadiroğlu, Oniki Şubat | — |
| Muğla | 2013 | Merkez | Menteşe, Seydikemer | Fethiye |
| Sakarya | 2008 | Merkez | Adapazarı, Arifiye, Erenler, Serdivan | — |
| Samsun | 2008 | Merkez | Atakum, Canik, İlkadım | — |
| Tekirdağ | 2013 | Merkez | Ergene, Kapaklı, Süleymanpaşa | Çerkezköy |
| Şanlıurfa | 2013 | Merkez | Eyyübiye, Haliliye, Karaköprü | — |
| Van | 2013 | Merkez | İpekyolu, Tuşba | Edremit |
| Zonguldak | 2013 | — | Kilimli, Kozlu | Zonguldak |

## Nasıl okunur

* **Ayrılan**: o yıl listeden düşen ilçe. Çoğu zaman 'Merkez'.
* **Gelen**: aynı il ve aynı yılda listeye giren ilçeler.
* **Büyüyen**: zaten var olan ama o yıl iki katından fazla büyüyen ilçe — yani
  toprağın bir kısmını alan. Bu kural yalnız olay yıllarında işletiliyor:
  2018'de %40'ı aşan on sekiz sıçrama var ve hiçbiri sınır değişikliği değil,
  2023'tekiler ise depremin yerinden ettiği nüfus.
* **Ad değişikliği bölünme değildir**: bir çıkıp bir girdiğinde bu dosya
  karışmıyor, `detect_district_renames.py` ve kayıttaki geçerlilik aralıkları
  o işi yapıyor.

Grup kimliği, gruptaki en küçük alan kimliğidir — okuma sırasına göre değişmesin
diye. Etiket, üyeleri 2025 nüfusuna göre büyükten küçüğe yazar.
