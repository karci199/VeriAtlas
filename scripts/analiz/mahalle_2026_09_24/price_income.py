"""Endeksa price and income fields: within-district variance and price-to-income (found unreliable; kept for the record).

Run from the repository root of the main checkout (reads public/fact.parquet and public/tiles).
Intermediate files: C:\veri-ham\analiz\2026_09_24. Session 2026-09-24, one-off analysis kept as run."""

import csv
import glob
import json

import polars as pl

names = {
    r["area_id"]: r["name_tr"]
    for r in csv.DictReader(
        open(r"C:\veri\src\veriatlas\data\areas_tr.csv", encoding="utf-8")
    )
}
rows = []
for f in glob.glob(r"C:\veri-ham\endeksa\demography\TR-*.json"):
    did = f.split("\\")[-1][:-5]
    for mid, m in json.load(open(f, encoding="utf-8")).items():
        x = m.get("demography") or {}
        if (x.get("HouseholdCount") or 0) <= 0:
            continue
        rows.append(
            {
                "mid": mid,
                "did": did,
                "il": did[:5],
                "ilce": x.get("CountyName"),
                "mah": x.get("DistrictName"),
                "pop": x.get("PopulationTotal") or 0,
                "hh": x["HouseholdCount"],
                "inc": x.get("HouseIncome") or None,
                "price": x.get("HouseUnitPriceForSale") or None,
                "rent": x.get("HouseUnitPriceForRent") or None,
                "list": x.get("TotalOwnerListingCount") or 0,
            }
        )
D = pl.DataFrame(rows).filter(
    pl.col("inc").is_not_null()
    & pl.col("price").is_not_null()
    & (pl.col("pop") >= 1000)
)
D = D.with_columns((pl.col("inc") / (pl.col("pop") / pl.col("hh"))).alias("pci"))
print("mahalle", D.height)
# variance decomposition of log income and log price: share between districts
import numpy as np

for c in ["inc", "pci", "price"]:
    y = np.log(D[c].to_numpy())
    dm = D.with_columns(pl.lit(y).alias("y")).with_columns(
        pl.col("y").mean().over("did").alias("m")
    )
    within = np.var((dm["y"] - dm["m"]).to_numpy())
    total = np.var(y)
    print(c, "ilçe içi varyans payı %", round(within / total * 100, 1))
D.write_parquet(r"C:\veri-ham\analiz\2026_09_24\pi.parquet")
