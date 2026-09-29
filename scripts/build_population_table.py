"""Population by year for every province, district, belde and neighbourhood/village, for the
ranking page web/nufus.html.

usage: build_population_table.py [--fact PATH]

Levels
  province, district  ADNKS district totals (sum of the age x sex rows), 2007-2025
  neighbourhood       every neighbourhood and village id with its own years: ids of 2007-2012
                      and of 2013-2025 are different registries, so a place renumbered in
                      2013 shows as two rows, each with its own span
  belde               the belde a neighbourhood belonged to in 2013 (eski_statu in the
                      urban/rural list, C:/veri-ham/analiz/kent_kir/<p>/kent_<p>_son.csv),
                      summed 2013-2025; a belde's quarters are also listed as neighbourhoods

Writes public/nufus_birimler.json (git-ignored, ~8 MB):
  years, provinces [[id, name]], districts [[id, name, province index]],
  settlements [name], units [[level, name, district index, first year index, [population ...],
  settlement index (neighbourhoods/villages only, -1 when unknown -- ids of 2007-2012)]]
"""
import json
import sys
from pathlib import Path

import duckdb
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
FACT = sys.argv[sys.argv.index("--fact") + 1] if "--fact" in sys.argv else "C:/veri/public/fact.parquet"
KK = Path("C:/veri-ham/analiz/kent_kir")
YEARS = list(range(2007, 2026))

areas = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr.csv", infer_schema_length=0)
prov = areas.filter(pl.col("area_level") == "province").sort("area_id")
dist = pl.read_csv(ROOT / "src/veriatlas/data/areas_tr_districts.csv", infer_schema_length=0).sort("area_id")
P = {r["area_id"]: i for i, r in enumerate(prov.iter_rows(named=True))}
D = {r["area_id"]: i for i, r in enumerate(dist.iter_rows(named=True))}

pop = duckdb.sql(f"""select area_id, area_level, year(period_start) y, sum(value) v from read_parquet('{FACT}')
  where indicator_id='population' and area_level in ('district','neighbourhood','village') group by 1,2,3""").pl()
series = {}
for r in pop.iter_rows(named=True):
    series.setdefault((r["area_id"], r["area_level"]), {})[r["y"]] = int(r["v"])


def pack(s):
    ys = [y for y in YEARS if y in s]
    if not ys:
        return None
    first, last = YEARS.index(ys[0]), YEARS.index(ys[-1])
    return first, [s.get(YEARS[i]) for i in range(first, last + 1)]


names = {}
for f, suffix in (("areas_tr_neighbourhoods.csv", " Mah."), ("areas_tr_villages.csv", " Köy.")):
    for r in pl.read_csv(ROOT / "src/veriatlas/data" / f, infer_schema_length=0).iter_rows(named=True):
        names[r["area_id"]] = r["name_tr"].removesuffix(suffix).strip()

sys.path.insert(0, str(ROOT / "scripts/analiz/kent_kir_2026_09_27"))
_argv, sys.argv = sys.argv, [sys.argv[0], "06"]
from il import wh  # noqa: E402

sys.argv = _argv
# settlement ("yerleşim") of each current neighbourhood: town quarter group, "<district> Köyleri"
# or the belde, from semt.py's output of the urban/rural run
SETTLE, SETTLE_NAMES = {}, []
for f in sorted(KK.glob("*/semt_*_mahalle.csv")):
    for r in pl.read_csv(f, infer_schema_length=0).iter_rows(named=True):
        if r["semt"]:
            if r["semt"] not in SETTLE_NAMES:
                SETTLE_NAMES.append(r["semt"])
            SETTLE[wh(r["area_id"])] = SETTLE_NAMES.index(r["semt"])

units = []
for (aid, lvl), s in series.items():
    if lvl != "district" or aid not in D:
        continue
    first, vals = pack(s)
    units.append(["ilce", dist["name_tr"][D[aid]], D[aid], first, vals])
prov_tot = {}
for (aid, lvl), s in series.items():
    if lvl == "district" and aid[:5] in P:
        for y, v in s.items():
            prov_tot.setdefault(aid[:5], {}).setdefault(y, 0)
            prov_tot[aid[:5]][y] += v
for pid, s in prov_tot.items():
    first, vals = pack(s)
    units.append(["il", prov["name_tr"][P[pid]], -1 - P[pid], first, vals])  # negative index = province
for (aid, lvl), s in series.items():
    if lvl == "district":
        continue
    did = aid.rsplit("-", 1)[0]
    if did not in D:
        continue
    first, vals = pack(s)
    units.append(["koy" if lvl == "village" else "mahalle", names.get(aid, aid), D[did], first, vals, SETTLE.get(aid, -1)])

# beldes as of 2013, from the urban/rural list
belde = {}
for p in sorted(x.name for x in KK.iterdir() if (x / f"kent_{x.name}_son.csv").exists()):
    for r in pl.read_csv(KK / p / f"kent_{p}_son.csv", infer_schema_length=0).iter_rows(named=True):
        e = r["eski_statu"] or ""
        if e.startswith("belde:"):
            did = r["area_id"].rsplit("-", 1)[0]
            wid = wh(r["area_id"])
            s = series.get((wid, "neighbourhood")) or series.get((wid, "village")) or {}
            b = belde.setdefault((did, e[6:]), {})
            for y, v in s.items():
                if y >= 2013:
                    b[y] = b.get(y, 0) + v
for (did, name), s in belde.items():
    if did in D and s:
        first, vals = pack(s)
        units.append(["belde", name, D[did], first, vals])

out = dict(years=YEARS, provinces=[[r["area_id"], r["name_tr"]] for r in prov.iter_rows(named=True)],
           districts=[[r["area_id"], r["name_tr"], P.get(r["area_id"][:5], -1)] for r in dist.iter_rows(named=True)],
           settlements=SETTLE_NAMES, units=units)
dst = ROOT / "public/nufus_birimler.json"
dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
from collections import Counter  # noqa: E402
print(dst, f"{dst.stat().st_size / 1e6:.1f} MB", Counter(u[0] for u in units))
