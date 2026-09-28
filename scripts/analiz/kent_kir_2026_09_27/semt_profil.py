"""Demographic profile per semt: neighbourhoods, population, children, mean age, education, dwellings.

Sources: ADNKS 2025 (population, 0-17 -- missing for some villages in some years, then the
18+ row holds the total, so those neighbourhoods are left out of the child share, not zero);
mean age from the 2026-09-27 analysis (measured from Endeksa age bands where they add up,
otherwise modelled); education and dwellings from Endeksa 2024 (share among people with a
known level; small villages carry a zero template, so a neighbourhood with no education
rows is left out).

usage: semt_profil.py 16 <dir with semt_16_mahalle.csv>
"""

import json, sys
from pathlib import Path
import duckdb, polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG, LOCAL24, wh, geo_code  # noqa: E402



def fold(t):
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalpha())


m = pl.read_csv(D / f"semt_{PLATE}_mahalle.csv")
p = duckdb.sql(f"""select area_id, sum(value) filter (where dims='age=0-17') c, sum(value) filter (where dims='age=18+') a
 from read_parquet('{ROOT}/public/fact.parquet') where indicator_id='population' and area_id like 'TR-{PLATE}-%-%'
 and year(period_start)={YEAR} group by 1""").pl()
m = m.join(p, on="area_id", how="left").with_columns((pl.col("c").fill_null(0) + pl.col("a").fill_null(0)).alias("nufus"))

# mean age, joined on (district, name)
ya = pl.read_csv("C:/veri-ham/analiz/2026_09_27/mahalle_ort_yas_tum.csv", infer_schema_length=0).filter(pl.col("ilce_id").str.starts_with(f"TR-{PLATE}-"))
YAS = {(r["ilce_id"], fold(r["mahalle"])): (float(r["ort_yas"]), r["kaynak"]) for r in ya.iter_rows(named=True) if r["ort_yas"]}
m = m.with_columns(pl.struct("area_id", "name").map_elements(
    lambda s: YAS.get((s["area_id"].rsplit("-", 1)[0], fold(s["name"])), (None, None))[0], return_dtype=pl.Float64).alias("yas"))

# Endeksa education and dwellings, keyed by the neighbourhood code
EDU = {}
for f in Path("C:/veri-ham/endeksa/demography").glob(f"TR-{PLATE}-*.json"):
    for code, v in json.loads(f.read_text(encoding="utf-8")).items():
        e = v.get("demography") or {}
        known = sum(e.get(k) or 0 for k in ("EduNonLiterated", "EduLiteratedUntutored", "EduPrimarySchool", "EduMiddleSchool",
                                              "EduPrimaryEducation", "EduHighSchool", "EduLicenseDegree", "EduGraduate", "EduDoctorate"))
        uni = sum(e.get(k) or 0 for k in ("EduLicenseDegree", "EduGraduate", "EduDoctorate"))
        EDU[str(code)] = (known, uni, uni + (e.get("EduHighSchool") or 0), e.get("HousingCount") or 0)
m = m.with_columns(pl.col("area_id").map_elements(lambda a: list(EDU.get(geo_code(a), (0, 0, 0, 0))), return_dtype=pl.List(pl.Int64)).alias("_e"))
m = m.with_columns(pl.col("_e").list.get(0).alias("edu_n"), pl.col("_e").list.get(1).alias("uni"),
                   pl.col("_e").list.get(2).alias("lise_ust"), pl.col("_e").list.get(3).alias("konut")).drop("_e")

has_c = pl.col("c").is_not_null()
s = m.group_by("district", "semt").agg(
    pl.col("son_sinif").unique().sort().str.join("+").alias("tur"),
    pl.len().alias("mahalle"),
    pl.col("nufus").sum().cast(pl.Int64),
    pl.col("c").sum().cast(pl.Int64).alias("cocuk"),
    (pl.col("c").sum() / pl.col("nufus").filter(has_c).sum() * 100).round(1).alias("cocuk%"),
    (~has_c & (pl.col("nufus") > 0)).sum().alias("cocuk_verisiz_mah"),
    ((pl.col("yas") * pl.col("nufus")).sum() / pl.col("nufus").filter(pl.col("yas").is_not_null()).sum()).round(1).alias("ort_yas"),
    (pl.col("lise_ust").sum() / pl.col("edu_n").sum() * 100).round(1).alias("lise_ust%"),
    (pl.col("uni").sum() / pl.col("edu_n").sum() * 100).round(1).alias("universite%"),
    pl.col("konut").sum().alias("konut"),
    pl.col("name").sort_by("nufus", descending=True).str.join(", ").alias("mahalleler"),
).filter(pl.col("nufus") > 0).sort("district", "nufus", descending=[False, True])
s.write_csv(D / f"semt_{PLATE}_profil.csv")
print(s.height, "semt; ort. yaş eşleşmeyen mahalle:", m.filter(pl.col("yas").is_null() & (pl.col("nufus") > 0)).height,
      "; eğitimsiz:", m.filter((pl.col("edu_n") == 0) & (pl.col("nufus") > 0)).height)
