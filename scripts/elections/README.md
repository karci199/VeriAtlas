# TÜİK milletvekili genel seçimi analizleri

TÜİK'in `biruni.tuik.gov.tr/secimdagitimapp` uygulamasından çekilen seçim
verisini ayrıştıran ve analiz eden betikler.

## Veri nerede

Ham raporlar ve üretilen CSV'ler **depoda değil** (`raw/` gitignore'da):

| Klasör | İçerik |
|---|---|
| `raw/tuik_secim_ilce/` | "Seçim çevresi ve ilçelere göre" — tüm Türkiye, 17 seçim (1961–2023), **ilçe** kırılımı. 1.342 HTML, `secim_ilce.csv` (651 bin satır) |
| `raw/tuik_secim/` | "Seçim çevresi ve bölgelerine göre" — Bursa + Ankara, 10 seçim (1991–2023), **mahalle/köy** kırılımı. 415 HTML, `secim_mahalle.csv` (565 bin satır) |

Betikler kendi klasörlerinden çalışacak şekilde yazıldı; birbirlerini dosya
adıyla import ediyorlar. Çalıştırmak için ilgili `raw/` klasörüne kopyala ya da
oradan çalıştır.

## Betikler

**`district/`** — ilçe düzeyi veri

| Betik | Ne yapar |
|---|---|
| `dl.py` | Manifestteki rapor URL'lerini indirir |
| `parse.py` | HTML → `secim_ilce.csv`; yıl **ve il** doğrulaması yapar |
| `blok.py` | Sol/sağ blok payları (sınıflandırma burada, tek yerde) |
| `degisim.py` | 1977→2018 blok kayması, il ve ilçe |
| `egilim.py` | Ülke ortalamasına göre göreli eğilim, dönem ortalamaları |
| `ortalama.py` | Türkiye'ye en benzeyen il/ilçe (parti vektörü uzaklığı) |
| `rekabet.py` | Her zaman rekabetçi yerler (1.–2. parti farkı) |
| `enp.py` | Etkin parti sayısı (Laakso-Taagepera) |
| `secmen.py` | Kayıtlı seçmen / geçerli oy toplamları, sandalye başına oy |
| `kayip.py` | Kayıtlı seçmenin geçerli oya dönüşmeyen kısmı |
| `degisim1523.py`, `akp_transfer.py`, `mhp_iyi.py`, `mhp_iyi_oran.py` | 2015-Kas → 2023 parti geçişleri |
| `goc.py` | Göç ↔ sol kayması ilişkisi |
| `kazanan_nufus.py` | Kazanan partinin oyu / geçerli oy / kayıtlı seçmen / nüfus |
| `ilce_profil.py` | Tek ilçe profili: `python ilce_profil.py <ilçe> <il>` |

**`neighbourhood/`** — mahalle/köy düzeyi veri (Bursa + Ankara)

`dl.py`, `parse.py`, `iznik.py`, `iznik_partiler.py`, `kalecik.py`.

## Bilinen borç

Bu betiklerin dosya adları, fonksiyon adları ve değişkenleri **Türkçe** — CLAUDE.md
K1 kuralına (kod İngilizce, Türkçe yalnızca `label_tr`) aykırı. Keşif sırasında
hızlı yazıldılar; depoya alınmalarının sebebi kaybolmamaları. İngilizceye
çevrilmeleri gerekiyor; import'lar dosya adıyla bağlı olduğu için birlikte
yapılmalı.

## Veri notları

- Blok sınıflandırması yorum içerir ve `blok.py` içinde tek kümede durur.
- 2007 ve 2011'de Kürt siyaseti bağımsız adaylarla girdi (BĞMZ), blok
  hesaplarında sahte salınım üretir; ilgili analizlerde bu iki seçim dışlanır.
- CHP 2023'te yedi ilde liste çıkarmadı (Aksaray, Bayburt, Bitlis, Çankırı,
  Gümüşhane, Muş, Yozgat); İYİ Parti dokuz ilde. Sıfırlar tercih değil.
- 1989 sonrası kurulan 14 il, uzun dönem karşılaştırmalarda çıktıkları ile
  geri katlanır.
