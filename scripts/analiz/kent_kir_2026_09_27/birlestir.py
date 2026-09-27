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
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG  # noqa: E402
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
    # building rule says rural
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
res = [ELLE.get(r["area_id"]) or decide(r) for r in nb.iter_rows(named=True)]
nb = nb.with_columns(pl.Series("son_sinif", [a for a, _ in res]), pl.Series("arada", [b for _, b in res]))
nb.write_csv(OUT / f"kent_{PLATE}_son.csv")
p = pl.col("pop").cast(pl.Float64).fill_null(0)
tot = nb.select(p.sum()).item()
print(nb.group_by("son_sinif").agg(pl.len().alias("mahalle"), p.sum().alias("nufus")).with_columns(
    (pl.col("nufus") / tot * 100).round(1).alias("pay")).sort("nufus", descending=True))
print("arada kalan:", nb.filter(pl.col("arada") != "").height)
