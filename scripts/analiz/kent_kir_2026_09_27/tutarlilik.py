"""Consistency of the final urban/rural list against every other source, Türkiye-wide.
Reads only; writes nothing but its own report files.

usage: tutarlilik.py

Per neighbourhood/village (2025 ADNKS population), our class (kent_<p>_son.csv) beside
  sources  resmi (TÜİK legal status outside metropolitan provinces, şehir = urban), endeksa_tip
           (Endeksa BELEDİYE MAHALLESİ / KÖY, same scope), haritatr (merkez / köyler), degurba (EU), aatoplu (user's 2015 list,
           label() from aatoplu_onay.py), kullanici (user's 8-province files, kullanici_fark)
  profile  growth 2013->2025, dwellings per building and persons per building (building
           texture / sprawl), men per woman and 65+ share (Endeksa 2024), institutional and
           foreign head counts (_kurum_tespit.csv)
A class is "profile-inconsistent" when an urban place has village texture and a shrinking,
old population, or a rural place has apartment texture and a growing one.

Writes C:/veri-ham/analiz/kent_kir/_tutarlilik_{mahalle,il,profil_celiski}.csv.
"""
import json
import sys
from pathlib import Path

import duckdb
import polars as pl

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.argv = [sys.argv[0], "06"]  # il.py wants a plate; only wh() is used
from il import wh  # noqa: E402

# the name matcher of aatoplu_onay.py without running its decision pass
_src = (HERE / "aatoplu_onay.py").read_text(encoding="utf-8").split("\nplates = ")[0]
A = {"__file__": str(HERE / "aatoplu_onay.py")}
exec(compile(_src, "aatoplu_onay.py", "exec"), A)
BASE, KENT, label, prov, IL_ALIAS = A["BASE"], A["KENT"], A["label"], A["prov"], A["IL_ALIAS"]

plates = sorted(p.name for p in BASE.iterdir() if (p / f"kent_{p.name}_son.csv").exists())
ser = duckdb.sql("""select area_id, sum(value) filter (where year(period_start)=2013) y13,
    sum(value) filter (where year(period_start)=2025) y25 from read_parquet('C:/veri/public/fact.parquet')
    where indicator_id='population' and area_level in ('neighbourhood','village') group by 1""").pl()
POP = {r["area_id"]: (r["y13"], r["y25"]) for r in ser.iter_rows(named=True)}
kurum = {r["area_id"]: r for r in pl.read_csv(BASE / "_kurum_tespit.csv", infer_schema_length=0).iter_rows(named=True)}
END = {}
for fn in Path("C:/veri-ham/endeksa/demography").glob("TR-*.json"):
    for k, v in json.loads(fn.read_text(encoding="utf-8")).items():
        e = v.get("demography") or {}
        if e.get("PopulationTotal"):
            END[f"{fn.stem}-{k}"] = e


def endeksa(aid):
    e = END.get(aid)
    if not e:
        did, code = aid.rsplit("-", 1)
        e = END.get(f"{did}-{int(code) + 2000000}") if code.isdigit() else None
    return e or {}


rows = []
for p in plates:
    son = pl.read_csv(BASE / p / f"kent_{p}_son.csv", infer_schema_length=0)
    ik = {r["area_id"]: r for r in pl.read_csv(BASE / p / f"kent_{p}_ikili.csv", infer_schema_length=0).iter_rows(named=True)}
    fark = BASE / p / f"kullanici_fark_{p}.csv"
    kf = {(r["district"], r["name"]) for r in pl.read_csv(fark, infer_schema_length=0).iter_rows(named=True)} if fark.exists() else None
    il = IL_ALIAS.get(prov[p], prov[p])
    for r in son.filter(pl.col("son_sinif") != "osb").iter_rows(named=True):
        wid = wh(r["area_id"])
        y13, y25 = POP.get(wid, (None, None))
        n = y25 or 0
        lab = label(il, r["district"], r["name"], r["eski_statu"])
        k = kurum.get(wid)
        e = endeksa(r["area_id"]) or endeksa(wid)
        b = float(r["buildings"] or 0)
        dw = float(e.get("HousingCount") or 0)
        en = e.get("PopulationTotal") or 0
        m = e.get("PopulationMale") or 0
        rows.append(dict(plate=p, il=prov[p], district=r["district"], name=r["name"], area_id=wid, pop=n, sinif=r["son_sinif"],
                         biz=r["son_sinif"] in KENT,
                         # metropolitan provinces have no legal şehir/köy split any more ("bsb")
                         resmi=(ik[r["area_id"]]["resmi"] == "sehir") if r["area_id"] in ik and ik[r["area_id"]]["resmi"] not in (None, "", "bsb") else None,
                         haritatr=True if r["haritatr"] == "merkez" else False if r["haritatr"] == "koyler" else None,
                         endeksa_tip=None if not e.get("DistrictType") or ik.get(r["area_id"], {}).get("resmi") == "bsb"
                         else e["DistrictType"] == "BELEDİYE MAHALLESİ",
                         degurba=("KENT" in r["degurba"]) if r["degurba"] else None,
                         aatoplu=None if lab in (None, "Belde") else lab == "Mahalle",
                         kullanici=None if kf is None else (r["district"], r["name"]) not in kf,
                         buyume=(y25 / y13) if y13 and y25 else None,
                         konut_bina=dw / b if b and dw else None, kisi_bina=n / b if b else None,
                         ek=m / (en - m) if en > m > 0 else None,
                         y65=(e.get("Age_65_Total") or 0) / en if en else None,
                         kurum=int(float(k["kurum_tahmini"])) if k else 0,
                         yabanci=int(float(k["yabanci_tahmini"] or 0)) if k else 0))
d = pl.DataFrame(rows, infer_schema_length=None)
d.write_csv(BASE / "_tutarlilik_mahalle.csv")

T, K = d["pop"].sum(), d.filter(pl.col("biz"))["pop"].sum()
print(f"nüfus {T:,.0f} | kent %{K / T * 100:.1f} | kurum {d['kurum'].sum():,} | yabancı {d['yabanci'].sum():,} "
      f"| kurum dışı kent %{(K - d.filter(pl.col('biz'))['kurum'].sum()) / (T - d['kurum'].sum()) * 100:.1f}")
for c in ("resmi", "endeksa_tip", "haritatr", "degurba", "aatoplu", "kullanici"):
    x = d.filter(pl.col(c).is_not_null())
    same = x.filter(pl.col("kullanici")) if c == "kullanici" else x.filter(pl.col("biz") == pl.col(c))
    share = "" if c == "kullanici" else f" | kaynağın kent payı %{x.filter(pl.col(c))['pop'].sum() / x['pop'].sum() * 100:.1f}"
    print(f"{c}: {len(x)} birim, uyum %{len(same) / len(x) * 100:.1f} sayı / %{same['pop'].sum() / x['pop'].sum() * 100:.1f} nüfus{share}")

# class profiles
print("profil (ortanca):")
print(d.filter(pl.col("pop") >= 200).group_by("biz").agg(
    pl.col("buyume").median().round(2), pl.col("konut_bina").median().round(2), pl.col("kisi_bina").median().round(2),
    pl.col("ek").median().round(2), pl.col("y65").median().round(3), pl.len()).rows())
prof = d.filter(pl.col("pop") >= 500).with_columns(
    pl.when(pl.col("biz") & (pl.col("konut_bina") < 1) & (pl.col("buyume") <= 1.0) & (pl.col("y65") >= 0.2))
    .then(pl.lit("kent ama köy profili")).when(~pl.col("biz") & (pl.col("konut_bina") >= 3) & (pl.col("buyume") >= 1.3))
    .then(pl.lit("kır ama kent profili")).otherwise(None).alias("celiski")).filter(pl.col("celiski").is_not_null())
prof = prof.with_columns((pl.col("kurum") > 0.3 * pl.col("pop")).alias("kurum_agirlikli"))
prof.sort("pop", descending=True).write_csv(BASE / "_tutarlilik_profil_celiski.csv")
print("profil çelişkisi:", prof.group_by("celiski", "kurum_agirlikli").agg(pl.len(), pl.col("pop").sum()).rows())
src = ["resmi", "haritatr", "degurba", "aatoplu"]
d2 = d.with_columns(pl.sum_horizontal([(pl.col(c).is_not_null() & (pl.col(c) != pl.col("biz"))).cast(pl.Int8) for c in src]).alias("karsi"))
print("karşı çıkan kaynak sayısı (0-4):", d2.group_by("karsi").agg(pl.len(), pl.col("pop").sum()).sort("karsi").rows())
g = d2.group_by("plate", "il").agg(
    pl.col("pop").sum().alias("nufus"), (pl.col("pop").filter(pl.col("biz")).sum() / pl.col("pop").sum() * 100).round(1).alias("kent"),
    (pl.col("pop").filter(pl.col("karsi") >= 2).sum() / pl.col("pop").sum() * 100).round(1).alias("iki_kaynak_karsi"))
g.sort("iki_kaynak_karsi", descending=True).write_csv(BASE / "_tutarlilik_il.csv")
print("en tutarsız:", g.sort("iki_kaynak_karsi", descending=True).head(6).select("il", "kent", "iki_kaynak_karsi").rows())
print("en tutarlı:", g.sort("iki_kaynak_karsi").head(6).select("il", "kent", "iki_kaynak_karsi").rows())
