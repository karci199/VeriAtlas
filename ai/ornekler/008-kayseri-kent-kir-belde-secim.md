# Soru
tamam nereler buralar, ayrıca analiz yap (Kayseri'de işaretlenen kent/kır kararları)

# Yol
Sınıf: `scripts/analiz/kent_kir_2026_09_27/kullanici_karar.json` (`TR-38-*`, 715 birim). Kent = İlçe Merkezi + Kentsel Belde,
kır = Kırsal Belde + Köy. Belde kümesi kararın `y` alanı.
Nüfus: `C:\veri\warehouse.duckdb`, `population`, mahalle düzeyi. Yer ve yaş/eğitim/konut payları: `public/kentkir_kontrol.json`
(`xy`, `u17`, `o65`, `uni`, `kpb`; git dışı, 8 Ekim). Seçim: `public/tiles/secim-<kod>-mahalle-TR-38.json`
(`cb2023t2`, `mv2023`, `yerel_bsb_2019`, `yerel_bsb_2024`), `~` içeren anahtarlar sınıflara girmez, payları ayrıca söylenir.

Tuzaklar:
- Kırılımlı ve kırılımsız nüfus satırı birlikte toplanmaz: birimin yılında `dims=''` varsa o, yoksa `age=0-17` + `age=18+`.
- 2013-2017 kimliklerinin %88'i bağlanıyor, 2013'ten değişim sahte çıkıyor (Erkilet +%300): değişim 2018'den (%98,2), 2018'de Kocasinan'da 24.219 kişi kararsız.
- Mesafe `xy`'nin nüfus ağırlıklı ortalaması; şehir merkezi = Melikgazi + Kocasinan İlçe Merkezi birimleri.
- `mv2023` `CUMHUR İTTİFAKI` ortak oyları partilere dağıtılmaz.

# Sorgu
```sql
select area_id, year(period_start) y, dims, sum(value) v
from fact
where indicator_id = 'population' and area_id like 'TR-38-%' and length(area_id) > 9
group by 1, 2, 3;

-- province check
select year(period_start), sum(value)
from fact
where indicator_id = 'population' and area_id = 'TR-38' and dims like 'age=%;sex=%'
group by 1;
```

# Sonuç
Panelde il ve şehir çevresi nokta haritası, belde tablosu, sınıf tablosu, ilçe kent oranı çubukları (PATTERN 2), dört seçim tablosu.
2025: 1.458.297 kişi, kent %87,5; beş kentsel belde şehrin 8-14 km çevresinde. Köy 2018→25 −%16,7. MV 2023'te kent/kır farkı AK Parti'de değil MHP'de
(17,9 / 26). Büyükşehir 2024 katılımı kent %75,7, kır %88,2.
