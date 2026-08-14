"""Neighbourhood population, split at 18, from the MEDAS exports.

One CSV per province and set of years, pipe-delimited like the district export, with the
year filled in only when it changes::

    2013|Bursa(Büyükorhan/Büyükorhan Bel./Akçasaz Mah.)-183537|173.0|68.0|
        |Bursa(Büyükorhan/Büyükorhan Bel./Aktaş Mah.)-183539|401.0|132.0|

The label packs four things: province, district, municipality-or-village, neighbourhood
— and then the MEDAS code, which is the only part worth joining on (K15).

**The 18 split is stored as two age bands**, `0-17` and `18+`, in the same `age`
dimension the five-year bands use. They are age groups; giving them a dimension of their
own would mean the page had to learn a second word for the same idea, and summing across
`age` would stop giving the total. The bands differ from the district file's, which is
fine — the explorer already lists a breakdown's values per level, because the province
file stops at 75+ where the district file runs to 90+.

MEDAS offers this cut by sex *or* by age, never both at once, so a row carries one or the
other. That is a property of the source, not a gap to fill.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "medas" / "mahalle"

#: `Bursa(Büyükorhan/Büyükorhan Bel./Akçasaz Mah.)-183537`
LABEL = re.compile(r"^(?P<province>[^(]+)\((?P<path>.*)\)-(?P<code>\d+)$")

#: The value columns, in the order MEDAS writes them: "18 yaş ve üzeri: Evet / Hayır".
BANDS = ("18+", "0-17")


@dataclass(frozen=True)
class Cell:
    year: int
    province: str
    district: str
    municipality: str
    name: str
    code: str
    age: str
    value: float


def read_export(path: Path) -> list[Cell]:
    """One MEDAS neighbourhood CSV to cells."""
    cells: list[Cell] = []
    year = None

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 4:
            continue
        if parts[0].isdigit() and len(parts[0]) == 4:
            year = int(parts[0])

        match = LABEL.match(parts[1])
        if match is None or year is None:
            continue

        path_parts = [p.strip() for p in match["path"].split("/")]
        if len(path_parts) != 3:
            raise ValueError("beklenmeyen etiket: " + parts[1])
        district, municipality, name = path_parts

        for index, band in enumerate(BANDS):
            try:
                value = float(parts[index + 2])
            except ValueError:
                # A suppressed cell is a gap, not a zero — the Kestel OSB neighbourhood
                # has 29 adults published and its under-18 count withheld.
                continue
            cells.append(
                Cell(
                    year=year,
                    province=match["province"],
                    district=district,
                    municipality=municipality,
                    name=name,
                    code=match["code"],
                    age=band,
                    value=value,
                )
            )
    return cells


class TuikNeighbourhoodPopulation:
    """Population per neighbourhood and year, split at 18."""

    source_id = "tuik_medas"
    indicator_id = "population"

    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 14)

    def fetch(self) -> Path:
        if not any(DOWNLOADS.glob("*.csv")):
            raise FileNotFoundError("indirilmis mahalle dosyasi yok: " + str(DOWNLOADS))
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        from ..areas import load_neighbourhoods

        indicator = get(self.indicator_id)

        cells = [
            cell for path in sorted(raw.glob("*.csv")) for cell in read_export(path)
        ]
        if not cells:
            raise ValueError("indirilen dosyalarda satir yok")

        # The registry is built from these same exports
        # (`scripts/build_neighbourhood_registry.py`), so a code with no entry means the
        # registry is stale — rebuild it rather than let the row through unlabelled.
        # The code is read back as a number by the CSV reader and compared against the
        # export's text, so it is spelled out here rather than trusted to match.
        known = {
            str(row["medas_code"]): row["area_id"]
            for row in load_neighbourhoods().to_dicts()
        }
        missing = sorted({c.code for c in cells} - set(known))
        if missing:
            raise KeyError(
                "kayitta olmayan mahalle kodu ("
                + str(len(missing))
                + "): "
                + ", ".join(missing[:20])
                + "  — once build_neighbourhood_registry.py"
            )

        frame = pl.DataFrame(
            [(c.year, known[c.code], c.age, c.value) for c in cells],
            schema=["year", "area_id", "age", "value"],
            orient="row",
        )

        dims = {band: format_dims({"age": band}) for band in BANDS}

        return frame.with_columns(
            pl.lit("neighbourhood").alias("area_level"),
            pl.date(pl.col("year").cast(pl.Int32), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.col("age").replace_strict(dims).alias("dims"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).drop("year", "age")
