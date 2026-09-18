r"""TKGM MEGSİS: how much of the cadastre is on the map, province by province.

`scripts/fetch_tkgm_megsis.py` saves the province table of
cbs.tkgm.gov.tr/istatistik/MegsisGenel.aspx as a CSV in `C:\veri-ham\tkgm\`. It is a
snapshot of the day it was taken, not a series — the page prints one "Güncelleme Tarihi"
and no history — so it is stored under the year of that date and will be replaced, not
appended to, when it is taken again.

Three readings of the same parcels, which is why they are three indicators and not one
breakdown: what the registers hold (the title deed's parcels, the cadastre's parcels, and
the parcels the cadastre has but the title deed does not), whether the parcel's geometry
has been approved, and how good its coordinates are. Adding across those three would count
the same parcel three times.

`onayli_oran` is not written: it is the approved share, which follows from the counts.
"""

from __future__ import annotations

import csv
import datetime as dt
from functools import cache
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import province_id, provinces

FOLDER = RAW / "tkgm" if (RAW / "tkgm").exists() else Path("C:/veri-ham/tkgm")
SOURCE = "tkgm_megsis"

#: Indicator -> {CSV column: dimension value}. The dim key is the indicator's own.
REGISTERS = {
    "tapu_parsel": "title_deed",
    "kadastro_parsel": "cadastre",
    "tapuda_olmayan_parsel": "not_in_title_deed",
}
APPROVALS = {"onayli_parsel": "approved", "onaysiz_parsel": "unapproved"}
COORDINATES = {
    "kesin_koordinatli": "final",
    "gecici_koordinatli": "provisional",
    "iyilestirilmis_koordinatli": "improved",
}


def snapshot() -> Path:
    """The newest saved snapshot; the file name carries the page's update date."""
    files = sorted(FOLDER.glob("megsis_il_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"TKGM anlık görüntüsü yok: {FOLDER} (scripts/fetch_tkgm_megsis.py)"
        )
    return files[-1]


@cache
def table() -> tuple[dt.date, dict[str, dict[str, float]]]:
    """(snapshot date, {area_id: {column: count}}), with all 81 provinces or it raises."""
    path = snapshot()
    taken = dt.date.fromisoformat(path.stem.rsplit("_", 1)[1])
    rows: dict[str, dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            area = province_id(row["il"])
            if area in rows:
                raise ValueError(f"TKGM: {row['il']} iki kez")
            rows[area] = {
                column: float(row[column])
                for column in (*REGISTERS, *APPROVALS, *COORDINATES)
            }
    missing = sorted(set(provinces().values()) - set(rows))
    if missing:
        raise ValueError(f"TKGM: eksik il {missing}")
    return taken, rows


class Megsis:
    """One reading of the parcel table, as of the snapshot date."""

    source_id = SOURCE
    unit = "parcel"
    indicator_id: str
    dim: str
    columns: dict[str, str]

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        taken, rows = table()
        records = [
            {
                "area_id": area,
                "dims": f"{self.dim}={value}",
                "value": counts[column],
            }
            for area, counts in sorted(rows.items())
            for column, value in self.columns.items()
        ]
        return (
            pl.DataFrame(records)
            .with_columns(
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit("province").alias("area_level"),
                pl.lit(dt.date(taken.year, 1, 1)).alias("period_start"),
                pl.lit("annual").alias("frequency"),
                pl.lit(self.unit).alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit(taken.strftime("%Y-%m")).alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(taken).alias("retrieved_at"),
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


class Parcels(Megsis):
    indicator_id = "cadastral_parcels"
    dim = "parcel_register"
    columns = REGISTERS


class ParcelApproval(Megsis):
    indicator_id = "cadastral_parcels_by_approval"
    dim = "parcel_approval"
    columns = APPROVALS


class ParcelCoordinates(Megsis):
    indicator_id = "cadastral_parcels_by_coordinate"
    dim = "coordinate_quality"
    columns = COORDINATES


TKGM_ADAPTERS = {
    "cadastral_parcels": Parcels,
    "cadastral_parcels_by_approval": ParcelApproval,
    "cadastral_parcels_by_coordinate": ParcelCoordinates,
}
