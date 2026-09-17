r"""OECD regional statistics at TL3, which for Türkiye is the 81 provinces.

`scripts/fetch_oecd_tl3.py` saves one SDMX-CSV file per dataflow in `C:\veri-ham\oecd_tl3\`,
with the columns MEASURE, REF_AREA, TIME_PERIOD, OBS_VALUE, UNIT_MEASURE and UNIT_MULT.
REF_AREA is the NUTS-3 code (TR100, TR211); the province is read from the codelist's name,
saved beside the data as `cl_regional_tr.json`. TRZZZ is extra-regio — trade that no
province can be given — and is left out, so a year's provinces do not add up to the country.

What is loaded, and what it is:

* Climate (1981-2024, 1981-2023 for degree days). ERA5 reanalysis averaged over the
  province's whole area, which is a different measurement from MGM's, taken at the
  provincial centre's station: over 1991-2020 the two agree in shape (r = 0.80) but the
  areal mean is 2.6 °C colder on average, and most so where a coastal station sits below a
  mountainous hinterland (Rize -8.6, Giresun -7.8, Trabzon -7.1 °C). Both are kept; neither
  replaces the other.
* Foreign trade (2002-2023), from TÜİK's provincial trade statistics as OECD restates them
  in US dollars. The province is the one that declared at customs, where TİM's series
  (`tim_exports`) is the one the exporter is registered in: over 1,612 province-years the
  two move together (r = 0.992) and the difference is systematic — 2023 İstanbul 127.7
  against 95.9 billion dollars, Kocaeli and Bursa the other way round. Imports have no
  counterpart in the repository.

The `*_DIFF_1981_2010` measures are differences from the 1981-2010 average and are not
written: they follow from the level series.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import province_id

FOLDER = (
    RAW / "oecd_tl3" if (RAW / "oecd_tl3").exists() else Path("C:/veri-ham/oecd_tl3")
)
#: dataflow file -> {OECD measure: dimension value}, per indicator
CLIMATE_DAYS = {
    "HOT_DAYS": "hot_days",
    "TROP_NIGHTS": "tropical_nights",
    "ICING_DAYS": "icing_days",
    "EXT_PRECIP_DAYS": "extreme_precipitation_days",
}
DEGREE_DAYS = {"HDD": "heating", "CDD": "cooling"}
TRADE = {"X": "exports", "M": "imports"}


def provinces() -> dict[str, str]:
    """{NUTS-3 code: area_id}, from the codelist saved with the data."""
    codes = json.loads((FOLDER / "cl_regional_tr.json").read_text(encoding="utf-8"))
    return {
        code["id"]: province_id(code["name"])
        for code in codes
        if len(code["id"]) == 5 and code["id"] != "TRZZZ"
    }


def read(
    flow: str, measures: dict[str, str] | None = None, unit: str | None = None
) -> pl.DataFrame:
    """One dataflow's rows as area_id, year and value, keeping the measures asked for."""
    path = FOLDER / f"{flow}.csv"
    if not path.exists():
        raise FileNotFoundError(f"OECD TL3: {path} yok (scripts/fetch_oecd_tl3.py)")
    frame = pl.read_csv(path, infer_schema_length=30_000)
    if unit is not None:
        frame = frame.filter(pl.col("UNIT_MEASURE") == unit)
    if measures is not None:
        frame = frame.filter(pl.col("MEASURE").is_in(list(measures)))
    areas = provinces()
    frame = frame.with_columns(
        pl.col("REF_AREA").replace_strict(areas, default=None).alias("area_id"),
        pl.col("TIME_PERIOD").cast(pl.Int32, strict=False).alias("year"),
        pl.col("OBS_VALUE").cast(pl.Float64, strict=False).alias("value"),
    ).filter(pl.col("area_id").is_not_null() & pl.col("value").is_not_null())
    if frame.is_empty():
        raise ValueError(f"OECD TL3 {flow}: satır kalmadı")
    count = frame["area_id"].n_unique()
    if count != 81:
        raise ValueError(f"OECD TL3 {flow}: {count} il")
    return frame


class OecdFrame:
    """Shared frame: every indicator here is annual, by province, measured."""

    source_id = "oecd_regional"
    indicator_id: str
    unit: str

    def fetch(self) -> Path:
        return FOLDER

    def rows(self) -> pl.DataFrame:
        raise NotImplementedError

    def parse(self, raw: Path) -> pl.DataFrame:
        return (
            self.rows()
            .with_columns(
                pl.date(pl.col("year"), 1, 1).alias("period_start"),
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit("province").alias("area_level"),
                pl.lit("annual").alias("frequency"),
                pl.lit(self.unit).alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit("2026-09").alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
            )
            .select(
                "indicator_id",
                "area_id",
                "area_level",
                "period_start",
                "frequency",
                "value",
                "unit",
                "dims",
                "quality_flag",
                "vintage",
                "source_id",
                "retrieved_at",
            )
        )


class Temperature(OecdFrame):
    indicator_id = "oecd_temperature"
    unit = "celsius"

    def rows(self) -> pl.DataFrame:
        return read("DSD_REG_CLIM_DF_AIR_TEMP", {"AIR_TEMP2M": ""}).with_columns(
            pl.lit("").alias("dims")
        )


class Precipitation(OecdFrame):
    indicator_id = "oecd_precipitation"
    unit = "mm"

    def rows(self) -> pl.DataFrame:
        return read("DSD_REG_CLIM_DF_PRECIPITATION", {"PRECIP_SUM": ""}).with_columns(
            pl.lit("").alias("dims")
        )


class ClimateDays(OecdFrame):
    """Hot days, tropical nights, icing days and days of extreme rainfall, in one indicator."""

    indicator_id = "oecd_climate_days"
    unit = "day"

    def rows(self) -> pl.DataFrame:
        parts = [
            read(flow, {m: v for m, v in CLIMATE_DAYS.items() if m in keep})
            for flow, keep in (
                ("DSD_REG_CLIM_DF_AIR_TEMP", ("HOT_DAYS", "TROP_NIGHTS", "ICING_DAYS")),
                ("DSD_REG_CLIM_DF_PRECIPITATION", ("EXT_PRECIP_DAYS",)),
            )
        ]
        return pl.concat(parts).with_columns(
            ("climate_day=" + pl.col("MEASURE").replace_strict(CLIMATE_DAYS)).alias(
                "dims"
            )
        )


class DegreeDays(OecdFrame):
    indicator_id = "oecd_degree_days"
    unit = "degree_day"

    def rows(self) -> pl.DataFrame:
        return read("DSD_REG_CLIM_DF_DEGREE_DAYS", DEGREE_DAYS).with_columns(
            ("degree_day_type=" + pl.col("MEASURE").replace_strict(DEGREE_DAYS)).alias(
                "dims"
            )
        )


class ForeignTrade(OecdFrame):
    """Exports and imports in millions of dollars, written as thousands like `tim_exports`."""

    indicator_id = "foreign_trade_by_province"
    unit = "thousand_usd"

    def rows(self) -> pl.DataFrame:
        return read("DSD_REG_ECO_DF_TRAD", TRADE, unit="USD").with_columns(
            ("trade_flow=" + pl.col("MEASURE").replace_strict(TRADE)).alias("dims"),
            (pl.col("value") * 1000).alias(
                "value"
            ),  # millions in the file, thousands here
        )


OECD_TL3_ADAPTERS = {
    "oecd_temperature": Temperature,
    "oecd_precipitation": Precipitation,
    "oecd_climate_days": ClimateDays,
    "oecd_degree_days": DegreeDays,
    "foreign_trade_by_province": ForeignTrade,
}
