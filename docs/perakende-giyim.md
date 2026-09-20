# Giyim, ayakkabı ve yeme-içme zincirleri (2026-09-21)

Ham veri `C:\veri-ham\perakende\`. Mağaza zincirlerinin genel kalıbı ve robots
kuralı [docs/zincir-magazalar.md](zincir-magazalar.md)'de; burada yalnız bu turda
eklenenler ve markaya özgü tuzaklar var.

## Çekilenler

| Marka | Kayıt | Uç nokta / yöntem | Kırılım |
|---|---:|---|---|
| LC Waikiki | 519 | `corporate.lcwaikiki.com` → `ClientSiteWebService.asmx/GetStoresByTown`, gövde `{CountryID:'48'}` | il + ilçe + koordinat |
| Mavi | 398 | `p1-api.mavi.com/maviwebservices/v2/mavi/stores?pageSize=2000` | adres + koordinat |
| Kahve Dünyası | 355 | sayfaya gömülü kartlar (`stores_card`) | adres |
| DeFacto | 322 | `/magazalar` sayfasına gömülü JSON + `StoreCities` açılır kutusu | il + koordinat |
| Toyzz Shop | 263 | sayfaya gömülü kartlar | adres |
| Koton | 243 (TR) | `/stores/?format=json` (391 kaydın 243'ü Türkiye) | il + ilçe + koordinat |
| Sarar | 119 | sayfada maps bağlantısı | koordinat |
| HD İskender | 96 | `/restoranlarimiz`, `data-lat`/`data-name` | koordinat |
| Zara | 39 | `/tr/tr/stores-locator/extended/search`, 15 merkezden `radius=500` süpürme | şehir + koordinat |
| Skechers | 33 | `/magazalar`, `<li data-latitude>` | koordinat |

## Markaya özgü tuzaklar

- **robots'u tarayıcı kullanıcı ajanıyla çek.** Python'ın `robotparser`'ı robots.txt'i
  kendi ajanıyla ister; Toyzz Shop, Baydöner ve FLO bu isteğe **403** dönüyor ve
  ayrıştırıcı cevabı okuyamadığı için **her yolu yasaklı** sayıyor. Üçünden ikisi
  (Toyzz, Baydöner) aslında açık. Yanlış "kapalı" kararı, `hata-veri-degildir`
  kuralının robots'taki karşılığı.
- **FLO gerçekten kapalı**: robots'ta `User-agent: ClaudeBot` … `Disallow: /`
  (157-187. satırlar, büyük bir bot bloğunun içinde). Denenmeyecek.
- **LC Waikiki'nin mağaza listesi kurumsal sitede.** `lcw.com/magazalar` →
  `corporate.lcwaikiki.com/magazalar`. `lcw.com` robots'u yalnız `/magaza/`
  (tekil mağaza sayfaları) kapatıyor, liste değil. Ülke kodu Türkiye = **48**
  (sıralama alfabetik değil; '1' Cezayir'i veriyor).
- **Mavi'nin uç noktası ayrı alan adında**: sayfa `mavi.com/maviwebservices/...`
  diye görünüyor ama gerçek adres `p1-api.mavi.com`. Sayfadaki göreli yolu
  denemek 404 veriyor; performans kaydından tam adres alınmalı.
- **Koton'un mağaza sayfası** `/magazalar` değil `/address/stores/`; liste
  `/stores/?format=json` ile geliyor ve **dünya geneli**. Türkiye süzgeci
  `township.city.country.name` üzerinden.
- **Zara yarıçap sorgusu istiyor.** `radius` en çok 500; 2000 doğrulama hatası
  veriyor. 15 merkezden süpürüp kimliğe göre tekilleştirdim: 39 mağaza, 9 şehir.
- **DeFacto'nun il alanı GUID.** `CityId` bir kimlik; ad karşılığı sayfadaki
  `StoreCities` açılır kutusunda. Eşleştirme yapılmadan il sayılamaz.

## Alınamayanlar (bu tur)

| Marka | Durum |
|---|---|
| **FLO** | robots'ta ClaudeBot'a kapalı |
| **H&M** | mağaza bulucu ayrı bir bileşen, sayfa yüklenirken hiçbir mağaza isteği çıkmıyor; harita etkileşimi gerekiyor |
| Greyder, Ceyo | mağaza sayfası bulunamadı (tahmin edilen yolların hepsi 404) |
| Baydöner | robots açık ama ana sayfa bağlantı vermiyor; şube sayfası JS ile geliyor |
| Usta Dönerci, Dönerci Şahin Usta, Pizza Lazza, Terra Pizza | alan adları yanıt vermiyor (DNS/URLError) — doğru alan adları aranacak |
| Tavuk Dünyası, Little Caesars, Pizza Hut | bakılacak |

Domino's zaten depoda (`docs/zincir-magazalar.md`, 311 şube, yarım).
