# Örnek arşivi

Her cevaplanan soru buraya bir dosya olarak kaydedilir: `NNN-kisa-ad.md`.
Yeni bir soru gelince beceri önce buraya bakar — benzer soru daha önce nasıl
çözüldüyse aynı yol izlenir. Arşiv büyüdükçe cevaplar tutarlılaşır.

Dosya biçimi:

```markdown
# Soru
(kullanıcının sorusu, olduğu gibi)

# Yol
(hangi kaynak: public/*.csv.gz mi, warehouse.duckdb mi; hangi gösterge/kırılım)

# Sorgu
(kullanılan DuckDB SQL'i ya da csv okuma adımı — birebir, tekrar koşulabilir)

# Sonuç
(panele yazılan bölümün özeti: hangi şablon, kaç seri, dikkat edilenler)
```
