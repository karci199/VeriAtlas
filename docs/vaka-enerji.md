# Vaka: enerji tüketimi ve diğer il göstergeleri

2026-09-15. EPDK il serileri (`epdk_*`) SEGE, nüfus, araç, trafik ve SGK verileriyle
birleştirildi. Düzey il; sorgular `public/fact.parquet` üzerinde DuckDB ile.

## Bulgular

1. **Gelişmişlik neyi yakıyor.** SEGE-2017 il skoru ile 2017 kişi başı tüketim korelasyonu:
   konut doğalgazı 0,64; akaryakıt 0,58; elektrik 0,52; tüplü LPG 0,14. Tüp LPG
   gelişmişlikle ilgisiz: gazın ulaşmadığı yerin yakıtı.
2. **Güneydoğu otogazı.** 2024'te LPG'li araç başına otogaz satışı: Şanlıurfa 1,67 t,
   Diyarbakır 1,66 t, Batman 1,43 t, Van 1,43 t, Mardin 1,18 t. Olağan binek kullanımının
   üstü; açıklama (ticari araç yoğunluğu, il dışı kayıtlı araç, otogazın başka kullanımı)
   veriyle sınanmadı.
3. **Edirne transit yakıt.** 2024 kişi başı akaryakıt satışı Edirne 1,82 t; ikinci Bolu
   0,80 t, sonra Kırıkkale, Burdur. Sınır kapısı ve otoyol güzergâhı etkisi.
4. **İş kazası ve sanayi elektriği.** 2024'te il iş kazası sayısı (SGK 4a) ile sanayi
   elektrik tüketimi korelasyonu 0,81. Sıradaki adım: GWh başına iş kazası ile sanayinin
   görece tehlikeli olduğu illeri ayırmak (hesaplanmadı).
5. **Yakıt başına trafik ölümü — kesinleşmedi.** Osmaniye, Erzincan, Malatya, Şanlıurfa öne
   çıktı; ancak `road_deaths` cinsiyet ve ölüm zamanı kırılımlı, toplama çift sayım içerebilir.
   Kullanmadan önce kırılım toplamı düzeltilmeli.

## Sorgu kalıbı

```sql
create view f as select * from 'public/fact.parquet' where area_level='province';
create table pop as select area_id, year(period_start) y, sum(value) p
  from f where indicator_id='population' group by all;
```

Kişi başı değerlerde nüfus yaş × cinsiyet kırılımının toplamıdır.
