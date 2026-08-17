# Eğitim — okuma yazma durumu

Yeni konu (`topic.egitim`). Kaynak: TÜİK MEDAS, "Ulusal Eğitim İstatistikleri" →
"Okuma Yazma Durumu". Üç ayrı çekim, üç ayrı gösterge — kapsamları (yaş eşiği, düzey,
yıl aralığı) farklı, birleştirilmedi:

| Gösterge | Düzey | Yaş | Yıl | Kırılım |
|---|---|---|---|---|
| `literacy` | il + Türkiye | 15+ | **2008-2025** (zaman serisi) | cinsiyet × durum |
| `literacy_district` | ilçe | 15+ | 2008, 2025 (tek kesit ×2) | cinsiyet × durum |
| `literacy_by_age` | il + Türkiye | **6+** | 2008, 2025 (tek kesit ×2) | cinsiyet × yaş bandı × durum |

15+ ve 6+ ayrı popülasyonlar — aynı yaş kırılımına koymak toplanabilirliği bozardı,
o yüzden ayrı gösterge.

## Bulgu — okuma yazma bilmeyen oranı, aynı coğrafya, hızlı düşüş

En yüksek (2025, 15+): Mardin %7,1, Şanlıurfa %7,1, Ağrı %6,9, Siirt %6,6, Muş %6,3,
Iğdır %5,8 — vehicle/hane bulgularıyla (Bulgu 10) aynı coğrafya.

En düşük: Antalya %0,76, Çanakkale %0,82, Muğla %0,98, Denizli %0,99, İzmir %1,02.

2008→2025 düşüş her ilde büyük: Mardin %23,2→%7,1 (−16,1 puan), Siirt %25,9→%6,6
(−19,4 puan, en sert düşüş). Yani seviye hâlâ doğu-batı ekseninde ayrışıyor ama hız her
yerde yüksek — aradaki fark daralıyor, kapanmıyor henüz.

## Durum

- ✔ Üç adaptör: `tuik_literacy.py`, `tuik_literacy_district.py`, `tuik_literacy_age.py`
- ✔ Sözlük: `topic.egitim`, `dim.literacy_status`, üç `indicator.*` bloğu
- ✔ Ekran: `export_web.py`'a `DATASETS`/`BROKEN_DOWN`/`fine` eklendi, üçü de menüde
- ✔ Excel: `scripts/build_literacy_excel.py` → `cikti/okuma-yazma-analizi.xlsx`
  (İller, İlçeler, Yaş Grubu, Notlar)
- Kaynak dosyalar `Desktop/demografi/Egitim/` ve `Desktop/demografi/` altında; adaptörler
  ilk çalıştırmada `raw/tuik_medas/`'a kendi kopyalarını alıyor.
- MEDAS'ın kendisi ayrıca 6+ yaş için 15+'a paralel bir toplam da yayımlıyor
  ("Okuma yazma oranı (%)" ölçümü, Örgün/Ulusal Eğitim altında) — henüz çekilmedi.
