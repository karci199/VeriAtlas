"""Voter profile reports (TÜİK election application, district level) -> two tidy tables.

Input: C:/veri-ham/secim/profil/secmen/<election>__<table>__<province>.html, 5 elections
(2011, 2015_7_haziran, 2015_1_kasim, 2018, 2023) x 81 provinces x 3 tables.
Output (C:/veri-ham/secim/profil/):
  secmen_yas_egitim.parquet   election, province, district, age group, sex, education bucket, count
  secmen_yas_medeni.parquet   election, province, district, age group, sex, marital status, count
Education rows go through scripts/aday_profili.read (header drift, shifted columns, the
report's own Toplam as the check). Marital blocks are simpler: one header per district,
columns fixed (Hiç evlenmedi, Evli, Boşandı, Eşi öldü, Toplam); a row whose parts do not
add up to its Toplam is counted as unread, never silently kept.
"""

import html, re, sys
from pathlib import Path
import polars as pl

sys.path.insert(0, "C:/veri/scripts")
from aday_profili import read, AGE, fold  # noqa: E402

PROFIL = Path("C:/veri-ham/secim/profil")
SRC = PROFIL / "secmen"
MAR = ["Hiç evlenmedi", "Evli", "Boşandı", "Eşi öldü"]
MARF = [fold(m) for m in MAR]
COUNT = re.compile(r"^\d{1,3}(?:\.\d{3})*$|^\d+$")


def rows_of(path):
    raw = path.read_bytes()
    try:
        t = raw.decode("utf-8")
    except UnicodeDecodeError:
        t = raw.decode("cp1254", errors="replace")
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        cells = [c for c in cells if c]
        if cells:
            out.append(cells)
    return out


def read_marital(path):
    """[(district, age, sex, {status: n})], unread rows."""
    out, bad, district, age = [], 0, None, None
    for c in rows_of(path):
        f = [fold(x) for x in c]
        if len(c) >= 6 and all(m in f for m in MARF) and "toplam" in f:
            district = c[0]
            continue
        if district is None:
            continue
        if AGE.match(c[0]):
            age = c[0]; c = c[1:]
        if not c or c[0] not in ("Erkek", "Kadın") or age is None:
            continue
        sex, nums = c[0], c[1:]
        if any(fold(x) == "toplam" for x in nums):
            continue
        vals = [int(x.replace(".", "")) if COUNT.match(x) else 0 if x == "-" else None for x in nums]
        if len(vals) != 5 or None in vals or sum(vals[:4]) != vals[4]:
            bad += 1
            continue
        out.append((district, age, sex, dict(zip(MAR, vals[:4]))))
    return out, bad


edu, mar, log = [], [], []
for path in sorted(SRC.glob("*.html")):
    election, table, prov = path.stem.split("__")[0], "__".join(path.stem.split("__")[1:3]), path.stem.split("__")[-1]
    if table == "yas_grubu__egitim_durumu":
        rows, bad = read(path)
        for area, age, sex, counts in rows:
            for k, v in counts.items():
                edu.append(dict(election=election, province=prov, district=area, age=age, sex=sex, education=k, n=v))
    elif table == "yas_grubu__medeni_durum":
        rows, bad = read_marital(path)
        for area, age, sex, counts in rows:
            for k, v in counts.items():
                mar.append(dict(election=election, province=prov, district=area, age=age, sex=sex, marital=k, n=v))
    else:
        continue
    log.append(dict(file=path.name, rows=len(rows), unread=bad))
pl.DataFrame(edu).write_parquet(PROFIL / "secmen_yas_egitim.parquet")
pl.DataFrame(mar).write_parquet(PROFIL / "secmen_yas_medeni.parquet")
lg = pl.DataFrame(log)
lg.write_csv(PROFIL / "secmen_okuma_gunlugu.csv")
print("eğitim satırı", len(edu), "| medeni satırı", len(mar))
print(lg.group_by(pl.col("file").str.extract(r"__(yas_grubu__[a-z_]+)__")).agg(pl.len(), pl.col("rows").sum(), pl.col("unread").sum()))
print(lg.filter(pl.col("unread") > 0).sort("unread", descending=True).head(10))
m = pl.DataFrame(mar)
print(m.group_by("election").agg(pl.col("n").sum(), pl.col("district").n_unique()).sort("election"))
