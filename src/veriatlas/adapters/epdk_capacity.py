"""EPDK installed electricity capacity by province.

Two sources, both flattened by `scripts/extract_epdk_docx_tables.py`:

* unlicensed capacity (rooftop and small solar, mostly) by province and source, from the
  December issue of the monthly electricity report, 2016-2025 —
  `raw/epdk/docx_resmi_cells.parquet`;
* licensed capacity by province (total only), from the yearly market report, 2017-2024 —
  `raw/epdk/docx_cells.parquet`. The yearly report does not split it by source.

Each table is checked against its row totals and its Genel Toplam row. The licensed table is
printed in two side-by-side column pairs (province, MW, share); provinces with no licensed
plant are not listed, so a province missing from it means no licensed capacity.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import polars as pl

from ..config import RAW
from .epdk import Epdk, TotalMismatch, fact, row
from .epdk_history import near, number_tr, province_or_none
from .kgm import fold

MONTHLY_CELLS = RAW / "epdk" / "docx_resmi_cells.parquet"

SOURCES = {
    "biyokutle": "biomass",
    "dogalgaz": "natural_gas",
    "gunes": "solar",
    "gunesfotovoltaik": "solar",
    "gunesyogunls": "solar",
    "hidrolik": "hydro",
    "ruzgar": "wind",
    "linyit": "lignite",
}


@cache
def monthly_tables() -> dict[tuple[str, int], tuple[str, list[list[str]]]]:
    cells = pl.read_parquet(MONTHLY_CELLS)
    out = {}
    for (file, table), group in cells.group_by(["file", "table"]):
        rows: dict[int, dict[int, str]] = {}
        for r, c, t in group.select("row", "col", "text").iter_rows():
            rows.setdefault(r, {})[c] = t
        grid = [
            [rows[r].get(c, "") for c in range(max(rows[r]) + 1)] for r in sorted(rows)
        ]
        out[(file, table)] = (group["caption"][0], grid)
    return out


class EpdkUnlicensedCapacity(Epdk):
    """December of each year: unlicensed capacity by province and source (MW)."""

    indicator_id = "epdk_unlicensed_capacity"

    def fetch(self) -> Path:
        return MONTHLY_CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        pattern = re.compile(
            r"Aralık (20\d\d) Döneminde Lisanssız Elektrik Kurulu Gücünün İllere ve Kaynaklara"
        )
        records = []
        years = set()
        for (_file, _table), (caption, grid) in monthly_tables().items():
            match = pattern.search(caption)
            if not match:
                continue
            year = int(match.group(1))
            if year in years:
                raise ValueError(f"lisanssız kurulu güç {year}: iki tablo")
            years.add(year)
            header = [fold(h) for h in grid[0]]
            total_col = header.index("toplam")
            provinces: dict[str, dict[str, float]] = {}
            for line in grid[1:]:
                if fold(line[0]) == "geneltoplam":
                    near(
                        sum(sum(v.values()) for v in provinces.values()),
                        number_tr(line[total_col]),
                        f"lisanssız {year} Türkiye",
                        0.01 * 81,
                    )
                    continue
                if not line[0].strip() or fold(line[0]) == "iller":
                    continue
                # An unrecognised name stops the load rather than being skipped: "Küthahya"
                # (December 2021) dropped 119 MW silently until the national total caught it.
                pid = province_or_none(line[0])
                if not pid:
                    raise KeyError(f"lisanssız {year}: tanınmayan il adı {line[0]!r}")
                values: dict[str, float] = {}
                for i, h in enumerate(header):
                    if h in SOURCES and i < len(line):
                        values[SOURCES[h]] = values.get(SOURCES[h], 0.0) + (
                            number_tr(line[i]) or 0.0
                        )
                near(
                    sum(values.values()),
                    number_tr(line[total_col]),
                    f"lisanssız {year} {pid}",
                    0.03,
                )
                provinces[pid] = values
            # Provinces without any unlicensed plant are not listed (63 in 2016); the national
            # total above is what guarantees none was dropped.
            if len(provinces) < 50:
                raise ValueError(f"lisanssız kurulu güç {year}: {len(provinces)} il")
            records += [
                row(pid, year, "energy_source=" + source, value)
                for pid, values in provinces.items()
                for source, value in values.items()
            ]
        if years != set(range(2016, 2026)):
            raise ValueError(f"lisanssız kurulu güç yılları: {sorted(years)}")
        return fact(records, self.indicator_id, "mw", "2026-02")


class EpdkLicensedCapacity(Epdk):
    """Licensed installed capacity by province (MW), year end 2017-2024."""

    indicator_id = "epdk_licensed_capacity"

    def fetch(self) -> Path:
        return RAW / "epdk" / "docx_cells.parquet"

    def parse(self, raw: Path) -> pl.DataFrame:
        from .epdk_history import find

        records = []
        for _file, year, grid in find(
            "Lisanslı Kurulu Gücün İl Bazında", "elektrik_yillik"
        ):
            provinces: dict[str, float] = {}
            unassigned = 0.0
            grand = None
            for line in grid:
                for start in range(0, len(line) - 1, 3):
                    name, value = line[start], line[start + 1]
                    if fold(name) == "geneltoplam":
                        grand = number_tr(value)
                        continue
                    pid = province_or_none(name)
                    if pid and number_tr(value) is not None:
                        if pid in provinces:
                            # 2019 prints AYDIN twice (1,194.9 and 44.0 MW); both are in the
                            # national total, and every other province is listed, so the
                            # second row belongs to a province the table does not name. The
                            # first row (in line with 2018 and 2020) is kept, the second left
                            # unassigned. Any other duplicate stops the load.
                            if (year, pid) != (2019, "TR-09"):
                                raise TotalMismatch(f"lisanslı {year}: {pid} iki kez")
                            unassigned += number_tr(value)
                            continue
                        provinces[pid] = number_tr(value)
            # Kilis has no licensed plant and is never listed.
            if grand is None or len(provinces) < 75:
                raise ValueError(
                    f"lisanslı kurulu güç {year}: {len(provinces)} il, toplam {grand}"
                )
            near(
                sum(provinces.values()) + unassigned,
                grand,
                f"lisanslı {year} Türkiye",
                0.01 * 81,
            )
            records += [row(pid, year, "", value) for pid, value in provinces.items()]
        return fact(records, self.indicator_id, "mw", "2025-06")


EPDK_CAPACITY_ADAPTERS = {
    "epdk_unlicensed_capacity": EpdkUnlicensedCapacity,
    "epdk_licensed_capacity": EpdkLicensedCapacity,
}
