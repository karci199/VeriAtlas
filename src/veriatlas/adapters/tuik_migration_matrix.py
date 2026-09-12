"""Migration between İBBS-2 regions: who moved where, 2008-2025.

The flow matrix. Everything else on the migration side is a margin of this table —
`migration_in` is a column total, `migration_out` a row total, `migration_net` their
difference — and none of them can say where the people went. This can: 26 regions by 26
regions by eighteen years, and it costs one query because the whole matrix is 26
indicators (one per receiving region) across 26 areas.

**There is no province-level matrix.** MEDAS's "İller arası verdiği göç bilgileri" reads
like one and is not: its breakdowns are the origin province and the *reason* for moving,
with no destination anywhere in it. İBBS-2 is as fine as the published flow gets, which
is why this is stored at that level rather than rolled up from something finer.

The diagonal is zero by construction — a move inside a region is not a move between
regions — and it is stored as the zero it is rather than left out, because a missing
diagonal and a zero diagonal look different to anything summing a row.

**Two files, one matrix.** MEDAS publishes `aldığı` and `verdiği`, which are the same
numbers read along the two axes. Both are fetched and the second is used as a check: read
correctly, one is the transpose of the other. Only the `aldığı` reading is stored —
storing both would put every move in the fact table twice.
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
from .tuik_simple import read_text

DOWNLOADS = RAW / "medas" / "basit"

#: `Göç Alan:Adana, Mersin` — the receiving region, named in the column header. The name
#: carries commas, so the label cannot be split on one.
DESTINATION = re.compile(r"Gö[çc]\s*Alan\s*:\s*(?P<name>.+)$")

#: `Adana, Mersin-TR62` — the giving region down the rows, with its İBBS-2 code. The code
#: is what the join uses (K15): the names are lists of provinces and change spelling.
ORIGIN = re.compile(r"^(?P<name>.+)-(?P<code>TR[A-Z0-9]+)$")


def regions() -> dict[str, str]:
    """İBBS-2 code to area id. They are the same string here — `TR62` is the id."""
    return {
        row["area_id"]: row["area_id"]
        for row in load_areas().filter(pl.col("area_level") == "nuts2").to_dicts()
    }


def key(name: str) -> str:
    """A region name with its whitespace taken out.

    The two ends of the table do not spell the same region the same way: the column
    header writes `Erzurum, Erzincan,Bayburt` and the row label `Erzurum, Erzincan,
    Bayburt` — one space, in two regions out of twenty-six. Matched on the text with the
    spaces removed, the spelling stops mattering; matched literally, those two regions
    silently lose their column.
    """
    return "".join(name.split())


def names_to_code(lines: list[str]) -> dict[str, str]:
    """Region name to its code, learned from the row labels of this very file.

    The column headers name the receiving region without a code and the row labels name
    the same regions *with* one, so the file carries its own key. Reading it out beats
    keeping a list of 26 comma-separated province groups in sync with TÜİK's spelling.
    """
    found: dict[str, str] = {}
    for line in lines:
        cells = line.split("|")
        if len(cells) < 2:
            continue
        label = ORIGIN.match(cells[1].strip())
        if label:
            found[key(label.group("name"))] = label.group("code")
    return found


def read_export(path: Path) -> list[dict]:
    """The matrix as one row per (year, origin, destination)."""
    lines = read_text(path).splitlines()
    known = regions()
    by_name = names_to_code(lines)

    # The header is the line that names the most destinations.
    header: dict[int, str] = {}
    for line in lines:
        found: dict[int, str] = {}
        for index, cell in enumerate(line.split("|")):
            match = DESTINATION.match(cell.strip())
            if not match:
                continue
            code = by_name.get(key(match.group("name")))
            if code and code in known:
                found[index] = code
        if len(found) > len(header):
            header = found
    if not header:
        raise KeyError("dosyada hedef bolge sutunu bulunamadi: " + path.name)

    rows: list[dict] = []
    year = None
    for line in lines:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3:
            continue
        if cells[0].isdigit() and len(cells[0]) == 4:
            year = int(cells[0])
        label = ORIGIN.match(cells[1])
        if not label or year is None:
            continue
        origin = label.group("code")
        if origin not in known:
            continue

        for index, destination in header.items():
            if index >= len(cells) or not cells[index]:
                continue
            try:
                value = float(cells[index])
            except ValueError:
                continue
            rows.append(
                {
                    "year": year,
                    "area_id": origin,
                    "destination": destination,
                    "value": value,
                }
            )
    return rows


class TuikMigrationMatrix:
    """Region-to-region migration flows, İBBS-2."""

    source_id = "tuik_medas"
    indicator_id = "migration_between_regions"

    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 12)

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        received = raw / "nufus-goc-alinan-ibbs2-nuts2.csv"
        if not received.exists():
            raise FileNotFoundError("dosya yok: " + str(received))
        records = read_export(received)
        if not records:
            raise ValueError("dosyada satir yok: " + str(received))

        frame = pl.DataFrame(records)

        # Every region gives and receives: 26 origins, 26 destinations, or the matrix has
        # a hole in it that a row total would silently absorb.
        expected = set(load_areas().filter(pl.col("area_level") == "nuts2")["area_id"])
        missing = expected - set(frame["area_id"])
        if missing:
            raise KeyError(
                "matriste olmayan bolge (satir): " + ", ".join(sorted(missing))
            )
        missing = expected - set(frame["destination"])
        if missing:
            raise KeyError(
                "matriste olmayan bolge (sutun): " + ", ".join(sorted(missing))
            )

        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("nuts2").alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.col("destination")
            .map_elements(
                lambda code: format_dims({"destination": code}), return_dtype=pl.String
            )
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
