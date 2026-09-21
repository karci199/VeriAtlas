# Dal temizliği (2026-09-22)

26 dalda ana dala hiç girmemiş iş vardı (`git cherry main <dal>` ile ölçüldü; aynı
değişikliği başka hash'le taşıyan commit'ler sayılmadı). Dalların hiçbiri olduğu gibi
birleştirilmedi: çoğu Ağustos'tan kalma, ana dal o dosyaları sonradan yeniden yazdı ve
kör birleştirme yeni kodu eskisiyle ezerdi. Kural şuydu:

1. **Ana dalda hiç olmayan dosya** → dalın en son hâliyle alındı (ekleme, risksiz).
   339 dosya: betikler, belgeler, testler, web sayfaları ve onların okuduğu `public/`
   dilimleri. `scratch/`, `toc.txt`, `sec117.txt` karalama olduğu için alınmadı.
2. **Adaptör** → ana dala takıldı, ham veriyle `fetch`+`parse` denendi; çalışan ve ana
   dalda karşılığı olmayan kaydedildi.
3. **İki tarafta da olan belge** → yalnız dalda bulunan `##` bölümleri, dosyanın sonuna
   "… dalından kurtarılan notlar" başlığıyla eklendi (38 bölüm). Çelişen yerde dosyanın
   üst kısmı geçerlidir.
4. **İki tarafta da olan kod** → ana dalınki geçerli; dal sürümü alınmadı.

Her dal silinmeden önce `arsiv/<dal>` etiketiyle saklandı; hiçbir commit kaybolmadı.

## Depoya giren göstergeler

| Gösterge | Kaynak dal | Adaptör |
| --- | --- | --- |
| `pharmacies` (31.451 eczane, 967 ilçe) | a101-background-pull | pharmacies.py |
| `card_*_by_sector`, `ecommerce_*_by_sector` (BKM, 4) | a101-background-pull | bkm_sector.py |
| Domino's (1.097 şube) → `chain_restaurants` | a101-background-pull | chain_stores.py |
| `net_enrollment_rate`, `gender_student_ratio`, `class_size`, `section_size`, `section_room_ratio`, `school_size` | nerde-kaldik-836888 | meb_education.py |
| `district_urbanization` | nerde-kaldik-836888 | ysk_urbanization.py |
| `births_by_age`, `births_by_marital`, `consanguineous_marriage`, `literacy`, `literacy_by_age` | nerede-kaldik-4998d7 | tuik_*.py |
| `education_attainment` | hanehalk-buyuklugu | tuik_household_excel.py |

## Alınan ama kaydedilmeyen adaptörler

Kod depoda, `ADAPTERS`'a eklenmedi. Tam yükleme onları çağırmaz.

| Adaptör | Neden |
| --- | --- |
| `endeksa.py` | `C:\veri-ham\endeksa` düzeni adaptörün beklediği gibi değil (`demography/` altına taşınmış). Katalog tanımları eklendi, test geçiyor. |
| `tuik_district_vital.py` | Ham veri yok: `scripts/fetch_medas_vital_districts.py dogum|olum` yeniden çalıştırılmalı. |
| `tuik_marriage.py` | Ham veri yok (ilçe evlenme/boşanma, ilk evlenme yaşı/eğitimi). |
| `tuik_household_excel.py` konut mülkiyeti / bina yaşı | `household-type.xlsx` yok. |

Ana dalda zaten başka adaptörle üretildiği için alınmayanlar: `yok_students.py`
(`yok_students` ailesi), `tuik_literacy_district.py` (`tuik_education_district`),
`tuik_household_excel` hane büyüklüğü (`tuik_household`).

## a101-background-pull dalının dersi

Bu dal 2026-09-20'de tam yükleme yapmış (898 gösterge), sonra ana dala hiç
birleştirilmemişti. Aynı gün ana dal BİM, Migros, Tarım Kredi, Vestel ve Koçtaş'ı başka
yöntemle yeniden yazdı; eczane ve BKM ise sonraki yüklemelerde depodan düştü. Oturum
sonunda dal ana dala alınmadıysa iş depoda görünür ama yarın yoktur.
