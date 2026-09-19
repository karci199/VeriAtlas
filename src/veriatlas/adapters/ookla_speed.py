r"""Measured mobile internet speed, by district and province.

Built by `scripts/build_ookla_speed.py` from Ookla's open Speedtest tiles, which that
script explains. The adapter only files the result, but three decisions live here:

* **Four indicators, not one with a unit dimension.** Download and upload are Mbit/s,
  latency is milliseconds and the test count is a count; an indicator carries one unit.
* **The test count is stored as well as the speeds.** It is the only thing that says how
  much weight a district's number can take — Tunceli's figure rests on a few dozen tests,
  İstanbul's on tens of thousands — and without it every district looks equally solid.
* **`quality_flag` is `measured`.** These are real measurements, but of a self-selected
  sample: people who chose to run a speed test. The definition says so; the flag records
  that nobody modelled or interpolated the number.

Provinces are summed from tiles rather than from their districts, so a coastal tile that
falls outside every district polygon still counts once at the province level.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW

SOURCE = RAW / "ookla" / "hiz_ilce.csv"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 17)

#: indicator id → (column in the built file, unit)
MEASURES = {
    "mobile_download_speed": ("download", "mbps"),
    "mobile_upload_speed": ("upload", "mbps"),
    "mobile_latency": ("latency", "millisecond"),
    "mobile_speedtests": ("tests", "item"),
}


def quarter_start(label: str) -> dt.date:
    year, quarter = label.split("-Q")
    return dt.date(int(year), 3 * int(quarter) - 2, 1)


class OoklaSpeed:
    source_id = "ookla_open_data"
    indicator_id = ""

    def fetch(self) -> Path:
        return SOURCE

    def parse(self, raw: Path) -> pl.DataFrame:
        column, unit = MEASURES[self.indicator_id]
        table = pl.read_csv(raw)
        return pl.DataFrame(
            {
                "indicator_id": [self.indicator_id] * len(table),
                "area_id": table["area_id"],
                "area_level": table["area_level"],
                "period_start": [quarter_start(p) for p in table["period"]],
                "frequency": ["quarterly"] * len(table),
                "dims": [""] * len(table),
                "value": table[column].cast(pl.Float64),
                "unit": [unit] * len(table),
                "quality_flag": ["measured"] * len(table),
                "vintage": [VINTAGE] * len(table),
                "source_id": [self.source_id] * len(table),
                "retrieved_at": [RETRIEVED] * len(table),
            }
        )


OOKLA_ADAPTERS = {
    name: type(
        f"Ookla{name.title().replace('_', '')}", (OoklaSpeed,), {"indicator_id": name}
    )
    for name in MEASURES
}
