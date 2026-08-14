"""Kütük nüfusu: how many people a province's register holds, wherever they now live.

The measure is a square: 81 provinces of residence down the rows, 81 provinces of
registry across the columns, and in each cell the people who live in one and are
registered to the other. Both totals are real numbers and only one of them is new.

* Along a **row** — everyone living in Adana, whatever register they are on — is the
  resident population. We already hold it, counted directly, from a different file.
* Down a **column** — everyone registered to Sivas, wherever they live — is the kütük
  nüfusu, and it exists nowhere else.

The first reading is what `tuik_simple` would have produced, and it looked plausible:
every province came out with a registry-to-resident ratio of 1,00, and the national total
matched. It had to — both readings sum to the same country. The tell was that the ratio
was 1,00 for Ağrı and Sivas too, provinces half of whose registered people left decades
ago. So this adapter reads the other axis.

Two more things are unlike the narrow measures. The residence breakdown cannot be closed,
so 81 × 82 × 19 years is 126.000 cells against a limit of 50.000 and the download comes
one year at a time (`fetch_medas_simple kutuk-nufusu --yil=2019`). And the Düzey box does
nothing here — country and province download byte-for-byte the same file, all 82 areas in
both — so only the province copy is kept and read.
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
from .tuik_simple import header_of, read_text

#: The two halves of a register: living in the province, and living anywhere else.
OWN = "own"
ELSEWHERE = "elsewhere"

DOWNLOADS = RAW / "medas" / "basit"

STEM = "nufus-kutuk-nufusu-province"

#: The column header names the register, `Nüfusa Kayıtlı Olunan İl:Sivas` — a name, not
#: the `Sivas-58` code the row labels carry, so these are matched against the area
#: register by name.
COLUMN = re.compile(r"^N[üu]fusa Kay[ıi]tl[ıi] Olunan [İI]l\s*:\s*(?P<name>.+)$")

#: `Adana-1` in the row label: the province of *residence*.
ROW = re.compile(r"^(?P<name>.+)-[A-Z0-9]+$")


def by_name() -> dict[str, tuple[str, str]]:
    """Province name to `(area_id, level)`."""
    areas = load_areas().filter(pl.col("area_level") == "province")
    return {
        row["name_tr"]: (row["area_id"], "province")
        for row in areas.iter_rows(named=True)
    }


def read_square(path: Path, names: dict[str, tuple[str, str]]) -> list[dict]:
    """One year's square, read down its columns and split at the diagonal.

    Two rows per province: `residence=own` is the diagonal cell — people living where
    they are registered — and `residence=elsewhere` is the rest of the column. They sum
    to the register, so the page's own machinery gives the whole of it back: "Tümü
    (topla)" is the total, "içinde %" is how much of a register is still at home, and a
    derivation over either part is that part's growth rate.

    Written as two indicators first — the total and the diagonal — and that was worse in
    a way worth recording: two tables that cannot be added, two entries in the tree, and
    the ratio between them impossible to ask for at all. A breakdown is the shape of this
    fact, not a pair of measurements that happen to be related.
    """
    lines = read_text(path).splitlines()

    columns: dict[int, tuple[str, str]] = {}
    for index, label in header_of(lines).items():
        found = COLUMN.match(label)
        if not found:
            continue
        area = names.get(found.group("name").strip())
        if not area:
            # A column we cannot place is a province's entire register going missing from
            # the total, so it is refused rather than skipped.
            raise KeyError("registry_population: taninmayan il sutunu: " + label)
        columns[index] = area
    if len(columns) < len(names):
        raise KeyError(
            "registry_population: dosyada "
            + str(len(columns))
            + " il sutunu var, "
            + str(len(names))
            + " bekleniyor: "
            + path.name
        )

    #: (area_id, level, year, where) → running total, where `where` is own or elsewhere.
    totals: dict[tuple[str, str, int, str], float] = {}
    year = None
    for line in lines:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3:
            continue
        if cells[0].isdigit() and len(cells[0]) == 4:
            year = int(cells[0])
        label = ROW.match(cells[1]) if len(cells) > 1 else None
        if year is None or not label:
            continue

        # The province this row is about: where these people live. A row we cannot place
        # would land its whole line in the wrong half of the split, so it is refused.
        living = names.get(label.group("name").strip())
        if not living:
            raise KeyError("registry_population: taninmayan il satiri: " + cells[1])

        for index, (area_id, level) in columns.items():
            if index >= len(cells) or not cells[index]:
                continue
            try:
                value = float(cells[index])
            except ValueError:
                continue
            where = OWN if area_id == living[0] else ELSEWHERE
            key = (area_id, level, year, where)
            totals[key] = totals.get(key, 0.0) + value

    return [
        {
            "area_id": area_id,
            "area_level": level,
            "year": year,
            "dims": format_dims({"residence": where}),
            "value": value,
        }
        for (area_id, level, year, where), value in totals.items()
    ]


class TuikRegistryPopulation:
    """Kütük nüfusu, one file per year."""

    source_id = "tuik_medas"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 14)
    indicator_id = "registry_population"

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        names = by_name()

        # Named years only. A wildcard would also take `-2.csv`, the leftover of an
        # earlier attempt at slicing this measure automatically, and that file holds three
        # years of the same numbers already counted.
        pieces = sorted(
            path
            for path in raw.glob(STEM + "-*.csv")
            if re.fullmatch(r"\d{4}", path.stem[len(STEM) + 1 :])
        )
        records: list[dict] = []
        for path in pieces:
            records.extend(read_square(path, names))
        if not records:
            raise ValueError("kutuk nufusu dosyasi yok: " + STEM + "-<yil>.csv")

        indicator = get(self.indicator_id)
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
        found = set(frame["area_id"])
        if expected - found:
            raise KeyError(
                "registry_population: dosyada karsiligi olmayan il ("
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
