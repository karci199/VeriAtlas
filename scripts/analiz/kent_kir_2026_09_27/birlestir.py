"""Final urban/rural class per neighbourhood of one province from five signals.

Signals: (1) building clusters (kent_il.py output), (2) TÜİK DEGURBA 2025, (3) registry
number block, (4) 2007-2012 TÜİK registry status (mahalle / köy / belde), (5) haritatr semt
(support only, never decisive on its own).

Decisions (user, 2026-09-27): when in doubt rural; DEGURBA alone never moves a place to
urban; urban = pre-2013 municipal neighbourhood inside the built-up town; separate
settlement >= 5,000 = urban belde; 2,000-5,000 = kasaba (rural); OSB left out.

usage: birlestir.py 16 <kent_il output dir> <out dir>
"""

import sys
from pathlib import Path
import polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG, LOCAL24, wh, geo_code  # noqa: E402
SRC = OUT = D



def fold(t):
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(a, b)
    t = "".join(ch for ch in t if ch.isalnum())
    return t.removesuffix("mah").removesuffix("mahallesi")


nb = pl.read_csv(SRC / f"kent_{PLATE}_mahalle.csv", infer_schema_length=0)

# (2) DEGURBA, joined on the registry number
dg = pl.read_excel("C:/veri-ham/tuik/adnks/adnks-2025-il-ilce-belediye-mahalle-koy-kentkir.xlsx",
                   sheet_name="KENT-KIR SINIFLAMASI", has_header=False, read_options={"skip_rows": 3})
dg = dg.select(pl.col(dg.columns[1]).alias("il"), pl.col(dg.columns[4]).cast(pl.Utf8).alias("code"),
               pl.col(dg.columns[12]).alias("degurba")).filter(pl.col("il").cast(pl.Utf8) == str(int(PLATE)))
nb = nb.join(dg.select("code", "degurba"), on="code", how="left")

# (3) registry block: < 100,500 existing neighbourhood before 2013; 140xxx split off an
# existing town around 2013; 18xxxx converted from a village in 2013; later = new split
c = pl.col("code").cast(pl.Int64)
nb = nb.with_columns(pl.when(c < 100500).then(pl.lit("eski_mahalle")).when(c < 150000).then(pl.lit("kasabadan_bolunen"))
                     .when(c < 190000).then(pl.lit("koyden")).otherwise(pl.lit("yeni_bolunen")).alias("kayit_blok"))

# (4) 2007-2012 status: the municipality its name was listed under before 2013
reg = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0).filter(
    pl.col("parent_id").str.starts_with(f"TR-{PLATE}-") & (pl.col("first_seen").cast(pl.Int64) <= 2012))
vil = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_villages.csv", infer_schema_length=0).filter(
    pl.col("parent_id").str.starts_with(f"TR-{PLATE}-"))
old = {}
for r in reg.iter_rows(named=True):
    old.setdefault((r["parent_id"], fold(r["name_tr"])), r["municipality"].removesuffix(" Bel."))
for r in vil.iter_rows(named=True):
    old.setdefault((r["parent_id"], fold(r["name_tr"].removesuffix(" Köy."))), "koy")
nb = nb.with_columns(pl.struct("area_id", "name").map_elements(
    lambda s: old.get((s["area_id"].rsplit("-", 1)[0], fold(s["name"])), "yok"), return_dtype=pl.Utf8).alias("eski_statu"))
# a former belde whose quarters were merged into one neighbourhood named after it in 2014
# (Urganlı, Sart, Yeniceköy) matches on the belde name, not on a quarter name
BEL = {}
for r in reg.iter_rows(named=True):
    BEL.setdefault(r["parent_id"], {})[fold(r["municipality"].removesuffix(" Bel."))] = r["municipality"].removesuffix(" Bel.")
# districts split after 2012 (Manisa Merkez -> Yunusemre/Şehzadeler): the belde sat under
# the old district, so the province-wide belde list is the second try
# only beldes whose old district no longer exists (split or renamed) may match across
# districts; otherwise a same-named belde elsewhere would be taken (Gemlik Kurşunlu / İnegöl Kurşunlu)
CUR = set(pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_districts.csv", infer_schema_length=0)
          .filter((pl.col("parent_id") == f"TR-{PLATE}") & (pl.col("valid_to").is_null() | (pl.col("valid_to") == "")))["area_id"])
BEL_IL = {}
for did, d in BEL.items():
    if did not in CUR:
        BEL_IL.update(d)
DNAME = {fold(r["name_tr"]) for r in pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_districts.csv", infer_schema_length=0)
         .filter(pl.col("parent_id") == f"TR-{PLATE}").iter_rows(named=True)}
nb = nb.with_columns(pl.struct("area_id", "name", "eski_statu").map_elements(
    lambda s: s["eski_statu"] if s["eski_statu"] != "yok" else BEL.get(s["area_id"].rsplit("-", 1)[0], {}).get(fold(s["name"]))
    or (BEL_IL.get(fold(s["name"])) if fold(s["name"]) not in DNAME and fold(s["name"]) != SLUG else None) or "yok",
    return_dtype=pl.Utf8).alias("eski_statu"))
# a municipality other than the district's own (or metropolitan Bursa) was a belde
nb = nb.with_columns(pl.struct("district", "eski_statu").map_elements(
    lambda s: s["eski_statu"] if s["eski_statu"] in ("koy", "yok") else "ilce_mahalle"
    if fold(s["eski_statu"]) in (fold(s["district"]), SLUG) else "belde:" + s["eski_statu"], return_dtype=pl.Utf8).alias("eski_statu"))

# (5) haritatr semt
ht = pl.read_csv(f"C:/veri-ham/haritatr/{PLATE}/semt_mahalle.csv", infer_schema_length=0)
hmap = {}
for r in ht.iter_rows(named=True):
    kind = "koyler" if r["semt"].endswith("Köyleri") else "merkez" if r["semt"].endswith("Merkez") else "belde:" + r["semt"]
    hmap[(fold(r["district"]), fold(r["neighbourhood"].removesuffix(" Köyü")))] = kind
nb = nb.with_columns(pl.struct("district", "name").map_elements(
    lambda s: hmap.get((fold(s["district"]), fold(s["name"])), "yok"), return_dtype=pl.Utf8).alias("haritatr"))


# (6) TKGM parcels and (7) PTT streets: people per parcel and per street. Informative
# columns and a check on the building rule; they do not decide. (PTT lists street codes in
# most towns and names only in some villages, so "named street" share is not usable.)
# TKGM names differ from ADNKS ("Yenimahalle", "Yeşilcami", "Boyalıca/kılıç"): match on the
# folded name, then on the name with "mahalle" stripped, then on the part before "/",
# summed over the pieces.
tk = pl.read_csv("C:/veri-ham/tkgm/megsis_mahalle_2026-09-18.csv").filter(pl.col("il").map_elements(fold, return_dtype=pl.Utf8) == SLUG)
TK = {}
for r in tk.iter_rows(named=True):
    d = fold(r["ilce"]); base = r["mahalle"].split("/")[0]
    for key in {fold(r["mahalle"]), fold(base), fold(base).removesuffix("mahalle").removesuffix("mah")}:
        TK.setdefault((d, key), [0.0, 0.0]); TK[(d, key)][0] += float(r["tapu_parsel"] or 0); TK[(d, key)][1] += float(r["kesin_koordinatli"] or 0)
pt = pl.read_csv("C:/veri-ham/ptt/postakodu_2026-09-18.csv", infer_schema_length=0).filter(pl.col("il") == PTT_IL)
pt = pt.group_by("ilce", "mahalle").agg(pl.col("sokak").n_unique().alias("sokak"))
PT = {(fold(r["ilce"]), fold(r["mahalle"].split("(")[0]).removesuffix("mah")): int(r["sokak"]) for r in pt.iter_rows(named=True)}


def ext(s):
    d, n = fold(s["district"]), fold(s["name"])
    keys = (n, n.removesuffix("mahalle").removesuffix("mah"), n + "koyu", n.removesuffix("koyu"))
    tkv = next((TK[(d, k)] for k in keys if (d, k) in TK), None)
    if tkv is None:  # spelling differences (Pirebeyler / Piribeyler): closest name in the district
        import difflib
        cands = [k for (dd, k) in TK if dd == d]
        best = [] if "osb" in n else difflib.get_close_matches(n, cands, n=1, cutoff=0.86)
        tkv = TK[(d, best[0])] if best else [None, None]
    ptv = next((PT[(d, k)] for k in keys if (d, k) in PT), None)
    return {"parsel": tkv[0], "kesin_koord": tkv[1], "sokak": ptv}


nb = nb.with_columns(pl.struct("district", "name").map_elements(ext, return_dtype=pl.Struct({"parsel": pl.Float64, "kesin_koord": pl.Float64, "sokak": pl.Int64})).alias("_x")).unnest("_x")
nb = nb.with_columns((pl.col("pop").cast(pl.Float64) / pl.col("parsel")).round(2).alias("kisi_parsel"),
                     (pl.col("pop").cast(pl.Float64) / pl.col("sokak")).round(1).alias("kisi_sokak"))
print("tapu eşleşen", nb.filter(pl.col("parsel").is_not_null()).height, "| sokak eşleşen", nb.filter(pl.col("sokak").is_not_null()).height, "/", nb.height)


def decide(r):
    bina = r["sinif"]
    if bina == "osb":
        return "osb", ""
    d_kent = (r["degurba"] or "").startswith(("YOĞUN", "ORTA"))
    s_old = r["kayit_blok"] in ("eski_mahalle", "kasabadan_bolunen", "yeni_bolunen") or r["eski_statu"] in ("ilce_mahalle",) or r["eski_statu"].startswith("belde:")
    h_kent = r["haritatr"] == "merkez" or r["haritatr"].startswith("belde:")
    votes = f"bina={bina} degurba={'kent' if d_kent else 'kır'} statü={'kent' if s_old else 'köy'} haritatr={r['haritatr']}"
    if bina in ("merkez", "kentsel_belde"):
        if s_old or d_kent:
            return bina, ("" if (s_old and d_kent) else "arada: " + votes)
        # built into the town but a village by record and rural by DEGURBA: when in doubt rural
        return "kir", "arada→kır (şüphede kır): " + votes
    # building rule says rural. District-centre exception (Black Sea towns: the centre is a
    # strip and its old quarters sit on the slopes): a 2007-2012 district-municipality
    # quarter that is not a converted village is urban when at least a fifth of its
    # buildings touch the town or DEGURBA calls it urban (matches the user's own lists, 2026-09-28)
    share = float(r["share"] or 0)
    if (bina == "kir" and r["eski_statu"] == "ilce_mahalle" and r["kayit_blok"] == "eski_mahalle"
            and r["haritatr"] != "koyler" and (share >= 0.2 or d_kent)):
        return "merkez", "ilçe merkezi istisnası: eski ilçe mahallesi, " + ("lekeye kısmen giriyor" if share >= 0.2 else "DEGURBA kent") + " · " + votes
    # no flip to urban: in Bursa many villages became neighbourhoods in 2004 (5216) or
    # before 2007, so an old registry number is no proof of a town (Adaköy, Kumlukalan)
    if s_old and r["haritatr"] == "koyler":
        return bina, "arada: 2013 öncesi mahalle yapılmış köy (haritatr Köyleri): " + votes
    if d_kent or s_old:
        return bina, "arada: " + votes
    return bina, ""


# manual decisions, each checked outside the data (user / web)
ELLE = {
    # split off the town in 2016, TOKİ blocks newer than the building footprints
    # (gursu.bel.tr "ipekyolu mahallemizdeki yeni toki konutlari"); part of the town
    "TR-16-003-197753": ("merkez", "elle: TOKİ, 2016'da merkezden ayrıldı, bina verisinde yok"),
}
# official split, kept beside the building rule. Outside the 30 metropolitan provinces the
# legal categories still exist in 2024: il/ilçe merkezi (the district's own municipality) =
# şehir, other municipalities = belde, villages = köy. TÜİK counts only şehir as urban.
METRO = LOCAL24 == "yerel_bsb_2024"
cur = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_neighbourhoods.csv", infer_schema_length=0).filter(
    pl.col("parent_id").str.starts_with(f"TR-{PLATE}-") & (pl.col("last_seen").cast(pl.Int64) >= YEAR))
MUN24 = {r["area_id"]: r["municipality"].removesuffix(" Bel.") for r in cur.iter_rows(named=True)}
VIL24 = set(pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_villages.csv", infer_schema_length=0).filter(
    pl.col("parent_id").str.starts_with(f"TR-{PLATE}-") & (pl.col("last_seen").cast(pl.Int64) >= YEAR))["area_id"])


def resmi(s):
    if METRO:
        return "bsb"
    if s["area_id"] in VIL24:
        return "koy"
    m = MUN24.get(s["area_id"])
    if m is None:
        return "yok"
    return "sehir" if fold(m) in (fold(s["district"]), SLUG) else "belde"


nb = nb.with_columns(pl.struct("area_id", "district").map_elements(resmi, return_dtype=pl.Utf8).alias("resmi"))
res = [ELLE.get(r["area_id"]) or decide(r) for r in nb.iter_rows(named=True)]
nb = nb.with_columns(pl.Series("son_sinif", [a for a, _ in res]), pl.Series("arada", [b for _, b in res]))
nb.write_csv(OUT / f"kent_{PLATE}_son.csv")
p = pl.col("pop").cast(pl.Float64).fill_null(0)
tot = nb.select(p.sum()).item()
print(nb.group_by("son_sinif").agg(pl.len().alias("mahalle"), p.sum().alias("nufus")).with_columns(
    (pl.col("nufus") / tot * 100).round(1).alias("pay")).sort("nufus", descending=True))
print("arada kalan:", nb.filter(pl.col("arada") != "").height)
