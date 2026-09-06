# Oturum notu — 2026-09-06 akşam

Dal `claude/veri-cekmeye-devam-f01ae0`. Bu not, oturum kapanırken diskte ne olduğunu ve
neyin yarım kaldığını kaydeder; devam eden oturum buradan başlar.

## Tamamlananlar

**Mahalle seçim verisi (TÜİK, `raw/tuik_secim`).** 2015 Haziran ve 2011 çekildi ve
`mahalle_toplam.py` ile doğrulandı: 2015H 970 ilçe / 48.956 yerleşim (tutmayan 1:
Gaziantep/Nurdağı −221), 2011 957 ilçe / 48.852 yerleşim (tutmayan 2: İstanbul/Şişli
−8.809, Nurdağı −269). CSV 5,4 M satırı aştı. 2007 çekimi **921/884+ ilçede yarım
kaldı** — `python zk_fetch.py 2007` yeniden başlatılırsa diskteki dosyalardan devam eder,
sonra `parse.py`.

**MEDAS mahalle 18± dökümü tamam: 81 il.** Büyük iller yıl dilimlerine bölünerek indi
(`nufus-mahalle-ANKARA-2025_2020.csv` gibi). Kapsam denetimi (`kapsam_denetimi.py`):
30 büyükşehirde %99,91 (İstanbul %100), 51 ilde %67,31 — eksiğin tamamı köyler, çünkü
kaynak köyleri yayımlamıyor.

**Endeksa mahalle demografisi tarayıcısız çözüldü** (`raw/endeksa_cek.py`, ayrıntı
`docs/endeksa.md`). Dört kimlik birden verilince uçlar girişsiz cevap veriyor; jeton
gerekmiyor. Bursa, Ankara, İstanbul, Adana ve Adıyaman'ın bir kısmı indi (99 ilçe dosyası).
`python endeksa_cek.py --eksik` kaldığı yerden sürer.

**Çocuk payı × oy analizi 81 ille yeniden üretildi** (`raw/tuik_secim/cocuk_orani_oy.py`,
`cocuk_orani_duzey.py`, `cocuk_orani_rapor.py`): 29.240 yerleşim, 56,2 M seçmen,
Türkiye'nin %92,6'sı. Sayfa üç düzeyli (yerleşim / ilçe / il), çizgiler açılıp
kapanıyor ve eksen açık olanlara göre ölçekleniyor.

**Parti × yaş modeli** (`parti_yas_modeli.py`): 973 ilçenin yaş piramidi ile oyu,
düzgünleştirilmiş NNLS + bootstrap. İYİ 57,0 · Millet 55,7 · CHP 55,1 · MHP 51,4 ·
Cumhur 42,4 · AKP 41,0 · YRP 31,8 · Emek ve Özgürlük 23,4 (18+ nüfus ortalaması 44,0).
Ekolojik çıkarım; R² 0,04–0,27.

**Semt katmanı** (`raw/ptt/`). PTT'nin 2022 posta kodu dosyası bulundu (semt sütunu
duruyor, bugünkü PTT sitesinde yok). 2.771 semt üç türe ayrıldı: gerçek semt, kır
torbası, bölünmemiş ilçe. Çıktılar: `semt_analiz.html`, `semt_tablo.xlsx/csv/html`,
`semt_arayuz.html` (koyu tema, il/ilçe süzgeci, dağılım grafiği, semt kartı).

## Düzeltilen hatalar

1. **Kapanmış ilçeye asılı mahalleler.** MEDAS ilçenin eski adını yazmayı sürdürüyor
   (Eyüp, Kazan); kayıt hem kapanmış ilçeyi hem ardılını tuttuğu için eşleşme kapanmış
   olana düşüyor, o mahalleler ilçe nüfusu olmayan bir kimliğe asılı kalıyordu —
   Eyüpsultan'ın 28 mahallesi böyle kayıptı (ilçe 420.194, mahalle toplamı 12.079).
   `build_neighbourhood_registry.py` içine iki yeniden adlandırma işlendi. Commit b207d60.
2. **Gizlenen çocuk hücresi sıfır sayılıyordu.** TÜİK küçük sayıyı basmıyor; boş hücre
   sıfır okununca yerleşim %0 çocuk payına düşüyordu. Artık en yakın önceki yılın oranı
   kullanılıyor.
3. **Oran geri çevirimi patlıyordu.** Aynı düzeltmede `oran/(1-oran)` ile sayıya dönerken
   geçmiş yılın yetişkin hücresi de boşsa oran 1'e gidiyor ve çocuk sayısı milyarlara
   çıkıyordu; oran %60'ı aşarsa o yıl kullanılmıyor.
4. **Kurumsal sandıklar analizin içindeydi.** İlk dilimde katılım %108 çıkıyordu. Ad
   listesi yerine aritmetik kural: oy kullanan > kayıtlı seçmen olan yerleşim dışarıda
   (298 yerleşim, 108 bin seçmen). Silivri, Sincan/Adalet, Maltepe/Büyükbakkalköy.
5. **Registry eksik illerle üretilmişti.** Mahalle kaydı 78 ille kurulmuştu (Manisa,
   Samsun, Şanlıurfa yoktu); MEDAS tamamlanınca yeniden üretildi (32.681 mahalle) ve
   `fact.parquet` içindeki mahalle satırları bununla değiştirildi.
6. **PTT "MERKEZ" ilçesi eşleşmiyordu.** Büyükşehir olmayan illerde PTT merkez ilçeye
   "MERKEZ" der, kayıt ilin adını verir; eşleme takma adla çözüldü.
7. **PTT köy içi mahalleleri.** `AĞIT MAH (ZÜMRÜT KÖYÜ)` gibi satırlar köyün kendisine
   bağlanıyor (parantez içi ad); yoksa Kastamonu gibi illerde yüzlerce satır boş kalıyordu.

## Açık kalanlar

- **Semt tablosunda mükerrer sayım.** Toplam nüfus 88,8 M çıkıyor, oysa yerleşim
  toplamı 86,1 M. Sebep: 7.441 alan birden çok PTT satırına denk geliyor (aynı köyün
  mahalleleri, bir de "MERKEZ"/il adı ikili yazımı). `semt_tablo.py` içine alan kimliğine
  göre tekilleştirme yazıldı ama **dosyaya işlenmedi** (grep `alinmis` boş) — ilk iş bu.
- 2007 çekimi yarım; ardından 2002, 1999, 1995, 1991.
- Köy toplam nüfus dökümü 76/81 il indi (`raw/medas/yerlesim`); tamamlanınca köy kaydı
  yeniden üretilmeli — Derecik'in 66 yerleşiminden yalnız 1'i kayıtta, Şemdinli ile
  karışıyor.
- `load.py <tek adaptör>` ambarı ve `fact.parquet`'i **yalnız o adaptörle** yeniden
  yazıyor; tam yükleme ise ilçe nüfusu ve köy ham dökümleri eksik olduğu için şu an
  çalışmıyor. Bu oturumda tablo bir kez bu yüzden 708 bin satıra düştü, başka bir
  worktree'deki 30 Ağustos kopyasından geri yüklendi (2,34 M satır / 28 gösterge).
- Semtin resmî sınırı yok; analizlerde "PTT dağıtım bölgesi" olarak adlandırılmalı.
