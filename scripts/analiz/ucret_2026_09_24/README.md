# Ücret, istihdam ve fiyat analizleri (2026-09-24)

Oturumda üretilen tek seferlik analiz betikleri. Girdiler `C:/veri/warehouse.duckdb` ve
`C:/veri-ham/ucret/...`; çıktılar (PNG, CSV) `C:/veri-ham/analiz/2026-09-24/`. Grafikler için
matplotlib gerekir (proje ortamında yok): `uv run --no-project --with matplotlib --with duckdb python <betik>`.

| Betik | Ne |
|---|---|
| `noter_analiz.py`, `noter_kor.py`, `noter_ilce.py` | Noter sayısı il/ilçe, nüfus ve diğer göstergelerle korelasyon (ilki çıktı klasörünü argüman alır) |
| `sirket_il.py`, `sirket_il2.py` | TOBB kurulan/tasfiye/kapanan şirket, il il oranlar, deprem bölgesi |
| `asgari_usd_png.py`, `asgari_usd_6ay*.py` | Net asgari ücret, dolar ve ABD TÜFE ile reel, aylık ve 6 aylık |
| `alim_gucu.py`, `alim_gucu_png.py` | Asgari ücretle alınan ürün miktarı 2003–2026 (2022 sonrası TÜFE alt endeksiyle tahmin) |
| `reel_analizler.py`, `reel_png.py` | Konut m², mevduat, vergi, şirket sermayesi, il GSYH reel |
| `sgk_ucret.py`, `sgk_4abc.py`, `istihdam_oran.py` | SGK kazanç, 4/a-4/b-4/c, kayıtlı istihdamın 18–60 nüfusa oranı |
| `ufe_tufe.py` | ÜFE–TÜFE makası 1996–2026 |
| `memur_analiz.py` | Unvan bazında memur maaşı, reel ve asgari ücret katı |
