# VeriAtlas

Çok kaynaklı istatistik platformu. TÜİK, EVDS, Our World in Data, Dünya Bankası ve
diğer kaynakları tek bir kanonik veri modelinde toplayıp doğrulamak, görselleştirmek
ve raporlamak için.

**Durum: altyapı kuruldu, veri hattı henüz yazılmadı.**

Kod ve tanımlayıcılar İngilizce, kullanıcının gördüğü etiketler Türkçe
(bkz. [docs/kararlar.md](docs/kararlar.md)).

## Kurulum

```bash
cd C:\veri
uv sync
cp .env.example .env      # sonra .env icine EVDS anahtarini yapistir
uv run python scripts/check_env.py
```

`uv` kurulu değilse: `winget install astral-sh.uv`

## Yığın

| Katman | Araç |
|---|---|
| Dil | Python 3.13 (uv ile yönetiliyor) |
| Veri çerçevesi | polars (Rust) |
| Depo | DuckDB + Parquet |
| Excel okuma | python-calamine / fastexcel (Rust) |
| Doğrulama | pydantic v2 (Rust core) + pandera |
| HTTP | httpx + tenacity |
| Tarayıcı otomasyonu | playwright (MEDAS için) |
| Çıktı | XlsxWriter, typst (PDF) |
| Lint/format | ruff (Rust) |
| Arayüz (planlanan) | Observable Framework + Plot + MapLibre + DuckDB-WASM |

## Klasörler

```
src/veriatlas/    paket kodu (config.py: yollar ve ayarlar)
scripts/          tek seferlik betikler ve doğrulama araçları
docs/             oturum notları, tasarım belgeleri
raw/              ham indirilen dosyalar (git'e girmez)
public/           yayınlanan parquet dilimleri (git'e girmez)
warehouse.duckdb  kanonik depo (git'e girmez)
```

## Kaynak notları

### TCMB EVDS — EVDS3 geçişi (2026-08 itibarıyla doğrulandı)

Eski adres ve kullanım biçimi **artık çalışmıyor**. İnternetteki örnekler ve
`evds` PyPI paketi eskiye göre yazılmış, hepsi geçersiz.

| | Eski (EVDS2) | Yeni (EVDS3) |
|---|---|---|
| Taban | `evds2.tcmb.gov.tr/service/evds` | `evds3.tcmb.gov.tr/igmevdsms-dis` |
| Anahtar | `&key=...` sorgu parametresi | `key:` HTTP başlığı |

Parametreyle gönderilirse `403 Required request header 'key' is not present`.
Eski taban 404 yerine SPA'nın HTML'ini döndürür — sessiz hata, dikkat.

Çalışan uç noktalar:

```
/series={KOD}&startDate=GG-AA-YYYY&endDate=GG-AA-YYYY&type=json
/categories/type=json                     -> 154 kategori
/categories/withDatagroups/type=json
/serieList/fe/type=json&code={KOD}
```

### TÜİK MEDAS

Açık API yok. ZK (Java) tabanlı arayüz, sunucu turlarıyla çalışıyor; Playwright
gerekiyor. Bazı kırılımlar sunucu tarafında `disabled` işaretli ve hiç açılmıyor —
özellikle `FAALİYET A10 (NACE Rev.2)` (Bölgesel Hesaplar, Dönemsel Ulusal Hesaplar)
ve `NACE2` (İnşaat Üretim Endeksi). Bu yüzden sektörel GSYİH çekilemiyor.

Çalışan akış: Konu → Ölçüm → Kırılım + Tamam → Göstergeleri Ekle → İleri →
Periyot + yıllar → İleri → Düzey (İBBS3/İlçe) + iller → Rapor Oluştur.
Raporlar sayfalı gelebiliyor; tek sayfadan okumak eksik veri verir.

Not: her adım sunucu turu gerektiriyor, adımları tek seferde zincirlemek çalışmıyor.

## Sırada ne var

Yazılacak parçalar, bağımlılık sırasıyla:

1. Kanonik olgu tablosu şeması (SDMX'ten sadeleştirilmiş; vintage ve kalite bayrağı
   ilk sınıf alan)
2. Gösterge sözlüğü (konu ağacı, birim, frekans, `label_tr` / `label_en`)
3. Zamana bağlı coğrafya kaydı (6360 sayılı yasa, 2013 kırılması)
4. Adaptör sözleşmesi (fetch / parse / metadata + manifest) — ilk ikisi EVDS3 ve MEDAS
5. Kalite kuralları (pandera)

Açık tek karar: ilk tema hangisi olacak (öneri: nüfus ve doğurganlık).

## Belgeler

| Belge | İçerik |
|---|---|
| [docs/kararlar.md](docs/kararlar.md) | verilen kararlar ve açık işler |
| [docs/oturum-2026-08-13.md](docs/oturum-2026-08-13.md) | ön çalışma, bulgular, platformun çözmesi gereken 5 sorun |
