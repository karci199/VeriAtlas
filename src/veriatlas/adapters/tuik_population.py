"""Population by five-year age band and sex, provinces and Türkiye, 2007-2023.

Source is a MEDAS export someone downloaded by hand: single years of age across the
columns, year / province / sex down the rows, each label filled in only when it changes.
The MEDAS adapter will replace this once it can walk the report wizard; until then this
gets real age-and-sex data into the fact table so the population pyramid can be built.

Two decisions worth stating:

* Only male and female rows are kept. The file also carries a "Toplam" row per province,
  which is their sum — storing it too would let a careless query double the population.
* Single years are folded into five-year bands. The file's top band is already closed at
  75+, so that is where ours ends too; inventing 80+ or 85+ would be fabrication.
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
    r"C:\Users\katan\OneDrive\Desktop\demografi\demografi2"
    r"\il tek yas ve cinsiyete gore nufus.xls"
)

SHEET = "TOPLAM"
COUNTRY_LABEL = "Toplam-Total"
SEXES = {"Erkek-Male": "male", "Kadın-Female": "female"}
TOP_BAND = "75+"


def band_of(age: str) -> str:
    """Single year to its five-year band; the file's own top band passes through."""
    if age == TOP_BAND:
        return TOP_BAND
    start = (int(age) // 5) * 5
    return f"{start}-{start + 4}"


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
                .replace_strict(
                    {f"column_{index + 1}": band_of(age) for index, age in ages.items()}
                )
                .alias("age"),
                pl.col("sex").replace_strict(SEXES).alias("sex_id"),
                pl.col("value").cast(pl.Float64),
            )
            # Single years become bands, so the rows within a band are summed.
            .group_by("year", "area", "sex_id", "age")
            .agg(pl.col("value").sum())
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
