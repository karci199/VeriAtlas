"""Deaths by cause and province, 2022-2025.

A theme this repository did not have: until now a death was a death, counted by age and
sex. This says what people died *of* — nine groups covering the whole, so they sum to the
death count already loaded rather than sitting beside it as a different measurement.

MEDAS does not publish it; the death topic there offers sex, month, age and marital
status, and no cause at all. It comes as a spreadsheet, read the way `tuik_tfr` and
`tuik_birth_order` are read, with a copy kept under `raw/`.

**Only four years, and that is the source.** TÜİK revised the cause series onto a new
basis and publishes 2022 onward; the earlier years are not missing from the download,
they are not comparable and are not offered.

Two things in this table are worth knowing before reading it:

* **Dışsal yaralanma is where the earthquake is.** Adıyaman's external-cause deaths run
  at 122 in 2022 and 8.342 in 2023. That is 6 February, not a data error, and it is the
  clearest reason to keep the cause groups separate rather than folding them into
  "diğer".
* **COVID-19 has its own column and it empties out.** 22.054 deaths nationally in 2022,
  1.718 in 2023, 202 in 2024, 2 in 2025. A column that goes to almost nothing is still a
  column: dropping it would move those deaths into "diğer" and lose the shape of the
  ending.

`Bilinmeyen` is kept for the same reason every unknown here is kept — without it the
causes sum to less than the deaths they break down.
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

SOURCE_FILE = Path(
    r"C:\Users\katan\OneDrive\Desktop\demografi\Ölüm"
    r"\İl ve seçilmiş ölüm nedenlerine göre ölümler.xls"
)

#: `2023(r)` — the revision mark is about the vintage, not about which year it is.
YEAR = re.compile(r"^(?P<year>\d{4})")

#: Column index to cause id. The sheet runs: province, year, total, then the nine groups.
#: Ids in English (K1); the Turkish lives in the dictionary.
CAUSES = {
    3: "circulatory",
    4: "neoplasms",
    5: "respiratory",
    6: "nervous",
    7: "endocrine",
    8: "external",
    9: "covid19",
    10: "other",
    11: "unknown",
}


def fold(name: str) -> str:
    """Turkish name to a comparable key. Same rule the other registries use."""
    lowered = name.strip().lower()
    for turkish, plain in (
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


def read_export(path: Path) -> list[dict]:
    """The sheet as one row per (year, area, cause)."""
    areas = load_areas()
    provinces = {
        fold(row["name_tr"]): row["area_id"]
        for row in areas.filter(pl.col("area_level") == "province").to_dicts()
    }

    frame = pl.read_excel(path)
    rows: list[dict] = []
    area_id = None
    level = None
    unknown: set[str] = set()

    for record in frame.to_dicts():
        cells = [clean(v) for v in record.values()]
        if len(cells) < 12:
            continue

        # The province is written once, on its first year, and the three rows under it
        # leave the cell empty — so it carries down until the sheet names another.
        if cells[0]:
            name = fold(cells[0])
            if name == "turkiye":
                area_id, level = "TR", "country"
            elif name in provinces:
                area_id, level = provinces[name], "province"
            else:
                area_id, level = None, None
                # Only a row that actually carries a year is a data row; the sheet's own
                # header says `İl-Province` in this cell and would otherwise be reported
                # as a province the registry does not know.
                if YEAR.match(cells[1]):
                    unknown.add(cells[0])

        stamp = YEAR.match(cells[1])
        if not stamp or area_id is None:
            continue
        year = int(stamp.group("year"))

        for index, cause in CAUSES.items():
            cell = cells[index]
            if not cell or cell == "-":
                # "-" is "no data", which here means no death of that cause was recorded.
                # Left out rather than written as a zero.
                continue
            try:
                value = float(cell.replace(" ", "").replace(",", "."))
            except ValueError:
                continue
            rows.append(
                {
                    "year": year,
                    "area_id": area_id,
                    "area_level": level,
                    "cause": cause,
                    "value": value,
                }
            )

    if unknown:
        # Named rather than skipped: a province dropped here takes its deaths with it and
        # the year still looks complete.
        raise KeyError(
            "kayitta karsiligi olmayan il: " + ", ".join(sorted(unknown)[:10])
        )
    return rows


class TuikDeathCause:
    """Deaths by cause, province and country."""

    source_id = "tuik"
    indicator_id = "deaths_by_cause"

    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 12)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "tuik" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        records = read_export(raw)
        if not records:
            raise ValueError("dosyada satir yok: " + str(raw))

        frame = pl.DataFrame(records)

        # Every province or none, the guard the other adapters keep.
        expected = set(
            load_areas().filter(pl.col("area_level") == "province")["area_id"]
        )
        found = set(frame.filter(pl.col("area_level") == "province")["area_id"])
        if expected - found:
            raise KeyError(
                "dosyada karsiligi olmayan il ("
                + str(len(expected - found))
                + "): "
                + ", ".join(sorted(expected - found)[:10])
            )

        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.col("cause")
            .map_elements(lambda c: format_dims({"cause": c}), return_dtype=pl.String)
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
