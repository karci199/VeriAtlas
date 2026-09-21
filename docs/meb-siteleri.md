# MEB siteleri — okul ve ilçe verisi neden çekilmiyor

Durum: **askıda** (2026-09-13). Karar kullanıcıyla verildi: "şimdilik kalsın".

## Ne istendi

Okul ve ilçe milli eğitim müdürlüğü sitelerinden okul bazında derslik, öğretmen, öğrenci ve
branş sayılarını toplamak. İznik pilotunda ([vaka-iznik.md](vaka-iznik.md)) 32 okul sitesi
açılmış, 4 sayfa kalıbı ve `/tema/teskilat.php` branş dökümü çözülmüştü.

## Neden durdu

2026-09-12'de `robots.txt` kontrol edildi. Bakılan beş sitenin hepsinde aynı kural var:

| Site | Kural |
|---|---|
| www.meb.gov.tr | `ClaudeBot`, `anthropic-ai`, `Claude-Web` → `Disallow: /` |
| sgb.meb.gov.tr | aynı |
| bursa.meb.gov.tr | aynı |
| iznik.meb.gov.tr | aynı |
| iznikanadolulisesi.meb.k12.tr | aynı |

`GPTBot`, `CCBot`, `PerplexityBot` ve kullanıcı adına gezen `ChatGPT-User` da engelli. MEB,
yapay zekâ ajanlarının sitelerine girmesini açıkça istemiyor. Yapay zekâ asistanı bu sitelerden
sayfa açmaz, çekici yazmaz. İznik pilotu bu kontrolden önce yapılmıştı; toplanan toplu sayılar
(isim yok) vaka belgesinde kalır, MEB sitelerinden genişletilmez.

Hukuki not (görüş değil): `robots.txt` kanun değil; sayılar kamuya açık ve kişisel değil.
Öğretmen adları kişisel veridir — teşkilat şemasından isim toplanmaz (KVKK).

## Açık kalan yollar

| Yol | Not |
|---|---|
| CİMER / bilgi edinme başvurusu | Okul veya ilçe bazında derslik, öğretmen, öğrenci tablosu, Excel olarak |
| Kullanıcının kendi kaydettiği sayfalar | Tarayıcıda "Farklı kaydet" → `C:\veri-ham\meb_elle\`; ayrıştırma asistanda |
| Kullanıcının indirdiği SGB istatistik kitapları | Bazı tablolar ilçe kırılımlı olabilir |
| MEDAS (TÜİK) örgün eğitim | İl düzeyi: okullaşma, okul, öğrenci, öğretmen, derslik; engel yok |

## Zaten elde olan eğitim verisi

| Veri | Düzey | Yıl |
|---|---|---|
| Bitirilen eğitim düzeyi (MEDAS) | İlçe | 2008–2025 |
| Okuma-yazma durumu (MEDAS) | İlçe | 2008–2025 |
| MEB örgün eğitim Excel'leri (`raw/meb_orgun`) | İl | 2015–2025 |
| KYK yurt kapasitesi | İl, ilçe | — |
