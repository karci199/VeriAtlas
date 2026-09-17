# Açık işler (2026-09-17, akşam güncel)

Çekilip de alınamayan ya da yarım kalanlar, tahmini zorlukla. Yeni oturumda buradan devam.
Keşfedilmiş ama hiç başlanmamış kaynaklar `kaynak-envanteri.md`'de.

## Bu oturumda depoya girenler (2026-09-16/17)

| Kaynak | Gösterge | Kapsam |
|---|---|---|
| Sağlık Bakanlığı yıllığı | `moh_*` 20 gösterge: hastane, yatak, yoğun bakım, müracaat, ameliyat, doluluk, personel, 112 | il, 2012-2016 + 2018-2024 |
| TOBB | `tobb_foreign_*`: yabancı ortaklı kurulan şirket, sermaye, yabancı payı | il × anonim/limited, 2010-2025 |
| TİM | `tim_exports` il ihracatı | il, 2004-2025 |
| İŞKUR | `iskur_*`: başvuru, açık iş, yerleştirme, kayıtlı işgücü/işsiz/iş arayan | il × cinsiyet, 2003-2025 |
| Kültür Turizm | `ktb_*`: geliş, geceleme (il+ilçe), ortalama kalış, doluluk | il 2003-2022 (seçili yıllar), ilçe 2017-2022 |

Web export: TOBB yabancı, TİM, İŞKUR, KTB henüz dışa aktarılmadı.

## Yarım kalan çekimler

| Kaynak | Eksik | Neden | Zorluk |
|---|---|---|---|
| ~~İŞKUR~~ | ~~2003-2011~~ | 2026-09-17 yüklendi | — |
| ~~TİM~~ | ~~2004-2009~~ | 2026-09-17 yüklendi | — |
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
| Eurostat API | İBBS-2 işsizlik, istihdam, eğitim düzeyi; İBBS-3 GSYH (avro) | kolay |
| ~~AFAD deprem API~~ | 2026-09-17 yüklendi | — |
| ~~GSB~~ | ~~il kulüp, yetenek taraması~~ 2026-09-17 yüklendi (sporcu, antrenör, hakem yalnız Türkiye × federasyon, alınmadı) | — |
| MEDAS ekonomi | ücretli çalışan (il), girişim sayısı (il), tarımsal üretim değeri (il), işgücü (İBBS-2), gelir dağılımı ve yoksulluk, kazanç, yıllık sanayi-hizmet | orta (tarayıcı, tek oturum) |
| BDDK FinTürk | il kredi, mevduat, şube; çeyreklik | orta |
| ETKB | ulusal enerji denge 1972-2024 (yalnız Türkiye) | kolay |
| VAP (MKK) | il yatırımcı sayısı | bilinmiyor |

## Kullanıcı kararı bekleyen

- `claude/saglik-yilligi` dalının main'e birleştirilmesi (ileri sarma, çakışma yok).
- EPİAŞ hesabı (il fiilî üretim için), ceza infaz, yaşam memnuniyeti: kararla alınmadı.

## Bilinçli olarak alınmayanlar

MEB (robots.txt), İBB açık veri (robots.txt), TCDD (403), TOBB aylık il tabloları (yıllık depoda).
