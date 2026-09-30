"""Population 2007-2025 for every unit of the kent/kır check page, plus the province, district and
country totals of each year, for the change and share columns of web/kentkir.html.

Writes public/kentkir_nufus.json (git-ignored):
  years, tr [per year], il {area_id: [per year]}, ilce {area_id: [per year]}, s {unit id: [per year]}
A year is null when the unit has no population row that year (a place renumbered in 2013 has
none for 2007-2012 under its present id).
"""
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]
FACT = "C:/veri/public/fact.parquet"
YEARS = list(range(2007, 2026))
kk = json.loads((ROOT / "public/kentkir_kontrol.json").read_text(encoding="utf-8"))
ID = kk["keys"].index("id")
ids = {r[ID] for r in kk["rows"]}

con = duckdb.connect()
rows = con.sql(f"""select area_id, area_level, year(period_start) y, sum(value) v
  from read_parquet('{FACT}') where indicator_id='population'
  and area_level in ('country','province','district','neighbourhood','village') group by 1,2,3""").fetchall()
ix = {y: i for i, y in enumerate(YEARS)}
out = {"years": YEARS, "tr": [None] * len(YEARS), "il": {}, "ilce": {}, "s": {}}
for aid, lvl, y, v in rows:
    if y not in ix:
        continue
    if lvl == "country":
        out["tr"][ix[y]] = round(v)
    elif lvl == "province":
        out["il"].setdefault(aid, [None] * len(YEARS))[ix[y]] = round(v)
    elif lvl == "district":
        out["ilce"].setdefault(aid, [None] * len(YEARS))[ix[y]] = round(v)
    elif aid in ids:
        out["s"].setdefault(aid, [None] * len(YEARS))[ix[y]] = round(v)
print("tr", out["tr"][0], out["tr"][-1], "| il", len(out["il"]), "| ilce", len(out["ilce"]), "| birim", len(out["s"]), "/", len(ids))
missing_2007 = sum(1 for a in ids if a in out["s"] and out["s"][a][0] is None)
print("2007 boş:", missing_2007, "| serisi hiç olmayan:", len(ids - out["s"].keys()))
(ROOT / "public/kentkir_nufus.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
