# Perakende ve hizmet ağları: durum

**Bu dosya elle yazılmaz.** `scripts/build_retail_status.py` üretir (23.09.2026). Depodaki satırlar `fact.parquet`'ten sayılır; depo dışındakiler betikteki `OFF_WAREHOUSE` listesindedir. Sıralanabilir sürüm: `perakende-durum.html`.

## Depoda (89)

| Marka | Tür | Mağaza | İl | İlçe | Yöntem | Not |
|---|---|---|---|---|---|---|
| Akaryakıt istasyonları | Akaryakıt | 12.629 | 81 | 959 | EPDK lisans kaydı | 32 dağıtıcı birlikte |
| Ziraat Bankası | Banka | 1.733 | 81 | 959 | şube ve ATM bulucu | ATM 7.848 |
| Halkbank | Banka | 1.103 | 81 | 591 | şube ve ATM bulucu | ATM 4.962 |
| İş Bankası | Banka | 988 | 81 | 437 | şube ve ATM bulucu | ATM 5.227 |
| VakıfBank | Banka | 965 | 81 | 392 | şube ve ATM bulucu | ATM 4.117 |
| Yapı Kredi | Banka | 718 | 72 | 284 | şube ve ATM bulucu | ATM 4.970 |
| DenizBank | Banka | 592 | 81 | 319 | şube ve ATM bulucu | ATM 2.990 |
| Akbank | Banka | 589 | 76 | 279 | şube ve ATM bulucu | ATM 4.829 |
| Kuveyt Türk | Banka | 460 | 73 | 199 | şube ve ATM bulucu | ATM 1.443 |
| TEB | Banka | 417 | 69 | 210 | şube ve ATM bulucu | ATM 1.411 |
| Şekerbank | Banka | 237 | 67 | 197 | şube ve ATM bulucu | ATM 258 |
| Ziraat Katılım | Banka | 234 | 66 | 143 | şube ve ATM bulucu | ATM yok |
| Vakıf Katılım | Banka | 224 | 53 | 124 | şube ve ATM bulucu | ATM 198 |
| Albaraka Türk | Banka | 221 | 55 | 122 | şube ve ATM bulucu | ATM 237 |
| Türkiye Finans | Banka | 217 | 61 | 133 | şube ve ATM bulucu | ATM 428 |
| Emlak Katılım | Banka | 132 | 45 | 96 | şube ve ATM bulucu | ATM 127 |
| ING | Banka | 52 | 15 | 30 | şube ve ATM bulucu | ATM yok |
| Fibabanka | Banka | 38 | 10 | 26 | şube ve ATM bulucu | ATM 36 |
| Eczaneler | Eczane | 31.451 | 81 | 967 | TİTCK ruhsat kaydı | resmî ve tam liste |
| Vestel | Elektronik | 1.158 | 81 | 489 | mağaza bulucu |  |
| Vatan Bilgisayar | Elektronik | 150 | 57 | 113 | mağaza bulucu |  |
| Teknosa | Elektronik | 136 | 56 | 121 | elle kaydedilen sayfa | robots 403; sayfanın kendi toplamı 136 |
| Madame Coco | Ev | 660 | 80 | 310 | mağaza bulucu |  |
| English Home | Ev | 305 | 59 | 155 | Ticimax ortak ucu | 42 yurt dışı mağaza ayıklandı |
| Karaca | Ev | 167 | 55 | 111 | mağaza bulucu |  |
| Mudo | Ev | 127 | 28 | 69 | Akinon ortak ucu |  |
| Chakra | Ev | 66 | 18 | 38 | Akinon ortak ucu | 18 yurt dışı mağaza ayıklandı |
| LC Waikiki | Giyim | 510 | 81 | 257 | mağaza bulucu |  |
| Mavi | Giyim | 391 | 68 | 185 | mağaza bulucu |  |
| DeFacto | Giyim | 319 | 66 | 176 | mağaza bulucu |  |
| Koton | Giyim | 238 | 65 | 156 | mağaza bulucu |  |
| Superstep | Giyim | 191 | 36 | 86 | mağaza bulucu |  |
| Avva | Giyim | 146 | 44 | 99 | Ticimax ortak ucu | 23 yurt dışı mağaza ayıklandı |
| Sarar | Giyim | 119 | 45 | 86 | mağaza bulucu |  |
| H&M | Giyim | 45 | 16 | 35 | mağaza bulucu |  |
| Zara | Giyim | 39 | 9 | 29 | mağaza bulucu |  |
| Skechers | Giyim | 31 | 15 | 26 | mağaza bulucu |  |
| Şube | Kargo | 1.686 | 81 | 567 | PTT iş yeri bulucu |  |
| Merkez (müdürlük) | Kargo | 1.082 | 81 | 758 | PTT iş yeri bulucu |  |
| Yurtiçi Kargo | Kargo | 1.048 | 81 | 373 | şube kimliği taraması | 1-12000 tarandı; doğu 8010-8499 |
| DHL eCommerce (MNG) | Kargo | 821 | 81 | 358 | şube bulucu |  |
| Aras Kargo | Kargo | 788 | 81 | 399 | şube bulucu |  |
| Sürat Kargo | Kargo | 784 | 81 | 350 | ilçe ilçe sorgu | 388'i acente; 33 koordinatsız dışarıda |
| Acentelik | Kargo | 523 | 65 | 276 | PTT iş yeri bulucu |  |
| Kolay Gelsin | Kargo | 206 | 68 | 205 | teslimat noktası haritası | yalnız DN/DM birimleri; ~990 anlaşmalı nokta ham veride |
| Gratis | Kozmetik | 897 | 81 | 312 | mağaza bulucu |  |
| Rossmann | Kozmetik | 209 | 43 | 101 | mağaza bulucu | 23.09 elle kayıtta 211 mağaza; tutarlı |
| Flormar | Kozmetik | 108 | 30 | 69 | Akinon ortak ucu |  |
| Atasay (kuyum) | Kuyum | 154 | 46 | 95 | Akinon ortak ucu | 9 yurt dışı mağaza ayıklandı |
| BİM (FİLE dahil) | Market | 13.057 | 81 | 916 | ilçe sayımı | BİM ve FİLE birlikte; mağaza değil ilçe toplamı |
| ŞOK Market | Market | 11.220 | 80 | 809 | mağaza bulucu |  |
| Migros | Market | 3.442 | 81 | 528 | ilçe sayımı | Migros, MJet, Macrocenter birlikte; ilçe toplamı |
| Tarım Kredi Kooperatif Market | Market | 2.348 | 81 | 640 | mağaza bulucu |  |
| Seç Market | Market | 2.245 | 81 | 646 | ilçe etiketi | 12 mağazanın ilçe etiketi bozuk, dışarıda |
| Ekomini | Market | 2.173 | 81 | 614 | mağaza bulucu |  |
| Hakmar Express | Market | 813 | 7 | 55 | mağaza bulucu |  |
| Peynirci Baba | Market | 170 | 17 | 59 | mağaza bulucu |  |
| Mopaş | Market | 137 | 2 | 22 | mağaza bulucu |  |
| Yunus Market | Market | 92 | 7 | 18 | mağaza bulucu |  |
| Furpa | Market | 57 | 1 | 7 | mağaza bulucu |  |
| Esenlik | Market | 38 | 3 | 5 | mağaza bulucu |  |
| Seyhanlar | Market | 25 | 1 | 4 | mağaza bulucu |  |
| Groseri | Market | 24 | 2 | 6 | mağaza bulucu |  |
| Söz Market | Market | 20 | 2 | 2 | mağaza bulucu |  |
| Nurtaş Market | Market | 10 | 2 | 4 | mağaza bulucu |  |
| Bravo Süpermarket | Market | 5 | 1 | 3 | mağaza bulucu |  |
| İstikbal | Mobilya | 657 | 81 | 379 | bayi paneli |  |
| Bellona | Mobilya | 610 | 79 | 336 | bayi paneli |  |
| Mondi | Mobilya | 329 | 74 | 232 | bayi paneli |  |
| Doğtaş | Mobilya | 246 | 72 | 184 | bayi paneli |  |
| Kelebek | Mobilya | 234 | 69 | 170 | bayi paneli |  |
| Vodafone | Operatör | 5.836 | 81 | 837 | bayi bulucu | türler karışık: ödeme noktası 3.440, hizmet noktası 1.677, Cep Merkezi 756, kurumsal 18; kademelere bölünecek |
| Türk Telekom | Operatör | 892 | 81 | 279 | bayi bulucu | 871 markalı ofis ve mağaza (TTM Şube, TT Ofis, Mini Ofis); kurumsal liste aynı ortaklar |
| Opmar Optik | Optik | 69 | 24 | 48 | Ticimax ortak ucu |  |
| MACFit (spor salonu) | Spor | 171 | 18 | 67 | mağaza bulucu |  |
| Intersport | Spor | 25 | 9 | 23 | Akinon ortak ucu |  |
| Koçtaş | Yapı market | 134 | 38 | 108 | mağaza bulucu |  |
| Komagene | Yeme-içme | 3.805 | 81 | 608 | mağaza bulucu |  |
| Oses Çiğköfte | Yeme-içme | 1.629 | 80 | 416 | mağaza bulucu |  |
| Domino's Pizza | Yeme-içme | 1.092 | 78 | 310 | mağaza bulucu |  |
| Burger King | Yeme-içme | 835 | 78 | 257 | mağaza bulucu |  |
| Starbucks | Yeme-içme | 795 | 59 | 184 | mağaza bulucu |  |
| Ziyafet Çiğköfte | Yeme-içme | 459 | 57 | 170 | mağaza bulucu |  |
| McDonald's | Yeme-içme | 334 | 45 | 134 | mağaza bulucu |  |
| EspressoLab | Yeme-içme | 310 | 53 | 119 | mağaza bulucu |  |
| Köfteci Yusuf | Yeme-içme | 307 | 43 | 182 | elle kaydedilen sayfa | bot kontrolü; sayfa 308 şube / 43 il diyor |
| Simit Sarayı | Yeme-içme | 110 | 20 | 50 | mağaza bulucu |  |
| HD İskender | Yeme-içme | 95 | 22 | 57 | mağaza bulucu |  |
| Şarj istasyonları | Şarj | 16.345 | 81 | 728 | EPDK lisans kaydı | resmî ve tam liste |

## Ham veri var, bekliyor (14)

| Marka | Tür | Mağaza | İl | İlçe | Yöntem | Not |
|---|---|---|---|---|---|---|
| FLO | Giyim | 321 |  |  | elle kaydedilen sayfa | robots Claude'u engelliyor; 321 koordinatlı mağaza, sayfa 319 diyor |
| Boyner | Giyim | 132 |  |  | elle kaydedilen sayfa | ad ve adres, koordinat yok; ayrıca YKM 3, Costa Coffee 4 |
| Watsons | Kozmetik | 535 |  |  | elle kaydedilen sayfa | 79 il tam; ilçe %75, 136 mağaza elle yerleştirilecek |
| Sephora | Kozmetik | 45 |  |  | elle kaydedilen sayfa | ad ve adres var, koordinat yok |
| Yerel marketler (22 zincir) | Market | 327 |  |  | kendi siteleri | 3-44 mağazalık bölge zincirleri; Söz depoda |
| Happy Center | Market | 194 |  |  | mağaza bulucu | il yok, yalnız adres |
| Bizim Toptan | Market | 172 |  |  | mağaza bulucu | il ve ilçe etiketi var |
| Onur Market | Market | 154 |  |  | mağaza bulucu | il ve ilçe etiketi var, ilk satır bozuk |
| Turkcell dijital satış bayileri | Operatör | 3.516 |  |  | Turkcell'in PDF listesi | 23.09 sürümü 81 il; il özeti var; eski sürümde ilçe eşleşmesi %96,7 |
| Turkcell Ev Müşteri Merkezleri | Operatör | 38 |  |  | Turkcell'in PDF listesi | 25 il, yalnız Superbox |
| Toyzz Shop | Oyuncak | 263 |  |  | mağaza bulucu | yalnız serbest adres |
| Kahve Dünyası | Yeme-içme | 355 |  |  | mağaza bulucu | adresten il ve ilçe çıkarılacak |
| KFC | Yeme-içme | 43 |  |  | mağaza bulucu | yarım kaldı |
| Usta Dönerci | Yeme-içme |  |  |  | mağaza bulucu | yalnız il sayıları |

## Kısmi, tamamlanmalı (4)

| Marka | Tür | Mağaza | İl | İlçe | Yöntem | Not |
|---|---|---|---|---|---|---|
| Arçelik | Beyaz eşya | 1.000 |  |  | elle kaydedilen sayfa | sayfa 500 bayi sınırı; A-E ve S-Z var, F-R yok; il il kayıt gerek |
| Beko | Beyaz eşya | 991 |  |  | elle kaydedilen sayfa | sayfa 500 sınırı; A-G ve O-Z var, H-N yok; il il kayıt gerek |
| Turkcell mağaza sayfası | Operatör | 74 |  |  | elle kaydedilen sayfa | yalnız Adana; ad ve telefon, ilçe yok; 48'i DSN listesinde |
| Tekzen | Yapı market | 1 |  |  | Ticimax ortak ucu | uç yalnız 1 mağaza döndürdü |

## Kayıt boş, yeniden kaydet (1)

| Marka | Tür | Mağaza | İl | İlçe | Yöntem | Not |
|---|---|---|---|---|---|---|
| MediaMarkt | Elektronik |  |  |  | elle kaydedilen sayfa | liste yüklenmeden kaydedildi; arama yapıp kaydet |

## Alınamadı (22)

| Marka | Tür | Mağaza | İl | İlçe | Yöntem | Not |
|---|---|---|---|---|---|---|
| Garanti BBVA ATM | Banka |  |  |  |  | ATM listesi alınamadı |
| Altus | Beyaz eşya |  |  |  |  | yalnız adres arama haritası |
| Bosch, Siemens, Profilo | Beyaz eşya |  |  |  |  | bayi sayfaları 403 (eski not) |
| Petzz | Evcil hayvan |  |  |  |  | bağlantı kurulamadı |
| Noter | Kamu |  |  |  |  | Noterler Birliği reCAPTCHA |
| HepsiJet | Kargo |  |  |  |  | robots 403 |
| UPS | Kargo |  |  |  |  | Access Denied |
| Sendeo | Kargo |  |  |  |  | alan adı çözülmüyor |
| Trendyol Express | Kargo |  |  |  |  | şube bulucu yok |
| Pandora | Kuyum |  |  |  |  | robots 403 |
| A101 | Market |  |  |  | mağaza ucu bulundu | IP 403, robots 500; kendi açıklaması ~13.500 |
| CarrefourSA | Market |  |  |  |  | robots 403 |
| Atasun Optik | Optik |  |  |  |  | bağlantı kurulamadı |
| Avis | Oto kiralama |  |  |  |  | robots 403 |
| Budget | Oto kiralama |  |  |  |  | robots 403 |
| Garenta | Oto kiralama |  |  |  |  | ofis listesi sayfası yok |
| Petlas | Oto servis |  |  |  |  | bayi arama reCAPTCHA |
| Lassa | Oto servis |  |  |  |  | bayi sayfası 404 |
| Bosch Car Service | Oto servis |  |  |  |  | yönlendirme izlenmedi |
| Decathlon | Spor |  |  |  |  | robots 403 |
| Bauhaus | Yapı market |  |  |  |  | mağaza sayfası Cloudflare |
| Mado | Yeme-içme |  |  |  |  | 403 |

## Denenmedi (30)

| Marka | Tür | Mağaza | İl | İlçe | Yöntem | Not |
|---|---|---|---|---|---|---|
| Ebebek | Bebek |  |  |  | /magazalar |  |
| Taç | Ev |  |  |  | /magazalar |  |
| Paşabahçe | Ev |  |  |  | /magazalar/ |  |
| Özdilek | Ev |  |  |  | /tr/departman-magazalar |  |
| Penti | Giyim |  |  |  | /tr/store-finder/stores |  |
| Deichmann | Giyim |  |  |  | /tr-tr/storefinder |  |
| Kiğılı | Giyim |  |  |  | /pages/stores |  |
| Derimod | Giyim |  |  |  | /pages/magazalar | Akinon ucu sayı vermedi |
| Lescon | Giyim |  |  |  | /magazalarimiz/ |  |
| Suwen | Giyim |  |  |  | /magazalar |  |
| Jimmy Key | Giyim |  |  |  |  | mağaza sayfası bulunamadı |
| D&R | Kitap |  |  |  | /magazalar |  |
| Remzi | Kitap |  |  |  | /magazalarimiz/ |  |
| Eve Shop | Kozmetik |  |  |  |  | mağaza sayfası bulunamadı |
| Altınbaş | Kuyum |  |  |  | /magazalar |  |
| Metro Grossmarket | Market |  |  |  |  |  |
| Carrefour Express | Market |  |  |  |  | CarrefourSA robots 403 |
| Otomobil bayileri | Otomotiv |  |  |  |  | Renault, Fiat, Toyota… |
| Tchibo | Yeme-içme |  |  |  | /service/storefinder/ |  |
| Gloria Jeans | Yeme-içme |  |  |  | /store-finder |  |
| Baydöner | Yeme-içme |  |  |  | /restoranlar |  |
| Popeyes | Yeme-içme |  |  |  | /subeler | Arby's ile aynı altyapı |
| Arby's | Yeme-içme |  |  |  | /restoranlar | Popeyes ile aynı altyapı |
| Hatemoğlu | Yeme-içme |  |  |  | /magazalarimiz |  |
| Özsüt | Yeme-içme |  |  |  | /tr/magazalar |  |
| Tavuk Dünyası | Yeme-içme |  |  |  |  | robots yok (404) |
| Little Caesars | Yeme-içme |  |  |  |  | site yanıtı yarım |
| Pizza Hut | Yeme-içme |  |  |  |  | zaman aşımı |
| Caribou | Yeme-içme |  |  |  |  | robots yok (404) |
| Arabica, Coffy | Yeme-içme |  |  |  |  |  |
