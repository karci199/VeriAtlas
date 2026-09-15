"""TOBB company establishment and closure statistics by province, 2009-2025.

Source: TOBB Bilgi Erişim Müdürlüğü, "Kurulan ve Kapanan Şirket İstatistikleri", one Excel
per month (`raw/tobb/<year>-12.xls`, December files only). The December file's sheet
"İLLER ( BİRİKİMLİ)" is the whole year by province, and the year before beside it: groups
KURULAN (company, cooperative, sole trader), TASFİYE (company, cooperative) and KAPANAN
(company, cooperative, sole trader). Source: Türkiye Ticaret Sicili Gazetesi.

Columns are read from the two header rows rather than fixed positions: 2010-2012 have no
NUTS code column. Every column must add up to the TOPLAM row. The previous-year block of
each file is compared with that year's own file; the newer file wins and revisions are
recorded (TOBB updates the registry counts after the year closes).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold, province_id

FILES = RAW / "tobb"
EVENTS = {"kurulan": "established", "tasfiye": "liquidation", "kapanan": "closed"}
ENTITIES = {"sirket": "company", "koop": "cooperative", "gerkisi": "sole_trader"}

#: (year, cells revised, largest relative revision) from the next year's file.
REVISIONS: list[tuple[int, int, float]] = []


def entity(label: str) -> str | None:
    key = fold(label)
    for prefix, name in ENTITIES.items():
        if key.startswith(prefix):
            return name
    return None


def read_year_file(path: Path) -> dict[int, dict[tuple[str, str, str], float]]:
    """{year: {(area, event, entity): count}} for both blocks of one December file."""
    import re

    import xlrd

    sheet = xlrd.open_workbook(path).sheet_by_name("İLLER ( BİRİKİMLİ)")
    rows = [[str(v).strip() for v in sheet.row_values(r)] for r in range(sheet.nrows)]
    ev_row = next(i for i, r in enumerate(rows) if any(fold(c) == "kurulan" for c in r))
    years_row = next(
        i for i, r in enumerate(rows) if any("OCAK" in c.upper() for c in r)
    )
    years = [
        (j, int(re.search(r"(20\d\d)", c).group(1)))
        for j, c in enumerate(rows[years_row])
        if re.search(r"20\d\d", c)
    ]
    sub_row = next(
        i for i in range(ev_row + 1, ev_row + 3) if any(entity(c) for c in rows[i])
    )
    columns: dict[int, tuple[int, str, str]] = {}
    event = None
    for j, cell in enumerate(rows[ev_row]):
        if fold(cell) in EVENTS:
            event = EVENTS[fold(cell)]
        kind = entity(rows[sub_row][j]) if j < len(rows[sub_row]) else None
        if kind and event:
            starts = [(start, y) for start, y in years if start <= j]
            year = max(starts)[1] if starts else years[0][1]
            columns[j] = (year, event, kind)
    out: dict[int, dict[tuple[str, str, str], float]] = {}
    total_row = None
    for r in rows[sub_row + 1 :]:
        label = next((c for c in r[:2] if c and not re.fullmatch(r"TR\w\d\d", c)), "")
        if fold(label) == "toplam":
            total_row = r
            break
        # From 2019 a note row ("22 ŞUBAT 2019 ...") sits among the provinces, no numbers.
        if not label or all(r[j] in ("", "-") for j in columns if j < len(r)):
            continue
        # From 2019 İstanbul's NUTS code cell reads "22 ŞUBAT 2019": the name is taken
        # from whichever of the first two cells is a province.
        area = None
        for cell in r[:2]:
            try:
                area = province_id(cell)
                break
            except KeyError:
                continue
        if area is None:
            raise KeyError(f"TOBB {path.name}: tanınmayan il {r[:2]}")
        for j, (year, event, kind) in columns.items():
            value = float(r[j]) if r[j] not in ("", "-") else 0.0
            key = (area, event, kind)
            if key in out.setdefault(year, {}):
                raise ValueError(f"TOBB {path.name}: {label} iki kez")
            out[year][key] = value
    if total_row is None:
        raise ValueError(f"TOBB {path.name}: TOPLAM satırı yok")

    # TOPLAM puts its label in the first cell, where provinces have a NUTS code and then
    # the name: its numbers then sit one column left of the provinces'.
    def first_number(r):
        return next(i for i, c in enumerate(r) if re.fullmatch(r"\d+(\.0)?", c))

    province_row = next(r for r in rows[sub_row + 1 :] if any(c for c in r[:2]))
    offset = first_number(total_row) - first_number(province_row)
    for j, (year, event, kind) in columns.items():
        cell = total_row[j + offset] if 0 <= j + offset < len(total_row) else ""
        printed = float(cell) if cell not in ("", "-") else 0.0
        parts = sum(v for (a, e, k), v in out[year].items() if e == event and k == kind)
        if abs(parts - printed) > 0.5:
            raise ValueError(
                f"TOBB {path.name} {year} {event} {kind}: iller {parts:,.0f}, TOPLAM {printed:,.0f}"
            )
    for year, table in out.items():
        if len({a for a, _, _ in table}) != 81:
            raise ValueError(
                f"TOBB {path.name} {year}: {len({a for a, _, _ in table})} il"
            )
    return out


class TobbCompanies:
    source_id = "tobb"
    indicator_id = "tobb_companies"

    def fetch(self) -> Path:
        return FILES

    def parse(self, raw: Path) -> pl.DataFrame:
        merged: dict[int, dict[tuple[str, str, str], float]] = {}
        for path in sorted(FILES.glob("20??-12.xls*")):
            file_year = int(path.name[:4])
            for year, table in read_year_file(path).items():
                if year == file_year or year not in merged:
                    if year in merged and year == file_year:
                        raise ValueError(f"TOBB {year}: iki dosya")
                    if year != file_year:
                        merged[year] = table
                        continue
                    merged[year] = table
                else:
                    # The next file's previous-year block: newer counts win.
                    old = merged[year]
                    changed = [
                        k for k in table if abs(table[k] - old.get(k, 0.0)) > 0.5
                    ]
                    worst = max(
                        (
                            abs(table[k] - old[k]) / old[k]
                            for k in changed
                            if old.get(k)
                        ),
                        default=0.0,
                    )
                    REVISIONS.append((year, len(changed), worst))
                    merged[year] = table
        records = [
            {
                "area_id": area,
                "period_start": dt.date(year, 1, 1),
                "dims": f"company_event={event};company_type={kind}",
                "value": value,
            }
            for year, table in merged.items()
            for (area, event, kind), value in table.items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("company").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-07").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
        )


TOBB_ADAPTERS = {"tobb_companies": TobbCompanies}
