# İllerin Türkiye'ye göre eğilimi, 1983–2023

Soru: son kırk yılda hangi il ülke ortalamasına **göre** sola, hangisi sağa kaydı?
Ham sol blok payı işe yaramaz — bir il ülkeyle birlikte sağa gitmiş olabilir. Burada
bakılan, ilin sol blok payının aynı seçimdeki ülke payından **farkı** ve bu farkın
zaman içindeki hareketi.

Üretim: `uv run python scripts/analyze_province_lean.py` (veri `public/elections/`).

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

## Ne söylemiyor

- Bu bir **oy oranı** analizi değil, **göreli konum** analizi. "Sola kaydı", "sol
  partiler oyunu artırdı" demek değil; "ülkeye göre solda kalan mesafesi arttı" demek.
- Blok ayrımı bir yorumdur; parti listesi `scripts/build_election_series.py` içinde
  açıkça duruyor ve tartışmaya açıktır. YTP yıla göre çözülüyor (1961–69 sağ, 2002 sol).
- 1977'ye çıpalanmadı; 1977 solun tavan yaptığı seçim, oraya göre ölçünce her yer sağa
  kaymış görünür.
- Nüfus hareketi hesaba katılmadı. Alevi yoğun ilçelerde daha önce görülen "sağa dönmedi,
  boşaldı" bulgusu il düzeyinde de geçerli olabilir; bu analiz onu ayırt etmiyor.
