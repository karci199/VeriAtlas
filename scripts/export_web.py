"""Export a browser-sized slice of the fact table for the web screen.

The page is static, so it reads a plain CSV rather than querying the warehouse. Turkish
names are joined in here, not in the page: the fact table stores ids, the registry owns
labels (decision K1).

Run:  uv run python scripts/export_web.py
"""

import json
import sys

import polars as pl

sys.path.insert(0, "src")

from veriatlas.areas import load_areas
from veriatlas.config import PUBLIC
from veriatlas.indicators import load
from veriatlas.schema import parse_dims


def export_dictionary(loaded: set[str]) -> None:
    """Emit the tree and labels the page renders, so nothing is spelled out in HTML.

    Indicators without data yet still appear, marked unavailable: the tree is the plan
    as much as the inventory, and a greyed-out entry says "not yet" where an absent one
    would say "never".
    """
    tree = [
        {
            "topic": topic.label_tr,
            "indicators": [
                {
                    "id": ind.indicator_id,
                    "label": ind.label_tr,
                    "unit": ind.unit.label_tr,
                    "decimals": ind.unit.decimals,
                    "frequency": ind.frequency,
                    "definition": ind.definition_tr,
                    "available": ind.indicator_id in loaded,
                }
                for ind in indicators
            ],
        }
        for topic, indicators in load().tree()
    ]

    target = PUBLIC / "meta.json"
    target.write_text(
        json.dumps({"tree": tree}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("yazildi:", target)


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

    export_dictionary(set(fact["indicator_id"].unique()))


if __name__ == "__main__":
    main()
