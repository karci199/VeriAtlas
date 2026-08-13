# VeriAtlas — çalışma kuralları

Bu dosya, bu depoda çalışan yapay zekâ asistanı içindir. Proje kararları
[docs/kararlar.md](docs/kararlar.md)'de, kurulum [README.md](README.md)'de.

## Alt ajan kullanmak yasak

Agent / Task aracı kullanılmayacak. Arama, okuma, araştırma, kod yazma — hepsi ana
oturumda, doğrudan yapılacak. Alt ajana iş devredilmeyecek, arka planda ajan
çalıştırılmayacak.

Gerekçe: alt ajanın ne okuduğu ve neye dayanarak karar verdiği görünmüyor; dönen özet
doğrulanamıyor. Bu projede kaynağın izlenebilirliği işin kendisi.

## Kod dili

Kod, tanımlayıcı, dosya adı, docstring ve yorum İngilizce. Türkçe yalnızca kullanıcının
gördüğü etikettir ve veri modelinde ayrı alanda durur (`label_tr`), koda gömülmez.
Karar K1.

## Ortam

- `uv` winget ile kurulu; kabuk eski PATH'i taşıyorsa `.venv\Scripts\python.exe` ile
  doğrudan çalış.
- net kural: `uv run ruff check --fix`, `uv run ruff format`, `uv run pytest -q`
  değişiklikten sonra çalıştırılır.
- Node kurulu değil; web tarafı şimdilik derleme adımsız statik sayfa.

## Test

Her parçadan sonra test seti yazılmaz. Yalnızca gözle görülmeyen doğruluk sınanır:
çift anahtar reddi, tanınmayan ad, tanımsız kırılım gibi sessiz bozulma yolları.
