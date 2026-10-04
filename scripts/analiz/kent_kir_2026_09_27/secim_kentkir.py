"""Election results of one province split by the building-based urban/rural class.

Neighbourhood results come from the web tiles (public/tiles/secim-<e>-mahalle-TR-<plate>.json,
keyed by today's area_id). Institutional ballot boxes (votes >= registered + 20)
are left out -- a prison box skews its neighbourhood; the 1-4 extra votes of small
villages are poll workers and stay.

usage: secim_kentkir.py 16 <dir with kent_16_ikili.csv>
"""

import json, sys
from pathlib import Path
import polars as pl

import sys as _s; from pathlib import Path as _P; _s.path.insert(0, str(_P(__file__).parent))
from il import PLATE, YEAR, D, ROOT, NAME, IL_UP, PTT_IL, SLUG, LOCAL24, wh, geo_code  # noqa: E402

TILES = Path("C:/veri/public/tiles")
ELECTIONS = ["mv2015k", "mv2018", "mv2023", "cb2023t2", LOCAL24]
cls = pl.read_csv(D / f"kent_{PLATE}_ikili.csv", infer_schema_length=0).select("area_id", "district", "kent_kir", "son_sinif")

rows, dropped = [], []
for e in ELECTIONS:
    for aid, v in json.loads((TILES / f"secim-{e}-mahalle-TR-{PLATE}.json").read_text(encoding="utf-8")).items():
        if v["o"] >= v["k"] + 20:
            dropped.append((e, aid, v["ad"], v["k"], v["o"]))
            continue
        wa = wh(aid) if "~" not in aid else aid
        if wa.endswith("-0"):  # a registry code of exactly 2,000,000 collides with the
            continue  # island/lake placeholder id; the settlement has no geometry to attach to
        for party, n in v["v"].items():
            rows.append(dict(election=e, area_id=wa, party=party, votes=n))
# a few tile keys are unresolved names ("TR-16-003~kumlukalani"): match by name within
# the district, else the known central quarter (Kayhan, merged after 2015) is urban and
# the rest -- all small villages -- rural
def fold(t):
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu"):
        t = t.replace(a, b)
    return "".join(ch for ch in t if ch.isalpha())


full = pl.read_csv(D / f"kent_{PLATE}_ikili.csv", infer_schema_length=0)
byname = {}
for r in full.iter_rows(named=True):
    byname.setdefault(r["area_id"].rsplit("-", 1)[0], []).append((fold(r["name"]), r))
extra = []
for key in {r["area_id"] for r in rows if "~" in r["area_id"]}:
    did, nm = key.split("~")
    nm = nm.removesuffix("koyu").removesuffix("i") if nm not in ("kayhan",) else nm
    hit = [r for n, r in byname.get(did, []) if n.startswith(nm) or nm.startswith(n)]
    if hit:
        kk, sc = hit[0]["kent_kir"], hit[0]["son_sinif"]
    else:
        kk, sc = ("kent", "merkez") if nm == "kayhan" else ("kır", "kir")
    extra.append(dict(area_id=key, district=None, kent_kir=kk, son_sinif=sc))
    print("adla eşleşen:", key, "->", hit[0]["name"] if hit else "(yok)", kk)
cls = pl.concat([cls, pl.DataFrame(extra, schema=cls.schema)])
d = pl.DataFrame(rows).join(cls, on="area_id", how="left")
missing = d.filter(pl.col("kent_kir").is_null())["area_id"].unique().to_list()
if missing:
    # a whole district can be absent from kent_<p>_son.csv when kent_il.py found no
    # building under 5,000 m2 inside it (tiny/edge districts, e.g. Abana): its votes
    # cannot be classified, so they are dropped and the gap is logged, not fatal
    (D / f"secim_{PLATE}_eksik_mahalle.txt").write_text(chr(10).join(missing), encoding="utf-8")
    print(f"sınıfsız {len(missing)} mahalle atlandı (bkz. secim_{PLATE}_eksik_mahalle.txt)")
print("dışlanan kurum sandığı:", dropped)
d = d.filter(pl.col("kent_kir").is_not_null())


def shares(by):
    t = d.group_by("election", *by, "party").agg(pl.col("votes").sum())
    t = t.with_columns((pl.col("votes") / pl.col("votes").sum().over("election", *by) * 100).round(1).alias("pay"))
    return t


shares(["kent_kir"]).write_csv(D / f"secim_{PLATE}_kentkir.csv")
shares(["son_sinif"]).write_csv(D / f"secim_{PLATE}_sinif.csv")
shares(["district", "kent_kir"]).write_csv(D / f"secim_{PLATE}_ilce_kentkir.csv")
print("yazıldı", D)
