# Kurum kaynakları envanteri — il/ilçe verisi (taslak, 2026-09-14)

Amaç: TÜİK dışında il, ilçe, mahalle düzeyinde veri yayımlayan kurumları bulmak ve
"ne var, hangi düzey, hangi yıllar, indirilebilir mi" diye işaretlemek. Mevcut genel kaynak
listesi `docs/kaynaklar.md`; burası il/ilçe odaklı ek.

**Durum sütunu:** ✔ sayfası açılıp içeriği görüldü · ◐ arama sonucunda görüldü, sayfası
doğrulanmadı · ✘ otomatik erişime kapalı (tarayıcıyla denenecek) · depoda = yüklendi.

| Kurum | Veri | Düzey | Yıllar | Biçim | Durum |
|---|---|---|---|---|---|
| TBB Veri Sistemi | mevduat, kredi, çalışan, ATM, POS, işyeri | il | 1988-2025 | JSON (api/router) | depoda |
| TCMB EVDS | konut fiyat/kira, konut satış, bölge TÜFE, il GSYH 1987-2001, sınır kapısı ziyaretçi | il, İBBS-2 | çeşitli | JSON API | depoda |
| TÜİK MEDAS — Bölgesel Hesaplar | il GSYH hacim endeksi, reel değişim, kişi başı (TL/$), sektör ve bölgesel paylar (2009 bazlı); TL değeri ve fiyat kodu kırılımı sorgu kurmuyor | il | 2000-2024 | CSV | depoda |
| TKGM MEGSİS veri onay | tapu/kadastro parsel, onay, koordinat kalitesi | il (bölge); il düğmesi → birim alt tablosu, denenmedi | anlık (14.09.2026) | HTML (postback) | ham diskte, `scripts/fetch_tkgm_megsis.py`, TOPLAM tutuyor |
| TKGM 3B | 3B bina/kadastro sunumu | bina | — | harita, indirme | ✔ tablo değil |
| SGK istatistik yıllıkları | sigortalı (4a/4b/4c, cinsiyet, sektör, işyeri büyüklüğü), işyeri, kazanç, aylık/gelir alan, iş kazası, hastalık — 2025 yıllığında 36 il tablosu; ilçe yok | il | 2007-2025 | ZIP (Excel), biçim yıldan yıla değişir | ✔ ham diskte (`C:\veri-ham\sgk\yillik`), Tablo 1.8 il toplamı Toplam satırını tutuyor; adaptör yok |
| EPDK resmi istatistikler | elektrik, doğalgaz, petrol, LPG piyasası; il kırılımı Excel içinde olabilir | ◐ il | 2010-2026 | xlsx, docx | ✔ liste · Excel bağlantıları JS ile geliyor, httpx boş döner → tarayıcıyla |
| Hazine ve Maliye (Muhasebat) | genel bütçe gelirlerinin iller itibarıyla tahakkuk ve tahsilatı | il | 2004-2019 (+?) | ◐ | ✘ |
| GİB | bütçe gelirleri istatistikleri; İstanbul Defterdarlığı ayrıca | il (◐) | ◐ | ◐ | ✘ (IP engeli) |
| Adalet Bakanlığı Adli Sicil | adalet istatistikleri kitabı, haber bültenleri | il/adliye (◐) | yıllık | PDF | ◐ |
| UYAP İstatistik | dava/icra istatistikleri; RİP dışı, erişim kısıtlı | ◐ | ◐ | ◐ | ✘ |
| Sanayi ve Teknoloji — SEGE | il ve ilçe sosyoekonomik gelişmişlik (ilçe SEGE-2022: 973 ilçe, 56 değişken, 8 boyut) | il, ilçe | 2017, 2022 | PDF (kalkınma ajanslarında) | ✘ bakanlık sayfası · ◐ ajans kopyaları |
| Kalkınma ajansları (26) | SEGE kopyaları, bölge/il raporları | il, ilçe | düzensiz | PDF | ◐ |
| Türkiye Noterler Birliği | il bazında noter işlem istatistiği bulunamadı | — | — | — | ◐ yok |
| Valilikler | il istatistik yıllıkları (ör. Kırklareli: tapu, kadastro, imar) | il, ilçe | düzensiz | PDF | ◐ |
| Resmi İstatistik Portalı | RİP'teki bütün kurum istatistiklerinin kataloğu — envanterin asıl kaynağı | — | — | JS uygulaması | ✘ |
| Dünya Bankası API | kişi başı GSYH (cari $) TR ve dünya, ABD TÜFE | ülke | 1960-2025 | JSON | ✔ analiz `docs/analiz/kisi-basi-gsyh-reel.csv` |

## Sıradaki adımlar

0. SGK il tabloları için adaptör (yıl yıl sayfa adı ve başlık eşleme); EPDK Excel'lerini
   tarayıcıyla bulmak; kolaydan zora süpürme sırası: SGK → EPDK → TKGM birim → İlçe SEGE →
   Muhasebat → Resmi İstatistik Portalı → PDF kaynaklar.

1. Resmi İstatistik Portalı'nı tarayıcıyla açıp kurum × istatistik × düzey listesini çıkarmak
   (envanterin geri kalanı buradan).
2. SGK 2025 yıllığının ZIP'ini indirip il tablolarını doğrulamak.
3. EPDK yıllık Excel'inde il kırılımı var mı bakmak.
4. İlçe SEGE-2022 değişken tablosunun (56 değişken × 973 ilçe) PDF ekinde mi, Excel'de mi
   olduğunu bulmak — ilçe atlası için en değerli tek kaynak adayı.
5. Muhasebat il tahsilat serisinin 2020 sonrası devamı.
