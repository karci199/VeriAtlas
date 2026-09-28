# Kent/kır il kalıbı — ne üretiyor, nasıl okunur

`scripts/analiz/kent_kir_2026_09_27/run_il.py <plaka>` → `C:\veri-ham\analiz\kent_kir\<plaka>\`.
Taban yılı 2024 (Endeksa = ADNKS 2024). Ülke geneli: `run_tr.py`, durum `_durum.csv`.

## Sınıflar (her mahalle tam bir sınıfta)
- **merkez**: 2013 öncesi ilçe belediyesi mahallesi + binalarının ≥%50'si ilçe merkezinin bina lekesinde
  (Microsoft bina, 50 m tampon). İlçe merkezi istisnası: eski ilçe mahallesi, köyden dönme değilse ve
  ≥%20 lekedeyse ya da DEGURBA kent diyorsa merkez.
- **kentsel_belde**: merkezden ayrı yerleşim, ≥5.000 kişi. Kent.
- **kasaba**: ayrı yerleşim, 2.000-5.000 kişi; belde geçmişine bakılmaz. Kır.
- **kirsal_belde**: 2014'e kadar belediyesi olmuş, <2.000. Kır.
- **kir**: köy. **osb**: nüfussuz sanayi bölgesi, kent alanından düşülür.
- Şüphede kır. Elle kararlar `birlestir.py` `ELLE` sözlüğünde, kaynağıyla.

## Dosyalar (il başına)
| Dosya | İçerik |
|---|---|
| `kent_<p>_son.csv` | mahalle × 7 sinyal (bina payı, DEGURBA, kayıt no bloğu, 2007-12 statü, haritatr, parsel, sokak), son sınıf, `arada` gerekçesi, `kurum` |
| `kent_<p>_ikili.csv`, `_ikili_ilce.csv` | kent/kır ve ilçe kentleşme oranı |
| `semt_<p>.csv`, `semt_<p>_profil.csv`, `semt_<p>_mahalle.csv` | semt (PTT semti / eski belde / kentsel belde / kasaba / "İlçe Köyleri"), nüfus, çocuk, yaş, eğitim, seçim |
| `secim_<p>_kentkir.csv`, `_sinif.csv`, `_ilce_kentkir.csv`, `secim_tek_parti_<p>.csv` | 2015-2024 sonuçları sınıfa göre; AK Parti 2002-2024 kent/kır |
| `secmen_oran_*`, `secmen_iliski_*` | kayıtlı / oy / 18+ / nüfus; mahalle tipolojisi (kurum sandığı, seçmen dışı, gurbetçi) |
| `tarihsel_<p>.csv` | sayım 1965-2000 + ADNKS 2007-2012 kent/kır serisi |
| `yas_mc_<p>_ilce.csv`, `_semt.csv`, `_mahalle.csv`, `_holdout.csv`, `_duyarlilik.csv` | ortanca yaş (IPF + 200 tur MC, %90 aralık), gizli test, sınıf/kurum duyarlılığı |
| `sapmalar_<p>.csv` | elle bakılacaklar: merkezsiz ilçe, arada kalan, kurum, kullanıcı listesiyle fark |
| `kullanici_fark_<p>.csv` | yalnız 8 ilde: masaüstü `İLLER 18+ Merkez Çevre` listesiyle farklar |

## Bilinen sınırlar
2002-2011 seçimlerinde kapanan belde mahalleleri bugünkü kimliğe bağlanmıyor (o yıllar kır = köy);
TKGM ad eşleşmesi ~%88; 2023-2024 arasında mahalle sınırı değişen ilçelerde 2023 seçmen/18+ oranı bozuk;
küçük köylerde yaş ortancası ±2 yaş, 2.000+ kırsal beldelerde +3 yaş sapma; PTT sokak adları çoğu yerde kod.
