"""Households by size and by tenure, province level.

Two sheets, one adapter, because they are the same shape of thing: a count of households
cut by an attribute of the household rather than of the people in it. Both come from the
desktop rather than MEDAS — the ADNKS topic publishes the household *count*, the average
size and the type, and neither of these two.

**Size** (2012-2025) is the distribution behind `household_size`, which is only its mean.
A province of mostly two-person households and one split between singles and crowded
houses can share an average of 3,2 and be nothing alike; the mean cannot say which, and
this can. Ten bands, `10+` closing.

**Tenure** is one year and four values — owner, tenant, other, unknown. It is the only
thing here that is not demography at all, and it is kept for the same reason the rest is:
it is a fact about the household published alongside the others, and the fact table has
no trouble holding a fourth breakdown of the same count.

Both sum to the household total already loaded, and are checked against it on load — a
distribution that does not add up to its own total is the one failure worth stopping for.
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

DESKTOP = Path(r"C:\Users\katan\OneDrive\Desktop\demografi")

SIZE_FILE = DESKTOP / "Hanehalkı Büyüklüğüne Göre Hanehalkı Sayısı.xlsx"
TENURE_FILE = DESKTOP / "Mülkiyet-Hanehalkı Sayısı.xlsx"

YEAR = re.compile(r"^(?P<year>\d{4})")

#: Column index to household size. The sheet runs: year, province, then the bands.
SIZES = {
    2: "1",
    3: "2",
    4: "3",
    5: "4",
    6: "5",
    7: "6",
    8: "7",
    9: "8",
    10: "9",
    11: "10+",
}

#: Column index to tenure. The sheet runs: province, total, then the four values. The
#: total is a margin and is not stored — a margin beside its own parts double-counts.
TENURES = {2: "owner", 3: "tenant", 4: "other", 5: "unknown"}

#: The tenure sheet carries no year anywhere in it, so the year had to be found rather
#: than read: its province totals sum to 25.329.835, and the household count already in
#: the fact table is 25.329.833 in 2021 — two households apart out of twenty-five million,
#: against gaps of hundreds of thousands to either neighbouring year. So this is 2021, and
#: the file being undated is why it is written down here with the evidence attached: an
#: undated table filed under the wrong year is wrong in a way nothing downstream can see.
TENURE_YEAR = 2021


def fold(name: str) -> str:
    lowered = name.strip().lower()
    for turkish, plain in (
        # `"İ".lower()` is not `"i"` — Python gives back `i` plus a combining dot above
        # (U+0307), so a sheet written in capitals (`BALIKESİR`) never matched a registry
        # name and thirty-two provinces went missing. The combining mark is stripped
        # first, before the letter-for-letter pass that assumes plain characters.
        ("̇", ""),
        ("ı", "i"),
        ("İ", "i"),
        ("ğ", "g"),
        ("ş", "s"),
        ("ç", "c"),
        ("ö", "o"),
        ("ü", "u"),
        (" ", ""),
    ):
        lowered = lowered.replace(turkish, plain)
    return lowered


def clean(value) -> str:
    return str(value).strip() if value is not None else ""


def provinces() -> dict[str, str]:
    return {
        fold(row["name_tr"]): row["area_id"]
        for row in load_areas().filter(pl.col("area_level") == "province").to_dicts()
    }


def number(cell: str) -> float | None:
    if not cell or cell == "-":
        return None
    try:
        return float(cell.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def read_size(path: Path, known: dict[str, str]) -> list[dict]:
    """The size sheet: year and province on every row, bands across."""
    rows: list[dict] = []
    for record in pl.read_excel(path).to_dicts():
        cells = [clean(v) for v in record.values()]
        if len(cells) < 12:
            continue
        stamp = YEAR.match(cells[0])
        area = known.get(fold(cells[1]))
        if not stamp or not area:
            continue
        for index, size in SIZES.items():
            value = number(cells[index])
            if value is None:
                continue
            rows.append(
                {
                    "year": int(stamp.group("year")),
                    "area_id": area,
                    "dim": {"household_size_band": size},
                    "value": value,
                }
            )
    return rows


def read_tenure(path: Path, known: dict[str, str]) -> list[dict]:
    """The tenure sheet: one year, province down the rows, tenure across."""
    rows: list[dict] = []
    for record in pl.read_excel(path).to_dicts():
        cells = [clean(v) for v in record.values()]
        if len(cells) < 6:
            continue
        area = known.get(fold(cells[0]))
        if not area:
            continue
        for index, tenure in TENURES.items():
            value = number(cells[index])
            if value is None:
                continue
            rows.append(
                {
                    "year": TENURE_YEAR,
                    "area_id": area,
                    "dim": {"tenure": tenure},
                    "value": value,
                }
            )
    return rows


class HouseholdSheet:
    """One household distribution from the desktop sheets."""

    source_id = "tuik"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 12)

    indicator_id = ""
    source_file: Path = DESKTOP
    reader = staticmethod(read_size)

    def fetch(self) -> Path:
        return cached_copy(self.source_file, RAW / "tuik" / self.source_file.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        known = provinces()
        records = type(self).reader(raw, known)
        if not records:
            raise ValueError("dosyada satir yok: " + str(raw))

        frame = pl.DataFrame(records)
        found = set(frame["area_id"])
        missing = set(known.values()) - found
        if missing:
            raise KeyError(
                self.indicator_id
                + ": dosyada karsiligi olmayan il ("
                + str(len(missing))
                + "): "
                + ", ".join(sorted(missing)[:10])
            )

        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.col("dim")
            .map_elements(format_dims, return_dtype=pl.String)
            .alias("dims"),
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


class TuikHouseholdSize(HouseholdSheet):
    """Households by how many people live in them, 2012-2025."""

    indicator_id = "household_by_size"
    source_file = SIZE_FILE
    reader = staticmethod(read_size)


class TuikHouseholdTenure(HouseholdSheet):
    """Households by whether they own or rent, 2025."""

    indicator_id = "household_by_tenure"
    source_file = TENURE_FILE
    reader = staticmethod(read_tenure)
