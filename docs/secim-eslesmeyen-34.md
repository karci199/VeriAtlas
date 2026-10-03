# İstanbul: bugünkü mahalleye bağlanamayan seçim satırları (2015 Kasım ve öncesi)

Sandık dosyalarında (`public/tiles/secim-<seçim>-mahalle-TR-34.json`) bugünkü kimliği olmayan
mahalleler `TR-34-<ilçe>~<ad>` anahtarıyla yazılır. 2018, 2023 ve 2024'te hepsi bugünkü
kimliğe bağlı; sorun yalnız eski seçimlerde (2007–2015). Eşleştirme sırası: kimlik, ad,
aşağıdaki takma adlar, ilçenin tek sınıfı.

| Eski ad (ilçe) | Bugünkü birim | Nasıl çıkarıldı |
|---|---|---|
| Habipler (Sultangazi) | Habibler | yazım (p/b) |
| Bozkoca (Şile) | Bozgoca | yazım (k/g) |
| M.Fevzi Çakmak (Arnavutköy) | Mareşal Fevzi Çakmak | kısaltma |
| Eyüp Merkez (Eyüpsultan) | Merkez | ilçe adı ön ekli |
| Merkez (Sarıyer) | Sarıyer Merkez | oy 8.724, nüfus 11.571; Bahçeköy Merkez (3.609) olamaz |
| Kemer (Sarıyer) | Bahçeköy Kemer | oy 1.519, nüfus 2.231 |
| Sancaktepe, Balaban (Silivri) | Çanta Sancaktepe, Çanta Balaban | belde ön eki düşmüş |
| Fevzipaşa, İsmetpaşa (Silivri) | Değirmenköy Fevzipaşa, Değirmenköy İsmetpaşa | belde ön eki düşmüş |
| Kavaklı, Hürriyet (Silivri) | Kavaklı İstiklal, Kavaklı Hürriyet | belde ön eki düşmüş |
| Sinekli (Silivri) | Büyük Sinekli (küçüğü de olabilir, 267 oy) | belirsiz |
| **Kapadık, Eşkinoz (Esenyurt)** | **bağlanamadı** | 24.679 oy (%0,27); Esenyurt 2018'de yeniden mahalleleştirildi, hangi bugünkü mahalleye gittiği bilinmiyor; ilçe iki sınıf içerdiği için sınıf da belli değil |

## Kurum sandığı: Semizkumlar

Silivri Semizkumlar'ın kayıtlı seçmeni 3.754 (2023), kullanılan oy 8.402; nüfus 34.187. Marmara
Cezaevi kampüsü mahallenin içinde, nüfusun büyük bölümü hükümlü ve tutuklu. Oy ≥ kayıtlı + 20
kuralıyla mahalle tümüyle dışarıda kalıyor; cezaevi dışı sandıklar ayıklanamıyor (tile'da yalnız
mahalle toplamı var). Semizkumlar'ın kentsel belde olarak sınıflanması ve ortanca yaşı
bu yüzden şüpheli: 34 bin kişinin çoğu seçmen değil.
