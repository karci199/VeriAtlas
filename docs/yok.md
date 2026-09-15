# YÖK verileri

Kaynaklar: YÖK İstatistik (istatistik.yok.gov.tr, ZK 8 uygulaması, tarayıcısız istemci
`scripts/yok_zk.py`, indirici `scripts/fetch_yok_istatistik.py`, ham `C:\veri-ham\yok_istatistik`)
ve YÖK Atlas API (`scripts/fetch_yokatlas.py`). Adaptörler: `yok_istatistik.py`,
`yok_national.py`, `yks.py`, `yokatlas.py`.

| Gösterge | Kırılım | Dönem |
|---|---|---|
| `yok_students`, `yok_new_students`, `yok_graduates` | il + ilçe × düzey × öğretim türü × cinsiyet × üniversite türü | 2013/2014-2025 |
| `yok_*_archive` | Türkiye × düzey × öğretim türü × cinsiyet | 1982/1983-2012 |
| `yok_academic_staff` | il × unvan × cinsiyet × üniversite türü | 2013-2025 |
| `yok_international_students`, `yok_international_graduates`, `yok_foreign_academic_staff` | Türkiye × ülke × düzey/unvan × cinsiyet | 2013-2025 |
| `yok_new_students_by_age`, `yok_students_by_age`, `yok_graduates_by_age` | Türkiye × yaş × düzey × öğretim türü × cinsiyet | 2013-2025 |
| `yok_students_by_field`, `yok_graduates_by_field`, `yok_academic_staff_by_field` | Türkiye × ISCED alanı (geniş/dar/ayrıntılı) × düzey × cinsiyet | 2015-2025 |
| `yks_applicants_placed` | Türkiye başvuran / yerleşen | 1980-2025 |
| `yks_applicants_by_school` | okul türü × aday durumu × başvuran / lisans-önlisans-AÖ yerleşen | 2015-2025 |
| `university_quota`, `university_programs` | il × lisans/önlisans × devlet/vakıf (2026 kılavuz) | 2026 |

## Kontroller (her yıl kendi dosyasından, sonra çapraz)

- İl tabloları basılı TOPLAM'ı her sütunda tutar; ilçe kapsamı %99,7-100.
- Yaş ve alan tablolarının toplamı il tablolarıyla birebir (yaş 2024: +562 öğrenci).
- Akademisyen alan toplamı unvan tablosuyla birebir, 2024 hariç (−3.266).
- YKS yıllık dosyaları 1980-2025 serisini tutar (2024 yerleşen: 986.861 / 987.911).

## Sessizce bozan tuzaklar (düzeltildi)

- ZK artan `ZK-SID` ister; sabit değer eski yanıtı döndürür.
- Üst başlık etiketi sağa taşınır: "DOKTORA" toplam sütunlarına yapışıp uluslararası öğrenciyi
  iki kat sayıyordu (grup başlangıcında taşıma sıfırlanır; aynı anlamlı iki sütun hata).
- Ülke adları yıldan yıla farklı ("ALMANYA" / "ALMANYA FEDERAL CUMHURİYETİ"): tek koda;
  iki Kongo ayrı; "HAYMATLOS" → `_stateless`.
- `fold` rakamları siler: yaş kodları sayıdan üretilir (`17`, `lt16`, `65+`, `30-34`).
- Alan tabloları hiyerarşik ve kodsuz: düzey toplamlardan çözülür; SINIFLANMAMIŞ /
  BİLİNMEYEN ALAN tek satır; 2021-2023 TOPLAM etiketsiz ya da "Genel Toplam".
- 2016-2017 yeni kayıt doktora hücreleri karışık: satır toplamı − diğer düzeyler.
- MERKEZ (büyükşehir) ve başka ilin ilçesi olarak basılan kampüsler ilçeye yerleştirildi;
  yurt dışı kampüsler (Güzelyurt ≠ Aksaray) il düzeyinde.

## Alınmayanlar

- Alan tabloları 2013-2014, 2014-2015: eski sınıflama; 2014-2015'te satırlar toplamın 3 katını
  1.182 kişi eksik veriyor, hiyerarşi çözülmüyor.
- Lisansüstü alan mezun 2025-2026: sonda kodlu tekrar satırlar ("GENİŞ ALAN 08 …"), toplam 1 kişi
  tutmuyor. (2021-2022 lisansüstü öğrenci ve mezun düzeltildi: "(boş)" satırları sınıflanmamış
  alanın yanlış yere basılmış alt satırları.)
- 2025-2026 uluslararası öğrenci uyruk tablosu yayında yok.
- Yerleşen adayın geldiği il/lise (YÖK Atlas yeni API'de girişsiz değil).
- MEB: robots.txt engeli, çekilmez.
