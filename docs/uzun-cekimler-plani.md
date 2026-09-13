# Uzun MEDAS çekimleri planı (2026-09-13)

İki iş günlerce sürebilir: **bitkisel üretim ilçe düzeyi** ve **ceza infaz (4 ölçü, il,
kırılım kırılım)**. Bu belge ikisinin nasıl, hangi sırayla ve kesintiye dayanıklı biçimde
çekileceğini tanımlar. Ceza infaz kullanıcı "başla" deyince başlar.

## Ne çekilecek

| İş | Kapsam | Tahmini sorgu | Tahmini süre |
|---|---|---|---|
| Bitkisel ilçe | 7 ölçü (tahıl 395, sebze 116, meyve 405, süs 44, örtüaltı sebze 216, örtüaltı meyve 46, örtüaltı süs 136 gösterge; kuru/sulu 44) × 973 ilçe × 2004-2025 | 500-600 (il grupları) | 1-1,5 gün |
| Ceza infaz | giren/çıkan × ikamet ili/suç ili, 649 gösterge × 82 alan × 1990-2020, kırılım başına | ~300 | ~1 gün |

İkisi **aynı anda çalışmaz**: MEDAS tek oturumda yavaşlıyor, iki oturum birbirini
bozuyor (bkz. çekim kuralları). Sıra: kısa işler → bitkisel ilçe → ceza infaz.

## Kesintiye dayanıklılık

1. **Oturumdan bağımsız süreç.** Sohbete bağlı arka plan işi sohbetle ölüyor (2026-09-12'de
   yaşandı). Uzun iş `scripts/uzun_cekim.py` ile Windows'ta ayrık süreç olarak başlar
   (`Start-Process -WindowStyle Hidden`), günlüğü `C:\veri-ham\medas\uzun\<iş>.log`.
2. **İş listesi dosyada.** Başlarken bütün sorgular (ölçü × yıl × il grubu) tek tek
   `C:\veri-ham\medas\uzun\<iş>-kuyruk.json` dosyasına yazılır. Her sorgunun durumu:
   `bekliyor` / `indi` / `hata (n)`. Liste koddan değil bu dosyadan okunur; süreç ölürse
   aynı komut kaldığı sorgudan devam eder.
3. **Dosya atomik yazılır.** İndirme önce `.part` adıyla iner, satır sayısı ve alan
   sütunları denetlenince asıl adına çevrilir. Yarım dosya hiçbir zaman "indi" sayılmaz.
4. **Doğrulama her dosyada.** Beklenen ilçe sütunları var mı, yıl doğru mu, gösterge
   satırı sayısı keşifteki sayıyla uyuşuyor mu. Uyuşmazsa `hata`, 3 denemeden sonra
   atlanır ve günlükte adıyla kalır, sessizce geçilmez.
5. **Oturum yenileme.** Her 25 sorguda ya da bir sorgu 5 dakikayı aşınca tarayıcı kapatılıp
   yeniden açılır (MEDAS oturumu uzadıkça yavaşlıyor).
6. **Nöbetçi.** Süreç her dakika `<iş>-nabiz.txt` dosyasına zaman ve sıradaki sorguyu
   yazar. Görevzamanlayıcı her 15 dakikada nabza bakar; 20 dakikadır değişmediyse süreci
   yeniden başlatır. Bilgisayar yeniden başlarsa oturum açılışında da devreye girer.
7. **Yeniden eskiye.** Kuyruk 2025'ten geriye sıralanır: yarıda kalsa bile en yeni yıllar
   elde olur.

## Az sorgu: il grupları

Sınır `gösterge × alan × yıl ≤ 50.000`. Tek yıl, 395 göstergeli ölçü için sorgu başına
en fazla ~126 ilçe. İller ilçe sayısına göre sırayla gruplara doldurulur (İstanbul 39,
Konya 31 … tek başına sığan). Grup listesi kuyrukla birlikte dosyaya yazılır; ilk
denemede tek sorguda birden çok ilin ilçeleri seçilebildiği doğrulanır. Seçilemiyorsa
il başına sorguya düşülür ve süre yeniden hesaplanır.

## Yükleme

- Her sabah: o ana dek inen yıllar adaptörle depoya alınır (`crops_district_*`),
  il toplamı = MEDAS il değeri denetimi, `export_web`, commit + push.
- Tamamlanmayı beklemeden kısmi yıllar yüklenir; eksik yıllar gezginde görünmez, sahte
  sıfır yazılmaz.

## Kullanıcıdan gereken

- Bilgisayar uyku moduna geçmemeli (güç ayarı; sistem ayarı olduğu için asistan
  değiştirmez).
- Ceza infaz için "başla" onayı.

## Adımlar

1. Deneme: 2025, sebzeler (116), bir il grubu — çoklu il seçimi ve süre ölçümü.
2. `scripts/uzun_cekim.py`: kuyruk, atomik yazma, doğrulama, oturum yenileme, nabız.
3. Görev zamanlayıcı nöbetçisi (kullanıcı onayıyla kurulur).
4. Bitkisel ilçe başlar; her sabah yükleme.
5. Bitince ceza infaz, aynı düzenekle.
