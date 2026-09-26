"""Purchasing power of a month's net pay across every complete CPI subclass, 2005-2026.

The finest level that runs unbroken over the whole period is the five-digit COICOP 2018
subclass of the 2025=100 CPI (`cpi_2025_items`): 148 of 188 have every month from
2005-01 to 2026-08. Item-level prices (`average_item_price`) are finer but stop at
2022-04; the 2003=100 series runs longer but only in 57 coarse groups.

A subclass whose index moves more than 2.5x in one month is dropped as a measurement
break, not a price (remittance fees, and natural gas for the free month of 2023).

For each subclass and year: yearly mean net pay / yearly mean index, as a multiple of
the base year — 2005 for the minimum wage, 2014 for the entry-level teacher
(`civil_servant_salary`, single, no overtime lessons). 1.5 means the same month's pay
buys half as much again of that subclass as in the base year.

CPI indices are quality-adjusted: phones and computers look far cheaper than any shelf
price says. Clothing indices are seasonal and step oddly after 2022; read them loosely.
"""

import math
import sys
import tomllib

import duckdb
import polars as pl

sys.path.insert(0, "src")
from veriatlas.config import DATA, PUBLIC

FACT = str(PUBLIC / "fact.parquet")
MONTHS = 260
BREAK = math.log(2.5)
YEARS = [str(y) for y in range(2005, 2027)]


def labels() -> dict[str, str]:
    with open(DATA / "indicators.toml", "rb") as fh:
        values = tomllib.load(fh)["dim"]["cpi_2025_item"]["values"]
    return {k.removeprefix("tukfiy2025_"): v for k, v in values.items()}


def wage(con, indicator: str, dims: str, name: str) -> pl.DataFrame:
    return pl.from_arrow(
        con.sql(
            f"select year(period_start)::int as \"year\", avg(value) {name} from '{FACT}' "
            "where indicator_id = ? and area_id = 'TR' and dims = ? group by 1",
            params=[indicator, dims],
        ).arrow()
    )


def main() -> None:
    con = duckdb.connect()
    monthly = pl.from_arrow(
        con.sql(
            f"""
            with complete as (
                select dims from '{FACT}'
                where indicator_id = 'cpi_2025_items'
                  and regexp_matches(dims, '_[0-9]{{5}}$')
                group by dims having count(*) = {MONTHS}
            )
            select period_start d, dims, value from '{FACT}'
            where indicator_id = 'cpi_2025_items'
              and dims in (select dims from complete)
            """
        ).arrow()
    ).with_columns(pl.col("dims").str.extract(r"_(\d{5})$").alias("code"))
    jumps = (
        monthly.sort("d")
        .with_columns(
            (pl.col("value") / pl.col("value").shift(1).over("code"))
            .log()
            .abs()
            .alias("j")
        )
        .group_by("code")
        .agg(pl.col("j").max())
    )
    broken = jumps.filter(pl.col("j") >= BREAK)["code"].to_list()
    names = labels()
    print("complete subclasses:", monthly["code"].n_unique())
    print("dropped as breaks  :", [names[c] for c in broken])

    pay = wage(con, "minimum_wage", "wage_measure=net", "mw").join(
        wage(
            con,
            "civil_servant_salary",
            "civil_servant_profile=ogretmen;salary_item=net",
            "tw",
        ),
        on="year",
        how="left",
    )
    yearly = (
        monthly.filter(~pl.col("code").is_in(broken))
        .group_by("code", pl.col("d").dt.year().alias("year"))
        .agg(pl.col("value").mean())
        .join(pay, on="year")
        .with_columns(
            (pl.col("mw") / pl.col("value")).alias("mw_units"),
            (pl.col("tw") / pl.col("value")).alias("tw_units"),
        )
    )
    base_mw = yearly.filter(pl.col("year") == 2005).select(
        "code", pl.col("mw_units").alias("b")
    )
    base_tw = yearly.filter(pl.col("year") == 2014).select(
        "code", pl.col("tw_units").alias("t")
    )
    yearly = (
        yearly.join(base_mw, on="code")
        .join(base_tw, on="code")
        .with_columns(
            (pl.col("mw_units") / pl.col("b")).alias("minimum_wage"),
            (pl.col("tw_units") / pl.col("t")).alias("teacher"),
        )
    )

    mw = yearly.pivot(on="year", index="code", values="minimum_wage").sort("code")
    mw = mw.with_columns(
        pl.col("code").replace_strict(names).alias("subclass"),
        pl.concat_list(YEARS).list.max().alias("peak"),
        (pl.concat_list(YEARS).list.arg_max() + 2005).alias("peak_year"),
    ).with_columns((pl.col("2025") / pl.col("peak")).alias("vs_peak"))
    tw = yearly.filter(pl.col("year") >= 2014).pivot(
        on="year", index="code", values="teacher"
    )

    with pl.Config(
        tbl_rows=200, tbl_width_chars=220, fmt_str_lengths=55, float_precision=2
    ):
        print("\nMedian across subclasses")
        print(
            yearly.group_by("year")
            .agg(pl.col("minimum_wage", "teacher").median())
            .sort("year")
        )
        print("\nMinimum wage, 2005 = 1")
        print(
            mw.sort("2025").select(
                "subclass",
                "2013",
                "2021",
                "2023",
                "2025",
                "2026",
                "peak_year",
                "vs_peak",
            )
        )
        print("\nPeak year of the minimum wage's purchasing power")
        print(mw.group_by("peak_year").len().sort("peak_year"))
        print("\nTeacher, 2014 = 1: share of subclasses below 1")
        for year in ("2018", "2021", "2022", "2023", "2025"):
            print(f"  {year}: {(tw[year] < 1).mean():.0%}")


if __name__ == "__main__":
    main()
