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

Web export: 2026-09-17 tam; 8 dosyanın boş olması hata değil (yalnız ilçe düzeyi, satırlar `*-district.csv.gz`'de); MEDAS girişim, bitkisel/hayvansal değer ve EPDK bayiye teslim dahil.

## Yarım kalan çekimler

| Kaynak | Eksik | Neden | Zorluk |
|---|---|---|---|
| ~~İŞKUR~~ | ~~2003-2011~~ | 2026-09-17 yüklendi | — |
| ~~TİM~~ | ~~2004-2009~~ | 2026-09-17 yüklendi | — |
| TİM | il × sektör, il × ülke ihracatı | dosyalar `C:\veri-ham\tim`'de, adaptör yazılmadı | orta |
| Kültür Turizm | Bakanlık belgeli 1996-2002, 2004-2010, 2014-2015; belediye belgeli 2000-2014 | düzen farklı ya da iller GENEL TOPLAM'ı tutmuyor; 2007-2008 yalnız PDF | orta |
| Kültür Turizm | ilçe düzeyi 2017 öncesi | kaynakta ilçeler il toplamını %84'e varan farkla tutmuyor | kaynak hatası |
| ~~Sağlık yıllığı 2017~~ | 2026-09-17 yüklendi (kelime konumu + 2018 satır sırası); 2011 il tablosu basmıyor | — |
| Sağlık yıllığı | 2010 | yıllık sayfası açılmadı | bilinmiyor |
| BTK | "Gizli — kurum içi" damgalı sayfalar, pazar payı tabloları, AB karşılaştırmaları | `docs/btk.md` | orta |
| EPDK | ~~doğalgaz il tüketimi 2025~~ yüklendi 2026-09-17 (2015-2016 zaten vardı); 2014 yalnız il toplamı (kırılımsız, alınmadı); ~~akaryakıt 2012-2014~~ bayiye teslim (ton, il toplamı) yüklendi 2026-09-17; akaryakıt 2010-2011 (Tablo 3.18, ton) ve ürün kırılımı; 2024-2026 aylık kurulu güç | `docs/epdk.md` | orta |
| KGM | kaza özeti PDF tabloları, Trafik ve Ulaşım Bilgileri | `docs/kgm.md` | zor |
| ~~MGM~~ | ~~ilçe iklim normalleri~~ | 2026-09-17 kapandı: MGM yalnız il merkezi istasyonunu yayımlıyor (10 ad biçimi denendi, hepsi boş); ilçe istasyonları yalnız MEVBİS'te (hesap) | — |
| SGK | ~~sınıflama kodlarının Türkçe etiketleri~~ (2026-09-15 yapılmış, `scripts/sgk_national_labels.py`); 2010-2012 eski düzen | `docs/sgk.md` | orta |
| Seçim | yurt dışı seçmen profili temsilcilik düzeyi (148 ülke) | çekici klasör hatası | orta |

## Keşfedildi, başlanmadı

| Kaynak | Ne | Zorluk |
|---|---|---|
| ~~Eurostat API~~ | 2026-09-17 yüklendi (işgücü, eğitim, Ar-Ge) | — |
| ~~AFAD deprem API~~ | 2026-09-17 yüklendi | — |
| ~~GSB~~ | ~~il kulüp, yetenek taraması~~ 2026-09-17 yüklendi (sporcu, antrenör, hakem yalnız Türkiye × federasyon, alınmadı) | — |
| ~~MEDAS ekonomi~~ | 2026-09-17: girişim sayısı ve tarımsal üretim değerleri (il) yüklendi. Ücretli çalışan yalnız Türkiye aylık (ham `nufus-ekonomi-ucretli-01-aylik-*`, yüklenmedi: il yok, SGK il verisi depoda). İşgücü İBBS-2 Eurostat'tan. Gelir, yoksulluk, kazanç, yıllık sanayi-hizmet yalnız Türkiye/bölge | — |
| BDDK FinTürk | il kredi, mevduat, şube; çeyreklik | orta |
| ETKB | ulusal enerji denge 1972-2024 (yalnız Türkiye) | kolay |
| VAP (MKK) | il yatırımcı sayısı | bilinmiyor |

## Denetim (2026-09-17)

- Ulukışla kişi başı geceleme (2022, kişi başına 12,8 gece) kaynakla birebir; Niğde Toplam'ı tutuyor, 2020'de belediye belgeli tesisle sıçrama (Çiftehan kaplıcaları).
- pytest: 575 geçti, 368 atlandı (hepsi `raw/ref/makro_ceyreklik.csv` yok: BTK ARPU kur/reel çevrim testleri).
- ruff: 42 uyarı temizlendi; tek seferlik analiz betiklerine `pyproject.toml`'da dosya bazlı istisna. Değişen adaptörler (YÖK ulusal, EPDK aylık, BTK) depodakiyle satır satır aynı çıktı.

## Kullanıcı kararı bekleyen

- ~~main birleştirme~~ 2026-09-17 yapıldı; dal ve main aynı noktada.
- EPİAŞ hesabı (il fiilî üretim için), ceza infaz, yaşam memnuniyeti: kararla alınmadı.

## Bilinçli olarak alınmayanlar

MEB (robots.txt), İBB açık veri (robots.txt), TCDD (403), TOBB aylık il tabloları (yıllık depoda).
