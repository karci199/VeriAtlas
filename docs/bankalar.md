# Banka şube ve ATM ağı (2026-09-20)

Ham veri repo dışında: `C:\veri-ham\bankalar\`. Her dosya tek bir kurumun anlık
görüntüsü; `cekim` alanı tarihi, `kaynak` alanı uç noktayı taşır.

Kapsam ölçütü BDDK'nın kendi listesidir (`bddk_banka_listesi.json`, 68 banka:
36 mevduat, 21 kalkınma/yatırım, 10 katılım, 1 TMSF) ve tasarruf finansman için
`bddk_tasarruf_finansman.json` (9 şirket). Elle tutulan marka listesi yapılmaz.

## Çekilenler

| Kurum | Şube | ATM | Dosya | Kırılım |
|---|---:|---:|---|---|
| Ziraat | 1.735 | 7.858 | `ziraat_sube.json`, `ziraat_atm.json` | il+ilçe kodu, koordinat |
| VakıfBank | 1.225 | 4.129 | `vakifbank_sube_atm.json` | il+ilçe kodu, koordinat |
| Halkbank | 1.119 | — | `halkbank_sube.json` | il+ilçe **adı**, koordinat |
| İş Bankası | 988 | 5.245 | `isbank_sube_atm.json` | il, adres, koordinat |
| DenizBank | 850 | 3.022 | `denizbank_sube_atm.json` | adres, koordinat |
| Yapı Kredi | 718 | 4.978 | `yapikredi_sube_atm.json` | il+ilçe kodu, koordinat |
| Türkiye Finans | 658 | 429 | `turkiyefinans_sube_atm.json` | adres, koordinat |
| Akbank | 589 | 4.843 | `akbank_sube_atm.json` | il+ilçe kodu, **mahalle**, koordinat |
| Kuveyt Türk | 460 | 1.294 (+151 AIO) | `kuveytturk_sube_atm.json` | il+ilçe adı, koordinat |
| Vakıf Katılım | 422 | (şubeyle birlikte) | `vakifkatilim_sube_atm.json` | il+ilçe adı, koordinat |
| TEB | 421 | 1.428 | `teb_sube_atm.json` | adres metni, koordinat |
| Şekerbank | 238 | 269 | `sekerbank_sube_atm.json` | kendi il/ilçe kodu, koordinat |
| Ziraat Katılım | 235 | — | `ziraatkatilim_sube.json` | adres, koordinat |
| Albaraka | 224 | 237 | `albaraka_sube_atm.json` | il+ilçe adı, koordinat |
| Fibabanka | 74 (şube+ATM) | — | `fibabanka_sube_atm.json` | adres, koordinat |
| QNB | — | 3.624 | `qnb_atm.json` | adres, koordinat |

Toplam: **9.956 şube, 37.507 ATM**.

### Tasarruf finansman ("evim" sistemleri)

| Şirket | Şube | Dosya |
|---|---:|---|
| Fuzul | 270 | `fuzul_sube.json` |
| Eminevim | 193 | `eminevim_sube.json` (koordinatlı) |
| Katılımevim | 102 | `katilimevim_sube.json` |
| Birevim | 75 | `birevim_sube.json` |
| İyi Finans (Adil) | 60 kayıt | `iyifinans_sube.json` (ad ve adres ayrı kayıt, ayıklanmalı) |

## Çekim yöntemleri

Üç kalıp çıktı:

1. **Tek istekte tüm liste** — Türkiye Finans (`FrontEndService.svc/GetAllBranchAndATMLocationsCorporate`),
   DenizBank (`/api/branch-atm`), VakıfBank (`vakifbankBranchList`), Şekerbank
   (`/api/branchatm/list` POST `{}`), Fibabanka (OData `/api/branches/branches`),
   TEB (`servisAjx.aspx`, HTML), Ziraat (`GetAllSubeText`).
2. **İl (veya il × ilçe) döngüsü** — İş Bankası (`doSearchByCityProvince`, 81 istek),
   Akbank (`SearchBranchAtm`, 1.039 ilçe), Yapı Kredi (`FetchBranchByFilter`, sayfalı),
   Halkbank (`searchbranch`, 81 istek), Kuveyt Türk (`ApiEndpoints.branches&p5=il`),
   Albaraka (`filterBranchAndAtm`).
3. **Sayfaya gömülü liste** — Ziraat Katılım (Drupal `geolocation-location` öğeleri),
   Katılımevim, Fuzul, Eminevim, Birevim.

### Sessizce bozan yollar

- **Ziraat'in ATM listesi ilk istekte boş döner.** `GetAllAtmText` sayfada "ATM"
  seçeneği tıklanmadan 200 + boş gövde veriyor. Boş cevabı "ATM yok" saymak
  7.925 ATM'yi kaybettirirdi (`hata-veri-degildir`).
- **Düz istek (curl) çoğu bankada çalışmıyor.** İş Bankası'nda F5/TSPD, Ziraat'te
  boş gövde, Teknosa'daki gibi Cloudflare. Çekim tarayıcı içinden yapıldı; veri
  Blob indirme yoluyla diske alındı (sayfa CSP'si localhost'a POST'u da engelliyor).
- **Birevim'in listesi yalnız dar ekranda çiziliyor.** Masaüstü genişliğinde "şube
  bulunamadı" diyor; `resize_window mobile` sonrası 75 şube geldi. Sayfanın
  gömülü Qwik durumunda yalnız 8 kayıt var, DOM'dan okumak gerekiyor.
- **QNB hız sınırı serttir.** 0,22 saniyelik döngü birkaç istekte `500-QPG97`
  ile kapandı ve kapanma kalıcı oldu; ATM listesi (tek istek) alındı, şubeler
  alınamadı.
- **Akbank'ın gövde şekli kılı kırk yarıyor.** `city` sayı olmalı, `branchType`
  boş dizge (null değil), `districtName` gönderilmeli. Yanlış tipte 400 dönüyor,
  gövdesi boş — mesaj yok.
- **Türkiye Finans'ın 658 "branch" kaydı şüpheli yüksek** (bankanın kendi
  açıklaması ~300 şube). Adaptör yazılırken `ChannelName` ayrıştırılmalı.
- **Şekerbank'ın `cityid` alanı ilk kayıtta adresle uyuşmuyor** (İstanbul adresi,
  cityid 35). Kendi kodlaması doğrulanmadan il ataması yapılmamalı.

## Alınamayanlar

| Kurum | Durum |
|---|---|
| **Garanti BBVA** | Şube bulucu ayrı bir uygulama (`webforms.garantibbva.com.tr/public-atm-branch-app`), veriyi `customers.garantibbva.com.tr/digital-public/public-atm-branch-ch/v0/{branches,atms}` adreslerinden alıyor. Uygulamanın kendi isteği 200 dönüyor, aynı sayfadan elle yapılan fetch/XHR (hem ayrık hem ana dünyada) "Failed to fetch" veriyor; sunucu tarafında 500. Başlık tahmin edilmedi (`cekim-kurallari`). Ayrı oturum işi |
| **ING** | `ListBranchAndATM` uç noktası bulundu ama `CityTitle=-1` ile boş dizi dönüyor; il+ilçe birlikte gerekiyor, ilçe listesi ayrı çağrıda |
| **QNB şubeleri** | yukarıdaki hız sınırı |
| Emlak Katılım, İmece, Sinpaş, Albayrak | henüz bakılmadı (İmece 429, Sinpaş 403) |
| Halkbank ATM | `SearchType=2` boş dönüyor; ATM araması ayrı bir gövde istiyor |
| Ziraat Katılım ATM | sayfadaki ATM sekmesi aynı şube listesini veriyor |

## Neden depoda değil (henüz)

Bu dosyalar ham anlık görüntü. Warehouse'a girmesi için her kurumun adaptörü ve
nokta→mahalle düşürmesi gerekiyor; zincir mağazalarda kullanılan kalıbın aynısı
(`docs/zincir-magazalar.md`). Şube sayısının ilçe düzeyinde göstergeye dönmesi
bu adımdan sonra.
