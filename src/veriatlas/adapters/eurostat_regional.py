r"""Eurostat regional labour market, education and R&D tables for Türkiye's NUTS2 regions.

`scripts/fetch_eurostat_regional.py` keeps each dataset as JSON-stat in `C:\veri-ham\eurostat`,
filtered to the 26 İBBS-2 regions and TR. Eurostat's region codes are TÜİK's İBBS-2 codes,
so they are stored as they come (`area_level` nuts2).

The source is TÜİK's Household Labour Force Survey, harmonised by Eurostat: the regional
figures MEDAS does not offer at all. Each indicator fixes the dimensions it does not keep
(unit, education level, training status) in `SLICES`; sex and age are kept as breakdowns.

Eurostat flags some cells "u" (low reliability, small samples in eastern regions) and "b"
(break in series: 2014 and 2021 survey redesigns). They are loaded as published; the flags
are counted in FLAGS and named in the indicator notes, not dropped.

Checks: every kept cell's fixed dimensions match exactly one category; no (region, year,
breakdown) key twice.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from itertools import product
from pathlib import Path

import polars as pl

from ..config import RAW

FOLDER = (
    RAW / "eurostat" if (RAW / "eurostat").exists() else Path("C:/veri-ham/eurostat")
)
SEX = {"T": "total", "M": "male", "F": "female"}
#: indicator -> (dataset, fixed {dimension: category}, kept {dimension: our dim name}, unit)
SLICES = {
    "eu_unemployment_rate": (
        "lfst_r_lfu3rt",
        {"freq": "A", "unit": "PC", "isced11": "TOTAL"},
        {"sex": "sex", "age": "eu_age"},
        "percent",
    ),
    "eu_employment_rate": (
        "lfst_r_lfe2emprt",
        {"freq": "A", "unit": "PC"},
        {"sex": "sex", "age": "eu_age"},
        "percent",
    ),
    "eu_activity_rate": (
        "lfst_r_lfp2actrt",
        {"freq": "A", "unit": "PC"},
        {"sex": "sex", "age": "eu_age"},
        "percent",
    ),
    "eu_long_term_unemployment_share": (
        "lfst_r_lfu2ltu",
        {"freq": "A", "unit": "PC_UNE", "isced11": "TOTAL"},
        {"sex": "sex", "age": "eu_age"},
        "percent",
    ),
    "eu_neet_rate": (
        "edat_lfse_22",
        {"freq": "A", "unit": "PC", "training": "NO_FE_NO_NFE", "wstatus": "NEMP"},
        {"sex": "sex", "age": "eu_age"},
        "percent",
    ),
    "eu_early_leavers": (
        "edat_lfse_16",
        {"freq": "A", "unit": "PC", "age": "Y18-24"},
        {"sex": "sex"},
        "percent",
    ),
    "eu_educational_attainment": (
        "edat_lfse_04",
        {"freq": "A", "unit": "PC"},
        {"sex": "sex", "age": "eu_age", "isced11": "eu_education"},
        "percent",
    ),
    "eu_rd_expenditure_share": (
        "rd_e_gerdreg",
        {"freq": "A", "unit": "PC_GDP"},
        {"sectperf": "rd_sector"},
        "percent",
    ),
    "eu_rd_personnel": (
        "rd_p_persreg",
        {"freq": "A", "unit": "FTE", "prof_pos": "TOTAL"},
        {"sex": "sex", "sectperf": "rd_sector"},
        "person",
    ),
}
#: (indicator, status) -> cells loaded with that Eurostat flag
FLAGS: Counter = Counter()


def value_code(dimension: str, category: str) -> str:
    if dimension == "sex":
        return SEX[category]
    return category.lower().replace("-", "_")


def read(indicator: str) -> dict[tuple[str, str, int], float]:
    dataset, fixed, kept, _ = SLICES[indicator]
    body = json.loads((FOLDER / f"{dataset}.json").read_text(encoding="utf-8"))
    ids = body["id"]
    sizes = body["size"]
    categories = {d: body["dimension"][d]["category"]["index"] for d in ids}
    for dimension, category in fixed.items():
        if category not in categories[dimension]:
            raise ValueError(f"Eurostat {dataset}: {dimension}={category} yok")
    unexpected = set(ids) - set(fixed) - set(kept) - {"geo", "time"}
    if unexpected:
        raise ValueError(f"Eurostat {dataset}: seçilmemiş boyut {unexpected}")
    strides = [1] * len(ids)
    for i in range(len(ids) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    values, status = body["value"], body.get("status", {})
    loop = [
        [(fixed[d], categories[d][fixed[d]])]
        if d in fixed
        else list(categories[d].items())
        for d in ids
    ]
    out: dict[tuple[str, str, int], float] = {}
    for combo in product(*loop):
        flat = sum(position * strides[i] for i, (_, position) in enumerate(combo))
        value = values.get(str(flat)) if isinstance(values, dict) else values[flat]
        if value is None:
            continue
        cell = dict(zip(ids, (c for c, _ in combo), strict=True))
        dims = ";".join(
            f"{name}={value_code(d, cell[d])}"
            for d, name in sorted(kept.items(), key=lambda x: x[1])
        )
        key = (cell["geo"], dims, int(cell["time"]))
        if key in out:
            raise ValueError(f"Eurostat {dataset}: {key} iki kez")
        out[key] = float(value)
        if str(flat) in status:
            FLAGS[(indicator, status[str(flat)])] += 1
    return out


class EurostatRegional:
    source_id = "eurostat"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        unit = SLICES[self.indicator_id][3]
        records = [
            {
                "area_id": geo,
                "area_level": "country" if geo == "TR" else "nuts2",
                "period_start": dt.date(year, 1, 1),
                "dims": dims,
                "value": value,
            }
            for (geo, dims, year), value in read(self.indicator_id).items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit(unit).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


EUROSTAT_REGIONAL_ADAPTERS = {
    indicator: type(
        f"EurostatRegional_{indicator}",
        (EurostatRegional,),
        {"indicator_id": indicator},
    )
    for indicator in SLICES
}
