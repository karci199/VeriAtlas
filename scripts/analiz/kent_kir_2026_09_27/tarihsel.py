"""Historical urban/rural split of one province: censuses 1965-2000 and ADNKS 2007-2012.

Every settlement is typed by its status in that year: district centre ("Şehir" row in the
census, the district's own municipality in ADNKS), belde ("(B)" / another municipality) or
village. Same thresholds as kent_il.py: belde >= 5,000 urban, 2,000-5,000 kasaba (rural),
smaller belde rural.

usage: tarihsel.py 16 bursa <out dir>
"""

import difflib, html, re, sys
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


# census files carry the province name of the day
ALIAS = {"mersin": "icel", "kahramanmaras": "maras", "sanliurfa": "urfa"}
rows, check, warn = [], {}, []
for y in (1965, 1970, 1975, 1980, 1985, 1990, 2000):
    f = Path("C:/veri-ham/tuik_sayim") / str(y) / f"idari-{SLUG}-tum-yerlesim.html"
    if not f.exists() and SLUG in ALIAS:
        f = f.with_name(f"idari-{ALIAS[SLUG]}-tum-yerlesim.html")
    if not f.exists():  # provinces created after that census (Yalova 1995, Düzce 1999 ...)
        warn.append(f"{y}: sayım dosyası yok"); continue
    t = f.read_bytes().decode("cp1254")
    district = None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        c = [html.unescape(re.sub(r"<[^>]+>", "", x)).replace("\xa0", " ").strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        c = [x for x in c if x]
        if not c:
            continue
        nums = [x for x in c if isnum(x)]
        if len(c) >= 2 and fold(c[0]) in (SLUG, ALIAS.get(SLUG, SLUG)):
            district = c[1]; c = c[2:]
            if len(nums) < 3:
                continue
        elif len(nums) < 3:
            continue
        total = num(nums[-3])
        # "(*)": a bucak centre already counted inside the city's "Şehir" row (Ankara Cebeci 1965);
        # a numeric "Merkez" row is the same thing for the central bucak
        if any(x.endswith("(*)") for x in c) or c[0] == "Merkez" and not any("(B)" in x for x in c) and len(c) == 4:
            continue
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

got = pl.DataFrame(rows).group_by("year").agg(pl.col("pop").sum()) if rows else pl.DataFrame({"year": [], "pop": []})
# a few hundred people off (a row the reader cannot parse) is tolerated with a warning; a
# large gap (a summary row counted twice) drops the year
bad = {y for y, v in got.iter_rows() if check.get(y) is not None and abs(check[y] - v) > 0.005 * check[y]}
for y, v in got.iter_rows():
    if check.get(y) is not None and v != check[y] and y not in bad:
        warn.append(f"{y}: satırlar {v} != il toplamı {check[y]} (%{abs(check[y] - v) / check[y] * 100:.2f}, tutuldu)")
for y, v in got.iter_rows():
    if y in bad:
        warn.append(f"{y}: satırlar {v} != il toplamı {check.get(y)} -- yıl atlandı")
rows = [r for r in rows if r["year"] not in bad]
print("sayım il toplamı denetimi:", check, "| uyarı:", warn)
(OUT / f"tarihsel_{PLATE}_uyari.txt").write_text(" | ".join(warn), encoding="utf-8")

# ADNKS 2007-2012 from the warehouse
reg = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0)
vil = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_villages.csv", infer_schema_length=0)
dis = {r["area_id"]: r["name_tr"] for r in pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_districts.csv", infer_schema_length=0).iter_rows(named=True)}
# the registry keeps only the newest municipality name; the status of that year comes from
# the raw export (Emek, Alanyurt ... were still beldes in 2007)
sys.path.insert(0, str(ROOT / "src"))
from veriatlas.adapters.tuik_neighbourhoods import DOWNLOADS, read_export  # noqa: E402

MUN_NEW = {r["area_id"]: r["municipality"].removesuffix(" Bel.") for r in reg.iter_rows(named=True)}
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
        # a code-year missing from the export (Adana Sarıçam 2012) falls back to the newest
        # municipality in the registry
        m = MUNY.get((y, aid.rsplit("-", 1)[1]), "") or MUN_NEW.get(aid, "") or dis.get(did, "")
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


# 2007-2012 quarters of annexed beldes whose names survive nowhere today; user placed them
# (2026-09-28): Gemlik Şükrükaya -> Kurşunlu, Güzel Yalı / Şükrü Alemdar / Parsbey -> Umurbey
# Nilüfer Karaalı -> Çalı, Keles Çayören -> Hereke, Büyükorhan Veletler -> Bademlik,
# İnegöl İnayet -> Tuzla
OLD_TO_NEW = {"TR-16-002-11355": "140855", "TR-16-002-11356": "140853",
              "TR-16-002-11359": "140853", "TR-16-002-11361": "140853",
              "TR-16-012-11139": "11138", "TR-16-008-7655": "184111",
              "TR-16-001-7391": "183605", "TR-16-005-7484": "183781"}
# villages merged into another village, target unnamed; a village either way (user)
OLD_VILLAGE = {"TR-16-001-7362", "TR-16-008-7662",  # Büyükorhan Çökene, Keles Domalı
               "TR-16-002-11357", "TR-16-005-7532",  # Gemlik Memireis, İnegöl Mesruriye
               "TR-06-004-2476", "TR-06-004-2469",  # Bala Büyükbıyık, Altınçanak
               "TR-06-014-2740", "TR-06-018-2878",  # Haymana Karaömerli, Kızılcahamam Yanık
               "TR-06-009-2069"}  # Elmadağ Bağbahçe Yaylaevleri (summer site; rural when in doubt)
# quarters merged away whose class is known without a target (user, 2026-09-29)
OLD_CLASS = {"TR-06-019-1784": "merkez",  # Mamak PTT Evleri
             "TR-06-023-1836": "osb"}  # Sincan OSB


def fixed(r):
    did, code = r["area_id"].rsplit("-", 1)
    if r["area_id"] in OLD_VILLAGE:
        return "kir"
    if r["area_id"] in OLD_CLASS:
        return OLD_CLASS[r["area_id"]]
    code = OLD_TO_NEW.get(r["area_id"], code)
    if code in by_code:
        return by_code[code]
    nm = VNAME.get(r["area_id"]) or RNAME.get(r["area_id"]) or ""
    nm = fold(re.sub(r" (Köy|Mah)\.$", "", nm))
    # a belde quarter is matched by the belde's name first: its own quarter names
    # (Cumhuriyet, Yeni) collide with the district centre's and pulled Kınık, Kurşunlu,
    # Elbeyli ... into merkez
    if r["kind"] == "belde":
        bn = fold(r["name"] or "")
        for key in ((did, bn), (did, bn + "koy"), *(k for k in by_name if k[1] in (bn, bn + "koy"))):
            if key in by_name:
                return by_name[key]
    # "Nilüfer Köy." is today's Nilüferköy; a belde's quarters became one neighbourhood
    # named after the belde (Yeniceköy); a village may have moved district (Gürsu)
    for key in ((did, nm), (did, nm + "koy"), (did, fold(r["name"] or "")), *(k for k in by_name if k[1] in (nm, nm + "koy"))):
        if key in by_name:
            return by_name[key]
    # a belde annexed before 2007 is listed under the district municipality with its name as
    # prefix ("Umurbey Orhaniye" -> today's Umurbey): take the longest current name it starts with
    pre = [k for k in by_name if k[0] == did and len(k[1]) >= 4 and nm.startswith(k[1])]
    if pre:
        return by_name[max(pre, key=lambda k: len(k[1]))]
    # small spelling drift inside the district (Kazıklı -> Kazıklıköyü, Çağlıyan -> Çağlayan,
    # Eyerce -> Eğerce); a village never lands on a town neighbourhood this way (Mesruriye
    # köyü would otherwise take İnegöl's Mesudiye)
    base = lambda s: s.removesuffix("koyu").removesuffix("koy")
    cand = [(difflib.SequenceMatcher(None, base(nm), base(k[1])).ratio(), k) for k in by_name if k[0] == did]
    cand = [c for c in cand if c[0] >= 0.83 and not (r["kind"] == "koy" and by_name[c[1]] == "merkez")]
    if cand:
        return by_name[max(cand)[1]]
    # a quarter merged under a longer name keeps the old one as suffix (Kalecik Şenyurt ->
    # Ahikemalşenyurt)
    suf = [k for k in by_name if k[0] == did and len(nm) >= 5 and k[1].endswith(nm)]
    if len(suf) == 1:
        return by_name[suf[0]]
    # an unmatched district-centre row used to fall back to merkez silently, which carried
    # annexed villages and beldes into the town; it is kept apart and counted instead --
    # except in a district that is urban all through today (Altındağ's quarters merged by
    # the 2008-2012 renewal), where no village is left to carry
    if r["kind"] == "sehir" and URBAN_DISTRICT.get(did, 0) >= 0.99:
        return "merkez"
    return "eslesmedi"


_u = son.with_columns(pl.col("area_id").str.slice(0, 9).alias("did"), pl.col("pop").cast(pl.Float64).fill_null(0))
URBAN_DISTRICT = {r["did"]: r["k"] / r["t"] for r in _u.group_by("did").agg(
    pl.col("pop").sum().alias("t"), pl.col("pop").filter(pl.col("son_sinif").is_in(["merkez", "kentsel_belde"])).sum().alias("k")).iter_rows(named=True) if r["t"]}
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

# the same fixed list by district, 2007-2012 beside the newest ADNKS year (today's
# neighbourhoods, so the class needs no carrying)
DNAME = {aid.rsplit("-", 1)[0]: r for aid, r in ((r["area_id"], r["district"]) for r in son.iter_rows(named=True))}
URB = ["merkez", "kentsel_belde"]
old = a.group_by("year", "district").agg(
    pl.col("pop").sum().alias("toplam"), pl.col("pop").filter(pl.col("sabit").is_in(URB)).sum().alias("kent"))
new = duckdb.sql(f"""select area_id, year(period_start) y, sum(value) v from read_parquet('{ROOT}/public/fact.parquet')
 where indicator_id='population' and area_id like 'TR-{PLATE}-%-%'
   and period_start = (select max(period_start) from read_parquet('{ROOT}/public/fact.parquet')
                       where indicator_id='population' and area_id like 'TR-{PLATE}-%-%') group by 1,2""").pl()
cls = {r["area_id"]: r["son_sinif"] for r in son.iter_rows(named=True)}
new = new.with_columns(pl.col("area_id").str.slice(0, 9).replace_strict(DNAME, default=None).alias("district"),
                       pl.col("area_id").replace_strict(cls, default="eslesmedi").alias("sabit"))
new = new.group_by(pl.col("y").alias("year"), "district").agg(
    pl.col("v").sum().cast(pl.Int64).alias("toplam"), pl.col("v").filter(pl.col("sabit").is_in(URB)).sum().cast(pl.Int64).alias("kent"))
ilce = pl.concat([old.with_columns(pl.col("year").cast(pl.Int32), pl.col("toplam", "kent").cast(pl.Int64)),
                  new.with_columns(pl.col("year").cast(pl.Int32))])
ilce = ilce.with_columns((pl.col("kent") / pl.col("toplam") * 100).round(1).alias("kent%")).sort("district", "year")
ilce.write_csv(OUT / f"tarihsel_{PLATE}_ilce_sabit.csv")
a.write_csv(OUT / f"tarihsel_{PLATE}_sabit_satir.csv")
