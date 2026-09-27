"""SGK work-accident frequency and severity rates, Türkiye, 2007-2022.

Every yearbook prints "İş Kazası Sıklık ve Ağırlık Hızları": the year's accidents set
against the premium days reported, in four-month rows and a Toplam row. Only the Toplam
row is read for the frequencies; severity is printed once for the year. Four rates:

- frequency per 100 workers (accidents × 100 / workers, the worker count being premium
  days / 300),
- frequency per 1,000,000 working hours,
- severity in days lost per 1,000 working hours, and the same in hours.

The rates are stored as printed and not recomputed: their inputs (incapacity days, death
and permanent-incapacity day equivalents, premium days) are not all in the warehouse.
4/a from 2007, 4/b from 2017 (its own table). The 2023-2025 yearbooks no longer print
the table. Cells come from `raw/sgk/national_cells.parquet`.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from .sgk_national import CELLS
from .sgk_pensions_granted import plain

MEASURES = (
    ("frequency_per_100_workers", r"siklik", r"100 kiside"),
    ("frequency_per_million_hours", r"siklik", r"is saati"),
    ("severity_days", r"agirlik", r"gun"),
    ("severity_hours", r"agirlik", r"saat"),
)


def measure_of(header: str) -> str | None:
    parts = [plain(p) for p in header.split(" > ")]
    if len(parts) < 2:
        return None
    return next(
        (
            m
            for m, a, b in MEASURES
            if re.search(a, parts[-2]) and re.search(b, parts[-1])
        ),
        None,
    )


def read_all() -> dict[tuple[int, str, str], float]:
    cells = pl.read_parquet(CELLS)
    titles = [
        t
        for t in cells["title"].unique().to_list()
        if "siklik" in plain(t) and "agirlik" in plain(t)
    ]
    out: dict[tuple[int, str, str], float] = {}
    for (year, title), table in cells.filter(pl.col("title").is_in(titles)).group_by(
        "year", "title"
    ):
        scheme = "4b" if re.search(r"4[-/]1?[-/ ]?b", plain(title)) else "4a"
        is_total = pl.col("label").map_elements(
            lambda s: plain(s).startswith("toplam"), return_dtype=pl.Boolean
        )
        found = 0
        for header, value, total_row in table.select(
            "header", "value", is_total.alias("t")
        ).iter_rows():
            measure = measure_of(header)
            if measure is None or value is None:
                continue
            # Severity is one annual figure in a cell merged over the four-month rows;
            # it lands on whichever row the merge anchored to (the Toplam row in some
            # years, "Mayıs-Ağustos" in others). Frequencies come from the Toplam row.
            if measure.startswith("frequency") and not total_row:
                continue
            key = (year, scheme, measure)
            if key in out:
                raise ValueError(f"{key}: iki kez basılmış ({title})")
            out[key] = value
            found += 1
        if found != len(MEASURES):
            raise ValueError(f"{year} {scheme}: {found}/4 hız okundu ({title})")
    return out


class SgkWorkAccidentRates:
    source_id = "sgk"
    indicator_id = "sgk_work_accident_rates"

    def fetch(self) -> Path:
        return CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": f"accident_rate={measure};scheme={scheme}",
                "value": value,
            }
            for (year, scheme, measure), value in read_all().items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("accident_rate").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 14)).alias("retrieved_at"),
        )


SGK_ACCIDENT_RATES_ADAPTERS = {"sgk_work_accident_rates": SgkWorkAccidentRates}
