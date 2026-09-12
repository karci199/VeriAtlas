"""Births by the mother's age group and the birth order, Türkiye, 2012-2025.

The one thing about a birth this repository cannot work out for itself. Everything else
on the fertility side is arithmetic over rows we already hold — the age-specific rate is
births over women of that age, the general rate is births over women 15-49 — but whether
a birth was the mother's first or her fourth is not in any count of births. It has to
come from the source or not at all.

It comes as a spreadsheet rather than through MEDAS, which does not publish the order at
all (its birth measure offers month, sex and the mother's age group, and that is the
whole list). So this reads the desktop file the way `tuik_tfr` and `tuik_median_age` do,
keeping a copy under `raw/` that the load actually reads (`cached_copy`) — the original
moves, the copy is what the manifest describes.

**Country only, and its own indicator.** TÜİK publishes the order for Türkiye and not by
province, so folding it into `births` would give one indicator two shapes depending on
the area picked — the same trap `deaths_single_age` is kept out of. The two are checked
against each other instead: the order breakdown sums to the same births in every year.

The table is a cross — the mother's age down the rows, the order across the columns — and
both margins are written into it as `Toplam`. Only the inner cells are stored; a margin
loaded beside the cells it totals would double every birth under "Tümü (topla)".
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .base import cached_copy

SOURCE_FILE = Path(
    r"C:\Users\katan\OneDrive\Desktop\demografi"
    r"\Annenin yaş grubu ve doğum sırasına göre  doğumlar.xls"
)

#: `2020(r)` — the year with TÜİK's revision mark, which is about the data's vintage and
#: not about which year it is.
YEAR = re.compile(r"^(?P<year>\d{4})")

#: The age groups as the sheet writes them, to the ids the fact table stores (K1). The
#: sheet splits 15-19 into 15-17 and 18-19, which MEDAS does not — kept as published
#: rather than merged, since merging is possible later and splitting is not.
AGES = {
    "<15": "-15",
    "15-17": "15-17",
    "18-19": "18-19",
    "20-24": "20-24",
    "25-29": "25-29",
    "30-34": "30-34",
    "35-39": "35-39",
    "40-44": "40-44",
    "45-49": "45-49",
    "50+": "50+",
    "Bilinmeyen": "unknown",
}

#: Column index to birth order. The sheet's columns are: year, age group, total, the four
#: orders, and then `Bilinmeyen` — which is easy to miss, being outside the block the
#: header spans, and is why the breakdown first came up 3.831 births short of the total in
#: 2025. `4+` is a closing band, not a number; `unknown` is people, not a gap.
ORDERS = {3: "1", 4: "2", 5: "3", 6: "4+", 7: "unknown"}


def clean(value) -> str:
    return str(value).strip() if value is not None else ""


def read_export(path: Path) -> list[dict]:
    """The cross table as one row per (year, age group, order)."""
    frame = pl.read_excel(path)
    rows: list[dict] = []
    year = None
    for record in frame.to_dicts():
        cells = [clean(v) for v in record.values()]
        if len(cells) < 7:
            continue

        # The year is written once, on the first age group of its block, and the rows
        # under it leave the cell empty — the same shape the MEDAS exports use.
        stamp = YEAR.match(cells[0])
        if stamp:
            year = int(stamp.group("year"))
        if year is None:
            continue

        age = AGES.get(cells[1].split("\n")[0].strip())
        if age is None:
            # `Toplam` and the header rows land here. The total is a margin of the table,
            # and storing a margin next to the cells that make it is how a breakdown comes
            # to count everything twice.
            continue

        for index, order in ORDERS.items():
            cell = cells[index]
            if not cell or cell == "-":
                # "-" is TÜİK's "no data", which in this table means no such birth was
                # recorded — kept out rather than written as a zero.
                continue
            try:
                value = float(cell.replace(" ", "").replace(",", "."))
            except ValueError:
                continue
            rows.append(
                {
                    "year": year,
                    "area_id": "TR",
                    "area_level": "country",
                    "mother_age": age,
                    "birth_order": order,
                    "value": value,
                }
            )
    return rows


class TuikBirthOrder:
    """Births by mother's age and birth order — the one fertility fact we cannot derive."""

    source_id = "tuik"
    indicator_id = "births_by_order"

    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 12)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "tuik" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        records = read_export(raw)
        if not records:
            raise ValueError("dosyada satir yok: " + str(raw))

        indicator = get(self.indicator_id)
        return (
            pl.DataFrame(records)
            .with_columns(
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.date(pl.col("year"), 1, 1).alias("period_start"),
                pl.lit(indicator.frequency).alias("frequency"),
                pl.struct("mother_age", "birth_order")
                .map_elements(
                    lambda row: format_dims(
                        {
                            "mother_age": row["mother_age"],
                            "birth_order": row["birth_order"],
                        }
                    ),
                    return_dtype=pl.String,
                )
                .alias("dims"),
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
