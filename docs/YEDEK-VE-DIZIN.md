# VeriAtlas — yedek, dizin ve devam rehberi

2026-09-17 itibarıyla. Bu dosya HDD yedeği alınırken ve yeni bir bilgisayarda / yeni oturumda
işe dönerken okunacak tek giriş noktası. Ayrıntılar bağlantı verilen belgelerde.

---

## 1. Neyi yedeklemelisin (önem sırasıyla)

Git **her şeyi tutmuyor**. Aşağıdaki üç yerin üçü de ayrı ayrı kopyalanmalı.

| # | Ne | Nerede | Git'te mi? | Kaybolursa |
|---|---|---|---|---|
| 1 | **Ham veri deposu** — indirilen Excel, PDF, JSON, MEDAS CSV'leri | `C:\veri-ham\` | **Hayır** | Yeniden indirmek günler sürer; bazı kaynaklar (eski TİM/KTB dosyaları, MEDAS oturumları) bir daha aynı biçimde gelmeyebilir. **En değerli yedek bu.** |
| 2 | **Kod + belgeler + web** | GitHub `karci199/VeriAtlas` (`main` dalı), yerel `C:\veri\` | Evet | GitHub'dan geri gelir, yine de klasörü kopyala |
| 3 | **İşlenmiş depo** — `public/fact.parquet` (19,6 mn satır) ve `warehouse.duckdb` | en güncel hali: `C:\veri\.claude\worktrees\veri-cekme-secimler-durum-4771a4\public\` ve aynı klasördeki `warehouse.duckdb` | **Hayır** (`fact.parquet`, `warehouse.duckdb` git dışı) | Ham veriden `scripts/load.py` ile yeniden kurulur (saatler) |
| 4 | **Gizli anahtar** — EVDS API anahtarı | `C:\veri\.env` | **Hayır** (bilerek) | TCMB EVDS'den yeni anahtar alınır. **Yedeği şifreli ya da ayrı tut, paylaşma.** |
| 5 | Web'e aktarılmış dosyalar (`public/*.csv.gz`, `meta.json`) | worktree `public/` | Evet | `scripts/export_web.py` yeniden üretir |

Dikkat:

- **En güncel çalışma kopyası `C:\veri\` değil**, worktree:
  `C:\veri\.claude\worktrees\veri-cekme-secimler-durum-4771a4\`. `C:\veri\public\fact.parquet` ve
  `C:\veri\warehouse.duckdb` daha eski. Yedekte worktree'dekini al.
- `.venv\` klasörlerini yedekleme (1-2 GB, `uv sync` ile yeniden kurulur).
- `C:\veri-ham\` içindeki `*.log`, `*.sh`, `probe_*` dosyaları çekim kayıtlarıdır; yer kaplamaz,
  onlar da gitsin (hata ayıklamada işe yarıyor).
- Diğer worktree'ler (`C:\veri\.claude\worktrees\*`) eski dallar; kodları `main`'de. İçlerindeki
  `public/fact.parquet` kopyaları eskidir.

## 2. Yeni makinede geri kurma

```bash
git clone https://github.com/karci199/VeriAtlas.git C:\veri
cd C:\veri
winget install astral-sh.uv        # uv yoksa
uv sync                            # Python 3.13 + bağımlılıklar
uv run playwright install chromium # MEDAS / tarayıcı çekicileri için
# .env dosyasını yedekten geri koy (EVDS anahtarı)
# C:\veri-ham\ klasörünü yedekten geri koy (yol aynı kalmalı; farklıysa VERIATLAS_RAW ortam değişkeni)
# public\fact.parquet ve warehouse.duckdb'yi yedekten koy — ya da:
uv run python scripts/load.py      # tüm adaptörler, ham veriden depoyu yeniden kurar (uzun)
uv run python scripts/export_web.py
uv run python scripts/serve.py 8123   # web arayüzü: http://localhost:8123
uv run pytest -q
```

Ham veri yolu `src/veriatlas/config.py` → `RAW`: önce `VERIATLAS_RAW` / `VERIATLAS_HAM`
ortam değişkeni, yoksa repo içi `raw\`, o da yoksa `C:\veri-ham`.

## 3. Dizin — neresi ne

### Repo (`C:\veri\` / worktree)

| Yol | İçerik |
|---|---|
| `src/veriatlas/adapters/` | Kaynak başına okuyucu (65 modül). Her biri ham dosyayı olgu tablosuna çevirir ve kendi denetimlerini yapar. Modül başındaki açıklama kaynağı, tuzakları ve denetimleri anlatır. |
| `src/veriatlas/data/indicators.toml` | Gösterge sözlüğü: her göstergenin Türkçe adı, birimi, kırılımları, tanımı ve kaynak notu. Yeni gösterge önce buraya yazılır. |
| `src/veriatlas/data/areas_tr*.csv`, `nuts_tr.csv` | Alan kayıtları: il, ilçe, mahalle, köy, İBBS kodları |
| `src/veriatlas/schema.py` | Olgu tablosu şeması, kalite bayrakları, alan düzeyleri |
| `scripts/fetch_*.py` | İndiriciler (153 betik). Kaynak başına bir tane. |
| `scripts/load.py` | Adaptörleri çalıştırıp `public/fact.parquet` + `warehouse.duckdb` yazar. Ad verilirse yalnız o göstergeleri değiştirir, diğerlerini korur. |
| `scripts/export_web.py` | Web için gzip CSV'ler ve `meta.json` üretir. Hangi göstergenin web'e çıkacağı `DATASETS` önek listesinde. |
| `web/` | Statik arayüz: `explorer.html` (veri gezgini), `district.html` (ilçe dosyası), `atlas.html`, `secim.html`, `durum.html` |
| `tests/` | Gizli doğruluk testleri (çift anahtar, tanınmayan ad vb.) |
| `docs/` | Kararlar, kaynak notları, oturum notları (aşağıda) |

### Ham veri (`C:\veri-ham\`)

Kaynak başına klasör: `afad btk dhmi diyanet endeksa epdk etkb eurostat evds gsb iskur kgm ktb
medas mgm ptt saglik secim sege sgk tbb tim tkgm tobb tuik tuik_medas tuik_portal tuik_secim
worldbank yok_istatistik yokatlas ysk`. `medas\basit\` MEDAS'tan çekilen tüm CSV'ler,
`medas\kesif\` konu taramaları.

### Belgeler (`docs/`)

| Belge | Ne için |
|---|---|
| [acik-isler.md](acik-isler.md) | **Yapılacaklar**: yarım kalan çekimler, keşfedilip başlanmayanlar, bekleyen kararlar |
| [kaynak-envanteri.md](kaynak-envanteri.md) | Bakılan tüm kaynaklar, zorluk, neden alındı / alınmadı |
| [kararlar.md](kararlar.md) | Tasarım kararları (K1, K4, K8, K11, K14, K15, K30 …) |
| [yol-haritasi.md](yol-haritasi.md) | Uzun vadeli sıra, ekran eksikleri |
| [cekiciler.md](cekiciler.md) | Çekici yazma kalıbı |
| [medas.md](medas.md) | MEDAS'ı tarayıcıyla sürme yöntemi ve tuzakları |
| Kaynak notları | `btk.md dhmi.md diyanet.md epdk.md epdk-aylik.md etkb.md kgm.md mgm.md saglik.md sege.md sgk.md yok.md endeksa.md semt.md` |
| Oturum notları | `oturum-2026-*.md` — o günün devam noktası |
| Vaka analizleri | `vaka-iznik.md vaka-enerji.md vaka-secim-disari.md`, `analiz/`, `analizler/` |

## 4. Depoda ne var (2026-09-17)

19.633.161 satır, 828 gösterge, 24 kaynak.

| Kaynak (`source_id`) | Gösterge | Satır | Yıllar | Düzey |
|---|---|---|---|---|
| TÜİK MEDAS (`tuik_medas`) | 275 | 13,5 mn | 1967-2025 | mahalle, köy, ilçe, il, İBBS-2, Türkiye |
| TCMB EVDS (`cbrt_evds`) | 267 | 2,9 mn | 1970-2026 | Türkiye, il, İBBS |
| SGK | 50 | 1,1 mn | 2002-2025 | il |
| KGM (karayolu) | 15 | 1,1 mn | 1967-2026 | ilçe, il |
| YÖK İstatistik | 18 | 342 bin | 1980-2025 | ilçe, il |
| EPDK | 12 | 188 bin | 2006-2025 | il |
| Eurostat bölgesel | 9 | 104 bin | 1990-2025 | İBBS-2 |
| DHMİ | 3 | 90 bin | 2008-2026 | il (havalimanı) |
| Kültür Turizm (KTB) | 4 | 54 bin | 2003-2022 | ilçe, il |
| AFAD deprem | 1 | 54 bin | 1990-2025 | ilçe, il |
| TBB bankacılık | 7 | 50 bin | 1988-2025 | il |
| Sağlık Bakanlığı yıllığı | 20 | 29 bin | 2012-2024 | il |
| BTK | 91 | 25 bin | 2005-2026 | il, Türkiye |
| İŞKUR | 6 | 22 bin | 2003-2025 | il |
| TOBB | 5 | 20 bin | 2009-2025 | il |
| MGM iklim | 8 | 14 bin | 1929-2025 | il |
| TÜİK (diğer), Veri Portalı | 9 | 16 bin | 2012-2025 | il, Türkiye |
| SEGE | 6 | 6 bin | 2017-2022 | ilçe, il |
| ETKB | 2 | 3 bin | 2003-2025 | il |
| Diyanet | 13 | 3 bin | 2013-2023 | il |
| TİM ihracat | 1 | 2 bin | 2004-2025 | il |
| GSB spor | 4 | 2 bin | 2022-2025 | il |
| YÖK Atlas | 2 | 374 | 2026 | il |

Güncel sayıyı her zaman şununla al:
`uv run python -c "import duckdb; print(duckdb.sql(\"select source_id,count(distinct indicator_id),count(*) from 'public/fact.parquet' group by 1 order by 3 desc\"))"`

## 5. Yapılacaklar (özet — tam liste [acik-isler.md](acik-isler.md))

Seri içindeki boşluklar, kolaydan zora:

1. ~~EPDK doğalgaz il tüketimi~~ 2025 eklendi; 2015-2016 zaten vardı; 2014 yalnız il toplamı
2. ~~EPDK akaryakıt 2012-2014~~ bayiye teslim (ton) olarak eklendi; 2010-2011 Tablo 3.18 kaldı
3. Kültür Turizm 2007-2008 (yalnız PDF)
4. Sağlık yıllığı 2010 (sayfa açılmadı)
5. Kültür Turizm Bakanlık belgeli 1996-2002, 2004-2010, 2014-2015; belediye belgeli 2000-2014

Yeni ama orta zorlukta:

- TİM il × sektör ve il × ülke ihracatı (dosyalar inik, ad sözlüğü gerekiyor)
- BDDK FinTürk il kredi/mevduat (çeyreklik)
- Tarayıcıyla bakılacaklar: Sanayi teşvik belgeleri, Muhasebat il bütçesi, TÜRKPATENT
- 242 yaş grubu değerinin sözlükte Türkçe etiketi yok (sayfada ham kodla görünüyor)

Kapanmaz (kaynakta yok): BTK 2018-Q2/Q4, YÖK 2025-26 uyruk, Sağlık 2011 il tablosu.

## 6. Dikkat edilecekler (sessizce bozan yollar)

Bu projede hataların çoğu **uyarı vermeden yanlış sayı** üretir. Her yeni çekimde:

- **Toplam denetimi şart.** Her adaptör, illerin toplamını kaynağın basılı Türkiye / GENEL TOPLAM
  satırıyla karşılaştırır; tutmazsa yükleme durur. Denetimsiz adaptör yazma.
- **Sayı biçimi tuzakları**: ondalıklı basılmış sayım (İŞKUR 2006), -9,98E8 gizli hücre (MEDAS),
  bin dolar / dolar geçişi (TİM 2010), kaydırılmış rakam kodları (Sağlık 2017 PDF). Reddedilen bir
  hücre satırı sessizce düşürür.
- **Ad tuzakları**: eski il/ilçe adları (URFA, K.MARAŞ), bölünmüş satırlar ("Kahraman-" / "-maraş"),
  bozuk glif (U+FFFE), "Merkez" ilçesi. Tanınmayan ad yüklemeyi durdurmalı, atlanmamalı.
- **Kısmi yükleme**: `scripts/load.py <gösterge>` yalnız o göstergeyi değiştirir. Ama web'e
  aktarmadan önce depo tam olmalı. Aktarımdan sonra `git status public/` ile bak: yalnız zaman
  damgası değişen `.gz` dosyalarını commit'leme.
- **Windows dosya kilidi**: sunucu (`serve.py`) açıkken `public/` dosyaları kilitlenir; export ve
  `git checkout` "Invalid argument" verir. Önce sunucuyu kapat.
- **Ham veri repo dışında**: `C:\veri-ham`. Worktree içine ham veri yazma (2026-09-07'de kayıp oldu).
- **Tek MEDAS oturumu**: MEDAS çekimlerini aynı anda birden fazla çalıştırma; oturum yavaşlar,
  düzey kutusu daralır, "Ekle" görünmez olur. Ayrıntı `docs/medas.md`.
- **Aylık seriler web'e çıkmaz**: sayfa yıl başına tek değer çizer; aylık ya da karışık sıklıklı
  göstergeler `export_web.py`'de dışarıda tutulur.
- **robots.txt**: MEB, İBB açık veri yapay zekâ ajanlarını engelliyor; çekilmez.
- **Seri kırılmaları**: İŞKUR 2025'te "kayıtlı iş arayan" kavramına geçti; Eurostat 2014/2021 anket
  yenilemesi; TÜİK 2013 büyükşehir düzenlemesi (ilçe serileri). Gösterge tanımlarına yazıldı.

## 7. Günlük çalışma komutları

```bash
uv run ruff check --fix && uv run ruff format   # kod değişikliğinden sonra
uv run pytest -q
uv run python scripts/load.py <gösterge_id> ...   # yalnız bu göstergeler
uv run python scripts/export_web.py               # web dosyaları (4-5 dk)
git push origin HEAD:main                         # main ileri sarma (dal main'in önündeyse)
```
