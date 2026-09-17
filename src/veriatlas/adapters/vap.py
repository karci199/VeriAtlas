r"""MKK VAP: portfolio value held by investors, by province, December 2005-2025.

`scripts/fetch_vap.py` keeps the MicroStrategy map visualisation for each December in
`C:\veri-ham\vap\portfolio-<year>.json`: 81 provinces and their portfolio value in million TL
(all instruments: shares, funds, government and private debt, other securities; the investor's
registered province; market value at Borsa İstanbul closing prices).

The dossier returns nothing for December 2007; that year is not written.

Checks: 81 provinces every other year, each once; values positive.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..config import RAW

#: the dossier returns no rows for December 2007
EMPTY = {2007}
FOLDER = RAW / "vap" if (RAW / "vap").exists() else Path("C:/veri-ham/vap")


def load_all() -> list[dict]:
    rows = []
    for path in sorted(FOLDER.glob("portfolio-*.json")):
        year = int(path.stem.split("-")[1])
        answer = json.loads(path.read_text(encoding="utf-8"))
        if year in EMPTY:
            continue
        elements = answer["definition"]["grid"]["rows"][0]["elements"]
        values = answer["data"]["metricValues"]["raw"]
        areas = [e["id"].split(";")[0] for e in elements]  # "hTR34"
        if len(set(areas)) != 81 or len(values) != 81:
            raise ValueError(f"VAP {year}: {len(set(areas))} il")
        for area, (value,) in zip(areas, values, strict=True):
            if value is None or value <= 0:
                raise ValueError(f"VAP {year} {area}: değer {value}")
            rows.append(
                {
                    "area_id": "TR-" + area[3:],
                    "period_start": dt.date(year, 1, 1),
                    "dims": "",
                    "value": value * 1000,  # million -> thousand TL
                }
            )
    return rows


class VapPortfolio:
    source_id = "vap"
    indicator_id = "investor_portfolio_value"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        return pl.DataFrame(
            load_all(), schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("thousand_try").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


VAP_ADAPTERS = {"investor_portfolio_value": VapPortfolio}
