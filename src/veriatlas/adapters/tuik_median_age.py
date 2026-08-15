"""Median age by sex, Türkiye and provinces, 2007-2025.

A MEDAS export pulled by hand: sex across two columns, year and area down the rows, the
year filled in only when it changes.

    2007|Adana, Mersin-TR62|27.3|28.4|
        |Adana-1|27.0|27.8|

The join is on **codes, not names**. MEDAS packs the code into its own label — the plate
number for a province (`Adana-1`), the İBBS code for a statistical region (`TR62`), `TR`
for the country — and those codes are the province ids the registry already uses
(`TR-01`). Matching on the Turkish name instead would mean folding `Şanlıurfa`, guessing
at renames, and getting no warning when a guess misses.

Two things this export does that will bite anyone reading it by name:

* **Three provinces are missing.** Ankara, İstanbul and İzmir appear *only* as their
  single-province İBBS-2 row (`Ankara-TR51`), never as `Ankara-6`. MEDAS collapses the
  two levels where they are the same set of people. Dropped, they would be three holes
  in the middle of the map that look exactly like "no data". So a one-province İBBS-2
  region is read as that province — and which regions those are comes from the registry
  (`load_parents("nuts")`), not from a list typed out here.
* **There is no total.** Only Erkek and Kadın columns, so no unbroken median age is
  stored. A median of the two sexes is not the average of their medians and will not be
  invented here.

İBBS-1 and multi-province İBBS-2 rows are skipped: the screen works at country, province
and district level, and a statistical region nobody asked for is a level to maintain
rather than a level to have.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas, load_parents
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .base import cached_copy

SOURCE_FILE = Path(r"C:\Users\katan\OneDrive\Desktop\demografi\OrtancaYas.csv")

#: `Adana-1`, `Ankara-TR51`, `Türkiye-TR` — everything before the last dash is the name.
LABEL = re.compile(r"^(?P<name>.+)-(?P<code>TR[0-9A-C]*|\d{1,2})$")

#: The order the value columns come in. The export has no total column.
SEXES = ("male", "female")


def area_of(code: str, single: dict[str, str]) -> tuple[str, str] | None:
    """A MEDAS code to (area_id, level), or None for a level we do not keep."""
    if code == "TR":
        return ("TR", "country")
    if code.isdigit():
        # The plate number *is* the ISO 3166-2:TR code, which is the registry's own id.
        return ("TR-" + code.zfill(2), "province")
    # An İBBS region that contains exactly one province is that province.
    if code in single:
        return (single[code], "province")
    return None


def single_province_regions() -> dict[str, str]:
    """İBBS regions that contain exactly one province, mapped to it.

    Walked over the whole hierarchy rather than one level of it: İstanbul collapses all
    the way up, so it reaches the file as `İstanbul-TR1` — the İBBS-**1** code — while
    Ankara and İzmir stop at İBBS-2 (`TR51`, `TR31`). Counting ancestors instead of
    parents gets all three without a rule about which level to look at, and it stops
    being true on its own if TÜİK ever splits one.
    """
    parents = {
        row["area_id"]: row["parent_id"] for row in load_parents("nuts").to_dicts()
    }
    provinces = set(load_areas().filter(pl.col("area_level") == "province")["area_id"])

    under: dict[str, set[str]] = {}
    for province in provinces:
        node = parents.get(province)
        while node and node != "TR":
            under.setdefault(node, set()).add(province)
            node = parents.get(node)

    return {
        region: next(iter(members))
        for region, members in under.items()
        if len(members) == 1
    }


def read_export(
    path: Path, single: dict[str, str]
) -> list[tuple[int, str, str, str, float]]:
    """(year, area_id, level, sex, value) rows."""
    rows: list[tuple[int, str, str, str, float]] = []
    year = None

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 4:
            continue
        if cells[0].isdigit() and len(cells[0]) == 4:
            year = int(cells[0])

        match = LABEL.match(cells[1])
        if match is None or year is None:
            continue
        area = area_of(match["code"], single)
        if area is None:
            continue

        for index, sex in enumerate(SEXES):
            try:
                value = float(cells[index + 2])
            except ValueError:
                # A suppressed cell is a gap, not a zero.
                continue
            rows.append((year, area[0], area[1], sex, value))
    return rows


class TuikMedianAge:
    """Median age per province and year, by sex, from the MEDAS export."""

    source_id = "tuik_medas"
    indicator_id = "median_age"

    #: The export carries no release stamp, so the vintage is when we took it — the same
    #: known gap as every other TÜİK file here.
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 14)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "medas" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)

        records = read_export(raw, single_province_regions())
        if not records:
            raise ValueError("dosyada satir yok: " + str(raw))

        frame = pl.DataFrame(
            records,
            schema=["year", "area_id", "area_level", "sex", "value"],
            orient="row",
        )

        # Every province or none. A province quietly absent here draws as "veri yok" in
        # the middle of the map, which is indistinguishable from a real gap — the same
        # reason the district loader refuses an unmatched name.
        expected = set(
            load_areas().filter(pl.col("area_level") == "province")["area_id"]
        )
        found = set(frame.filter(pl.col("area_level") == "province")["area_id"])
        if expected - found:
            raise KeyError(
                "dosyada karsiligi olmayan il ("
                + str(len(expected - found))
                + "): "
                + ", ".join(sorted(expected - found))
            )

        dims = {sex: format_dims({"sex": sex}) for sex in SEXES}

        return frame.with_columns(
            pl.date(pl.col("year").cast(pl.Int32), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.col("sex").replace_strict(dims).alias("dims"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).drop("year", "sex")
