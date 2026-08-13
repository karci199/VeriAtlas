# İlçe adı değişiklikleri — gözlemden çıkarılan öneriler

`scripts/detect_district_renames.py` üretti. **Bunlar öneri**, kayda elle
işlenir: yanlış bir eşleştirme iki ayrı yeri tek seriye kaynatır.

Kural: aynı ilde bir ilçe biterken tam bir tanesi başlıyorsa ve arada boşluk
yoksa, aday sayılır. Oran (yeni/eski nüfus) 1'e yakınsa yeniden adlandırma,
uzaksa bölünme ya da katılma demektir.

| İl | Yıl | Eski | Yeni | Eski nüfus | Yeni nüfus | Oran |
|---|---|---|---|---|---|---|
| Ankara | 2016 → 2017 | Kazan | Kahramankazan | 50,746 | 52,079 | 1.03 |
| Aydın | 2012 → 2013 | Merkez | Efeler | 259,786 | 265,234 | 1.02 |
| Denizli | 2012 → 2013 | Merkez | Merkezefendi | 554,424 | 262,825 | 0.47 |
| Kırıkkale | 2018 → 2019 | Bahşili | Bahşılı | 7,907 | 7,399 | 0.94 |
| Mardin | 2012 → 2013 | Merkez | Artuklu | 139,254 | 148,066 | 1.06 |
| Ordu | 2012 → 2013 | Merkez | Altınordu | 186,000 | 186,097 | 1.00 |
| Trabzon | 2012 → 2013 | Merkez | Ortahisar | 312,060 | 306,286 | 0.98 |
| İstanbul | 2017 → 2018 | Eyüp | Eyüpsultan | 381,114 | 383,909 | 1.01 |

## Tek eşleşmeyenler (bölünme / katılma adayları)

Bunlara dokunulmadı: pay hesabı gerekiyor ve gözlemden çıkmıyor.

- **Antalya** 2007 → 2008: biten [Merkez], başlayan [Aksu, Döşemealtı, Kepez, Konyaaltı, Muratpaşa]
- **Balıkesir** 2012 → 2013: biten [Merkez], başlayan [Altıeylül, Karesi]
- **Diyarbakır** 2007 → 2008: biten [Merkez], başlayan [Bağlar, Kayapınar, Sur, Yenişehir]
- **Erzurum** 2007 → 2008: biten [Merkez], başlayan [Palandöken, Yakutiye]
- **Eskişehir** 2007 → 2008: biten [Merkez], başlayan [Odunpazarı, Tepebaşı]
- **Hatay** 2012 → 2013: biten [Merkez], başlayan [Antakya, Arsuz, Defne, Payas]
- **Kahramanmaraş** 2012 → 2013: biten [Merkez], başlayan [Dulkadiroğlu, Onikişubat]
- **Kocaeli** 2007 → 2008: biten [Merkez], başlayan [Başiskele, Çayırova, Darıca, Dilovası, İzmit, Kartepe]
- **Malatya** 2012 → 2013: biten [Merkez], başlayan []
- **Manisa** 2012 → 2013: biten [Merkez], başlayan [Şehzadeler, Yunusemre]
- **Mersin** 2007 → 2008: biten [Merkez], başlayan [Akdeniz, Mezitli, Toroslar, Yenişehir]
- **Muğla** 2012 → 2013: biten [Merkez], başlayan [Menteşe, Seydikemer]
- **Sakarya** 2007 → 2008: biten [Merkez], başlayan [Adapazarı, Arifiye, Erenler, Serdivan]
- **Samsun** 2007 → 2008: biten [Merkez], başlayan [Atakum, Canik, İlkadım]
- **Tekirdağ** 2012 → 2013: biten [Merkez], başlayan [Ergene, Kapaklı, Süleymanpaşa]
- **Van** 2012 → 2013: biten [Merkez], başlayan [İpekyolu, Tuşba]
- **İstanbul** 2007 → 2008: biten [Eminönü], başlayan [Arnavutköy, Ataşehir, Başakşehir, Beylikdüzü, Çekmeköy, Esenyurt, Sancaktepe, Sultangazi]
- **Şanlıurfa** 2012 → 2013: biten [Merkez], başlayan [Eyyübiye, Haliliye, Karaköprü]
