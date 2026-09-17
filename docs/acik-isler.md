# Açık işler (2026-09-17)

Çekilip de alınamayan ya da yarım kalanlar, tahmini zorlukla. Yeni oturumda buradan devam.
Keşfedilmiş ama hiç başlanmamış kaynaklar `kaynak-envanteri.md`'de.

## Yarım kalan çekimler

| Kaynak | Eksik | Neden | Zorluk |
|---|---|---|---|
| İŞKUR | 2003-2011 il genel çalışmalar | 2004-2011 tablo başına ayrı xls, zip içinde; 2003 tek xlsx | kolay |
| TİM | 2004-2009 il ihracatı | Aralık dosyalarında illerin altında adsız ek tablolar, Türkiye toplamı ayırt edilemiyor | kolay-orta |
| TİM | il × sektör, il × ülke ihracatı | dosyalar `C:\veri-ham\tim`'de, adaptör yazılmadı | orta |
| Kültür Turizm | Bakanlık belgeli 1996-2002, 2004-2010, 2014-2015; belediye belgeli 2000-2014 | düzen farklı ya da iller GENEL TOPLAM'ı tutmuyor; 2007-2008 yalnız PDF | orta |
| Kültür Turizm | ilçe düzeyi 2017 öncesi | kaynakta ilçeler il toplamını %84'e varan farkla tutmuyor | kaynak hatası |
| Sağlık yıllığı | 2017; 2011 | 2017 metin katmanı bozuk (görüntüden ~10 sayfa); 2011 il tablosu basmıyor | orta / yok |
| Sağlık yıllığı | 2010 | yıllık sayfası açılmadı | bilinmiyor |
| BTK | "Gizli — kurum içi" damgalı sayfalar, pazar payı tabloları, AB karşılaştırmaları | `docs/btk.md` | orta |
| EPDK | doğalgaz 2014-2016, akaryakıt 2011-2014, 2024-2026 aylık kurulu güç | `docs/epdk.md` | orta |
| KGM | kaza özeti PDF tabloları, Trafik ve Ulaşım Bilgileri | `docs/kgm.md` | zor |
| MGM | ilçe iklim normalleri | sayfa adlandırması farklı | orta |
| SGK | sınıflama kodlarının Türkçe etiketleri; 2010-2012 eski düzen | `docs/sgk.md` | orta |
| Seçim | yurt dışı seçmen profili temsilcilik düzeyi (148 ülke) | çekici klasör hatası | orta |

## Keşfedildi, başlanmadı

| Kaynak | Ne | Zorluk |
|---|---|---|
| GSB | il kulüp sayısı, sporcu, antrenör, hakem | kolay |
| MEDAS ekonomi | ücretli çalışan (il), girişim sayısı (il), tarımsal üretim değeri (il), işgücü (İBBS-2), gelir dağılımı ve yoksulluk, kazanç, yıllık sanayi-hizmet | orta (tarayıcı, tek oturum) |
| BDDK FinTürk | il kredi, mevduat, şube; çeyreklik | orta |
| ETKB | ulusal enerji denge 1972-2024 (yalnız Türkiye) | kolay |
| VAP (MKK) | il yatırımcı sayısı | bilinmiyor |

## Kullanıcı kararı bekleyen

- `claude/saglik-yilligi` dalının main'e birleştirilmesi (ileri sarma, çakışma yok).
- EPİAŞ hesabı (il fiilî üretim için), ceza infaz, yaşam memnuniyeti: kararla alınmadı.

## Bilinçli olarak alınmayanlar

MEB (robots.txt), İBB açık veri (robots.txt), TCDD (403), TOBB aylık il tabloları (yıllık depoda).
