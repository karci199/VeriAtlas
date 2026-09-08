# Çekici kalıbı

Her uzun çekimde aynı üç hata tekrarlandı ve her seferinde yeniden keşfedildi. Kalıp
burada duruyor; yeni bir çekici yazmadan önce buraya bak, yazdıktan sonra buraya ekle.

## 1. Tek geçiş yetmez — kazanç durana kadar süpür

Uzaktaki uygulama zamanlama yüzünden hata veriyor: onay kutusu sunucuya gidip dönmeden
"Göstergeleri Ekle" tıklanıyor ve adet 0 geliyor; ZK açılır listesi dolmadan cevap
veriyor; bağlantı birkaç yüz raporda bir sıfırlanıyor (`WinError 10054`). Aynı birim
**bir sonraki geçişte iniyor**. Bu yüzden liste bir kez gezilmez.

```python
missing = None
for _ in range(rounds):          # rounds yalnız tavan
    left = sweep(...)            # yalnız eksik olanları dener
    if not left:
        return
    if missing is not None and left >= missing:
        log("gecis kazanc getirmedi, %d eksik" % left)
        return                   # ilerleme durdu, sonsuza dönme
    missing = left
```

Sabit tur sayısıyla durmak (`for _ in range(3)`) açık hâlâ kapanırken kesiyor: mv2011
tam bu yüzden 70 eksikle bitmişti. Durma ölçütü tur sayısı değil, **kazancın sıfırlanması**.

Uygulandığı yerler: `fetch_secim.py:fetch`, `fetch_medas_neighbourhoods.py:main`,
`fetch_medas_neighbourhoods_early.py:main`.

## 2. Eksik kaynak hata vermez — sonda adıyla söyle

Mahalle ölçümü 46 ilde durdu, hiçbir hata basmadı, bitmiş göründü; 35 ilin eksikliği
günler sonra dosya sayarak fark edildi. Çekim bitişinde eksik kalanlar **ada ada**
yazılmalı, sayıya bırakılmamalı. Çıktı büyüklüğünü bir öncekiyle karşılaştır: paket
49 KB'den 58 KB'ye çıktığında veri geri gelmişti, tersi de sessizce olur.

## 3. Kaynak başına tek oturum

Aynı kaynağa paralel iki çekim hepsini zaman aşımına düşürüyor: 2010 halkoylaması üç
kopyayla 75 dakikada 2 ilçe, tek oturumda 15 dakikada 225 ilçe indi. Yeni çekim
başlatmadan önce eskisinin **öldüğünü doğrula**, varsayma:

```bash
wmic process where "name='python.exe'" get commandline | grep fetch_
```

Sıradaki iş kuyruğa alınır, paralel başlatılmaz — bekleyen bir zincir betiği
(`until grep -q BITTI <log>; do sleep 120; done`) doğru araçtır.

## 4. Kuyruk betiği uydurma komut kabul eder

`fetch_medas_simple.py cocuk-nufus-ilce` diye bir ölçüm yok ve o betik zaten yalnız
ülke+il düzeyi çekiyor; `fetch_medas_marital_district.py --olcum=hemsehrilik` diye bir
seçenek yok, ölçüm sabit. Üçü de hatasız çalıştı, yanlış dosyayı indirdi, kuyruk
"bitti" dedi. Kuyruğa bir komut eklemeden önce betiğin `--help`'ini ya da ölçüm
listesini **oku**; kuyruk çalıştıktan sonra beklenen dosya adlarının indiğini doğrula.

## 5. Türkçe metin argv'den geçmez

Git-bash'ten Windows'a giden argüman cp1254'e düşüyor; `select_option(label=...)` tam
eşleşme istediği için hiçbir şey bulamıyor ve sessizce boş dönüyor. Konu/ölçüm adı
kaynağa gömülür (`scan_medas_nufus.py` kalıbı), argv'ye konmaz. Aynı aile:
`"İstanbul".upper()` ayrık noktalı I üretir, `'İ'.lower()` birleşik `i̇` verir ve
mükerrer anahtar doğurur; CRLF dosyadan okunan adın sonundaki `\r` dosya adını
geçersiz kılar — rapor iner, kaydetme olur, dizinde iz kalmaz.

## 6. Ham veri repo ağacının dışında

`C:\veri-ham`. Worktree'ye junction **kurulmaz**: 2026-09-07'de worktree temizliği
junction'ın içinden geçip ortak depoyu boşalttı, 2,8 GB gitti. Araç repoda, veri dışarıda.
