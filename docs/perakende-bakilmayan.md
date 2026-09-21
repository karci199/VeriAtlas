# Perakende ve hizmet ağları: nereye bakıldı, nereye hiç bakılmadı (2026-09-22)

Ölçüt: tür adı ve belli başlı marka adları `docs/*.md` içinde ve zincir tarama
dökümlerinde (`zincir_tarama*.csv`, `marka_aday_havuzu.json`) aranmıştır. "Hiç
bakılmadı" = hiçbir belgede ve taramada geçmiyor. Yeni çekmeden önce yine
[envanter.md](envanter.md)'ye bakılır.

## Depoda

| Tür | Gösterge | Markalar |
| --- | --- | --- |
| Market / indirim | `chain_stores` | BİM, Migros, ŞOK, Hakmar, Tarım Kredi, Seç, Ekomini, Mopaş, Furpa, Seyhanlar, bölge zincirleri |
| Kozmetik | `chain_stores` | Gratis, Rossmann |
| Ev / mutfak | `chain_stores` | Karaca, Madame Coco |
| Yapı market | `chain_stores` | Koçtaş |
| Elektronik | `chain_stores` | Vatan, Vestel |
| Yeme-içme | `chain_restaurants` | McDonald's, Burger King, Domino's, Starbucks, EspressoLab, Komagene, Oses, Ziyafet |
| Giyim | `fashion_stores` | LC Waikiki, DeFacto, Mavi, Koton, Sarar, Zara, H&M, Superstep, Skechers |
| Banka | `bank_branch_locations`, `bank_atm_locations` | 16 banka |
| Operatör | `telecom_dealers` | Türk Telekom, Vodafone |
| Akaryakıt | `fuel_stations` | EPDK lisans kaydı, 32 dağıtıcı |
| Şarj | `charging_stations` | EPDK |
| Eczane | `pharmacies` | TİTCK ruhsat kaydı |
| Kargo | `cargo_branches` | Aras (Yurtiçi, DHL eCommerce, Sürat çekiliyor) |

## Ham verisi var, adaptör bekliyor

Kahve Dünyası (355), Simit Sarayı (110), Toyzz Shop (263), HD İskender (96), Usta
Dönerci (il sayıları), Bizim Toptan (172), Happy Center (194), Onur Market (154),
KFC (43, yarım), PTT iş yerleri (3.295; merkez / şube / acentelik ayrımıyla).

## Denendi, alınamadı

A101 (IP 403), CarrefourSA (robots), Watsons / Teknosa / Mado (403), MediaMarkt
(robots), Arçelik / Beko (beyaz eşyada kapalı kapılar), Turkcell (koordinat yok),
Garanti BBVA ATM, HepsiJet.

## Hiç bakılmadı

Değer sütunu: ilçe düzeyinde neyi ölçtüğü.

| Tür | Aday markalar / kayıt | Neyi ölçer |
| --- | --- | --- |
| **Mobilya** | İstikbal, Bellona, Doğtaş, Kelebek, Mondi, Enza, IKEA | yeni konut ve hane kurulumu talebi |
| **Oto servis / lastik** | Bosch Car Service, Petlas, Lassa, Michelin, Otokoç, marka yetkili servisleri | araç sahipliğinin yerel karşılığı |
| **Evcil hayvan** | Petzz, Pet Shop zincirleri | kentli, orta gelir göstergesi |
| **Spor salonu** | Mac Fit, Fitness Park, Hillside | gelir ve genç nüfus |
| **Sürücü kursu, dershane, kurs merkezi** | MEB özel öğretim kurumları kaydı | eğitim harcaması; MEB robots engeli ayrıca kontrol edilmeli ([[meb_robots_engeli]]) |
| **Optik** | Atasun, Opmar, Özdemir Optik | yaşlı nüfus ve gelir |
| **Spor giyim / ayakkabı** | Decathlon, Intersport, FLO, Deichmann | giyimin alt türü; Superstep ve Skechers dışında bakılmadı |
| **Kitap / kırtasiye** | D&R, Remzi, Nezih, Pandora | kültür harcaması |
| **Kuyum** | Atasay, Altınbaş | gelir ve birikim |
| **Beyaz eşya (kalan)** | Bosch/Siemens (BSH), Samsung, Profilo, Regal | Arçelik/Beko kapalı; diğerleri denenmedi |
| **Oto kiralama** | Avis, Budget, Enterprise, Garenta | turizm ve havalimanı etkisi |
| **Kuaför / güzellik** | zincir azdır; kayıt kaynağı yok | — (düşük öncelik) |
| **Çamaşır / kuru temizleme** | zincir azdır | — (düşük öncelik) |
| **Noter** | Türkiye Noterler Birliği noter listesi | kamusal hizmet erişimi; resmî ve tam liste |

**Öncelik önerisi:** Önce resmî ve tam listeler (Noterler Birliği, MEB özel öğretim
kayıtları; robots kontrolüyle), çünkü marka seçme sorunu yok. Sonra mobilya ve oto
servis, çünkü ilçe düzeyinde başka bir göstergenin vermediği şeyi ölçüyorlar.
