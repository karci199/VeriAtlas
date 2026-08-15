"""Village population, from the settlement exports MEDAS publishes without an age split.

The neighbourhood fetcher asks for the `18 yaş ve üzeri` breakdown, and MEDAS answers
that breakdown only inside municipalities: tick it and `Köy` drops out of the level box
(docs/medas.md). So villages have a total and nothing else, and this adapter loads that
total — which is the whole point, because outside the 30 metropolitan provinces a
sizeable share of the country lives in one. In Ardahan it is half.

Law 6360 is why there are 51 provinces here and not 81: in 2014 it turned every village
in the metropolitan provinces into a neighbourhood. Their villages are not missing from
this adapter, they stopped existing.

The label is the trap. Until 2016 a village is written
`Sivas(Akıncılar/Merkez Bucağı/Abdurrahman Köy.)-28662` and from 2017 the same village is
`Sivas(Akıncılar/Abdurrahman Köy.)-28662` — the bucak is dropped mid-series. A parser
that insists on three path segments loses nine years of nineteen and says nothing, because
a line that does not match is only a line that is skipped. The identity is the MEDAS code
either way (K15).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get
from ..schema import DIMS_NONE

DOWNLOADS = RAW / "medas" / "yerlesim"

#: `Sivas(Akıncılar/Merkez Bucağı/Abdurrahman Köy.)-28662`, with the bucak optional.
LABEL = re.compile(
    r"^(?P<province>[^(]+)\("
    r"(?P<district>[^/)]+)"
    r"(?:/(?P<bucak>[^/)]+))?"
    r"/(?P<name>[^)]+)\)-(?P<code>\d+)$"
)


@dataclass(frozen=True)
class Cell:
    year: int
    province: str
    district: str
    bucak: str | None
    name: str
    code: str
    value: float


def read_text(path: Path) -> str:
    """MEDAS serves either encoding depending on the export (docs/medas.md)."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "iso-8859-9"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("dosyanin kodlamasi cozulemedi: " + str(path))


def read_export(path: Path) -> list[Cell]:
    """One province's settlement CSV to cells.

    The year is written once, on the first row of its block, and left blank beneath — so
    it carries down until the file names another.
    """
    cells: list[Cell] = []
    year = None

    for line in read_text(path).splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        if parts[0].isdigit() and len(parts[0]) == 4:
            year = int(parts[0])

        found = LABEL.match(parts[1])
        if found is None or year is None or not parts[2]:
            continue
        try:
            value = float(parts[2])
        except ValueError:
            continue

        cells.append(
            Cell(
                year=year,
                province=found["province"].strip(),
                district=found["district"].strip(),
                bucak=found["bucak"].strip() if found["bucak"] else None,
                name=found["name"].strip(),
                code=found["code"],
                value=value,
            )
        )
    return cells


class TuikVillagePopulation:
    """Village totals, one file per province."""

    source_id = "tuik_medas"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 15)
    indicator_id = "population"

    def fetch(self) -> Path:
        if not any(DOWNLOADS.glob("nufus-koy-*.csv")):
            raise FileNotFoundError("indirilmis koy dosyasi yok: " + str(DOWNLOADS))
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        from ..areas import load_villages

        indicator = get(self.indicator_id)

        cells = [
            cell
            for path in sorted(raw.glob("nufus-koy-*.csv"))
            for cell in read_export(path)
        ]
        if not cells:
            raise ValueError("indirilen dosyalarda satir yok")

        # The registry is built from these same exports
        # (`scripts/build_village_registry.py`), so a code with no entry means the two are
        # out of step — refused rather than dropped, because a dropped village is a
        # village that quietly stops existing in every total built on this.
        known = {
            row["medas_code"]: row["area_id"] for row in load_villages().to_dicts()
        }
        missing = sorted({cell.code for cell in cells if int(cell.code) not in known})
        if missing:
            raise KeyError(
                "kayitta olmayan koy kodu ("
                + str(len(missing))
                + "): "
                + ", ".join(missing[:20])
                + "  — once build_village_registry.py"
            )

        frame = pl.DataFrame(
            [(cell.year, known[int(cell.code)], cell.value) for cell in cells],
            schema=["year", "area_id", "value"],
            orient="row",
        )

        # A village can arrive twice for one year when a province was fetched in more than
        # one pass. Identical rows are one observation written twice; disagreeing ones are
        # two answers to the same question and are refused.
        clash = (
            frame.group_by("year", "area_id")
            .agg(pl.col("value").n_unique().alias("kinds"))
            .filter(pl.col("kinds") > 1)
        )
        if not clash.is_empty():
            raise ValueError(
                "ayni koy-yil icin farkli degerler ("
                + str(len(clash))
                + "): "
                + str(clash.head(3).to_dicts())
            )
        frame = frame.unique(subset=["year", "area_id"], keep="first")

        return frame.with_columns(
            pl.lit("village").alias("area_level"),
            pl.date(pl.col("year").cast(pl.Int32), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(DIMS_NONE).alias("dims"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).drop("year")
