"""Export a browser-sized slice of the fact table for the web screen.

The page is static, so it reads a plain CSV rather than querying the warehouse. Turkish
names are joined in here, not in the page: the fact table stores ids, the registry owns
labels (decision K1).

Run:  uv run python scripts/export_web.py
"""

import sys

import polars as pl

sys.path.insert(0, "src")

from veriatlas.areas import load_areas
from veriatlas.config import PUBLIC
from veriatlas.schema import parse_dims


def main() -> None:
    fact = pl.read_parquet(PUBLIC / "fact_tfr.parquet")
    areas = load_areas().select("area_id", "name_tr")

    assert all(parse_dims(d) == {} for d in fact["dims"].unique()), (
        "this slice assumes no breakdowns; add dimension columns before exporting"
    )

    slim = (
        fact.join(areas, on="area_id", how="left")
        .select(
            "area_id",
            pl.col("name_tr").alias("area"),
            pl.col("period_start").dt.year().alias("year"),
            "value",
            "unit",
            "quality_flag",
            "vintage",
            "source_id",
        )
        .sort("area", "year")
    )

    target = PUBLIC / "tfr.csv"
    slim.write_csv(target)
    print("yazildi:", target, slim.height, "satir")


if __name__ == "__main__":
    main()
