"""How much a month's net pay buys: diesel, beer, rakı, cigarettes — 2003-2026.

Two earners:
- minimum wage, net (`minimum_wage`, ÇSGB; single-person AGİ included up to 2021);
- teacher, entry and 25-year senior, net (`civil_servant_salary`, memurlar.net robot,
  single, no children, no overtime lessons; 2014 →).

Prices are TÜİK average item prices (`average_item_price`, 2003 → 2022-04), carried
forward with the matching CPI item index (`cpi_2025_items`) chained at 2022-04. TÜİK
gives no unit; the price level says 50 cl beer, 70 cl rakı, a pack of 20. Cigarette
prices start 2013; 2005-2012 are the index run backwards from the same anchor.

Also prints petrol and diesel as multiples of the LPG (otogaz) price. The LPG index is
"other fuels" (07223), so the ratio after 2022-04 is looser than before it.

Each series is a yearly mean of monthly (or half-yearly) values; 2026 is the months
published so far.
"""

import sys

import duckdb
import numpy as np
import polars as pl

sys.path.insert(0, "src")
from veriatlas.config import PUBLIC

FACT = str(PUBLIC / "fact.parquet")
ANCHOR = pl.date(2022, 4, 1)

#: name -> (average-price item, CPI 2025 index item)
ITEMS = {
    "diesel": ("0722003", "07221"),
    "petrol": ("0722001", "07222"),
    "lpg": ("0722002", "07223"),
    "beer": ("0213001", "02130"),
    "raki": ("0211001", "02110"),
    "cigarettes": ("0220100", "02301"),
}
EARNERS = {
    "minimum_wage": ("minimum_wage", "wage_measure=net"),
    "teacher": (
        "civil_servant_salary",
        "civil_servant_profile=ogretmen;salary_item=net",
    ),
    "teacher_senior": (
        "civil_servant_salary",
        "civil_servant_profile=ogretmen_kidemli;salary_item=net",
    ),
}
BASKET = ("diesel", "beer", "raki", "cigarettes")


def series(con, indicator: str, dims: str, name: str) -> pl.DataFrame:
    return pl.from_arrow(
        con.sql(
            f"select period_start d, value from '{FACT}' "
            f"where indicator_id = ? and area_id = 'TR' and dims = ?",
            params=[indicator, dims],
        ).arrow()
    ).rename({"value": name})


def price(con, name: str) -> pl.DataFrame:
    """Monthly price: the real one where TÜİK has it, the chained index elsewhere."""
    item, index = ITEMS[name]
    level = series(con, "average_item_price", f"cpi_item={item}", "p")
    cpi = series(con, "cpi_2025_items", f"cpi_2025_item=tukfiy2025_{index}", "i")
    m = level.join(cpi, on="d", how="full", coalesce=True).sort("d")
    anchor = m.filter(pl.col("d") == ANCHOR).row(0, named=True)
    chained = anchor["p"] * pl.col("i") / anchor["i"]

    overlap = m.with_columns(chained.alias("x")).drop_nulls(["p", "x"])
    overlap = overlap.filter(pl.col("d").dt.year() >= 2015)
    growth = overlap.select(pl.col("p", "x").pct_change()).drop_nulls()
    r = np.corrcoef(growth["p"], growth["x"])[0, 1]
    print(f"{name:11} index vs real, monthly change 2015-2022: r = {r:.3f}")

    return m.select("d", pl.coalesce("p", chained).alias(name))


def yearly(frame: pl.DataFrame, name: str) -> pl.DataFrame:
    return frame.group_by(pl.col("d").dt.year().alias("year")).agg(pl.col(name).mean())


def main() -> None:
    con = duckdb.connect()
    table = pl.DataFrame({"year": list(range(2003, 2027))}, schema={"year": pl.Int32})
    for name in ITEMS:
        table = table.join(yearly(price(con, name), name), on="year", how="left")
    for name, (indicator, dims) in EARNERS.items():
        table = table.join(
            yearly(series(con, indicator, dims, name), name), on="year", how="left"
        )

    ratios = table.select(
        "year",
        (pl.col("petrol") / pl.col("lpg")).alias("petrol_x_lpg"),
        (pl.col("diesel") / pl.col("lpg")).alias("diesel_x_lpg"),
    )
    units = table.select(
        "year",
        *[
            (pl.col(earner) / pl.col(item)).round(0).alias(f"{earner}:{item}")
            for earner in EARNERS
            for item in BASKET
        ],
    )
    with pl.Config(tbl_rows=30, tbl_cols=20, tbl_width_chars=250, float_precision=2):
        print("\nPrice as a multiple of LPG")
        print(ratios)
        print("\nPrices (TL) and net monthly pay")
        print(table)
        print("\nUnits a month's net pay buys (litre, 50 cl, 70 cl, pack)")
        print(units)


if __name__ == "__main__":
    main()
