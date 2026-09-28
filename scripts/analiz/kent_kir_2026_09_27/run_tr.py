"""Run run_il.py for every province not done yet, three at a time, and keep a status table.

Output: C:/veri-ham/analiz/kent_kir/_durum.csv (plate, name, status, seconds, urban share,
borderline count, districts without a centre, institutional count) and per-province
sapmalar_<p>.csv (what to look at by hand: districts with no centre, borderline
neighbourhoods, institutional populations, disagreements with the user's lists where they exist).

usage: run_tr.py [workers=3]
"""

import subprocess, sys, time, csv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import polars as pl

HERE = Path(__file__).parent
PY = "C:/veri/.venv/Scripts/python.exe"
OUT = Path("C:/veri-ham/analiz/kent_kir")
W = int(sys.argv[1]) if len(sys.argv) > 1 else 3
plates = [f"{i:02d}" for i in range(1, 82)]


def sapmalar(p):
    d = OUT / p
    son = pl.read_csv(d / f"kent_{p}_son.csv", infer_schema_length=0)
    ilce = pl.read_csv(d / f"kent_{p}_ikili_ilce.csv", infer_schema_length=0)
    rows = []
    for r in ilce.filter(pl.col("kent_mah") == "0").iter_rows(named=True):
        rows.append(dict(tur="merkezsiz_ilce", district=r["district"], name="", pop=r["toplam"], not_="ilçede hiç merkez mahalle yok"))
    for r in son.filter(pl.col("arada").is_not_null() & (pl.col("arada") != "")).iter_rows(named=True):
        rows.append(dict(tur="arada", district=r["district"], name=r["name"], pop=r["pop"], not_=f"{r['son_sinif']} | {r['arada']}"))
    if "kurum" in son.columns:
        for r in son.filter(pl.col("kurum") == "1").iter_rows(named=True):
            rows.append(dict(tur="kurum", district=r["district"], name=r["name"], pop=r["pop"], not_="seçmen dışı / kurum nüfusu"))
    f = d / f"kullanici_fark_{p}.csv"
    if f.exists():
        for r in pl.read_csv(f, infer_schema_length=0).iter_rows(named=True):
            rows.append(dict(tur="kullanici_farki", district=r["district"], name=r["name"], pop=r["pop"], not_=f"kullanıcı {r['tip_k']} / kalıp {r['son_sinif']}"))
    pl.DataFrame(rows, schema={"tur": pl.Utf8, "district": pl.Utf8, "name": pl.Utf8, "pop": pl.Utf8, "not_": pl.Utf8}).rename({"not_": "not"}).write_csv(d / f"sapmalar_{p}.csv")
    return len([r for r in rows if r["tur"] == "merkezsiz_ilce"]), len([r for r in rows if r["tur"] == "arada"]), len([r for r in rows if r["tur"] == "kurum"])


def one(p):
    d = OUT / p
    t0 = time.time()
    done = (d / f"yas_mc_{p}_ilce.csv").exists()
    if not done:
        r = subprocess.run([PY, str(HERE / "run_il.py"), p], capture_output=True, text=True, encoding="utf-8", errors="replace")
        (d if d.exists() else OUT).joinpath(f"run_{p}.log").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
        if r.returncode:
            return dict(plate=p, status="HATA", seconds=round(time.time() - t0), note=(r.stdout or "").strip().splitlines()[-1:] or r.stderr[-200:])
    subprocess.run([PY, str(HERE / "karsilastir_kullanici.py"), p], capture_output=True)
    z, a, k = sapmalar(p)
    il = pl.read_csv(d / f"kent_{p}_ikili_ilce.csv", infer_schema_length=0)
    tot = il.filter(pl.col("district").str.to_uppercase() == pl.col("district"))
    return dict(plate=p, status="tamam" if not done else "vardı", seconds=round(time.time() - t0), kent_pct=tot["kent%"][0] if tot.height else None,
                nufus=tot["toplam"][0] if tot.height else None, merkezsiz_ilce=z, arada=a, kurum=k, note="")


rows = []
with ThreadPoolExecutor(W) as ex:
    for res in ex.map(one, plates):
        rows.append(res)
        print(res, flush=True)
        with open(OUT / "_durum.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["plate", "status", "seconds", "kent_pct", "nufus", "merkezsiz_ilce", "arada", "kurum", "note"])
            w.writeheader(); w.writerows([{k: r.get(k, "") for k in w.fieldnames} for r in rows])
print("bitti")
