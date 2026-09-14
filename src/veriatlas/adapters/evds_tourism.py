"""Foreign visitors arriving in Türkiye by nationality, monthly — CBRT EVDS `bie_odemgzs`.

Downloaded by `scripts/fetch_evds_housing.py bie_odemgzs`. The group holds a tree: five
continent totals, a grand total, and under each continent its countries plus an "other"
row. Only the leaves are stored — every country, each continent's "other", and the
nationless "Diğer" — so no number is stored twice; continents and the total are sums.

The leaves are checked against the published grand total month by month: a country
missing from the tree would otherwise vanish without a trace.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get, load
from ..schema import format_dims

DOWNLOAD = RAW / "evds" / "bie_odemgzs.json"
TOTAL = "TP.ODEMGZS.GTOPLAM"

#: Before 2008 the group is not monthly: one December row per year holding the annual
#: total, and only 51-52 countries, whose sum falls 0.8-2.3 million short of the grand
#: total. Stored as monthly it would read as twelve empty months and a December spike.
FIRST_MONTHLY_YEAR = 2008


def leaves(series: list[dict]) -> list[dict]:
    parents = {s["UST_SERIE_CODE"] for s in series}
    return [
        s for s in series if s["SERIE_CODE"] != TOTAL and s["SERIE_CODE"] not in parents
    ]


def value_id(code: str) -> str:
    return code.rsplit(".", 1)[1].lower()


class EvdsVisitorsByNationality:
    source_id = "cbrt_evds"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 14)
    indicator_id = "foreign_visitors_by_nationality"

    def fetch(self) -> Path:
        return DOWNLOAD

    def parse(self, raw: Path) -> pl.DataFrame:
        payload = json.loads(raw.read_text(encoding="utf-8"))
        kept = leaves(payload["series"])
        declared = load().dimensions["visitor_country"].values_tr
        missing = [
            s["SERIE_CODE"] for s in kept if value_id(s["SERIE_CODE"]) not in declared
        ]
        if missing:
            raise KeyError("sozlukte olmayan ulke: " + ", ".join(missing))

        total_col = TOTAL.replace(".", "_")
        records: list[dict] = []
        for item in payload["items"]:
            year, month = (int(p) for p in item["Tarih"].split("-"))
            if year < FIRST_MONTHLY_YEAR:
                continue
            month_sum, seen = 0.0, False
            for s in kept:
                cell = item.get(s["SERIE_CODE"].replace(".", "_"))
                if cell in (None, ""):
                    continue
                seen = True
                month_sum += float(cell)
                records.append(
                    {
                        "area_id": "TR",
                        "period_start": dt.date(year, month, 1),
                        "dims": format_dims(
                            {"visitor_country": value_id(s["SERIE_CODE"])}
                        ),
                        "value": float(cell),
                    }
                )
            total = item.get(total_col)
            # A few people either way is the source's own rounding (July 2025: 8 of
            # several million); a missing country is tens of thousands at least.
            if (
                seen
                and total not in (None, "")
                and abs(month_sum - float(total)) > max(100, float(total) * 0.0001)
            ):
                raise ValueError(
                    f"{item['Tarih']}: ulkeler toplami {month_sum:.0f}, genel toplam {total}"
                )
        indicator = get(self.indicator_id)
        return (
            pl.DataFrame(records)
            .with_columns(
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit("country").alias("area_level"),
                pl.lit(indicator.frequency).alias("frequency"),
                pl.lit(indicator.unit.unit_id).alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit(self.vintage).alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(self.retrieved_at).alias("retrieved_at"),
            )
            .select(
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
        )
