"""Flatten Endeksa fellow-countryman lists (top 10 registry provinces per neighbourhood) into one table.

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import glob
import json
import os

import polars as pl

names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
dn = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr_districts.csv", encoding="utf-8")
    )
}


def up(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


prov_by_upper = {
    up(v): k
    for k, v in names.items()
    if k.startswith("TR-") and k.count("-") == 1 and len(k) == 5
}
rows = []
unk = set()
for fp in glob.glob(r"C:\veri-ham\endeksa\fellowcountryman\*.json"):
    did = os.path.basename(fp)[:-5]
    host = did[:5]
    for mid, m in json.load(open(fp, encoding="utf-8")).items():
        for e in m.get("fellowcountryman") or []:
            p = prov_by_upper.get(e["CitizenCity"])
            if not p:
                unk.add(e["CitizenCity"])
                continue
            rows.append((did, host, mid, m.get("name_tr"), p, e["CountOf"]))
df = pl.DataFrame(
    rows, schema=["did", "host", "mid", "mname", "orig", "n"], orient="row"
)
print(df.height, df["mid"].n_unique(), "unknown:", list(unk)[:10])
df.write_parquet(r"C:\veri-ham\analiz\2026_09_24\hem.parquet")
# entries per mahalle distribution
print(df.group_by("mid").len()["len"].value_counts().sort("len"))
