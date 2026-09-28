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
