"""Load total fertility rate, 81 provinces x 2009-2025, into the fact table.

The first real data through the schema. Source file is the verified MEDAS pull from the
2026-08-13 exploratory session: wide layout, one column per year, semicolon separated.

Run:  uv run python scripts/load_tfr.py
"""

import datetime as dt
import sys

import duckdb
import polars as pl

sys.path.insert(0, "src")

from veriatlas.areas import resolve
from veriatlas.config import PUBLIC, WAREHOUSE, ensure_dirs
from veriatlas.schema import DIMS_NONE, validate

SRC = (
    r"C:\Users\katan\OneDrive\Desktop\demografi\cikti"
    r"\TUIK_toplam_dogurganlik_hizi_81il_2009-2025.csv"
)

INDICATOR_ID = "tfr"
UNIT = "çocuk/kadın"
SOURCE_ID = "tuik_medas"

# The file does not record when TUIK released these numbers, only when we pulled them.
# Approximating the vintage with the retrieval month is a known gap: once the MEDAS
# adapter reads the report header, the real release date replaces this.
VINTAGE = "2026-08"
RETRIEVED_AT = dt.date(2026, 8, 13)


def build() -> pl.DataFrame:
    wide = pl.read_csv(SRC, separator=";")
    years = [c for c in wide.columns if c != "il"]

    area_of = resolve(wide["il"].to_list())

    long = wide.unpivot(
        index="il", on=years, variable_name="year", value_name="value"
    ).with_columns(
        pl.col("il").replace_strict(area_of).alias("area_id"),
        pl.lit("province").alias("area_level"),
        pl.date(pl.col("year").cast(pl.Int32), 1, 1).alias("period_start"),
        pl.lit("annual").alias("frequency"),
        pl.lit(DIMS_NONE).alias("dims"),
        pl.lit(INDICATOR_ID).alias("indicator_id"),
        pl.lit(UNIT).alias("unit"),
        pl.lit("measured").alias("quality_flag"),
        pl.lit(VINTAGE).alias("vintage"),
        pl.lit(SOURCE_ID).alias("source_id"),
        pl.lit(RETRIEVED_AT).alias("retrieved_at"),
    )

    return validate(long.drop("il", "year"))


def main() -> None:
    ensure_dirs()
    fact = build()

    target = PUBLIC / "fact_tfr.parquet"
    fact.write_parquet(target)

    con = duckdb.connect(WAREHOUSE)
    con.execute(
        "create or replace table fact as select * from read_parquet(?)", [str(target)]
    )
    rows, areas, years = con.execute(
        "select count(*), count(distinct area_id), count(distinct period_start) from fact"
    ).fetchone()
    con.close()

    print("parquet   :", target)
    print("depo      :", WAREHOUSE)
    print("satir     :", rows, "=", areas, "il x", years, "yil")
    print("deger araligi:", fact["value"].min(), "-", fact["value"].max())


if __name__ == "__main__":
    main()
