"""Write the NİP workbooks out as long-format CSV, and check the one we do not load.

    uv run python scripts/convert_household_excel.py

The warehouse is the real destination — `scripts/load.py` runs the same adapters and puts
these rows in `fact`. This script exists for the two things the warehouse does not do:

* a flat CSV per measure, for reading the numbers outside the project;
* the household-type comparison. That workbook is deliberately not loaded — `tuik_simple`
  already brings `household_by_type` from MEDAS — so the only way to find out whether the
  two sources still agree is to parse it and look. If they ever diverge, that is a finding
  about the source, and it should not take a load to surface it.

Parsing lives in `adapters/tuik_household_excel.py`, not here. Two copies of a parser is
two things to keep in step, which is the same argument that keeps the workbook out of the
warehouse in the first place.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import polars as pl

sys.path.insert(0, "src")

from veriatlas.adapters.tuik_household_excel import (
    BUILDING_AGE,
    DOWNLOADS,
    TENURE,
    cross_section,
    education,
    household_sizes,
    household_types,
)
from veriatlas.config import WAREHOUSE

OUT = DOWNLOADS / "long"


def check_household_type() -> str:
    """Compare the workbook's household types with the MEDAS rows already loaded.

    The warehouse may not have been built yet, which is not an error here — this is a
    cross-check, not the reason the script runs.
    """
    workbook = household_types()
    if not WAREHOUSE.exists():
        return f"hanehalki tipi: {workbook.height} satir okundu, ambar yok, karsilastirilmadi"

    loaded = (
        duckdb.connect(str(WAREHOUSE), read_only=True)
        .execute(
            "select area_id, year(period_start) as year, dims, value "
            "from fact where indicator_id = 'household_by_type'"
        )
        .pl()
        .with_columns(pl.col("value").cast(pl.Int64))
    )
    if loaded.is_empty():
        return "hanehalki tipi: ambarda household_by_type yok, karsilastirilmadi"

    merged = workbook.join(loaded, on=["area_id", "year", "dims"], suffix="_medas")
    differing = merged.filter(pl.col("value") != pl.col("value_medas"))
    unmatched = workbook.height - merged.height
    return (
        f"hanehalki tipi: {merged.height} satir ambardakiyle karsilastirildi, "
        f"{differing.height} farkli, {unmatched} satir ambarda karsiliksiz"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=OUT, help="uzun formatli CSV'lerin yazilacagi dizin"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    written = {
        "household-size": household_sizes(),
        "education-attainment": education(),
        "tenure": cross_section("tenure", "tenure", TENURE),
        "building-age": cross_section("building-age", "building_period", BUILDING_AGE),
    }
    for stem, frame in written.items():
        path = args.out / f"{stem}.csv"
        frame.write_csv(path)
        print(f"{path.name}: {frame.height} satir, {frame['year'].n_unique()} yil")

    print(check_household_type())


if __name__ == "__main__":
    main()
