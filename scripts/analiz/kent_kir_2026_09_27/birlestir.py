"""Final urban/rural class per neighbourhood of one province from five signals.

Signals: (1) building clusters (kent_il.py output), (2) TÜİK DEGURBA 2025, (3) registry
number block, (4) 2007-2012 TÜİK registry status (mahalle / köy / belde), (5) haritatr semt
(support only, never decisive on its own).

Decisions (user, 2026-09-27): when in doubt rural; DEGURBA alone never moves a place to
urban; urban = pre-2013 municipal neighbourhood inside the built-up town; separate
settlement >= 5,000 = urban belde; 2,000-5,000 = kasaba (rural); OSB left out.

usage: birlestir.py 16 <kent_il output dir> <out dir>
"""

import csv
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
    t = t.removesuffix("mah").removesuffix("mahallesi")
    # a settlement's name can carry "Köyü"/"Köy" in the current geometry (kent_il.py's nb)
    # but not in the pre-2013 registry ("Dündar Köy." -> "Dündar" there already), or the other
    # way round -- strip it on both sides so the two never miss each other by a suffix alone
    return t.removesuffix("koyu").removesuffix("koy")


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
# a settlement's own id is the warehouse village id (kent_il.py already applies wh()): that is
# a direct, exact match and settles it outright, ahead of the fold-name lookup, which can miss
# on a suffix it did not expect ("Köyü" vs "Köy.") or on two villages sharing one folded name
VIL_IDS = set(vil["area_id"])
nb = nb.with_columns(pl.struct("area_id", "name").map_elements(
    lambda s: "koy" if s["area_id"] in VIL_IDS else old.get((s["area_id"].rsplit("-", 1)[0], fold(s["name"])), "yok"),
    return_dtype=pl.Utf8).alias("eski_statu"))
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
    # kayit_blok is a numeric-code guess calibrated on Bursa's own numbering (old mahalle
    # codes there sit under 100,500); other provinces gave their villages low codes too, so
    # the guess is worthless wherever a direct registry hit already says "köy" for certain
    s_old = (r["eski_statu"] not in ("koy",) and r["kayit_blok"] in ("eski_mahalle", "kasabadan_bolunen", "yeni_bolunen")) \
        or r["eski_statu"] in ("ilce_mahalle",) or r["eski_statu"].startswith("belde:")
    h_kent = r["haritatr"] == "merkez" or r["haritatr"].startswith("belde:")
    votes = f"bina={bina} degurba={'kent' if d_kent else 'kır'} statü={'kent' if s_old else 'köy'} haritatr={r['haritatr']}"
    if bina in ("merkez", "kentsel_belde"):
        # a former village the town has grown onto (Kuşadası Soğucak, Bigadiç Işıklar): urban
        # but not the town itself. Provisional rule (user, 2026-09-29): >= 3,000 people ->
        # kentsel belde, fewer -> village; every case stays in the "arada" list for review
        eski_koy = r["eski_statu"] == "koy" or (r["kayit_blok"] == "koyden" and r["eski_statu"] not in ("ilce_mahalle",) and not r["eski_statu"].startswith("belde:"))
        if bina == "merkez" and eski_koy:
            p = float(r["pop"] or 0)
            return (("kentsel_belde", "arada: kente bitişmiş eski köy, >=3.000 → kentsel belde (geçici kural) · " + votes) if p >= 3000
                    else ("kir", "arada: kente bitişmiş eski köy, <3.000 → köy (geçici kural) · " + votes))
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
    # (gursu.bel.tr "ipekyolu mahallemizdeki yeni toki konutlari"); satellite shows a dense
    # cluster detached from Gürsu's main fabric -- user checked the map (2026-09-28)
    "TR-16-003-197753": ("kentsel_belde", "elle: kullanıcı haritadan baktı, TOKİ, ayrı yoğun küme"),
    # Didim's old quarter, spread along the coast road; user checked the map (2026-09-29)
    "TR-09-004-10109": ("kentsel_belde", "elle: kullanıcı haritadan baktı, kentsel belde"),
    # Nilüfer Kayapa: "ilçe merkezi istisnası" wrongly forced this to merkez -- satellite shows
    # a dense, self-contained cluster by a lake, physically detached from Nilüfer's built-up
    # fabric; user checked the map (2026-09-28)
    "TR-16-012-11153": ("kentsel_belde", "elle: kullanıcı haritadan baktı, ayrı yoğun küme, kentsel belde"),
    # Mudanya Çağrışan: satellite shows dense grid attached to Mudanya Üniversitesi area, not a
    # scattered village; user checked the map (2026-09-28)
    "TR-16-010-184233": ("kentsel_belde", "elle: kullanıcı haritadan baktı, kentsel belde"),
    # Osmangazi Nilüferköy: satellite shows a substantial detached town cluster; user checked
    # the map (2026-09-28)
    "TR-16-015-183495": ("kentsel_belde", "elle: kullanıcı haritadan baktı, kentsel belde"),
    # Karacabey Yeni: user checked the map (2026-09-28), treats it as the district centre
    "TR-16-007-19982": ("merkez", "elle: kullanıcı haritadan baktı, merkez"),
    # İznik Elbeyli: former belde (eski_statu belde:Elbeyli), stayed rural in character; user
    # checked the map (2026-09-28)
    "TR-16-006-183893": ("kirsal_belde", "elle: kullanıcı haritadan baktı, eski belde, kırsal karakter"),
    # İnegöl Kurşunlu: AATOPLU 2015 lists it as Belde (like Gemlik Kurşunlu); user reconsidered
    # and matched both Kurşunlu's to kırsal_belde (2026-09-28)
    "TR-16-005-183703": ("kirsal_belde", "elle: AATOPLU 2015 belde diyor, Gemlik Kurşunlu ile eşleştirildi"),
    # Gemlik Ata: eski_statu=ilce_mahalle, haritatr=merkez, AATOPLU 2015 already lists it under
    # MAHALLE (not köy) -- three signals agree it was never a village; user confirmed merkez
    # (2026-09-28). Institutional population flagged (kurum=1), separate from this class call.
    "TR-16-002-11339": ("merkez", "elle: eski_statu ve AATOPLU 2015 (mahalle, köy değil) merkezi destekliyor"),
    # Osmangazi Gündoğdu: AATOPLU 2015 lists it under MAHALLE, not köy -- contradicts the "eski
    # köy" note, but user kept it as kır after reviewing (2026-09-28)
    "TR-16-015-11248": ("kir", "elle: AATOPLU 2015 mahalle diyor (köy değil) ama kullanıcı kır kararını sürdürdü"),
    # İnegöl Karalar: köy, AATOPLU 2015 confirms köy; kurum=1 (institutional population present,
    # user's "yurt mu" guess), reviewed (2026-09-28)
    "TR-16-005-183793": ("kir", "elle: köy, AATOPLU doğruluyor; kurum nüfusu var (kurum=1)"),
    # Gemlik Cihatlı: köy despite newer TOKİ blocks, AATOPLU 2015 confirms köy, reviewed (2026-09-28)
    "TR-16-002-183615": ("kir", "elle: TOKİ olsa da köy, AATOPLU doğruluyor"),
    # Gemlik Engürücük: köy, AATOPLU 2015 confirms köy; kurum=1 (institutional population),
    # reviewed (2026-09-28)
    "TR-16-002-183617": ("kir", "elle: köy, AATOPLU doğruluyor; kurum nüfusu var (kurum=1)"),
    # Osmangazi Alaşarköy: AATOPLU 2015 lists it under MAHALLE, not köy -- contradicts the "eski
    # köy" note, but user kept it as kır after reviewing (2026-09-28)
    "TR-16-015-11162": ("kir", "elle: AATOPLU 2015 mahalle diyor (köy değil) ama kullanıcı kır kararını sürdürdü"),
    # Osmangazi Yeniceabat: "ilçe merkezi istisnası" wrongly forced this to merkez -- AATOPLU
    # 2015 confirms it was a Köy, not part of the district centre; user corrected to kır (2026-09-28)
    "TR-16-015-11242": ("kir", "elle: AATOPLU 2015 köy diyor, ilçe merkezi istisnası yanlış tetiklenmiş"),
    # Mudanya Göynüklü: köy, isolated cluster on satellite, reviewed (2026-09-28)
    "TR-16-010-184243": ("kir", "elle: köy, uydu görüntüsünde izole küme"),
    # Gemlik Kurşunlu (Gemlik'teki, İnegöl'dekinden ayrı): AATOPLU 2015 lists it as Belde, fits
    # the demoted-belde/kırsal_belde rule; user confirmed (2026-09-28)
    "TR-16-002-140855": ("kirsal_belde", "elle: AATOPLU 2015 belde diyor, kırsal karakter"),
    # Nilüfer's remaining reviewed villages: all köy in eski_statu, kept as kır after review
    # (2026-09-28)
    "TR-16-012-183443": ("kir", "elle: incelendi, köy kaldı (Doğanköy)"),
    "TR-16-012-183469": ("kir", "elle: incelendi, köy kaldı (Yaylacık)"),
    "TR-16-012-11150": ("kir", "elle: incelendi, köy kaldı (Hasanağa)"),
    "TR-16-012-183463": ("kir", "elle: incelendi, köy kaldı (Tahtalı), DEGURBA da kır"),
    "TR-16-012-11141": ("kir", "elle: incelendi, köy kaldı (Gölyazı)"),
    "TR-16-012-11145": ("kir", "elle: incelendi, köy kaldı (İrfaniye)"),
    "TR-16-012-11148": ("kir", "elle: incelendi, köy kaldı (Büyükbalıklı)"),
    "TR-16-012-11146": ("kir", "elle: incelendi, köy kaldı (Gökçe)"),
    # reviewed, kept as-is (2026-09-28)
    "TR-16-014-184627": ("kirsal_belde", "elle: incelendi, kırsal_belde doğru (Orhangazi Yeniköy)"),
    "TR-16-004-11374": ("merkez", "elle: incelendi, ilçe merkezi kuralı doğru (Harmancık Merkez)"),
    "TR-16-002-140853": ("kasaba", "elle: incelendi, kasaba kaldı (Gemlik Umurbey)"),
    "TR-16-010-184257": ("kir", "elle: incelendi, köy kaldı (Mudanya Mürsel)"),
    # Gürsu Kumlukalan: "ilçe merkezi istisnası" forced merkez -- user judged it a village (2026-09-28)
    "TR-16-003-11369": ("kir", "elle: kullanıcı köy dedi, ilçe merkezi istisnası geçersiz kılındı"),
    # İnegöl Çeltikçi: not a plain village, close to Kurşunlu, but user rejected full urban --
    # settled on kırsal_belde (2026-09-28)
    "TR-16-005-183731": ("kirsal_belde", "elle: kullanıcı 'köy değil ama kent de değil' dedi, kırsal_belde"),
    # Mudanya Tirilye: eski_statu=belde:Tirilye -- was genuinely a belde, kept as kırsal_belde
    # per that rule; user confirmed after reconsidering (2026-09-28)
    "TR-16-010-184223": ("kirsal_belde", "elle: eski belde (eski_statu=belde:Tirilye), kırsal_belde doğru"),
    # Orhangazi Çakırlı: confirmed kırsal_belde, reviewed (2026-09-28)
    "TR-16-014-184621": ("kirsal_belde", "elle: incelendi, kırsal_belde doğru (Çakırlı)"),
    # Gürsu Adaköy: "ilçe merkezi istisnası" forced merkez -- user judged it a village (2026-09-28)
    "TR-16-003-11366": ("kir", "elle: kullanıcı köy dedi, ilçe merkezi istisnası geçersiz kılındı"),
    # Mudanya Hasköy: confirmed köy, reviewed (2026-09-28)
    "TR-16-010-20008": ("kir", "elle: incelendi, köy kaldı (Hasköy)"),
    # Orhaneli Karıncalı: confirmed kırsal_belde, reviewed (2026-09-28)
    "TR-16-013-184513": ("kirsal_belde", "elle: incelendi, kırsal_belde doğru (Karıncalı)"),
    # Mustafakemalpaşa Yeşilova: confirmed kırsal_belde, reviewed (2026-09-28)
    "TR-16-011-184299": ("kirsal_belde", "elle: incelendi, kırsal_belde doğru (Yeşilova)"),
    # Kestel Barakfakih: "ilçe merkezi istisnası" forced merkez -- user judged it a village that
    # used to have belde-like status, though eski_statu here reads ilce_mahalle not belde:
    # (2026-09-28)
    "TR-16-009-99957": ("kir", "elle: kullanıcı köy dedi (eskiden kırsal belde imiş), ilçe merkezi istisnası geçersiz kılındı"),
    # confirmed unchanged after review (2026-09-28)
    "TR-16-001-11334": ("merkez", "elle: incelendi, zaten merkez mahalle (Büyükorhan Orhan)"),
    "TR-16-008-19986": ("merkez", "elle: incelendi, zaten merkez mahalle (Keles Cuma)"),
    "TR-16-010-20009": ("kir", "elle: incelendi, köy kaldı (Mudanya Ülkü)"),
    "TR-16-010-184229": ("kir", "elle: incelendi, köy kaldı (Mudanya Aydınpınar)"),
    "TR-16-015-11258": ("kir", "elle: incelendi, köy kaldı (Osmangazi Kirazlı)"),
    # Mustafakemalpaşa Tepecik, Orhaneli Göynükbelen: user downgraded kirsal_belde to kır after
    # satellite review -- small isolated clusters, not treated as former-belde character (2026-09-28)
    "TR-16-011-184295": ("kir", "elle: kullanıcı köy dedi, kırsal_belde'den indirildi"),
    "TR-16-013-184511": ("kir", "elle: kullanıcı köy dedi, kırsal_belde'den indirildi"),
    # Gemlik Küçükkumla/Büyükkumla: contiguous with the main Kumla (already kentsel_belde,
    # 6.579 kişi) per user (2026-09-28)
    "TR-16-002-140857": ("kentsel_belde", "elle: Kumla'ya bitişik, kentsel_belde"),
    "TR-16-002-183613": ("kentsel_belde", "elle: Kumla'ya bitişik, kentsel_belde"),
    # İznik Boyalıca: eski belde, kırsal karakter -- user confirmed (2026-09-28)
    "TR-16-006-183891": ("kirsal_belde", "elle: eski belde (belde:Boyalıca), kırsal_belde"),
    # Keles Ertuğrulgazi: confirmed merkez, reviewed (2026-09-28)
    "TR-16-008-19988": ("merkez", "elle: incelendi, zaten merkez mahalle (Keles Ertuğrulgazi)"),
    # Orhangazi Sölöz: eski_statu=belde:Sölöz (was a belde) but user downgraded to köy after
    # satellite review (2026-09-28) -- flagged, goes against the belde-history signal
    "TR-16-014-184625": ("kir", "elle: eski belde idi (belde:Sölöz) ama kullanıcı köy dedi"),
    # İnegöl Edebey/Kulaca/Şipali/Ortaköy: confirmed köy, reviewed (2026-09-28). Ortaköy's
    # eski_statu is belde:Yeniceköy (was a belde) but user kept it as köy -- flagged
    "TR-16-005-183745": ("kir", "elle: incelendi, köy kaldı (Edebey)"),
    "TR-16-005-183807": ("kir", "elle: incelendi, köy kaldı (Kulaca)"),
    "TR-16-005-183839": ("kir", "elle: incelendi, köy kaldı (Şipali)"),
    "TR-16-005-183819": ("kir", "elle: eski belde idi (belde:Yeniceköy) ama kullanıcı köy dedi"),
    # Orhangazi Narlıca: eski_statu=belde:Narlıca (was a belde) but user downgraded to köy after
    # satellite review -- dense but self-contained olive-growing village (2026-09-28) -- flagged
    "TR-16-014-184623": ("kir", "elle: eski belde idi (belde:Narlıca) ama kullanıcı köy dedi"),
    # Nilüfer Yolçatı: statü köy, but a detached cluster of 5.593 (>=5.000) and DEGURBA kent;
    # user confirmed (2026-09-28)
    "TR-16-012-183471": ("kentsel_belde", "elle: kullanıcı onayladı, ayrı leke 5.593 kişi, kentsel belde"),
    # remaining Bursa "arada" rows, proposals grouped by type and accepted by the user (2026-09-28)
    "TR-16-001-183535": ("kirsal_belde", "elle: kullanıcı öneriyi onayladı, eski belde, kırsal_belde (Büyükorhan Kınık)"),
    "TR-16-001-11333": ("merkez", "elle: kullanıcı öneriyi onayladı, küçük ilçe merkezi, merkez kaldı (Büyükorhan Hocahasan)"),
    "TR-16-001-11331": ("merkez", "elle: kullanıcı öneriyi onayladı, küçük ilçe merkezi, merkez kaldı (Büyükorhan Cumhuriyet)"),
    "TR-16-001-11335": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Büyükorhan Armutçuk)"),
    "TR-16-001-11336": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Büyükorhan İsmetiye)"),
    "TR-16-001-183573": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Büyükorhan Hacılar)"),
    "TR-16-002-11352": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Gemlik Gençali)"),
    "TR-16-002-183629": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Gemlik Karacaali)"),
    "TR-16-002-183643": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Gemlik Yeniköy)"),
    "TR-16-002-183625": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Gemlik Hamidiyeköy)"),
    "TR-16-003-11367": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Gürsu Ağaköy)"),
    "TR-16-003-11368": ("kir", "elle: kullanıcı öneriyi onayladı, ilçe merkezi istisnası geçersiz, köy (Gürsu Hasanköy)"),
    "TR-16-004-11379": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Harmancık Ballısaray)"),
    "TR-16-004-11373": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Harmancık Ece)"),
    "TR-16-004-11376": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Harmancık Kepekdere)"),
    "TR-16-004-11380": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Harmancık Karaca)"),
    "TR-16-004-11378": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Harmancık Yayabaşı)"),
    "TR-16-004-11377": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Harmancık Kılavuzlar)"),
    "TR-16-004-11372": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Harmancık Çamoğlu)"),
    "TR-16-004-11375": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Harmancık Saçaklı)"),
    "TR-16-008-19991": ("merkez", "elle: kullanıcı öneriyi onayladı, küçük ilçe merkezi, merkez kaldı (Keles Yenice)"),
    "TR-16-008-19987": ("merkez", "elle: kullanıcı öneriyi onayladı, küçük ilçe merkezi, merkez kaldı (Keles Çukur)"),
    "TR-16-008-19990": ("merkez", "elle: kullanıcı öneriyi onayladı, küçük ilçe merkezi, merkez kaldı (Keles Sofular)"),
    "TR-16-008-19989": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Keles Küçük Kovacık)"),
    "TR-16-008-99408": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Keles Kirazlı)"),
    "TR-16-009-20000": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Kestel Serme)"),
    "TR-16-011-184301": ("kirsal_belde", "elle: kullanıcı öneriyi onayladı, eski belde, kırsal_belde (Mustafakemalpaşa Ovaazatlı)"),
    "TR-16-011-184291": ("kirsal_belde", "elle: kullanıcı öneriyi onayladı, eski belde, kırsal_belde (Mustafakemalpaşa Çeltikçi)"),
    "TR-16-011-184345": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Mustafakemalpaşa Hamidiyeköyü)"),
    "TR-16-013-20063": ("merkez", "elle: kullanıcı öneriyi onayladı, küçük ilçe merkezi, merkez kaldı (Orhaneli Karabekirpaşa)"),
    "TR-16-014-184663": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Orhangazi Örnekköy)"),
    "TR-16-014-184629": ("kirsal_belde", "elle: kullanıcı öneriyi onayladı, eski belde, kırsal_belde (Orhangazi Yenisölöz)"),
    "TR-16-015-11196": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Osmangazi İnkaya)"),
    "TR-16-015-11167": ("kir", "elle: kullanıcı öneriyi onayladı, ilçe merkezi istisnası geçersiz, köy (Osmangazi Armutköy)"),
    "TR-16-015-11180": ("kir", "elle: kullanıcı öneriyi onayladı, ilçe merkezi istisnası geçersiz, köy (Osmangazi Dereçavuşköy)"),
    "TR-16-016-184691": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Yenişehir Cihadiye)"),
    "TR-16-016-184787": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Yenişehir Yeniköy)"),
    "TR-16-017-183529": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Yıldırım Cumalıkızık)"),
    "TR-16-017-183527": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Yıldırım Hamamlıkızık)"),
    "TR-16-005-183707": ("kirsal_belde", "elle: kullanıcı öneriyi onayladı, eski belde, kırsal_belde (İnegöl Tahtaköprü)"),
    "TR-16-005-183721": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (İnegöl Bilalköy)"),
    "TR-16-005-183845": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (İnegöl Turgutalpköy)"),
    "TR-16-005-183875": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (İnegöl Osmaniyeköy)"),
    "TR-16-005-183887": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (İnegöl Yeniköy)"),
    # Ankara, user decisions (2026-09-28)
    # Mamak Kutludüğün, Çubuk Dumlupınar: the university campus inflates the register
    "TR-06-019-140424": ("kirsal_belde", "elle: kullanıcı, kırsal belde (Kutludüğün)"),
    "TR-06-008-2057": ("kirsal_belde", "elle: kullanıcı, kırsal belde; üniversite nüfusu şişiriyor (Dumlupınar)"),
    "TR-06-012-1653": ("kentsel_belde", "elle: kullanıcı, İncek'e bitişik kentsel belde (Gölbaşı Hacılar)"),
    "TR-06-012-1664": ("kirsal_belde", "elle: kullanıcı, kırsal belde (Gölbaşı Tulumtaş)"),
    "TR-06-008-2051": ("kirsal_belde", "elle: kullanıcı, kırsal (Çubuk Esenboğa Merkez)"),
    "TR-06-019-2092": ("kirsal_belde", "elle: kullanıcı, kırsal belde (Mamak Karşıyaka)"),
    "TR-06-019-2091": ("kirsal_belde", "elle: kullanıcı, kırsal belde (Mamak Lalahan)"),
    "TR-06-008-2027": ("kirsal_belde", "elle: kullanıcı, kırsal belde (Çubuk Akkuzulu)"),
    "TR-06-025-1905": ("kir", "elle: kullanıcı, köy (Yenimahalle Karacakaya)"),
    "TR-06-009-2075": ("merkez", "elle: kullanıcı, Elmadağ merkezi (Tatlıca)"),
    "TR-06-023-2237": ("kentsel_belde", "elle: kullanıcı, Temelli OSB yanı kentsel belde (Sincan Alcı)"),
    "TR-06-015-196407": ("kentsel_belde", "elle: kullanıcı, TUSAŞ yanı kentsel belde (Kazan Akıncı)"),
    # Kalecik town quarters, user's home district
    "TR-06-016-2140": ("merkez", "elle: kullanıcı, Kalecik merkezi (Halitcevriaslangil)"),
    "TR-06-016-2136": ("merkez", "elle: kullanıcı, Kalecik merkezi (Ahiler Yenice)"),
    "TR-06-016-2135": ("merkez", "elle: kullanıcı, Kalecik merkezi (Ahikemalşenyurt)"),
    "TR-06-016-2138": ("merkez", "elle: kullanıcı, Kalecik merkezi (Çanşa Kale)"),
    "TR-06-016-2139": ("merkez", "elle: kullanıcı, Kalecik merkezi (Halilağa Tabakhane)"),
    # Etimesgut: detached from the town's building patch (share 0); Fatih Sultan had been
    # forced to merkez by the district-centre exception
    "TR-06-010-183238": ("kentsel_belde", "elle: kullanıcı, ayrı yeni yerleşim (Etimesgut Atayurt)"),
    "TR-06-010-183242": ("kentsel_belde", "elle: kullanıcı, ayrı yeni yerleşim (Etimesgut Turkuaz)"),
    "TR-06-010-99784": ("kentsel_belde", "elle: kullanıcı, ayrı yerleşim, ilçe merkezi istisnası geçersiz (Etimesgut Fatih Sultan)"),
    "TR-06-010-1910": ("kir", "elle: kullanıcı öneriyi onayladı, ayrı yazlık yerleşim, istisna geçersiz (Etimesgut Yukarıyurtçu)"),
    "TR-06-010-1900": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Etimesgut Aşağıyurtçu)"),
    "TR-06-010-1908": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Etimesgut Şehitali)"),
    "TR-06-010-1901": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Etimesgut Balıkuyumcu)"),
    "TR-06-010-1904": ("kir", "elle: kullanıcı öneriyi onayladı, köy kaldı (Etimesgut Fevziye)"),
    # Gölbaşı: villa belt south of İncek (2015 villages, x2-5.5 growth, A+ 20-26%) is urban
    "TR-06-012-1673": ("kirsal_belde", "elle: eski belde, AATOPLU 2015 belde (Gölbaşı Bezirhane)"),
    "TR-06-012-1681": ("kirsal_belde", "elle: eski belde, AATOPLU 2015 belde (Gölbaşı Selametli Şehit Emrah)"),
    "TR-06-012-2118": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Boyalık)"),
    "TR-06-012-1674": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Soğulcak)"),
    "TR-06-012-1682": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Mahmatlıbahçe)"),
    "TR-06-012-1680": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Kırıklı)"),
    "TR-06-012-1672": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Bağiçi)"),
    "TR-06-012-2124": ("kirsal_belde", "elle: eski belde, AATOPLU 2015 belde (Gölbaşı Oyaca Yeşilçam)"),
    "TR-06-012-1683": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Tepeyurt)"),
    "TR-06-012-2123": ("kirsal_belde", "elle: eski belde, AATOPLU 2015 belde (Gölbaşı Oyaca Akarsu)"),
    "TR-06-012-1675": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Mahmatlı)"),
    "TR-06-012-1677": ("kasaba", "elle: eski belde, AATOPLU 2015 belde (Gölbaşı Karagedik Ercan)"),
    "TR-06-012-2120": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Dikilitaş)"),
    "TR-06-012-2121": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı İkizce)"),
    "TR-06-012-1676": ("kasaba", "elle: eski belde, AATOPLU 2015 belde (Gölbaşı Karagedik Aydın)"),
    "TR-06-012-1678": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Ahiboz)"),
    "TR-06-012-1679": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Günalan)"),
    "TR-06-012-1663": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Topaklı)"),
    "TR-06-012-1985": ("kirsal_belde", "elle: eski belde, AATOPLU 2015 belde (Gölbaşı Karaali Yazlık)"),
    "TR-06-012-1651": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Çayırlı)"),
    "TR-06-012-1670": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Subaşı)"),
    "TR-06-012-1666": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Yağlıpınar)"),
    "TR-06-012-1984": ("kirsal_belde", "elle: eski belde, AATOPLU 2015 belde (Gölbaşı Karaali Merkez)"),
    "TR-06-012-1671": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Gökçehüyük)"),
    "TR-06-012-1654": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Hacımuratlı)"),
    "TR-06-012-1665": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Velihimmetli)"),
    "TR-06-012-1660": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Oğulbey)"),
    "TR-06-012-1667": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Yavrucuk)"),
    "TR-06-012-1655": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Halaçlı)"),
    "TR-06-012-1659": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Koparan)"),
    "TR-06-012-1650": ("kentsel_belde", "elle: kullanıcı, villa kuşağı, istisna geçersiz (Gölbaşı Ballıkpınar)"),
    "TR-06-012-1657": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Karaoğlan)"),
    "TR-06-012-1652": ("kentsel_belde", "elle: kullanıcı, istisna yerine kullanıcı kararı (Gölbaşı Hacıhasan)"),
    "TR-06-012-1669": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Yurtbeyi)"),
    "TR-06-012-1668": ("kir", "elle: köy, AATOPLU 2015 köy (Gölbaşı Yaylabağ)"),
    "TR-06-012-1662": ("kentsel_belde", "elle: kullanıcı, villa kuşağı (Gölbaşı Taşpınar)"),
    # Mamak: user approved proposals (2026-09-29)
    "TR-06-019-181428": ("kentsel_belde", "elle: ayrı yeni yerleşim (Mamak Zirvekent)"),
    "TR-06-019-1760": ("merkez", "elle: kullanıcı, merkez (Mamak Derbent)"),
    "TR-06-019-1799": ("kir", "elle: köy, AATOPLU köy (Mamak Gökçeyurt)"),
    "TR-06-019-1801": ("kir", "elle: AATOPLU köy, istisna geçersiz (Mamak Kızılca)"),
    "TR-06-019-1803": ("kir", "elle: AATOPLU köy, istisna geçersiz (Mamak Ortaköy)"),
    "TR-06-019-1802": ("kir", "elle: köy, AATOPLU köy (Mamak Kusunlar)"),
    "TR-06-019-1806": ("kir", "elle: köy, AATOPLU köy (Mamak Bayındır)"),
    "TR-06-019-1798": ("kir", "elle: 196 kişilik ayrı yerleşim (Mamak Yukarı İmrohor)"),
    # Sincan: Temelli town quarters are one detached town; villages per AATOPLU (2026-09-29)
    "TR-06-023-2245": ("kentsel_belde", "elle: Temelli kasabası (Sincan Hürriyet)"),
    "TR-06-023-2234": ("kentsel_belde", "elle: Temelli kasabası (kullanıcı) (Sincan Cumhuriyet)"),
    "TR-06-023-2233": ("kentsel_belde", "elle: Temelli kasabası (Sincan Gazi)"),
    "TR-06-023-2235": ("kentsel_belde", "elle: Temelli kasabası (Sincan İstiklal)"),
    "TR-06-023-1833": ("merkez", "elle: kullanıcı, kent (Sincan Yeniçimşit)"),
    "TR-06-023-2244": ("kir", "elle: köy, AATOPLU köy (Sincan Beyobası)"),
    "TR-06-023-2242": ("kir", "elle: köy, AATOPLU köy (Sincan Ücret)"),
    "TR-06-023-2238": ("kir", "elle: köy, AATOPLU köy (Sincan Çokören)"),
    "TR-06-023-2243": ("kir", "elle: köy, AATOPLU köy (Sincan Yenihisar)"),
    "TR-06-023-2239": ("kir", "elle: köy, AATOPLU köy (Sincan Hisarlıkaya)"),
    "TR-06-023-2236": ("kir", "elle: köy, AATOPLU köy (Sincan Alagöz)"),
    "TR-06-023-2247": ("kir", "elle: köy, AATOPLU köy (Sincan Bacı)"),
    "TR-06-023-2240": ("kir", "elle: köy, AATOPLU köy (Sincan Malıköy)"),
    "TR-06-023-2246": ("kir", "elle: köy, AATOPLU köy (Sincan Girmeç)"),
    "TR-06-023-2241": ("kir", "elle: köy, AATOPLU köy (Sincan Türkobası)"),
    "TR-06-023-1827": ("kir", "elle: köy, AATOPLU köy (Sincan Çiçektepe)"),
    "TR-06-023-1828": ("kir", "elle: köy, AATOPLU köy (Sincan Esenler)"),
    "TR-06-023-1826": ("kir", "elle: köy, AATOPLU köy (Sincan Anayurt)"),
    "TR-06-023-1830": ("kir", "elle: köy, AATOPLU köy (Sincan Polatlar)"),
    "TR-06-023-1832": ("kir", "elle: köy, AATOPLU köy (Sincan Tatlar)"),
    "TR-06-023-1834": ("kir", "elle: köy, AATOPLU köy (Sincan Yenipeçenek)"),
    "TR-06-023-98558": ("kir", "elle: köy, AATOPLU köy (Sincan Kesiktaş)"),
    "TR-06-023-98560": ("kir", "elle: köy, AATOPLU köy (Sincan Erkeksu)"),
    "TR-06-023-1846": ("kir", "elle: köy, AATOPLU köy (Sincan Yenikayı)"),
    "TR-06-023-1841": ("kir", "elle: köy, AATOPLU köy (Sincan Akçaören)"),
    "TR-06-023-1843": ("kir", "elle: köy, AATOPLU köy (Sincan İlyakut)"),
    "TR-06-023-1845": ("kir", "elle: köy, AATOPLU köy (Sincan Mülk)"),
    "TR-06-023-1844": ("kir", "elle: köy, AATOPLU köy (Sincan İncirlik)"),
    # Sincan: user (2026-09-29)
    "TR-06-023-1829": ("kir", "elle: köy, AATOPLU köy (Sincan Osmaniye)"),
    "TR-06-023-1840": ("merkez", "elle: eski Yenikent beldesi, merkeze bitişik, semt gibi (Sincan Menderes)"),
    # Ayaş: user approved (2026-09-29)
    "TR-06-003-1950": ("kir", "elle: köy (Ayaş Tekke)"),
    "TR-06-003-1949": ("kir", "elle: köy (Ayaş Gökler)"),
    "TR-06-003-1963": ("kir", "elle: köy (Ayaş Sinanlı Cuma)"),
    "TR-06-003-1965": ("kir", "elle: köy (Ayaş Sinanlı Mahkeme)"),
    "TR-06-003-1938": ("merkez", "elle: kasabanın içinde (Ayaş Dervişimam)"),
    "TR-06-003-1937": ("merkez", "elle: kasabanın içinde (Ayaş Camiatik)"),
    "TR-06-003-1943": ("merkez", "elle: kasabanın içinde (Ayaş Ömeroğlu)"),
    "TR-06-003-177869": ("kirsal_belde", "elle: eski belde merkezi (Ayaş Oltan)"),
    "TR-06-003-1944": ("merkez", "elle: kullanıcı, AATOPLU 2015 mahalle (Ayaş Şeyhmuhittin)"),
    "TR-06-003-1939": ("merkez", "elle: kasabanın içinde (Ayaş Ferahfaki)"),
    "TR-06-003-1964": ("kir", "elle: köy (Ayaş Sinanlı Hocasinan)"),
    "TR-06-003-1952": ("merkez", "elle: kullanıcı, AATOPLU 2015 mahalle (Ayaş Emine Tevfika Ayaşlı)"),
    "TR-06-003-1941": ("merkez", "elle: kasabanın içinde (Ayaş Hacırecep)"),
    "TR-06-003-1940": ("merkez", "elle: kasabanın içinde (Ayaş Hacımemi)"),
    "TR-06-003-1942": ("merkez", "elle: kasabanın içinde (Ayaş Hacıveli)"),
    "TR-06-003-1945": ("kir", "elle: köy (Ayaş Başayaş)"),
    "TR-06-003-177887": ("kir", "elle: köy (Ayaş Bayram)"),
    "TR-06-003-1946": ("kir", "elle: köy (Ayaş Başbereket)"),
    "TR-06-003-177885": ("kir", "elle: köy (Ayaş Gökçebağ)"),
    "TR-06-003-1951": ("kir", "elle: köy (Ayaş Ulupınar)"),
    "TR-06-003-177889": ("kir", "elle: köy (Ayaş Ortabereket)"),
    "TR-06-003-1954": ("kir", "elle: köy (Ayaş Çanıllı Uluyol)"),
    "TR-06-003-1953": ("kir", "elle: köy (Ayaş Çanıllı Çiğdemci)"),
    "TR-06-003-177891": ("kir", "elle: köy (Ayaş Pınaryaka)"),
    "TR-06-003-177895": ("kir", "elle: köy (Ayaş Bayat)"),
    "TR-06-003-177893": ("kir", "elle: köy (Ayaş Evci)"),
    # Yenimahalle: user (2026-09-29)
    "TR-06-025-180658": ("kentsel_belde", "elle: ayrı yeni yerleşim (Yenimahalle Kuzey Yıldızı)"),
    "TR-06-025-1906": ("kir", "elle: köy, AATOPLU köy (Yenimahalle Memlik)"),
    "TR-06-025-1873": ("merkez", "elle: kullanıcı, kentin içinde (Yenimahalle İvedikköy)"),
    "TR-06-025-1911": ("kentsel_belde", "elle: kullanıcı, 2015 köy, bugün ayrı leke 6.617 (Yenimahalle Yuvaköy)"),
    # Bala: matches AATOPLU 2015 fully, user approved (2026-09-29)
    "TR-06-004-1981": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Kesikköprü)"),
    "TR-06-004-1982": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Kesikköprü Kızılırmak)"),
    "TR-06-004-1983": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Kesikköprü Erdemli)"),
    "TR-06-004-1994": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Ahmetçayırı)"),
    "TR-06-004-177897": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Afşar)"),
    "TR-06-004-1973": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Yeniköy)"),
    "TR-06-004-1975": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Çiğdemli)"),
    "TR-06-004-1967": ("merkez", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala İsmetpaşa)"),
    "TR-06-004-1992": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Yöreli)"),
    "TR-06-004-1968": ("merkez", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Kartaltepe)"),
    "TR-06-004-1966": ("merkez", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Göztepe)"),
    "TR-06-004-99986": ("merkez", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Hamidiye)"),
    "TR-06-004-1976": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Büyükboyalık)"),
    "TR-06-004-1969": ("merkez", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Şentepe)"),
    "TR-06-004-1974": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Küçükboyalık)"),
    "TR-06-004-1970": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Abazlı)"),
    "TR-06-004-1972": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Çatalçeşme)"),
    "TR-06-004-1971": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Tolköy)"),
    "TR-06-004-1978": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Köseli)"),
    "TR-06-004-1977": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Kerişli)"),
    "TR-06-004-914390": ("kir", "elle: AATOPLU 2015 ile aynı, kullanıcı onayladı (Bala Afşar Dedebey)"),
    # Akyurt: user (2026-09-29)
    "TR-06-001-1916": ("merkez", "elle: kullanıcı, kasaba ona kadar büyüdü (Akyurt Galaba)"),
    "TR-06-001-1925": ("kir", "elle: köy, AATOPLU köy (Akyurt Çardakbağı)"),
    "TR-06-001-1929": ("kir", "elle: köy, AATOPLU köy (Akyurt Güzelhisar)"),
    "TR-06-001-1927": ("kir", "elle: köy, AATOPLU köy (Akyurt Teberik)"),
    "TR-06-001-1926": ("kir", "elle: köy, AATOPLU köy (Akyurt Çınar)"),
    "TR-06-001-1935": ("kir", "elle: ayrı yerleşim, AATOPLU köy, istisna geçersiz (Akyurt Saracalar)"),
    "TR-06-001-1932": ("kir", "elle: köy, AATOPLU köy (Akyurt Karacalar)"),
    "TR-06-001-1921": ("kir", "elle: köy, AATOPLU köy (Akyurt Samut)"),
    "TR-06-001-1936": ("kir", "elle: köy, AATOPLU köy (Akyurt Şeyhler)"),
    "TR-06-001-1920": ("kir", "elle: köy, AATOPLU köy (Akyurt Balıkhisar)"),
    "TR-06-001-1933": ("kir", "elle: köy, AATOPLU köy (Akyurt Karayatak)"),
    "TR-06-001-1934": ("kir", "elle: köy, AATOPLU köy (Akyurt Kızık)"),
    "TR-06-001-1922": ("kir", "elle: köy, AATOPLU köy (Akyurt Büğdüz)"),
    "TR-06-001-1924": ("kir", "elle: köy, AATOPLU köy (Akyurt Çam)"),
    "TR-06-001-1931": ("kir", "elle: köy, AATOPLU köy (Akyurt Karacakaya)"),
    "TR-06-001-1930": ("kir", "elle: köy, AATOPLU köy (Akyurt Haydar)"),
    "TR-06-001-1923": ("kir", "elle: köy, AATOPLU köy (Akyurt Cücük)"),
    "TR-06-001-1928": ("kir", "elle: köy, AATOPLU köy (Akyurt Elecik)"),
    # Elmadağ: Hasanoğlan is one town of six quarters, 15.193 (user, 2026-09-29)
    "TR-06-009-2085": ("kentsel_belde", "elle: Hasanoğlan kasabası (Elmadağ Hasanoğlan Bahçelievler)"),
    "TR-06-009-2089": ("kentsel_belde", "elle: Hasanoğlan kasabası (Elmadağ Muzaffer Ekşi)"),
    "TR-06-009-2087": ("kentsel_belde", "elle: Hasanoğlan kasabası (Elmadağ Hasanoğlan Havuzbaşı)"),
    "TR-06-009-2086": ("kentsel_belde", "elle: Hasanoğlan kasabası (Elmadağ Hasanoğlan Fatih)"),
    "TR-06-009-2090": ("kentsel_belde", "elle: Hasanoğlan kasabası, istisna geçersiz (Elmadağ Şehitlik)"),
    "TR-06-009-2088": ("kentsel_belde", "elle: Hasanoğlan kasabası (Elmadağ İstasyon)"),
    "TR-06-009-2084": ("merkez", "elle: kullanıcı, merkez (Elmadağ Yenimahalle)"),
    "TR-06-009-2094": ("kirsal_belde", "elle: kullanıcı, eski Yeşildere beldesi (Elmadağ Seyitcemali)"),
    "TR-06-009-2093": ("kirsal_belde", "elle: eski Yeşildere beldesi (Elmadağ Yeşildere Fatih)"),
    "TR-06-009-2074": ("kir", "elle: köy (Elmadağ Lalabel)"),
    "TR-06-009-2081": ("kir", "elle: köy, AATOPLU köy (Elmadağ Kayadibi)"),
    "TR-06-009-2080": ("kir", "elle: köy, AATOPLU köy (Elmadağ Akçaali)"),
    "TR-06-009-2082": ("kir", "elle: köy, AATOPLU köy (Elmadağ Süleymanlı)"),
    "TR-06-009-2083": ("kir", "elle: köy, AATOPLU köy (Elmadağ Tekke)"),
    # Pursaklar: Saray and Altınova are separate towns (user, 2026-09-29)
    "TR-06-022-1739": ("kentsel_belde", "elle: Saray kasabası (Pursaklar Saray Fatih)"),
    "TR-06-022-1742": ("kentsel_belde", "elle: Saray kasabası (Pursaklar Saray Cumhuriyet)"),
    "TR-06-022-1741": ("kentsel_belde", "elle: Saray kasabası, AATOPLU mahalle (Pursaklar Saray Osmangazi)"),
    "TR-06-022-139854": ("kentsel_belde", "elle: Altınova kasabası (Pursaklar Altınova)"),
    "TR-06-022-1511": ("kentsel_belde", "elle: Altınova kasabası (Pursaklar Yıldırım Beyazıt)"),
    "TR-06-022-1510": ("kentsel_belde", "elle: Altınova kasabası (Pursaklar Peçenek)"),
    "TR-06-022-2061": ("kir", "elle: köy (Pursaklar Sirkeli Yeşilova)"),
    "TR-06-022-2062": ("kir", "elle: köy (Pursaklar Sirkeli Yeşilyurt)"),
    "TR-06-022-2068": ("kir", "elle: köy (Pursaklar Kösrelikkızığı)"),
    "TR-06-022-2066": ("kir", "elle: köy (Pursaklar Karşıyaka)"),
    "TR-06-022-1512": ("kir", "elle: köy (Pursaklar Yeni Karaköy)"),
    "TR-06-022-2063": ("kir", "elle: köy (Pursaklar Abadan)"),
    "TR-06-022-2067": ("kir", "elle: köy (Pursaklar Yuva)"),
    "TR-06-022-2065": ("kir", "elle: köy (Pursaklar Karaköy)"),
    # Pursaklar: user (2026-09-29)
    "TR-06-022-1740": ("kir", "elle: kullanıcı, köy karakteri, nüfus 18 yıldır sabit, istisna geçersiz (Pursaklar Saray Gümüşoluk)"),
    # Ankara remaining districts: bulk-approved where AATOPLU 2015 agrees and pop < 1.000 (user, 2026-09-29)
    "TR-06-002-1505": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Altındağ Tatlar)"),
    "TR-06-002-1503": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Altındağ Kavaklı)"),
    "TR-06-002-1504": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Altındağ Peçenek)"),
    "TR-06-002-1509": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Altındağ Gicik)"),
    "TR-06-002-1501": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Altındağ Aydıncık)"),
    "TR-06-005-177971": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Beypazarı Kırbaşı)"),
    "TR-06-005-2003": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Beypazarı Rüstempaşa)"),
    "TR-06-005-177973": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Beypazarı Uruş)"),
    "TR-06-005-177969": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Beypazarı Karaşar)"),
    "TR-06-006-178183": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çamlıdere Beşbeyler)"),
    "TR-06-006-2019": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Çamlıdere Ömerağa)"),
    "TR-06-006-2018": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Çamlıdere Orta)"),
    "TR-06-006-2017": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Çamlıdere Körler)"),
    "TR-06-006-2021": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Çamlıdere Yayalar)"),
    "TR-06-006-2020": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Çamlıdere Yahyalar)"),
    "TR-06-006-2015": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Çamlıdere Beyler)"),
    "TR-06-007-1987": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çankaya Çavuşlu)"),
    "TR-06-007-1989": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çankaya Karahasanlı)"),
    "TR-06-007-1986": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çankaya Akarlar)"),
    "TR-06-007-1993": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çankaya Yayla)"),
    "TR-06-007-1991": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çankaya Tohumlar)"),
    "TR-06-007-1990": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çankaya Kömürcü)"),
    "TR-06-007-1988": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çankaya Evciler)"),
    "TR-06-007-1617": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çankaya Karataş)"),
    "TR-06-007-1591": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Çankaya Orta İmrahor)"),
    "TR-06-008-2058": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Kızılca)"),
    "TR-06-008-2055": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk İkipınar)"),
    "TR-06-008-2053": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Melikşah)"),
    "TR-06-008-2042": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Taşpınar)"),
    "TR-06-008-2031": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk İmamhüseyin)"),
    "TR-06-008-2037": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Küçükali)"),
    "TR-06-008-2044": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Yazır)"),
    "TR-06-008-2056": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Kutuören)"),
    "TR-06-008-2064": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Gümüşyayla)"),
    "TR-06-008-2043": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Tuğla)"),
    "TR-06-008-2032": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Kapaklı)"),
    "TR-06-008-2039": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Ömercik)"),
    "TR-06-008-2026": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Akbayır)"),
    "TR-06-008-2035": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Kargın)"),
    "TR-06-008-178277": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Mutlu)"),
    "TR-06-008-2033": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Karaağaç)"),
    "TR-06-008-2036": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Kızılöz)"),
    "TR-06-008-2034": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Karaman)"),
    "TR-06-008-2045": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Yazlıca)"),
    "TR-06-008-2029": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Camili)"),
    "TR-06-008-2041": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Tahtayazı)"),
    "TR-06-008-99931": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Çubuk Yukarı Çavundur)"),
    "TR-06-011-2098": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Evren Yeni)"),
    "TR-06-011-2097": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Evren Şerafettin Yılmaz)"),
    "TR-06-011-2095": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Evren Esentepe)"),
    "TR-06-011-2096": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Evren Modern)"),
    "TR-06-013-197249": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Güdül Güneyce)"),
    "TR-06-013-178311": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Güdül Çağa)"),
    "TR-06-013-2099": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Güdül Aşağı)"),
    "TR-06-013-2101": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Güdül Yeni)"),
    "TR-06-013-2100": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Güdül Emirler)"),
    "TR-06-013-178315": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Güdül Yeşilöz)"),
    "TR-06-013-2102": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Güdül Yukarı)"),
    "TR-06-013-178313": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Güdül Sorgun)"),
    "TR-06-014-178369": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Haymana Bumsuz)"),
    "TR-06-014-178371": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Haymana Yurtbeyli)"),
    "TR-06-014-178367": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Haymana Balçıkhisar)"),
    "TR-06-014-178363": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Haymana Çalış)"),
    "TR-06-014-178505": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Haymana Deveci)"),
    "TR-06-016-2151": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Yalımköy)"),
    "TR-06-016-2149": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Gölköy)"),
    "TR-06-016-2150": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Şeyhmahmut)"),
    "TR-06-016-2137": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Cuma Saray)"),
    "TR-06-016-2146": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Yenidoğan Yeşilyurt)"),
    "TR-06-016-2148": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Arkbürk)"),
    "TR-06-016-178575": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Eskiköy)"),
    "TR-06-016-2158": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Kızılkaya)"),
    "TR-06-016-2155": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Çiftlikköy)"),
    "TR-06-016-178579": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Buğra)"),
    "TR-06-016-2153": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Akkaynak)"),
    "TR-06-016-2152": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Akcataş)"),
    "TR-06-016-2157": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Karahöyük)"),
    "TR-06-016-178577": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Değirmenkaya)"),
    "TR-06-016-2161": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Yılanlı)"),
    "TR-06-016-2156": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Hasayaz)"),
    "TR-06-016-2160": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Yeniçöte)"),
    "TR-06-016-2159": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kalecik Tavşancık)"),
    "TR-06-017-1737": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Keçiören Kösrelik)"),
    "TR-06-017-1738": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Keçiören Sarıbeyler)"),
    "TR-06-017-1735": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Keçiören Çalseki)"),
    "TR-06-017-1736": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Keçiören Bağlum Güzelyurt)"),
    "TR-06-018-178613": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Kızılcahamam Çeltikçi)"),
    "TR-06-018-2200": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Kızılcahamam Gazi Mustafa Kemalpaşa)"),
    "TR-06-020-178821": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Nallıhan Sarıyar)"),
    "TR-06-024-179139": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Şereflikoçhisar Çalören)"),
    "TR-06-024-179141": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Şereflikoçhisar Devekovan)"),
    "TR-06-024-179229": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Şereflikoçhisar Yeşilyurt)"),
    "TR-06-024-2262": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Şereflikoçhisar Şeyh Kuyusu)"),
    "TR-06-024-179145": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Şereflikoçhisar Kacarlı)"),
    "TR-06-024-179143": ("kirsal_belde", "elle: AATOPLU 2015 ile aynı, toplu onay (Şereflikoçhisar Gülhüyük)"),
    # Kahramankazan (Kazan in 2015): bulk-approved where AATOPLU 2015 agrees (user, 2026-09-29)
    "TR-06-015-2176": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Dağyaka)"),
    "TR-06-015-2189": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Saray)"),
    "TR-06-015-2184": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Kışla)"),
    "TR-06-015-2186": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Orhaniye)"),
    "TR-06-015-2174": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Bitik)"),
    "TR-06-015-2181": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan İmrendi)"),
    "TR-06-015-2173": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Aydın)"),
    "TR-06-015-2175": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Çimşit)"),
    "TR-06-015-2177": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Emirgazi)"),
    "TR-06-015-2178": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Fethiye)"),
    "TR-06-015-2185": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Kumpınar)"),
    "TR-06-015-2193": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Yazıbeyli)"),
    "TR-06-015-2183": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Karalar)"),
    "TR-06-015-2172": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Alpagut)"),
    "TR-06-015-2182": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan İymir)"),
    "TR-06-015-2169": ("merkez", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Yavuz Sultan Selim)"),
    "TR-06-015-2171": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Ahi)"),
    "TR-06-015-2179": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Günbaşı)"),
    "TR-06-015-2188": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Sancar)"),
    "TR-06-015-2187": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Peçenek)"),
    "TR-06-015-2191": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Uçarı)"),
    "TR-06-015-2180": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan İçören)"),
    "TR-06-015-2194": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Çalta)"),
    "TR-06-015-2190": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Sarılar)"),
    "TR-06-015-2192": ("kir", "elle: AATOPLU 2015 ile aynı, toplu onay (Kahramankazan Yayalar)"),
    # Çubuk: village texture (more buildings than dwellings, falling population), AATOPLU köy (user, 2026-09-29)
    "TR-06-008-2028": ("kir", "elle: köy dokusu, AATOPLU köy (Çubuk Aşağıçavundur)"),
    "TR-06-008-2054": ("kir", "elle: köy dokusu, AATOPLU köy (Çubuk Güldarpı)"),
    "TR-06-008-2040": ("kir", "elle: kasabaya bitişik ama köy (kullanıcı) (Çubuk Sünlü)"),
    "TR-06-008-2025": ("kir", "elle: köy dokusu, AATOPLU köy (Çubuk Ağılcık)"),
    "TR-06-008-2030": ("kir", "elle: köy dokusu, AATOPLU köy (Çubuk Gökçedere)"),
    "TR-06-008-2052": ("kir", "elle: AATOPLU köy (Çubuk Yenice)"),
    # Çankaya: AATOPLU 2015 (user, 2026-09-29)
    "TR-06-007-1607": ("kir", "elle: köy dokusu, AATOPLU köy (Çankaya Yeşilkent)"),
    "TR-06-007-1618": ("kasaba", "elle: AATOPLU belde, 3.801 kişi (Çankaya Yakupabdal)"),
    # Çamlıdere: AATOPLU 2015
    "TR-06-006-2016": ("merkez", "elle: AATOPLU mahalle (Çamlıdere Kayabaşı)"),
    # Kahramankazan: AATOPLU 2015
    "TR-06-015-2166": ("merkez", "elle: AATOPLU mahalle (Kahramankazan Kanuni Sultan Süleyman)"),
    "TR-06-015-2170": ("merkez", "elle: AATOPLU mahalle (Kahramankazan Yıldırımbeyazıt)"),
    # Beypazarı: AATOPLU 2015
    "TR-06-005-2004": ("merkez", "elle: AATOPLU mahalle (Beypazarı Yeşilağaç)"),
    # Haymana: AATOPLU 2015
    "TR-06-014-178465": ("merkez", "elle: AATOPLU mahalle (Haymana Yeniköy)"),
    "TR-06-014-197931": ("kir", "elle: köy (Haymana Baltalin)"),
    # Nallıhan: AATOPLU 2015
    "TR-06-020-178825": ("merkez", "elle: AATOPLU mahalle (Nallıhan Akdere)"),
    # Polatlı: AATOPLU 2015
    "TR-06-021-178977": ("kasaba", "elle: AATOPLU köy, ayrı leke 2.346 (Polatlı Basrı)"),
    # Şereflikoçhisar: AATOPLU 2015
    "TR-06-024-98870": ("merkez", "elle: AATOPLU mahalle (Şereflikoçhisar Mehmet Akif Ersoy)"),
}
# bulk decisions for the other provinces, written by aatoplu_onay.py; a hand entry above wins
_bulk = Path(__file__).parent / "elle_aatoplu.csv"
if _bulk.exists():
    for _r in csv.DictReader(_bulk.open(encoding="utf-8")):
        ELLE.setdefault(_r["area_id"], (_r["sinif"], _r["not"]))
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
