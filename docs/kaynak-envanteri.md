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
| TÜİK MEDAS — Bölgesel Hesaplar | il GSYH endeks, kişi başı, sektör payı (2009 bazlı); GSYH değeri sorgu kurmuyor | il | 2000-2024 | CSV | çekiliyor |
| TKGM MEGSİS veri onay | tapu/kadastro parsel, onay, koordinat kalitesi | il (bölge); il → birim alt tablosu var, denenmedi | anlık (14.09.2026) | HTML (postback) | ham diskte |
| TKGM 3B | 3B bina/kadastro sunumu | bina | — | harita, indirme | ✔ tablo değil |
| SGK istatistik yıllıkları | sigortalı, işyeri, aylık alan, iş kazası (il kırılımı arama özetine göre) | il (◐) | 2007-2025 | ZIP (Excel) | ✔ liste · içerik ✘ |
| EPDK resmi istatistikler | elektrik, doğalgaz, petrol, LPG piyasası; sayfada il kırılımı görünmüyor (Excel içinde olabilir) | ◐ il | 2010-2026 | xlsx, docx | ✔ |
| Hazine ve Maliye (Muhasebat) | genel bütçe gelirlerinin iller itibarıyla tahakkuk ve tahsilatı | il | 2004-2019 (+?) | ◐ | ✘ |
| GİB | bütçe gelirleri istatistikleri; İstanbul Defterdarlığı ayrıca | il (◐) | ◐ | ◐ | ✘ (IP engeli) |
| Adalet Bakanlığı Adli Sicil | adalet istatistikleri kitabı, haber bültenleri | il/adliye (◐) | yıllık | PDF | ◐ |
| UYAP İstatistik | dava/icra istatistikleri; RİP dışı, erişim kısıtlı | ◐ | ◐ | ◐ | ✘ |
| Sanayi ve Teknoloji — SEGE | il ve ilçe sosyoekonomik gelişmişlik (ilçe SEGE-2022: 973 ilçe, 56 değişken, 8 boyut) | il, ilçe | 2017, 2022 | PDF (kalkınma ajanslarında) | ✘ bakanlık sayfası · ◐ ajans kopyaları |
| Kalkınma ajansları (26) | SEGE kopyaları, bölge/il raporları | il, ilçe | düzensiz | PDF | ◐ |
| Türkiye Noterler Birliği | il bazında noter işlem istatistiği bulunamadı | — | — | — | ◐ yok |
| Valilikler | il istatistik yıllıkları (ör. Kırklareli: tapu, kadastro, imar) | il, ilçe | düzensiz | PDF | ◐ |
| Resmi İstatistik Portalı | RİP'teki bütün kurum istatistiklerinin kataloğu — envanterin asıl kaynağı | — | — | JS uygulaması | ✘ |

## Sıradaki adımlar

1. Resmi İstatistik Portalı'nı tarayıcıyla açıp kurum × istatistik × düzey listesini çıkarmak
   (envanterin geri kalanı buradan).
2. SGK 2025 yıllığının ZIP'ini indirip il tablolarını doğrulamak.
3. EPDK yıllık Excel'inde il kırılımı var mı bakmak.
4. İlçe SEGE-2022 değişken tablosunun (56 değişken × 973 ilçe) PDF ekinde mi, Excel'de mi
   olduğunu bulmak — ilçe atlası için en değerli tek kaynak adayı.
5. Muhasebat il tahsilat serisinin 2020 sonrası devamı.
