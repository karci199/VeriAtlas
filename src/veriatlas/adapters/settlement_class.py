"""Settlement class of every neighbourhood we classified by hand: district centre, urban
town (kentsel belde), rural town (kırsal belde) or village.

Source: `raw/kent_kir/kullanici_karar.json`, the review decisions of 2026-09/10 for Ankara,
Bursa, Denizli, İstanbul and Manisa (`scripts/analiz/kent_kir_2026_09_27/`). Each key is a
neighbourhood id; `s` is the decided class, `n` the note, `k` the cluster of units counted
as one town. One row per neighbourhood, value 1: join with `population` to get the urban and
rural population. The cluster stays in the JSON, a cluster name is not a dimension value.

Checks: a class we do not know is an error, an id the registry does not hold is an error
(a typo would silently drop a place from the urban population). The one exception: the
organised-industrial-zone and census-block rows (OSB, Sb) of the review carry no
population and are no registry neighbourhoods; they are recognised by the note and left out.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..areas import load_neighbourhoods
from ..config import RAW

FILE = RAW / "kent_kir" / "kullanici_karar.json"
CLASSES = {
    "İlçe Merkezi": "district_center",
    "Kentsel Belde": "urban_town",
    "Kırsal Belde": "rural_town",
    "Köy": "village",
}


class SettlementClass:
    source_id = "kullanici_karar"
    indicator_id = "settlement_class"

    def fetch(self) -> Path:
        return FILE

    def parse(self, raw: Path) -> pl.DataFrame:
        decisions = json.loads(raw.read_text("utf-8"))
        known = set(load_neighbourhoods()["area_id"].to_list())
        unknown_class = sorted({d["s"] for d in decisions.values()} - set(CLASSES))
        if unknown_class:
            raise ValueError("bilinmeyen sinif: " + ", ".join(unknown_class))
        zone = re.compile(r"osb|\bsb\b", re.IGNORECASE)
        missing = sorted(
            a for a, d in decisions.items() if a not in known and not zone.search(d["n"])
        )
        if missing:
            raise ValueError(f"kayitta olmayan {len(missing)} mahalle: {missing[:6]}")
        records = [
            {
                "area_id": area_id,
                "dims": f"settlement_class={CLASSES[d['s']]}",
                "value": 1.0,
            }
            for area_id, d in sorted(decisions.items())
            if area_id in known
        ]
        return pl.DataFrame(records, schema_overrides={"value": pl.Float64}).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("neighbourhood").alias("area_level"),
            pl.lit(dt.date(2024, 1, 1)).alias("period_start"),
            pl.lit("annual").alias("frequency"),
            pl.lit("item").alias("unit"),
            pl.lit("estimated").alias("quality_flag"),
            pl.lit("2026-10").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 10, 3)).alias("retrieved_at"),
        )


SETTLEMENT_CLASS_ADAPTERS = {SettlementClass.indicator_id: SettlementClass}
