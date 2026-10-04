"""Agreement with the user's hand-made classification (Desktop/demografi/İLLER 18+ Merkez Çevre/<İL>.xlsx,
sheet TÜM-SAYI: YERLEŞİM TİPİ Mahalle / Kentsel Belde / Kırsal Belde / Köy and a SEMT). Available for
eight provinces; used as validation, never as input.

usage: karsilastir_kullanici.py 16
"""

import openpyxl, polars as pl
from pathlib import Path

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, D, PTT_IL, fold  # noqa: E402

f = Path("C:/Users/katan/OneDrive/Desktop/demografi/İLLER 18+ Merkez Çevre") / f"{PTT_IL}.xlsx"
if not f.exists():
    raise SystemExit(f"kullanıcı dosyası yok: {f.name}")
ws = openpyxl.load_workbook(f, read_only=True, data_only=True)["TÜM-SAYI"]
rows = [r for r in ws.iter_rows(values_only=True)][1:]
u = pl.DataFrame([dict(ilce=fold(str(r[1])), ad=fold(str(r[3])), tip_k=r[2], semt_k=str(r[6]).strip() if r[6] else None) for r in rows if r[0] and r[3]])
s = pl.read_csv(D / f"kent_{PLATE}_son.csv", infer_schema_length=0).with_columns(
    pl.col("district").map_elements(fold, return_dtype=pl.Utf8).alias("ilce"), pl.col("name").map_elements(fold, return_dtype=pl.Utf8).alias("ad"), pl.col("pop").cast(pl.Float64))
j = s.join(u, on=["ilce", "ad"], how="inner")
KENT = {"Mahalle": "kent", "Kentsel Belde": "kent", "Kırsal Belde": "kır", "Köy": "kır"}
j = j.with_columns(pl.col("tip_k").replace_strict(KENT, default=None).alias("kk_k"),
                   pl.when(pl.col("son_sinif").is_in(["merkez", "kentsel_belde", "osb"])).then(pl.lit("kent")).otherwise(pl.lit("kır")).alias("kk"))
agree = (j["kk"] == j["kk_k"])
print(f"eşleşen mahalle {j.height}/{s.height} | kent-kır uyumu %{agree.mean() * 100:.1f} (nüfusla %{j.filter(agree)['pop'].sum() / j['pop'].sum() * 100:.1f})")
pl.Config.set_tbl_rows(40); pl.Config.set_tbl_width_chars(220)
print(j.group_by("tip_k", "son_sinif").agg(pl.len(), pl.col("pop").sum().cast(pl.Int64)).sort("tip_k", "son_sinif"))
d = j.filter(~agree).sort("pop", descending=True).select("district", "name", "pop", "tip_k", "son_sinif", "share", "degurba", "eski_statu")
d.write_csv(D / f"kullanici_fark_{PLATE}.csv")
print(d.head(20))
