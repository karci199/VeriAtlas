"""Diesel-to-petrol pump price ratio against the diesel share of cars, 2005-2025.

Prices: TÜİK average item prices (TL/litre, `average_item_price`, 2003 → 2022-04),
carried forward with the CPI item indices (`cpi_2025_items` 07221/07222/07223) chained at
2022-04. Over the overlap the index-implied ratio tracks the real one at r = 0.98.

Cars: `cars_by_fuel` (year-end stock). The yearly change in the diesel stock over the
change in the whole stock stands in for the diesel share of sales before ODMD's
powertrain table (`odmd_car_sales_by_powertrain`, 2020 →); where both exist they agree
within a few points. 2018-2019 are left out of the correlation: sales collapsed and
scrapping made the net change near zero, so the share is meaningless (191 %).
"""

import sys

import duckdb
import numpy as np
import polars as pl

sys.path.insert(0, "src")
from veriatlas.config import PUBLIC

FACT = str(PUBLIC / "fact.parquet")
ANCHOR = (2022, 4)


def rows(con, indicator: str, where: str = "") -> pl.DataFrame:
    return pl.from_arrow(
        con.sql(
            f"select period_start d, dims, value from '{FACT}' "
            f"where indicator_id = '{indicator}' and area_id = 'TR' {where}"
        ).arrow()
    )


def prices(con) -> pl.DataFrame:
    level = (
        rows(con, "average_item_price", "and dims like 'cpi_item=072200%'")
        .pivot(on="dims", index="d", values="value")
        .rename(
            {
                "cpi_item=0722001": "petrol",
                "cpi_item=0722002": "lpg",
                "cpi_item=0722003": "diesel",
            }
        )
    )
    index = (
        rows(
            con,
            "cpi_2025_items",
            "and dims similar to 'cpi_2025_item=tukfiy2025_0722[123]'",
        )
        .pivot(on="dims", index="d", values="value")
        .rename(
            {
                "cpi_2025_item=tukfiy2025_07221": "i_diesel",
                "cpi_2025_item=tukfiy2025_07222": "i_petrol",
                "cpi_2025_item=tukfiy2025_07223": "i_lpg",
            }
        )
    )
    m = index.join(level, on="d", how="left").sort("d")
    anchor = m.filter(pl.col("d") == pl.date(*ANCHOR, 1)).row(0, named=True)
    for fuel in ("petrol", "lpg", "diesel"):
        chained = anchor[fuel] * pl.col("i_" + fuel) / anchor["i_" + fuel]
        m = m.with_columns(pl.coalesce(pl.col(fuel), chained).alias(fuel))
    return (
        m.group_by(pl.col("d").dt.year().alias("year"))
        .agg(pl.col("petrol", "diesel", "lpg").mean())
        .with_columns(
            (pl.col("diesel") / pl.col("petrol")).alias("diesel_petrol"),
            (pl.col("lpg") / pl.col("petrol")).alias("lpg_petrol"),
        )
        .sort("year")
    )


def cars(con) -> pl.DataFrame:
    stock = (
        rows(con, "cars_by_fuel")
        .with_columns(pl.col("d").dt.year().alias("year"))
        .group_by("year")
        .agg(
            pl.col("value")
            .filter(pl.col("dims") == "fuel=diesel")
            .sum()
            .alias("diesel"),
            pl.col("value").sum().alias("total"),
        )
        .sort("year")
    )
    sales = (
        rows(con, "odmd_car_sales_by_powertrain")
        .with_columns(pl.col("d").dt.year().alias("year"))
        .group_by("year")
        .agg(
            (
                100
                * pl.col("value").filter(pl.col("dims") == "powertrain=diesel").sum()
                / pl.col("value").sum()
            ).alias("odmd_diesel_pct")
        )
    )
    return stock.with_columns(
        (100 * pl.col("diesel") / pl.col("total")).alias("stock_diesel_pct"),
        (100 * pl.col("diesel").diff() / pl.col("total").diff()).alias(
            "net_diesel_pct"
        ),
    ).join(sales, on="year", how="left")


def main() -> None:
    con = duckdb.connect()
    table = prices(con).join(cars(con), on="year").sort("year")
    with pl.Config(tbl_rows=30, tbl_cols=12, float_precision=3):
        print(
            table.select(
                "year",
                "diesel_petrol",
                "lpg_petrol",
                "stock_diesel_pct",
                "net_diesel_pct",
                "odmd_diesel_pct",
            )
        )
    x = table.drop_nulls("net_diesel_pct").filter(~pl.col("year").is_in([2018, 2019]))
    a, b, y = (x[c].to_numpy() for c in ("diesel_petrol", "net_diesel_pct", "year"))
    detrend = [v - np.polyval(np.polyfit(y, v, 1), y) for v in (a, b)]
    print("r same year          :", round(np.corrcoef(a, b)[0, 1], 2))
    print("r detrended          :", round(np.corrcoef(*detrend)[0, 1], 2))
    early = x.filter(pl.col("year") <= 2017)
    print(
        "r 2006-2017          :",
        round(np.corrcoef(early["diesel_petrol"], early["net_diesel_pct"])[0, 1], 2),
    )


if __name__ == "__main__":
    main()
