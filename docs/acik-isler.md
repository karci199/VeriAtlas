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
| TİM | ~~il × sektör 2013-2025~~, ~~il × ülke 2013-2025~~ yüklendi 2026-09-17 (`tim_exports_by_sector`, `tim_exports_by_country`); kalan: 2004-2012 (farklı sektör sınıflaması, 2012 dosyası eksik satırlı) | `tim_sectors.py`, `tim_countries.py` | büyük |
| ~~Kültür Turizm~~ | 2026-09-17 kapandı: Bakanlık belgeli 1996, 2000-2021; belediye 2000, 2002-2006, 2008-2022. Kaynakta kullanılamaz: 1997 (il başlıkları kaymış), 1998 (genel toplamı 277 bin yerli eksik), 1999 (genel toplam yok, sayfa geçişinde Ankara başlığı kayıp) | `src/veriatlas/adapters/ktb.py` | — |
| ~~Kültür Turizm~~ | ~~ilçe düzeyi 2017 öncesi~~ | 2026-09-17: kaynak hatası değil, '-' satırlarını atan okuyucuydu; çoğu yıl açıldı | — |
| ~~Sağlık yıllığı 2017~~ | 2026-09-17 yüklendi (kelime konumu + 2018 satır sırası); 2011 il tablosu basmıyor | — |
| ~~Sağlık yıllığı~~ | ~~2010~~ | 2026-09-17 kapandı: PDF indi, il tablosu basmıyor (2011 gibi yalnız bölge grafiği) | — |
| ~~BTK~~ | 2026-09-17 kapandı (kullanıcı kararı): "Gizli — kurum içi" damgalı sayfalar okunmuyor; pazar payı ve AB karşılaştırma tabloları alınmadı | `docs/btk.md` | — |
| EPDK | ~~doğalgaz il tüketimi 2025~~ yüklendi 2026-09-17 (2015-2016 zaten vardı); 2014 yalnız il toplamı (kırılımsız, alınmadı); ~~akaryakıt 2012-2014~~ bayiye teslim (ton, il toplamı) yüklendi 2026-09-17; ~~akaryakıt 2011~~ (Tablo 3.18, ton) 2026-09-17 bayiye teslim serisine eklendi, 2010 raporu il tablosu basmıyor; ürün kırılımı; 2024-2026 aylık kurulu güç | `docs/epdk.md` | orta |
| KGM | kaza özeti PDF tabloları, Trafik ve Ulaşım Bilgileri | `docs/kgm.md` | zor |
| ~~MGM~~ | ~~ilçe iklim normalleri~~ | 2026-09-17 kapandı: MGM yalnız il merkezi istasyonunu yayımlıyor (10 ad biçimi denendi, hepsi boş); ilçe istasyonları yalnız MEVBİS'te (hesap) | — |
| SGK | 2026-09-17 yeniden sayıldı: ulusal tablolarda 2013-2025 açık iş yok. Atlanan: 2010-2012 iş kazası × meslek 4 tablo ve 2013 Tablo 3.8 (başlıkta konu satırı yok, meslekler ISCO-88; yalnız Türkiye, üç yıl — değmez, alınmadı); 2019 Tablo 3.1.17 ve 3.1.21 (kaynak kendi toplamını tutmuyor); çalışma süresi 2022+ (kaynak bozuk, bilerek) | `docs/sgk.md` | kapandı |
| ~~Seçim~~ | ~~yurt dışı seçmen profili~~ | 2026-09-17 kapandı: 1.662 rapor inmişti (çekici 20dfb32'de düzeltilmiş), özet `docs/vaka-secim-disari.md` §4 | — |

## Keşfedildi, başlanmadı (2026-09-17 akşam güncel)

| Kaynak | Ne | Zorluk |
|---|---|---|
| ~~Muhasebat~~ | il genel bütçe gelirleri 2004-2025 yüklendi (`budget_revenue_by_province`) | — |
| ~~BDDK FinTürk~~ | 6 tablo × 7 banka grubu 2007-2025 yüklendi (`bank_group_*`, 545 bin satır) | — |
| ~~VAP (MKK)~~ | il portföy değeri 2005-2025 yüklendi (`investor_portfolio_value`); yatırımcı sayısı panoda yalnız ilk 10 il, alınmadı | — |
| ~~Muhasebat~~ | il merkezi yönetim bütçe geliri ve gideri 2004-2025, mahalli idare bütçe geliri ve gideri 2006-2025 yüklendi (`central_budget_*_by_province`, `local_budget_*_by_province`, 70 bin satır); gideri ekonomik ve fonksiyonel sınıflandırmayla | — |
| OECD bölgesel (SDMX) | ~~keşif ve ilk çekim yapıldı~~ 2026-09-17: `scripts/fetch_oecd_tl3.py`, ham veri `C:eri-ham\oecd_tl3`. Yüklendi: dış ticaret (2002-2023, ihracat+ithalat), sıcaklık/yağış/iklim gün sayıları (1981-2024), derece-gün (1981-2023). **Diskte hazır, adaptörü yok:** sağlık hizmeti (hekim/yatak/hemşire/taburcu 2000-2023 — Sağlık Bakanlığı yıllığının 2012 öncesini kapatır), sağlık durumu, sağlık riski (PM2,5 maruziyeti — model, ölçüm değil), patent (PCT 1995-2024), göç akımı (2016-2025), DSD_REG_SOC dosyaları (geniş bant, konut, güvenlik, taşıt, seçmen katılımı — beşi de aynı boyutta indi, aynı üst küme olabilir, ölçüleri ayrıştırılmalı). **TL3'te yok (404):** enerji tüketimi, elektrik üretimi, hava kirliliği, atık, turizm, eğitim, istihdam, gelir, verimlilik, kuraklık, yangın, sel. **Alınmadı:** iklim projeksiyonu ve sera gazı (ilki kullanıcı kararı, ikincisi EDGAR ızgara modeli — ölçüm değil) | — |
| TEDAŞ | istatistikkitabi.tedas.gov.tr, il elektrik dağıtım | bilinmiyor (zaman aşımı) |
| TKGM MEGSİS | tapu/kadastro, ham veri diskte, adaptör yok | orta |
| Adalet Bakanlığı | adalet istatistikleri, il/adliye, PDF | zor |
| ETKB | ulusal enerji denge 1972-2024 (il yok) | kolay |
| Erişilemeyen | GİB (IP engeli), MEB ve İBB (robots.txt), TCDD (403), UYAP (kısıtlı), İzmir/Konya açık veri (robots `/api/`), Wikidata SPARQL (robots) | — |

## Sıradaki oturumun ilk işi

1. **Tam yükleme** (`uv run python scripts/load.py`, tam liste) — ama **ana kopyada
   (`C:eri`), worktree'de değil.** 2026-09-17 akşamı Muhasebat'ın dört ve OECD'nin beş
   göstergesi yazıldı, warehouse'a girmedi. Worktree'de denendi ve 675 adaptörden sonra
   çöktü: `load.py`'nin son türetme adımı `public/fact.parquet`'i okuyor, o dosya
   `.gitignore`'da olduğu için worktree'ye gelmiyor (`IOException: No files found that
   match the pattern ...worktrees\...\publicact.parquet`). Hiçbir şey yazılmadı, veri
   kaybı yok. Doğru sıra: dalı main'e al, `C:eri`'de tam yüklemeyi çalıştır.
   Web export bilerek yapılmadı (kullanıcı: "şimdilik webe aktarma"), yükleme bitince
   kullanıcıya sorulacak.
2. OECD'nin diskte bekleyen dosyaları için adaptör (yukarıdaki listede).

## Kullanıcı kararı bekleyen

- ~~main birleştirme~~ 2026-09-17 yapıldı; dal ve main aynı noktada.
- EPİAŞ hesabı (il fiilî üretim için), ceza infaz, yaşam memnuniyeti: kararla alınmadı.

## Bilinçli olarak alınmayanlar

MEB (robots.txt), İBB açık veri (robots.txt), TCDD (403), TOBB aylık il tabloları (yıllık depoda).
