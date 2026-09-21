"""Literacy status by sex, province and country, 15+ population, 2008-2025.

The province-level counterpart to `tuik_literacy_district`: same measure, same 15+
scope, same row-label shape (`Erkek ve 15+ Yaş ve Okuma Yazma Bilmeyen`), but a full
annual series rather than two snapshots, and provinces are matched by plate number
(`Adana-1`) the way `tuik_marital` and `tuik_median_age` do it — not the MEDAS district
code the district file uses.

İBBS columns ride along in the export (`Adana, Mersin-TR62`) and are dropped rather
than stored: a region spanning more than one province is not a level this fact table
keeps, and `area_of` already encodes that rule for every other province-level adapter.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .base import cached_copy
from .tuik_median_age import area_of, single_province_regions
from .tuik_simple import LABEL, read_text

SOURCE_FILE = Path(r"C:\Users\katan\OneDrive\Desktop\demografi\OkumaYazmaİller.csv")

SEXES = {"Erkek": "male", "Kadın": "female"}
STATUSES = {
    "Okuma Yazma Bilen": "literate",
    "Okuma Yazma Bilmeyen": "illiterate",
    "Bilinmeyen": "unknown",
}

LABEL_IN_ROW = re.compile(r"^(?P<sex>Erkek|Kadın) ve 15\+ Yaş ve (?P<status>.+)$")


class TuikLiteracy:
    """Literacy status (15+), sex × status, province and country, 2008-2025."""

    source_id = "tuik_medas"
    indicator_id = "literacy"

    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 17)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "tuik_medas" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        single = single_province_regions()
        lines = read_text(raw).splitlines()

        # Header found by "names the most areas", the same rule the district adapters
        # use — a leading blank cell count has moved between MEDAS exports before.
        header: dict[int, tuple[str, str]] = {}
        for line in lines:
            found: dict[int, tuple[str, str]] = {}
            for index, cell in enumerate(line.split("|")):
                match = LABEL.match(cell.strip())
                if not match:
                    continue
                area = area_of(match.group("code"), single)
                if area:
                    found[index] = area
            if len(found) > len(header):
                header = found
        if not header:
            raise KeyError(self.indicator_id + ": dosyada alan sutunu bulunamadi")

        records: list[dict] = []
        label = ""
        for line in lines:
            cells = line.split("|")
            if len(cells) < 4:
                continue
            stamp = cells[2].strip()
            if not (stamp.isdigit() and len(stamp) == 4):
                continue
            year = int(stamp)
            if cells[1].strip():
                label = cells[1].strip()

            parsed = LABEL_IN_ROW.match(label)
            if not parsed:
                raise ValueError(
                    self.indicator_id + ": beklenmeyen satir etiketi: " + label
                )
            status = parsed.group("status")
            if status not in STATUSES:
                raise KeyError(
                    self.indicator_id + ": bilinmeyen okuma yazma durumu: " + status
                )
            dims = format_dims(
                {"sex": SEXES[parsed.group("sex")], "literacy_status": STATUSES[status]}
            )

            for index, (area_id, area_level) in header.items():
                if index >= len(cells):
                    continue
                cell = cells[index].strip()
                if not cell:
                    continue
                records.append(
                    {
                        "area_id": area_id,
                        "area_level": area_level,
                        "year": year,
                        "dims": dims,
                        "value": float(cell),
                    }
                )

        if not records:
            raise ValueError(self.indicator_id + ": dosyada satir yok")

        frame = pl.DataFrame(records).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        )

        # Every province or none — the guard every other province adapter keeps. A
        # province quietly absent draws as "veri yok" in the middle of the map, which
        # nobody can tell from a real gap.
        expected = set(
            load_areas().filter(pl.col("area_level") == "province")["area_id"]
        )
        last = frame.select(pl.col("year").max()).item()
        found = set(frame.filter(pl.col("year") == last)["area_id"])
        if expected - found:
            raise KeyError(
                self.indicator_id
                + ": son yilda karsiligi olmayan il ("
                + str(len(expected - found))
                + "): "
                + ", ".join(sorted(expected - found))
            )

        return frame.select(
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
