"""EVDS archive groups, one indicator per group, Türkiye only.

The archive is 178 retired tables (old price bases, 1987/1998 accounts, labour and
industry series, old budget and balance-of-payments presentations). They are stored as
they are: one indicator per group, one dimension value per series, unit "source unit"
because the unit and base year live in each series name and differ inside a group.

The group list is generated (`data/evds_archive_groups.json`) and lists the series codes
kept: the group's main frequency only, series with at least one value. A code present in
the download but not in the list — or listed but gone — is an error, not a skip.
Excluded on purpose: `bie_urgsyih2` (series names belong to a banking table).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..config import DATA, RAW
from ..indicators import get
from ..schema import format_dims
from .evds_series import item_value, rows_of

DOWNLOADS = RAW / "evds"
GROUPS = json.loads((DATA / "evds_archive_groups.json").read_text(encoding="utf-8"))


class EvdsArchive:
    source_id = "cbrt_evds"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 14)
    indicator_id = ""
    #: Group specs by indicator id; `evds_groups.py` reuses the class with its own list.
    groups = GROUPS

    def fetch(self) -> Path:
        spec = self.groups[self.indicator_id]
        # Daily groups were downloaded as monthly averages, `<group>-aylik.json`.
        return DOWNLOADS / spec.get("file", spec["group"] + ".json")

    def parse(self, raw: Path) -> pl.DataFrame:
        spec = self.groups[self.indicator_id]
        payload = json.loads(raw.read_text(encoding="utf-8"))
        kept = set(spec["codes"])
        present = {s["SERIE_CODE"] for s in payload["series"]}
        if not kept <= present:
            raise KeyError(
                f"{self.indicator_id}: listedeki seri indirmede yok: {sorted(kept - present)[:5]}"
            )
        records = [
            {
                "area_id": "TR",
                "area_level": "country",
                "period_start": date,
                "dims": format_dims({spec["dim"]: item_value(series["SERIE_CODE"])}),
                "value": value,
            }
            for series, date, value in rows_of(payload)
            if series["SERIE_CODE"] in kept
        ]
        frame = pl.DataFrame(records)
        if frame.select("period_start", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni kalem-donem iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
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


EVDS_ARCHIVE_ADAPTERS = {
    "evds_" + ident: type(
        "Evds" + "".join(p.title() for p in ident.split("_")),
        (EvdsArchive,),
        {"indicator_id": ident},
    )
    for ident in GROUPS
}
