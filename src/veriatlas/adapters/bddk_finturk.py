r"""BDDK FinTürk: banking by province and bank group, December 2007-2025.

`scripts/fetch_bddk_finturk.py` keeps one JSON answer per table, bank group and year in
`C:\veri-ham\bddk\finturk\<table>-<group>-<year>.json`: one row per province (plus YURT DIŞI,
branches abroad, not written) with the table's columns in thousand TL.

Tables loaded: 1 loans, 2 deposits, 3 retail banking, 4 selected sectoral loans, 6 branches
(the branch count only; population per branch and per-capita amounts are derived from the
others), 7 gold loans and deposits (from 2015). Table 5, ratios, is derived from 1-4 and is not
loaded. Development and investment banks take no deposits: their table 2 answers with an error,
and there is nothing to write.

Bank groups: the sector, split two ways. By kind: deposit + development and investment +
participation banks. By ownership: state + domestic private + foreign (all kinds).

Checks: for every table, year, province and column both splits add up to the sector (within 2 thousand
TL, the rounding of the source); deposits: savings = TL + FX, other =
TL + FX, total = savings + other; loans: total cash = performing + non-performing.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold, province_id

FOLDER = (
    RAW / "bddk" / "finturk"
    if (RAW / "bddk").exists()
    else Path("C:/veri-ham/bddk/finturk")
)
GROUPS = {
    10001: "sector",
    10002: "deposit",
    10003: "development_investment",
    10004: "participation",
    10005: "foreign",
    10006: "state",
    10007: "domestic_private",
}
SECTORS = (
    "food_beverage_tobacco",
    "construction",
    "metal_mining",
    "financial_institutions",
    "textiles",
    "wholesale_trade",
    "tourism",
    "agriculture_fishing",
    "energy",
    "maritime",
)
#: table -> (indicator, column item codes in printed order; None drops the column)
TABLES = {
    1: (
        "bank_group_loans",
        ["cash_total", "cash_performing", "non_performing", "non_cash"],
    ),
    2: (
        "bank_group_deposits",
        [
            "savings",
            "savings_try",
            "savings_fx",
            "other",
            "other_try",
            "other_fx",
            "total",
        ],
    ),
    3: (
        "bank_group_retail_loans",
        [
            "vehicle",
            "housing",
            "overdraft",
            "other_consumer",
            "credit_cards",
            "vehicle_non_performing",
            "housing_non_performing",
            "other_consumer_non_performing",
        ],
    ),
    4: (
        "bank_group_sector_loans",
        [f"{s}_cash" for s in SECTORS]
        + [f"{s}_non_performing" for s in SECTORS]
        + ["credit_cards_non_performing"]
        + [f"{s}_non_cash" for s in SECTORS],
    ),
    6: ("bank_group_branches", ["branches", None, None, None, None, None]),
    7: (
        "bank_group_gold",
        [
            "gold_loans",
            "gold_deposits_persons",
            "gold_deposits_companies",
            "gold_deposits",
        ],
    ),
}
ABROAD = "yurtdisi"


def read(table: int) -> dict[tuple[str, int, int, str], float]:
    """{(province, year, group, item): value} for one table, every file on disk."""
    _, items = TABLES[table]
    out: dict[tuple[str, int, int, str], float] = {}
    for path in sorted(FOLDER.glob(f"{table}-*.json")):
        _, group, year = (int(x) for x in path.stem.split("-"))
        answer = json.loads(path.read_text(encoding="utf-8"))
        if not answer.get("success"):
            continue
        body = answer["Json"]
        if len(body["colNames"]) - 5 != len(items):
            raise ValueError(f"FinTürk {path.name}: {len(body['colNames']) - 5} sütun")
        for row in body["data"]["rows"]:
            cell = row["cell"]
            if cell[0] != group or cell[1] != year or cell[2] != 12:
                raise ValueError(
                    f"FinTürk {path.name}: satır başka döneme ait {cell[:3]}"
                )
            if fold(cell[3]) == ABROAD:
                continue
            area = province_id(cell[3])
            for item, value in zip(items, cell[5:], strict=True):
                if item is None:
                    continue
                key = (area, year, group, item)
                if key in out:
                    raise ValueError(f"FinTürk {path.name}: {key} iki kez")
                out[key] = float(value or 0)
    return out


def check(table: int, data: dict) -> None:
    def get(area, year, group, item):
        return data.get((area, year, group, item), 0.0)

    cells = {(a, y, i) for a, y, _, i in data}
    for area, year, item in cells:
        sector = get(area, year, 10001, item)
        parts = (
            get(area, year, 10002, item)
            + get(area, year, 10003, item)
            + get(area, year, 10004, item)
        )
        owners = sum(get(area, year, g, item) for g in (10005, 10006, 10007))
        if abs(sector - parts) > 2 or abs(sector - owners) > 2:
            raise ValueError(
                f"FinTürk tablo {table} {area} {year} {item}: sektör {sector:,.0f}, "
                f"banka türleri {parts:,.0f}, sahiplik {owners:,.0f}"
            )
    rules = {
        2: [
            ("savings", ("savings_try", "savings_fx")),
            ("other", ("other_try", "other_fx")),
            ("total", ("savings", "other")),
        ],
        1: [("cash_total", ("cash_performing", "non_performing"))],
    }.get(table, [])
    for area, year, group, _ in {k[:3] + (None,) for k in data}:
        for whole, pieces in rules:
            left = get(area, year, group, whole)
            right = sum(get(area, year, group, p) for p in pieces)
            if abs(left - right) > 2:
                raise ValueError(
                    f"FinTürk tablo {table} {area} {year} grup {group}: {whole} {left:,.0f}, "
                    f"{'+'.join(pieces)} {right:,.0f}"
                )


class FinturkTable:
    source_id = "bddk"
    table = 0
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        data = read(self.table)
        check(self.table, data)
        unit = "facility" if self.table == 6 else "thousand_try"
        records = [
            {
                "area_id": area,
                "period_start": dt.date(year, 1, 1),
                "dims": f"bank_group={GROUPS[group]};finturk_item={item}"
                if len(TABLES[self.table][1]) > 1 and self.table != 6
                else f"bank_group={GROUPS[group]}",
                "value": value,
            }
            for (area, year, group, item), value in sorted(data.items())
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit(unit).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


FINTURK_ADAPTERS = {
    indicator: type(
        re.sub(r"\W", "", indicator.title()),
        (FinturkTable,),
        {"table": table, "indicator_id": indicator},
    )
    for table, (indicator, _) in TABLES.items()
}
