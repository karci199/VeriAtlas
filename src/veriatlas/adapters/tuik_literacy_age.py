"""Literacy status by sex and age band, province and country, 6+ population, 2008 & 2025.

The third literacy file: same source and row shape as `tuik_literacy`, but scoped to
6+ rather than 15+ and broken down by thirteen age bands (`6-13` up to `65+`) instead
of a single threshold — a genuinely finer breakdown, not a re-cut of the other two, so
it is its own indicator rather than an `age` dim bolted onto `literacy`. Mixing them
would put a "15+ total" value in the same dim as "14-17", and summing the age dim would
double-count everyone 15 and over.

Two years only (2008, 2025) — MEDAS was asked for those two, not a series.
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

SOURCE_FILE = Path(
    r"C:\Users\katan\OneDrive\Desktop\demografi\İllereGoreOkumaYazmaYaslar.csv"
)

SEXES = {"Erkek": "male", "Kadın": "female"}
STATUSES = {
    "Okuma Yazma Bilen": "literate",
    "Okuma Yazma Bilmeyen": "illiterate",
    "Bilinmeyen": "unknown",
}

#: Age bands come through as-is (`6-13`, `65+`) — no id mapping needed, same as every
#: other age dim in the fact table.
LABEL_IN_ROW = re.compile(
    r"^(?P<sex>Erkek|Kadın) ve (?P<age>[\d]+-[\d]+|\d+\+) ve (?P<status>.+)$"
)


class TuikLiteracyAge:
    """Literacy status (6+), sex × age × status, province and country, 2008 & 2025."""

    source_id = "tuik_medas"
    indicator_id = "literacy_by_age"

    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 17)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "tuik_medas" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        single = single_province_regions()
        lines = read_text(raw).splitlines()

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
                {
                    "sex": SEXES[parsed.group("sex")],
                    "age": parsed.group("age"),
                    "literacy_status": STATUSES[status],
                }
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
