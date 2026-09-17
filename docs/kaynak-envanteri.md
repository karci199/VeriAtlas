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
| Hazine ve Maliye (Muhasebat) | genel bütçe gelirlerinin iller itibarıyla tahakkuk ve tahsilatı (2004-2025); iller itibarıyla merkezi yönetim bütçe geliri ve gideri (2004-2025); mahalli idareler bütçe geliri ve gideri (2006-2025) | il | 2004-2025 | xls, portal API | ✔ yüklendi (`scripts/fetch_muhasebat.py`, `adapters/muhasebat.py`) |
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

## Keşif turu 2026-09-15 (httpx ile 5 dakikalık bakış)

| Kurum | Ne var | Biçim | Zorluk | Not |
|---|---|---|---|---|
| TOBB kurulan/kapanan şirket | il bazında kurulan-kapanan şirket, il sermaye; Aralık dosyasında yıllık birikimli | xls/xlsx, 2010-2026 aylık | kolay | `Documents/ResmiDosya/<yıl>/<yıl>-<ay>.xls`; sayfa "İLLER (BİRİKİMLİ)" |
| YÖK İstatistik | üniversite/birim öğrenci, öğretim elemanı | ZK uygulaması (MEDAS gibi) | orta | ZK protokolü MEDAS'ta çözülmüştü |
| YÖK Atlas | program bazında taban puan, kontenjan, yerleşen profili (il, lise) | React + `/api` | orta | robots.txt gerçek dosya değil; API uç noktaları bulunmalı |
| MEB SGB | örgün eğitim istatistikleri | xls, pdf | ✘ | robots.txt yapay zekâ ajanlarını engelliyor — alınmaz |
| Adalet Adli Sicil | adalet istatistikleri kitabı 2022-2025 | PDF | zor | il/adliye tabloları PDF'te |
| Diyanet, OGM, SBB | yayın/istatistik | PDF | zor | |
| Sağlık Bakanlığı, İŞKUR, AFAD, Muhasebat | istatistik sayfaları | JS uygulaması | orta/bilinmiyor | tarayıcıyla bakılmalı |
| Kültür Turizm, GSB, Veri Portalı, Ankara BB | — | bağlantı hatası | bilinmiyor | buradan erişilemedi, tarayıcıyla denenmeli |
| İBB Açık Veri | CKAN API | JSON | ✘ | robots.txt yasak |
| ÖSYM | sonuç istatistikleri | — | bilinmiyor | istatistik sayfası adresi bulunamadı |

## Keşif turu 2026-09-16 (BTK bitti, yeni kaynak avı)

| Kurum | Ne var | Biçim | Zorluk | Durum |
|---|---|---|---|---|
| DHMİ | havalimanı bazında uçak, yolcu, yük, kargo; iç/dış hat; aylık birikimli | xlsx, 2008-2026 | kolay | **depoda** (`docs/dhmi.md`) |
| MGM | il bazında aylık iklim normalleri (sıcaklık, güneş, yağış, yağışlı gün) ve rekorlar | HTML tablo | kolay | **depoda** (`docs/mgm.md`) |
| EPİAŞ Şeffaflık | elektrik üretim/tüketim/fiyat, saatlik; 301 uç nokta, dağıtım bölgesi kırılımı | REST API + swagger | orta | ✘ tarihsel veri TGT (hesap) istiyor; açık uçlar yalnız bugünün üretimi ve tek günlük fiyat. Kullanıcı hesap açarsa çekilebilir |
| TEİAŞ | elektrik üretim-iletim istatistikleri | JS uygulaması | orta | ✘ httpx ile dosya görünmüyor |
| AFAD | afet istatistikleri | PDF | orta | ◐ sayfada 4 PDF |
| TCDD | demiryolu istatistikleri | — | bilinmiyor | ✘ 403 |
| NVİ, OGM, UAB | — | — | bilinmiyor | ✘ 404 |
| İŞKUR, Ticaret Bakanlığı, Kültür Turizm, GSB | istatistik sayfaları | JS / bağlantı hatası | bilinmiyor | ✘ tarayıcıyla denenmeli |
| BDDK | aylık bülten | — | bilinmiyor | ✘ bağlantı kurulamadı |

MGM'de ilçe düzeyi de var ama sayfa adlandırması farklı (`m=IZNIK` boş döndü); ilçe iklim
verisi ayrı bir iş olarak duruyor.

## Keşif turu 2026-09-16 akşam (ETKB ve Diyanet çekildi, EPİAŞ kapandı)

| Kurum | Ne var | Biçim | Zorluk | Durum |
|---|---|---|---|---|
| ETKB / EİGM | il × kaynak devreye giren kurulu güç ve santral sayısı, 2003-2025 | xls/xlsx, yılda bir dosya | kolay | **depoda** (`docs/etkb.md`) |
| Diyanet | cami, personel, Kur'an kursu, hac-umre, ihtida, bütçe; il tabloları İBBS-3 | 11 xls/xlsx | kolay | **depoda** (`docs/diyanet.md`) |
| EPİAŞ Şeffaflık | PTF/SMF saatlik fiyat, gerçek zamanlı üretim (kaynak bazında), santral bazlı üretim, dağıtım bölgesi tüketimi, dengesizlik, YEKDEM, doğal gaz piyasası | REST API | orta | ✘ **kapatıldı.** Dört uç nokta denendi, hepsi kimlik istiyor (`401` ya da "TGT göndermeniz gerekmektedir"). Hesap açmak kullanıcıya ait; kullanıcıyla "çok gerekli mi" diye konuşuldu ve **vazgeçildi**: fiyat tarafı EVDS+EPDK'da, üretim-tüketim aylık olarak EPDK'da var; EPİAŞ'ın eklediği saatlik çözünürlük ve santral bazı, projenin il ekseninde az kazanç. Tek gerçek boşluk il bazında **fiilî üretim** — istenirse hesapla açılır |
| Sağlık Bakanlığı (SBSGM) | Sağlık İstatistikleri Yıllığı: il bazında hastane, yatak, hekim, başvuru, aşılama | PDF (e-kütüphane), sayfalar JS ile çiziliyor, Excel yok | orta | ◐ **sıradaki aday.** BTK'da geliştirilen PDF merdiveni burada da işler. Depoda TÜİK/MEDAS'tan gelen 7 sağlık göstergesi var (hastane, yatak, hekim, hekime başvuru), yıllık bunları uzatır ve derinleştirir |
| İŞKUR | işgücü piyasası, açık iş, işe yerleştirme | sayfa JS; httpx'le bağlantı yok | bilinmiyor | ✘ tarayıcıyla yeniden denenmeli |
| MEB | örgün eğitim istatistikleri | xls/pdf | ✘ | **alınmadı ve alınmayacak**: robots.txt yapay zekâ ajanlarını engelliyor. Eğitimde depodaki veri TÜİK/MEDAS (ilçe eğitim düzeyi, okuryazarlık) ve YÖK üzerinden geliyor; okul/öğretmen/öğrenci sayıları eksik kalıyor |

## Keşif turu 2026-09-17 (kolay olanlar: Excel ve API)

| Kurum | Ne var | Kapsam | Biçim | Zorluk | Not |
|---|---|---|---|---|---|
| TİM | ihracat: il, il × sektör, il × ülke; sektör, ülke, alt mal grubu | il, 2005-2026 aylık (Aralık = yıl) | xls/xlsx, ~1.600 dosya | kolay | `tim.org.tr/tr/ihracat-rakamlari`; bağlantılar sayfa HTML'inde, dosya adları yıldan yıla değişiyor. Depoda il ihracatı yok |
| İŞKUR | istatistik yıllığı tabloları (başvuru, açık iş, yerleştirme, kayıtlı işsiz, il) | il, 2003-2025 | xlsx/xls, 2004-2011 zip | kolay | `iskur.gov.tr/kurumsal/istatistikler/istatistik-yilliklari/`; 1978-2002 yalnız PDF |
| Kültür Turizm (YİGM) | turizm işletme belgeli tesis konaklama: il-ilçe | il, ilçe, 1996-2025 | xlsx/xls (2007-2008 PDF) | kolay | `yigm.ktb.gov.tr/TR-208783`; depodaki turizm yalnız Türkiye geneli |
| BDDK FinTürk | il bazında kredi, mevduat, şube, kişi başı, oranlar; 7 tablo × banka grubu | il, çeyreklik (75 dönem) | jqGrid JSON (form + ajax) | orta-kolay | httpx'te SSL zinciri eksik (verify kapatılmalı ya da tarayıcı); TBB il verisiyle kısmen örtüşür |
| GSB Spor Hizmetleri | illere göre kulüp sayısı, sporcu, antrenör, hakem, madalya | il (kulüp), Türkiye | xlsx | kolay | `shgm.gsb.gov.tr/Sayfalar/175/105/Istatistikler`; yalnız son yıllar |
| ETKB/EİGM | Ulusal Enerji Denge Tabloları; enerji yatırımları | Türkiye, 1972-2024; 2003-2025 | xlsx/xls | kolay | `enerji.gov.tr/eigm-raporlari`; il yok |
| VAP (MKK) | illere göre yatırımcı sayısı ve portföy | il | JS uygulaması | bilinmiyor | httpx'te veri yok; tarayıcıda API aranmalı |
| Göç İdaresi | ikamet izinleri, uluslararası koruma, düzensiz göç | il (◐) | HTML/grafik | bilinmiyor | sayfalar grafik, tablo indirme görünmüyor |
| KOSGEB, SPK, TÜRKPATENT, TKGM, Ticaret Bak. | — | — | — | ✘ | Excel ya da il tablosu görünmedi |

## Keşif turu 2026-09-17 akşam (API)

| Kurum | Ne var | Kapsam | Biçim | Zorluk | Not |
|---|---|---|---|---|---|
| Eurostat | bölgesel işsizlik ve istihdam oranı (`lfst_r_lfu3rt`, `lfst_r_lfe2emprt`), bölge ve il GSYH avro (`nama_10r_2gdp`, `nama_10r_3gdp`), eğitim düzeyi (`edat_lfse_04`), hastane yatağı (`hlth_rs_bdsrg`), turizm geceleme (`tour_occ_nin2`) | İBBS-2 (26 bölge), GSYH İBBS-3; 1999/2000-2025 | JSON-stat REST, anahtarsız | kolay | MEDAS'ta alınmayan bölgesel işgücünü kapatır. `ilc_li41` (yoksulluk) TR için boş |
| AFAD deprem | olay bazında deprem: tarih, büyüklük, derinlik, il, ilçe, mahalle | nokta → il/ilçe, yıllık sayım | JSON REST (`deprem.afad.gov.tr/apiv2/event/filter` → servisnet yönlendirmesi), anahtarsız | kolay | tarih aralığıyla parça parça çekilir |
| OECD Regional | TL2/TL3 bölgesel veritabanı | il/bölge | SDMX REST | orta | Eurostat'la büyük ölçüde örtüşür |
| SBB, Sanayi (teşvik, sicil), TÜRKPATENT, MAPEG, OSBÜK, ESBİS, Muhasebat, EGM, YSK, OGM | — | — | JS kabuk, 404 ya da bağlantı yok | ✘ | httpx'le veri görünmedi; tarayıcıyla ayrıca bakılabilir |
