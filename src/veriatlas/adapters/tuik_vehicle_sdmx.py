"""Registered vehicles, Türkiye only — three more TÜİK SDMX flows beside the province stock.

Same source and request as `tuik_vehicle_stock` (JSON-stat from the TÜİK data browser,
pulled 2026-09-26 into `veri-ham/tuik_sdmx`):

- `DF_MOTORLU_KARA_TASIT_KULLANIM_AMAC_V2` — year-end stock by vehicle type and use
  (private, commercial, official), 2005-2025.
- `DF_MOTORLU_KARA_TASIT_MODEL_YIL_V2` — year-end stock by vehicle type and model year,
  2020-2025. The oldest band is "1983 and earlier".
- `DF_MOTORLU_KARA_TASIT_YAKIT_CINSI_V4` — cars only, by fuel, monthly from 2005-01. Only
  December is kept (the year-end stock). `vehicles_by_fuel` is every vehicle type and starts
  in 2020; this is the car series back to 2005. Electric starts 2011, hybrid 2012 — the
  cells before are absent, not zero.

Each flow carries its own totals; they are used only to prove the parts add up, and are
not stored. Percent cells (`PT`) are derivable and dropped.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from ..indicators import get
from ..schema import format_dims
from .tuik_vehicle_stock import DOWNLOADS, TOTAL, TYPES, read_jsonstat

USES = {"1": "private", "2": "commercial", "3": "official"}
FUELS = {
    "1": "petrol",
    "2": "diesel",
    "6": "lpg",
    "20": "hybrid",
    "5": "electric",
    "_U": "unknown",
}
OLDEST_MODEL_YEAR = "1983_"


def model_years(codes: set[str]) -> dict[str, str]:
    """Model-year codes to stored values; anything that is not a year stops the load."""
    out = {OLDEST_MODEL_YEAR: "-1983"}
    for code in codes - {OLDEST_MODEL_YEAR, TOTAL}:
        if not (code.isdigit() and 1984 <= int(code) <= 2100):
            raise KeyError(f"tasit model yili: taninmayan kod {code}")
        out[code] = code
    return out


@dataclass(frozen=True)
class Flow:
    indicator_id: str
    flow: str
    #: SDMX column -> (dim name, code -> stored value); None means "build from the data".
    dims: dict[str, tuple[str, dict[str, str] | None]]
    monthly: bool = False


FLOWS = {
    "vehicles_by_use": Flow(
        "vehicles_by_use",
        "DF_MOTORLU_KARA_TASIT_KULLANIM_AMAC_V2",
        {
            "ARAC_TUR": ("vehicle_type", TYPES),
            "ARAC_KULLANIM_TUR": ("vehicle_use", USES),
        },
    ),
    "vehicles_by_model_year": Flow(
        "vehicles_by_model_year",
        "DF_MOTORLU_KARA_TASIT_MODEL_YIL_V2",
        {"ARAC_TUR": ("vehicle_type", TYPES), "MODEL_YIL": ("model_year", None)},
    ),
    "cars_by_fuel": Flow(
        "cars_by_fuel",
        "DF_MOTORLU_KARA_TASIT_YAKIT_CINSI_V4",
        {"YAKIT_TUR": ("fuel", FUELS)},
        monthly=True,
    ),
}


class TuikVehicleSdmx:
    source_id = "tuik_veri_portali"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 26)
    flow: Flow
    indicator_id: str

    def fetch(self) -> Path:
        path = DOWNLOADS / (self.flow.flow + ".json")
        if not path.exists():
            raise FileNotFoundError(
                f"{path} yok; tuik_vehicle_stock.fetch ile ayni istekle indirilir"
            )
        return path

    def parse(self, raw: Path) -> pl.DataFrame:
        cells = read_jsonstat(raw).filter(
            (pl.col("UNIT_MEASURE") == "PN") & (pl.col("REF_AREA") == "TR")
        )
        if self.flow.monthly:
            cells = cells.filter(pl.col("TIME_PERIOD").str.ends_with("-12"))
        cols = list(self.flow.dims)
        maps = {}
        for col, (_, mapping) in self.flow.dims.items():
            if mapping is None:
                mapping = model_years(set(cells[col]))
            unknown = set(cells[col]) - set(mapping) - {TOTAL}
            if unknown:
                raise KeyError(
                    f"{self.indicator_id}: taninmayan {col} kodu: "
                    + ", ".join(sorted(unknown))
                )
            maps[col] = mapping

        # Each dimension's total must equal the sum of its parts, the other dims held.
        for col in cols:
            others = [c for c in cols if c != col]
            parts = (
                cells.filter(pl.col(col) != TOTAL)
                .group_by([*others, "TIME_PERIOD"])
                .agg(pl.col("value").sum().alias("parts"))
            )
            off = (
                cells.filter(pl.col(col) == TOTAL)
                .join(parts, on=[*others, "TIME_PERIOD"])
                .filter((pl.col("value") - pl.col("parts")).abs() > 0.5)
            )
            if not off.is_empty():
                raise ValueError(
                    f"{self.indicator_id}: {off.height} hucrede {col} toplami tutmuyor"
                )

        leaves = cells.filter(pl.all_horizontal(pl.col(c) != TOTAL for c in cols))
        frame = leaves.with_columns(
            pl.date(pl.col("TIME_PERIOD").str.slice(0, 4).cast(pl.Int32), 1, 1).alias(
                "period_start"
            ),
            pl.struct(cols)
            .map_elements(
                lambda row: format_dims(
                    {self.flow.dims[c][0]: maps[c][row[c]] for c in cols}
                ),
                return_dtype=pl.String,
            )
            .alias("dims"),
        )
        if frame.select("period_start", "dims").is_duplicated().any():
            raise ValueError(f"{self.indicator_id}: ayni yil-kirilim iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).select(
            "indicator_id",
            "area_id",
            "area_level",
            "period_start",
            "frequency",
            "dims",
            "value",
            "unit",
            "quality_flag",
            "vintage",
            "source_id",
            "retrieved_at",
        )


VEHICLE_SDMX_ADAPTERS = {
    "tuik_" + name: type(
        "Tuik" + "".join(p.title() for p in name.split("_")),
        (TuikVehicleSdmx,),
        {"flow": flow, "indicator_id": name},
    )
    for name, flow in FLOWS.items()
}
