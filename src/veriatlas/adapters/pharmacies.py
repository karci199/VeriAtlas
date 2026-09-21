r"""Pharmacies by district — the one shop type the state actually counts.

Every other shop in this warehouse is counted off a chain's own store finder, which can
only answer "how many branches of this brand". A pharmacy needs a licence, and TİTCK, the
medicines agency, keeps the register of them. So this is a **census of a trade**, not a
snapshot of a brand: `pharmacies` answers "how many pharmacies are in this district" the
way `population` answers how many people, and nothing in `chain_stores` can be read that
way.

Read from `C:\veri-ham\eczane\eczaneler_*.csv`, which `scripts/fetch_eczaneler.py` pulls
province by province.

**The district comes from the register's own label, and here that is the right source.**
A licence is issued to a district by the authority writing it down; there is no marketing
geography in between, which is what makes the coordinate necessary for chains. The labels
are matched with `areas.resolve_district`, and its three exception classes — `Merkez`,
four province aliases, ten district spellings — cover this file exactly, with nothing left
over. That is worth stating: BİM's store finder, Migros' dropdown and a state register
share no code and no vendor, and they diverge from the registry in precisely the same
ten places.

**The `id` column is not an identifier.** The grid numbers its rows 1..N *per page*, so
a province read in four pages carries four rows called `1`. Nothing here can therefore
tell two pharmacies apart, and nothing tries: the count is the number of rows, and the
guarantee that no row is missing or doubled comes from the fetcher, which checks each
province's pages against the `Total` the grid reports for it.

**A snapshot, not a series.** The register shows who is licensed today and keeps no
history, so rows are filed under the snapshot's year and replaced on a refetch — the same
rule as the chains and TKGM's parcel view.

The province row is written here as an exact sum of its districts rather than left to
`aggregate`, which would stamp it `estimated`.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import polars as pl

from ..areas import resolve_district
from ..config import RAW

FOLDER = RAW / "eczane"
SOURCE_ID = "titck"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 20)
SNAPSHOT = dt.date(2026, 9, 20)


def dump() -> Path:
    found = sorted(FOLDER.glob("eczaneler_*.csv"))
    if not found:
        raise FileNotFoundError(f"eczane dökümü yok: {FOLDER}")
    return found[-1]


class Pharmacies:
    indicator_id = "pharmacies"
    source_id = SOURCE_ID

    def fetch(self) -> Path:
        return dump()

    def parse(self, raw: Path) -> pl.DataFrame:
        districts: dict[str, int] = {}
        read = 0
        with raw.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                read += 1
                area = resolve_district(row["il"], row["ilce"])
                districts[area] = districts.get(area, 0) + 1
        if not districts:
            raise ValueError(f"eczane yok ({raw})")
        # `resolve_district` raises rather than skipping, so this can only fail if it is
        # ever softened. It is cheap insurance against that.
        if sum(districts.values()) != read:
            raise ValueError(f"{read} satır okundu, {sum(districts.values())} yerleşti")
        provinces: dict[str, int] = {}
        for area, count in districts.items():
            provinces[area[:5]] = provinces.get(area[:5], 0) + count
        if len(provinces) != 81:
            raise ValueError(f"81 il beklenirken {len(provinces)} il var")

        records = []
        for level, counts in (("district", districts), ("province", provinces)):
            for area, count in sorted(counts.items()):
                records.append(
                    {
                        "indicator_id": self.indicator_id,
                        "area_id": area,
                        "area_level": level,
                        "period_start": dt.date(SNAPSHOT.year, 1, 1),
                        "frequency": "annual",
                        "dims": "",
                        "value": float(count),
                        "unit": "item",
                        "quality_flag": "measured",
                        "vintage": VINTAGE,
                        "source_id": self.source_id,
                        "retrieved_at": RETRIEVED,
                    }
                )
        return pl.DataFrame(records)


PHARMACY_ADAPTERS = {"pharmacies": Pharmacies}
