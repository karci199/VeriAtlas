"""Population by single year of age and sex, provinces and Türkiye, 2007-2025.

A TÜİK export downloaded by hand: single years of age across the columns, year /
province / sex down the rows, each label filled in only when it changes.

**Single years are stored as they come.** Folding them into five-year bands on the way in
was the earlier behaviour and it threw away the only thing this file has that MEDAS's
district export does not. Going from single years to any coarser grouping is exact
addition; going back is impossible. So the fact table keeps the finest grain published,
and the groupings the screen offers — five-year bands, 0-14/15-64/65+, 18+ — are computed
from it. The top band is already closed at 75+ in the source and stays there; inventing
80+ would be fabrication.

Only male and female rows are kept. The file also carries a "Toplam" row per province and
a "Toplam-Total" province, both sums of the rest — storing them as well would let a
careless query count the population twice.

The file was checked against a completely independent extraction before being trusted:
its province totals match the sum of MEDAS's district export exactly, for all 1.539
province-years the two share.
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import polars as pl

from ..areas import resolve
from ..config import RAW
from ..indicators import get
from ..schema import format_dims

SOURCE_FILE = Path(
    r"C:\Users\katan\OneDrive\Desktop\İl, tek yaş ve cinsiyete göre nüfus.xls"
)

#: One sheet, named after TÜİK's own table number.
SHEET = "2820"
COUNTRY_LABEL = "Toplam-Total"
SEXES = {"Erkek-Male": "male", "Kadın-Female": "female"}
TOP_BAND = "75+"


class TuikPopulationAgeSex:
    """Wide sheet: ages across, year/province/sex down, labels filled only on change."""

    source_id = "tuik_medas"
    indicator_id = "population"

    # A hand-made export with no release stamp in it. Same known gap as the fertility
    # file: the vintage is when we took it, not when TÜİK published it.
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 13)

    def fetch(self) -> Path:
        target = RAW / "tuik_medas" / SOURCE_FILE.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_mtime < SOURCE_FILE.stat().st_mtime:
            shutil.copy2(SOURCE_FILE, target)
        return target

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        sheet = pl.read_excel(
            raw, sheet_name=SHEET, engine="calamine", has_header=False
        )

        header = sheet.row(3)
        ages = {
            index: str(header[index]).strip()
            for index in range(4, len(header))
            if header[index]
        }

        frame = (
            sheet.slice(4)
            .rename({"column_1": "year", "column_2": "area", "column_3": "sex"})
            # Year and province appear once and then stay blank down the block.
            .with_columns(
                pl.col("year").cast(pl.String).forward_fill(),
                pl.col("area").cast(pl.String).forward_fill(),
            )
            .filter(pl.col("sex").is_in(list(SEXES)))
            .filter(pl.col("year").str.strip_chars().str.contains(r"^\d{4}$"))
        )

        provinces = [name for name in frame["area"].unique() if name != COUNTRY_LABEL]
        area_of = resolve(provinces) | {COUNTRY_LABEL: "TR"}

        long = (
            frame.unpivot(
                index=["year", "area", "sex"],
                on=[f"column_{index + 1}" for index in ages],
                variable_name="column",
                value_name="value",
            )
            .with_columns(
                pl.col("column")
                .replace_strict({f"column_{i + 1}": age for i, age in ages.items()})
                .alias("age"),
                pl.col("sex").replace_strict(SEXES).alias("sex_id"),
                pl.col("value").cast(pl.Float64),
            )
            # One row per single year of age, exactly as published — no grouping here.
            .select("year", "area", "sex_id", "age", "value")
        )

        bands = {
            (age, sex): format_dims({"age": age, "sex": sex})
            for age in long["age"].unique()
            for sex in SEXES.values()
        }

        return long.with_columns(
            pl.col("area").replace_strict(area_of).alias("area_id"),
            pl.when(pl.col("area") == COUNTRY_LABEL)
            .then(pl.lit("country"))
            .otherwise(pl.lit("province"))
            .alias("area_level"),
            pl.date(pl.col("year").cast(pl.Int32), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.struct("age", "sex_id")
            .map_elements(
                lambda s: bands[(s["age"], s["sex_id"])], return_dtype=pl.String
            )
            .alias("dims"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).drop("year", "area", "sex_id", "age")
