"""Bugun yasadigimiz uc sorunun cozuldugunu dogrular:
1) eski .xls dosyasini Excel COM olmadan okuma
2) Turkce karakter / ondalik ayraci bozulmadan
3) DuckDB + Parquet gidis-donus
"""

import time
from pathlib import Path

import duckdb
import polars as pl

XLS = Path(r"C:\Users\katan\OneDrive\Desktop\demografi1\SEÇİM\Sandık.xls")
XLSX = Path(r"C:\Users\katan\OneDrive\Desktop\demografi\demografi2\VERİ\ilçeler1.xls")

t0 = time.perf_counter()
df = pl.read_excel(XLS, sheet_name="2020", engine="calamine")
t1 = time.perf_counter()

print(f"[1] .xls okundu  {df.height} satir x {df.width} sutun   ({t1 - t0:.2f} sn)")
print("    ilk 3 il:", df[:3, 0].to_list())

df2 = pl.read_excel(XLSX, sheet_name="YAŞ GRUPLARI", engine="calamine")
print(f"[2] Turkce sayfa adi + il adlari  {df2.height} satir")
print("    ornek:", df2[0, 0], "|", df2[0, 1], df2[0, 2], df2[0, 3])

out = Path(r"C:\veri\public")
out.mkdir(exist_ok=True)
pq = out / "test.parquet"
df2.write_parquet(pq)

con = duckdb.connect()
n = con.execute(f"select count(*) from read_parquet('{pq.as_posix()}')").fetchone()[0]
top = con.execute(
    f"select * from read_parquet('{pq.as_posix()}') order by 4 desc limit 3"
).fetchall()
print(f"[3] DuckDB parquet okudu: {n} satir")
for r in top:
    print("    ", r[0], r[1], r[2], r[3])

print(f"\ntoplam {time.perf_counter() - t0:.2f} sn")
