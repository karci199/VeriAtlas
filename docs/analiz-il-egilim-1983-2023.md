# İl ve ilçelerin Türkiye'ye göre eğilimi, 1983–2023

Soru: son kırk yılda hangi il ülke ortalamasına **göre** sola, hangisi sağa kaydı?
Ham sol blok payı işe yaramaz — bir il ülkeyle birlikte sağa gitmiş olabilir. Burada
bakılan, ilin sol blok payının aynı seçimdeki ülke payından **farkı** ve bu farkın
zaman içindeki hareketi.

Üretim: `uv run python scripts/analyze_province_lean.py` (il) ve
`uv run python scripts/analyze_province_lean.py --level ilce --start 1995` (ilçe);
veri `public/elections/`.

## Yöntem ve kapsam dışı bırakılanlar

- **Seçimler:** 1983–2023, **2007 ve 2011 hariç**. O iki seçimde Kürt siyaseti bağımsız
  adaylarla girdi; oylar "bağımsız" havuzunda durduğu için sol blok, seçmenle ilgisi
  olmayan bir sebeple çöküyor.
- **CHP listesi olmayan il-seçimler atlandı** (2023'te Bitlis, Gümüşhane, Muş, Yozgat,
  Çankırı). Olmayan liste bir tercih değil.
- **1989 sonrası kurulan 14 il** çıktıkları ile katlandı; karşılaştırmanın iki ucu aynı
  toprağı kapsıyor. Kalan: **67 il**.
- **Kayma** = 2018–2023 ortalama farkı − 1983–1991 ortalama farkı (puan). **Eğilim** =
  aynı farkın en küçük kareler eğimi (puan / 10 yıl). İkisi de aynı hikâyeyi anlatıyor;
  kayma daha okunur, eğilim tek bir seçime bağlı değil.
- İki okuma yan yana: **Kürt partileri solda** ve **Kürt partileri hariç**. Anlaşmadıkları
  yer bulgunun kendisi.

Ülke sol blok payı bu dönemde %30,4 → %37,4 (Kürt partileri hariç %30,4 → %28,5).
Yani aşağıdaki hareketler ulusal bir salınım değil, **yeniden dağılım**.

## 1. Kürt partileri solda sayılınca

| En çok sola | kayma | | En çok sağa | kayma |
|---|---|---|---|---|
| Ağrı | **+36,3** | | Sivas | **−19,4** |
| Van | +35,5 | | Niğde | −17,5 |
| Hakkari | +29,2 | | Sinop | −16,7 |
| Siirt | +27,8 | | Zonguldak | −14,2 |
| Bitlis | +27,3 | | Yozgat | −13,8 |
| Muş | +26,3 | | Tokat | −13,4 |
| Diyarbakır | +23,0 | | Ordu / Trabzon | −12,9 |
| Mardin | +22,1 | | Gümüşhane | −12,9 |

Sola kayan ilk sekizin hepsi Kürt illeri. Ağrı 1983–91'de ülkenin 4,8 puan sağındayken
2018–23'te 31,5 puan solunda: **kırk yılda 36 puan**, listenin açık ara birincisi.
Karşı uçta İç Anadolu ve Batı Karadeniz: Sivas 1983'te ülkeyle aynı yerdeyken bugün
18,6 puan sağında.

## 2. Kürt partileri hariç tutulunca eksen değişiyor

| En çok sola | kayma | | En çok sağa | kayma |
|---|---|---|---|---|
| Muğla | **+16,8** | | Diyarbakır | **−31,8** |
| Antalya | +13,9 | | Tunceli | −29,4 |
| Kırklareli | +13,2 | | Hakkari | −28,7 |
| Aydın | +11,8 | | Mardin | −26,2 |
| Çanakkale | +11,3 | | Siirt | −23,4 |
| Isparta | +10,9 | | Kars | −22,4 |
| İzmir | +9,5 | | Muş | −17,9 |

Aynı iller iki listede ters uçlarda: Diyarbakır bir okumada +23,0, diğerinde −31,8.
Sebep basit ve önemli — güneydoğuda CHP tipi sol **yok olmadı, yerini Kürt partilerine
bıraktı**. Hangi listeyi okuduğunuz, o oyları nasıl saydığınıza bağlı.

Kürt partileri dışarıda bırakıldığında geriye kalan asıl hareket **kıyı–iç ayrışması**:
Ege, Batı Akdeniz ve Trakya sola; İç Anadolu, Karadeniz ve güneydoğu sağa.

## 3. Parti tanımından bağımsız olan hareket

İki okumada da aynı yöne kayan iller — sonuç blok tanımına bağlı değil:

- **Sola:** Muğla (+11,4 / +16,8), Antalya (+9,6 / +13,9), Aydın (+9,8 / +11,8),
  Kırklareli (+5,3 / +13,2), İzmir (+8,7 / +9,5), Çanakkale, Isparta, Eskişehir,
  Balıkesir, Artvin.
- **Sağa:** Sivas (−19,4 / −10,3), Niğde (−17,5 / −8,1), Sinop (−16,7 / −7,4),
  Zonguldak (−14,2 / −4,8), Gaziantep (−11,5 / −11,1), Kocaeli, Tokat, Yozgat,
  Trabzon, Ordu.

Not: Isparta ve Bolu "sola kaydı" derken hâlâ ülkenin sağında (−5,5 ve −4,9); kayma
yönü söyler, konumu değil.

## 4. İki okumanın en çok ayrıldığı iller

Fark, Kürt partilerinin o ildeki katkısının büyüklüğü:

| il | kürtlü | kürtsüz | fark |
|---|---|---|---|
| Hakkari | +29,2 | −28,7 | 57,9 |
| Diyarbakır | +23,0 | −31,8 | 54,8 |
| Siirt | +27,8 | −23,4 | 51,2 |
| Ağrı | +36,3 | −13,5 | 49,7 |
| Mardin | +22,1 | −26,2 | 48,3 |
| Van | +35,5 | −12,0 | 47,5 |
| Muş | +26,3 | −17,9 | 44,1 |
| Tunceli | +8,4 | −29,4 | 37,9 |
| Kars | +1,3 | −22,4 | 23,7 |

Tunceli ilginç: iki okumada da ülkenin solunda (bugün +42,6 / +4,7), ama Kürt partileri
sayılmazsa 1983'teki +34,2'lik solculuğunun neredeyse tamamını kaybetmiş görünüyor.

## 5. İlçe düzeyi (1995–2023)

`--level ilce --start 1995`. **750 ilçe**, 7 seçim. 1995'ten başlıyor çünkü 1983–87
raporlarında ilçelerin çoğu hâlâ "Merkez" diye geçiyor. İki ek eleme var, ikisi de
sessiz bozulmayı kesmek için:

- **Sınırı değişmiş sayılanlar (38 ilçe):** seçmeni ülkenin 0,45–2,5 katı dışında
  hareket eden ilçe fikir değil şekil değiştirmiştir. En uçtakiler Battalgazi ×9,0,
  Edremit (Van) ×7,2, Yeşilyurt ×7,0, Etimesgut ×3,6, Nilüfer ×2,5 — hepsi 2013
  büyükşehir düzenlemesinin ya da merkez bölünmelerinin ürünü.
- **5.000 seçmenin altındakiler** dışarıda: birkaç bin seçmen eğilimle değil gürültüyle
  salınıyor (bu eleme olmadan listenin tepesine Yedisu, Bozcaada gibi yerler çıkıyor).

**Kürt partileri solda — en çok sola:** Güçlükonak (Şırnak) **+49,1**, Patnos (Ağrı)
+45,4, Muradiye (Van) +39,1, İdil (Şırnak) +36,8, Mazıdağı (Mardin) +35,2, Hamur (Ağrı)
+34,5, Taşlıçay +33,7, Dargeçit +33,4.

**En çok sağa:** Akkuş (Ordu) **−21,8**, Ayvacık (Samsun) −19,3, Eflani (Karabük) −18,6,
Erfelek (Sinop) −17,7, Kumru (Ordu) −17,7, Ulus (Bartın) −17,6, Şenkaya (Erzurum) −17,6,
Çarşamba (Samsun) −17,4. **Liste neredeyse tamamen Karadeniz kırsalı.**

**Kürt partileri hariç — en çok sola:** Datça (Muğla) **+17,6**, Fındıklı (Rize) +16,3,
Şavşat (Artvin) +15,8, Bodrum +15,8, Fethiye +15,3, Karşıyaka +15,1, Hacıbektaş +14,9,
Güzelbahçe +14,6, Beşiktaş +14,5, Karaburun +14,2, Dikili +14,1. **En çok sağa:** Eruh
(Siirt) −24,6, Şenkaya −20,5, Adaklı (Bingöl) −16,9, Akkuş −14,1, Iğdır Merkez −14,0.

İl düzeyindeki resim ilçede de aynı, daha keskin hâliyle çıkıyor:

- İki okumada da sola gidenler **turizm kıyısı ve büyük şehrin eğitimli merkezi**:
  Datça (+19,8 / +17,6), Bodrum, Adalar (+22,0 / +12,6), Beşiktaş (+17,5 / +14,5).
- İki okumada da sağa gidenlerin hepsi **Orta ve Doğu Karadeniz kırsalı**: Akkuş,
  Ayvacık, Eflani, Erfelek, Kumru, Ulus, Çarşamba, Gökçebey.
- Fındıklı ve Şavşat ilginç istisna: Rize ve Artvin'in içinde, ülkeye göre sola giden
  iki ilçe.

40 yıllık uzun pencere (`--start 1983`) yalnız **486 ilçe** bırakıyor — 230'u sınır
değişikliği elemesine takılıyor — ama sıralamanın tepesi aynı yöne bakıyor: Karayazı
(Erzurum) **+59,5**, Başkale (Van) +52,0, Bulanık (Muş) +51,2.

## Ne söylemiyor

- Bu bir **oy oranı** analizi değil, **göreli konum** analizi. "Sola kaydı", "sol
  partiler oyunu artırdı" demek değil; "ülkeye göre solda kalan mesafesi arttı" demek.
- Blok ayrımı bir yorumdur; parti listesi `scripts/build_election_series.py` içinde
  açıkça duruyor ve tartışmaya açıktır. YTP yıla göre çözülüyor (1961–69 sağ, 2002 sol).
- 1977'ye çıpalanmadı; 1977 solun tavan yaptığı seçim, oraya göre ölçünce her yer sağa
  kaymış görünür.
- Nüfus hareketi hesaba katılmadı. Alevi yoğun ilçelerde daha önce görülen "sağa dönmedi,
  boşaldı" bulgusu il düzeyinde de geçerli olabilir; bu analiz onu ayırt etmiyor.
