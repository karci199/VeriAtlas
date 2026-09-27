"""Historical urban/rural split of one province: censuses 1965-2000 and ADNKS 2007-2012.

Every settlement is typed by its status in that year: district centre ("Şehir" row in the
census, the district's own municipality in ADNKS), belde ("(B)" / another municipality) or
village. Same thresholds as kent_il.py: belde >= 5,000 urban, 2,000-5,000 kasaba (rural),
smaller belde rural.

usage: tarihsel.py 16 bursa <out dir>
"""

import html, re, sys
from pathlib import Path
import duckdb, polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG  # noqa: E402
OUT = D

num = lambda s: int(s.replace(".", ""))
isnum = lambda s: re.fullmatch(r"[\d.]+", s) is not None


def fold(t):
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalpha())


rows, check = [], {}
for y in (1965, 1970, 1975, 1980, 1985, 1990, 2000):
    t = (Path("C:/veri-ham/tuik_sayim") / str(y) / f"idari-{SLUG}-tum-yerlesim.html").read_bytes().decode("cp1254")
    district = None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).replace("\xa0", " ").strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        c = [x for x in c if x]
        if not c:
            continue
        nums = [x for x in c if isnum(x)]
        if len(nums) < 3:
            if len(c) >= 2 and fold(c[0]) == fold(SLUG) and not nums:
                district = c[1]
            continue
        total = num(nums[-3])
        if any("toplam" in x.lower() for x in c):
            if any(x.startswith("İl toplam") for x in c):
                check[y] = total
            continue
        if "Şehir" in c:
            kind, name = "sehir", district
        else:
            name = re.sub(r"\s*\(.*$", "", [x for x in c if not isnum(x) and x != "(B)"][-1])
            kind = "belde" if any("(B)" in x for x in c) else "koy"
        rows.append(dict(year=y, district=district, name=name, kind=kind, pop=total))

got = pl.DataFrame(rows).group_by("year").agg(pl.col("pop").sum())
for y, v in got.iter_rows():
    assert check.get(y) in (None, v), f"{y}: satırlar {v} != il toplamı {check.get(y)}"
print("sayım il toplamı denetimi:", check)

# ADNKS 2007-2012 from the warehouse
reg = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0)
vil = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_villages.csv", infer_schema_length=0)
dis = {r["area_id"]: r["name_tr"] for r in pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_districts.csv", infer_schema_length=0).iter_rows(named=True)}
# the registry keeps only the newest municipality name; the status of that year comes from
# the raw export (Emek, Alanyurt ... were still beldes in 2007)
sys.path.insert(0, str(ROOT / "src"))
from veriatlas.adapters.tuik_neighbourhoods import DOWNLOADS, read_export  # noqa: E402

MUNY = {}
for f in DOWNLOADS.glob(f"nufus-mahalle-{IL_UP}*.csv"):
    for cell in read_export(f):
        if 2007 <= cell.year <= 2012:
            MUNY[(cell.year, cell.code)] = cell.municipality.removesuffix(" Bel.")
VIL = set(vil["area_id"])
pop = duckdb.sql(f"""select area_id, year(period_start) y, sum(value) v from read_parquet('{ROOT}/public/fact.parquet')
 where indicator_id='population' and area_id like 'TR-{PLATE}-%-%' and year(period_start) between 2007 and 2012 group by 1,2""").pl()
for aid, y, v in pop.iter_rows():
    did = aid.rsplit("-", 1)[0]
    if aid in VIL:
        kind, name = "koy", aid
    else:
        m = MUNY.get((y, aid.rsplit("-", 1)[1]), "")
        assert m, f"{y} {aid}: belediye yok"
        own = fold(m) in (fold(dis.get(did, "")), fold(SLUG))
        kind, name = ("sehir", dis.get(did)) if own else ("belde", m)
    rows.append(dict(year=y, district=dis.get(did), name=name, kind=kind, pop=int(v), area_id=aid))

d = pl.DataFrame(rows)
# a belde is one unit: sum its rows (ADNKS lists it by neighbourhood)
b = d.filter(pl.col("kind") == "belde").group_by("year", "district", "name").agg(pl.col("pop").sum())
b = b.with_columns(pl.when(pl.col("pop") >= 5000).then(pl.lit("kentsel_belde")).when(pl.col("pop") >= 2000)
                   .then(pl.lit("kasaba")).otherwise(pl.lit("kirsal_belde")).alias("kind"))
s = d.filter(pl.col("kind") != "belde").group_by("year", "kind").agg(pl.col("pop").sum())
s = pl.concat([s, b.group_by("year", "kind").agg(pl.col("pop").sum())])
w = s.pivot(on="kind", index="year", values="pop").fill_null(0).sort("year")
for k in ("sehir", "kentsel_belde", "kasaba", "kirsal_belde", "koy"):
    if k not in w.columns:
        w = w.with_columns(pl.lit(0).alias(k))
w = w.with_columns(pl.sum_horizontal("sehir", "kentsel_belde", "kasaba", "kirsal_belde", "koy").alias("toplam"))
w = w.with_columns(
    (pl.col("sehir") / pl.col("toplam") * 100).round(1).alias("sehir%"),
    ((pl.col("sehir") + pl.col("kentsel_belde")) / pl.col("toplam") * 100).round(1).alias("kent%"),
    ((pl.col("sehir") + pl.col("kentsel_belde") + pl.col("kasaba") + pl.col("kirsal_belde")) / pl.col("toplam") * 100).round(1).alias("resmi_belediye%"),
    pl.col("year").is_in([2007, 2008, 2009, 2010, 2011, 2012]).map_elements(lambda x: "ADNKS" if x else "sayım", return_dtype=pl.Utf8).alias("kaynak"))
w.write_csv(OUT / f"tarihsel_{PLATE}.csv")
b.sort("year", "pop", descending=[False, True]).write_csv(OUT / f"tarihsel_{PLATE}_belde.csv")
pl.Config.set_tbl_cols(20); pl.Config.set_tbl_width_chars(220)
print(w.select("year", "kaynak", "toplam", "sehir", "kentsel_belde", "kasaba", "kirsal_belde", "koy", "sehir%", "kent%", "resmi_belediye%"))


# TÜİK's own split (il/ilçe merkezi vs belde+köy) for the same years
legal = duckdb.sql(f"""select year(period_start) y, dims, value from read_parquet('{ROOT}/public/fact.parquet')
 where indicator_id='urban_rural_legal' and area_id='TR-{PLATE}' and year(period_start) <= 2012""").pl()
tuik = legal.pivot(on="dims", index="y", values="value").rename({"y": "year", "settlement=town": "tuik_merkez", "settlement=village": "tuik_belde_koy"})

# fixed list: today's building-based class of every place, carried back to 2007-2012
son = pl.read_csv(OUT / f"kent_{PLATE}_son.csv", infer_schema_length=0)
by_code = {r["code"]: r["son_sinif"] for r in son.iter_rows(named=True)}
by_name = {(r["area_id"].rsplit("-", 1)[0], fold(r["name"])): r["son_sinif"] for r in son.iter_rows(named=True)}
VNAME = {r["area_id"]: r["name_tr"] for r in vil.iter_rows(named=True)}
RNAME = {r["area_id"]: r["name_tr"] for r in reg.iter_rows(named=True)}


def fixed(r):
    did, code = r["area_id"].rsplit("-", 1)
    if code in by_code:
        return by_code[code]
    nm = VNAME.get(r["area_id"]) or RNAME.get(r["area_id"]) or ""
    nm = fold(re.sub(r" (Köy|Mah)\.$", "", nm))
    # "Nilüfer Köy." is today's Nilüferköy; a belde's quarters became one neighbourhood
    # named after the belde (Yeniceköy); a village may have moved district (Gürsu)
    for key in ((did, nm), (did, nm + "koy"), (did, fold(r["name"] or "")), *(k for k in by_name if k[1] in (nm, nm + "koy"))):
        if key in by_name:
            return by_name[key]
    return "merkez" if r["kind"] == "sehir" else "eslesmedi"


a = pl.DataFrame([r for r in rows if r["year"] >= 2007])
a = a.with_columns(pl.struct("area_id", "kind", "name").map_elements(fixed, return_dtype=pl.Utf8).alias("sabit"))
fx = a.group_by("year").agg(
    (pl.col("pop").filter(pl.col("sabit").is_in(["merkez", "kentsel_belde"])).sum() / pl.col("pop").sum() * 100).round(1).alias("sabit_liste_kent%"),
    pl.col("pop").filter(pl.col("sabit") == "eslesmedi").sum().alias("eslesmeyen"))
a.filter((pl.col("sabit") == "eslesmedi") & (pl.col("year") == 2012)).sort("pop", descending=True).write_csv(OUT / "eslesmeyen.csv")
cmp = w.filter(pl.col("year") >= 2007).join(tuik, on="year").join(fx, on="year").with_columns(
    (pl.col("tuik_merkez") / pl.col("toplam") * 100).round(1).alias("tuik_merkez%"))
cmp = cmp.select("year", "toplam", "tuik_merkez", "sehir", "tuik_merkez%", "resmi_belediye%", "kent%", "sabit_liste_kent%", "eslesmeyen")
cmp.write_csv(OUT / f"tarihsel_{PLATE}_2007_2012.csv")
print(cmp)
