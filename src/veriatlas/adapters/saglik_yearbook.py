r"""Ministry of Health statistics yearbooks, 2012-2016 and 2018-2024: the provincial tables.

`scripts/fetch_saglik_yearbooks.py` keeps the PDFs and their text layer in
`C:\veri-ham\saglik` (`siy<year>_text.json`, one string per page).

Every yearbook closes four chapters with a table "İllere Göre Bazı Sağlık Göstergeleri": one
row per province plus a Türkiye row, split over two pages. The tables are found by their rows,
not by their titles (the 2017 title text is unreadable): a row is a province name followed by
numbers, and a table is a run of adjacent pages whose rows have the same number of cells. Their
order within the book is fixed, so each year lists the tables it prints in order (`LAYOUTS`).

Only published counts and the ratios that cannot be rebuilt from counts are kept; "per 10,000
people", "population per unit" and "visits per person" are left out, they depend on the
ministry's population figure.

The 2017 text layer has two encoding faults, both regular: digits and the thousands dot come
as control characters 29 code points below their value, and the Turkish letters ı ğ ş ö Ç as
other glyphs. `repair` undoes both.

Years not loaded: 2011 prints no provincial tables (regional charts only); 2017's text layer
breaks rows mid-line and scrambles the names of the staff table. 2012-2014 print hospitals with
the family medicine and 112 columns in one table, and visits with inpatient care in another.
2016 prints the "i" of "Türkiye" as U+FFFE; 2014 breaks "Kahraman-maraş" over two lines;
2012 prints the Türkiye row of the hospital table without its name.

Checks on every load: each table has 81 provinces; every count column sums to the printed
Türkiye row (2017's staff table prints no Türkiye row, its total is not checked).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import province_id

FOLDER = RAW / "saglik" if (RAW / "saglik").exists() else Path("C:/veri-ham/saglik")
YEARS = (2012, 2013, 2014, 2015, 2016, 2018, 2019, 2020, 2021, 2022, 2023, 2024)
SKIP = None
#: table kind -> one entry per printed column: (indicator, dims) or SKIP
COLUMNS = {
    "hospital11": [
        ("moh_hospitals", ""),
        ("moh_hospital_beds", ""),
        SKIP,
        ("moh_qualified_beds", ""),
        ("moh_icu_beds", ""),
        ("moh_family_medicine_units", ""),
        SKIP,
        ("moh_emergency_stations", ""),
        SKIP,
        ("moh_emergency_ambulances", ""),
        SKIP,
    ],
    "use13": [
        ("moh_visits", "care_level=primary"),
        ("moh_visits", "care_level=secondary_tertiary"),
        SKIP,
        ("moh_dental_visits", ""),
        SKIP,
        ("moh_inpatients", ""),
        ("moh_inpatient_days", ""),
        ("moh_surgeries", ""),
        ("moh_bed_occupancy", ""),
        ("moh_average_stay", ""),
        ("moh_bed_turnover_rate", ""),
        ("moh_bed_turnover_interval", ""),
        ("moh_hospital_crude_death_rate", ""),
    ],
    "hospital7": [
        ("moh_hospitals", ""),
        ("moh_hospital_beds", ""),
        SKIP,
        ("moh_qualified_beds", ""),
        ("moh_icu_beds", ""),
        ("moh_qualified_bed_share", ""),
        SKIP,
    ],
    "hospital9": [
        ("moh_hospitals", ""),
        ("moh_hospital_beds", ""),
        SKIP,
        ("moh_qualified_beds", ""),
        ("moh_icu_beds", ""),
        ("moh_qualified_bed_share", ""),
        SKIP,
        ("moh_family_medicine_units", ""),
        SKIP,
    ],
    "primary_care6": [
        ("moh_family_medicine_units", ""),
        SKIP,
        ("moh_emergency_stations", ""),
        SKIP,
        ("moh_emergency_ambulances", ""),
        SKIP,
    ],
    "visits5": [
        ("moh_visits", "care_level=primary"),
        ("moh_visits", "care_level=secondary_tertiary"),
        SKIP,
        ("moh_dental_visits", ""),
        SKIP,
    ],
    "inpatient7": [
        ("moh_inpatients", ""),
        ("moh_inpatient_days", ""),
        ("moh_surgeries", ""),
        ("moh_bed_occupancy", ""),
        ("moh_average_stay", ""),
        ("moh_bed_turnover_rate", ""),
        ("moh_bed_turnover_interval", ""),
    ],
    "inpatient8": [
        ("moh_inpatients", ""),
        ("moh_inpatient_days", ""),
        ("moh_surgeries", ""),
        ("moh_bed_occupancy", ""),
        ("moh_average_stay", ""),
        ("moh_bed_turnover_rate", ""),
        ("moh_bed_turnover_interval", ""),
        ("moh_hospital_crude_death_rate", ""),
    ],
    "staff9": [
        ("moh_health_staff", "health_profession=specialist"),
        ("moh_health_staff", "health_profession=general_practitioner"),
        ("moh_health_staff", "health_profession=resident"),
        SKIP,  # total doctors = the three above
        ("moh_health_staff", "health_profession=dentist"),
        ("moh_health_staff", "health_profession=pharmacist"),
        ("moh_health_staff", "health_profession=nurse"),
        ("moh_health_staff", "health_profession=midwife"),
        ("moh_health_staff", "health_profession=other"),
    ],
    "emergency5": [
        ("moh_emergency_stations", ""),
        SKIP,
        ("moh_emergency_ambulances", ""),
        SKIP,
        ("moh_false_emergency_call_share", ""),
    ],
}
#: year -> the provincial tables in the order printed
LAYOUTS = {
    **{year: ["hospital11", "use13", "staff9"] for year in (2012, 2013, 2014)},
    2015: ["hospital7", "primary_care6", "visits5", "inpatient8", "staff9"],
    2016: ["hospital7", "primary_care6", "visits5", "inpatient8", "staff9"],
    2017: ["hospital7", "primary_care6", "visits5", "inpatient8", "staff9"],
    2018: ["hospital7", "primary_care6", "visits5", "inpatient8", "staff9"],
    2019: ["hospital9", "visits5", "inpatient8", "staff9", "emergency5"],
    **{
        year: ["hospital9", "visits5", "inpatient7", "staff9", "emergency5"]
        for year in range(2020, 2025)
    },
}
UNITS = {
    "moh_hospitals": "facility",
    "moh_hospital_beds": "bed",
    "moh_qualified_beds": "bed",
    "moh_icu_beds": "bed",
    "moh_qualified_bed_share": "percent",
    "moh_family_medicine_units": "item",
    "moh_emergency_stations": "facility",
    "moh_emergency_ambulances": "vehicle",
    "moh_false_emergency_call_share": "percent",
    "moh_visits": "item",
    "moh_dental_visits": "item",
    "moh_inpatients": "person",
    "moh_inpatient_days": "item",
    "moh_surgeries": "item",
    "moh_bed_occupancy": "percent",
    "moh_average_stay": "day",
    "moh_bed_turnover_rate": "source_unit",
    "moh_bed_turnover_interval": "day",
    "moh_hospital_crude_death_rate": "source_unit",
    "moh_health_staff": "person",
}
RATIOS = {
    "moh_qualified_bed_share",
    "moh_false_emergency_call_share",
    "moh_bed_occupancy",
    "moh_average_stay",
    "moh_bed_turnover_rate",
    "moh_bed_turnover_interval",
    "moh_hospital_crude_death_rate",
}
CELL = r"-|[\d.]+(?:,\d+)?"
ROW = re.compile(r"^(\S+)((?:\s+(?:" + CELL + r"))+)$")
TOTAL = re.compile(r"^(?:" + CELL + r")(?:\s+(?:" + CELL + r")){4,}$")
GLYPHS = str.maketrans({"Ŧ": "ı", "Œ": "ğ", "Ɣ": "ş", "Ƃ": "ö", "\x17": "Ç", "\ufffe": "i"})
#: names a line break or a lost glyph (U+FFFE, read as "i" above) broke
NAME_FIXES = {
    "-maraş": "Kahramanmaraş",
    "Kahramanimaraş": "Kahramanmaraş",
    "Barin": "Bartın",
}
Row = tuple[str, str, str, int]  # indicator, area, dims, year


def repair(line: str) -> str:
    """Undo the 2017 encoding: shifted digits in the cells, other glyphs in the name."""
    name, _, rest = line.strip().partition(" ")
    rest = re.sub(r"[\x11-\x1c]", lambda m: chr(ord(m.group()) + 29), rest)
    name = name.translate(GLYPHS)
    return NAME_FIXES.get(name, name) + " " + rest


def number(cell: str) -> float | None:
    return None if cell == "-" else float(cell.replace(".", "").replace(",", "."))


def tables(pages: list[str]) -> list[dict[str, list[str]]]:
    """Runs of adjacent pages whose province rows have the same number of cells."""
    runs: list[tuple[int, int, dict[str, list[str]]]] = []  # last page, cells, rows
    for index, text in enumerate(pages):
        by_width: dict[int, dict[str, list[str]]] = {}
        unlabeled: dict[int, list[str]] = {}
        for line in text.splitlines():
            if TOTAL.match(line.strip()):
                # 2012 prints the Türkiye row without its name
                cells = line.split()
                unlabeled[len(cells)] = cells
                continue
            match = ROW.match(repair(line).strip())
            if not match or len(match.group(2).split()) < 5:
                continue
            cells = match.group(2).split()
            by_width.setdefault(len(cells), {})[match.group(1)] = cells
        for width, rows in by_width.items():
            if len(rows) < 15:
                continue
            if "Türkiye" not in rows and width in unlabeled:
                rows["Türkiye"] = unlabeled[width]
            for i, (last, cells, found) in enumerate(runs):
                if last == index - 1 and cells == width:
                    found.update(rows)
                    runs[i] = (index, cells, found)
                    break
            else:
                runs.append((index, width, dict(rows)))
    # the demographic table of chapter 1 and the 81-province runs only
    provincial = []
    for _, _, rows in runs:
        names = [name for name in rows if name != "Türkiye"]
        try:
            ids = {province_id(name) for name in names}
        except KeyError:
            continue
        if len(ids) == 81:
            provincial.append(rows)
    return provincial


def read_year(year: int) -> dict[Row, float]:
    path = FOLDER / f"siy{year}_text.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} yok (scripts/fetch_saglik_yearbooks.py)")
    pages = json.loads(path.read_text(encoding="utf-8"))
    found = tables(pages)
    layout = LAYOUTS[year]
    # chapter 1 opens with the demographic table, which is not loaded
    if len(found) != len(layout) + 1:
        raise ValueError(
            f"Sağlık yıllığı {year}: {len(found)} il tablosu, beklenen {len(layout) + 1}"
        )
    out: dict[Row, float] = {}
    for kind, rows in zip(layout, found[1:], strict=True):
        columns = COLUMNS[kind]
        if any(len(cells) != len(columns) for cells in rows.values()):
            raise ValueError(f"Sağlık yıllığı {year} {kind}: sütun sayısı tutmuyor")
        printed = rows.get("Türkiye")
        if printed is None and (year, kind) != (2017, "staff9"):
            raise ValueError(f"Sağlık yıllığı {year} {kind}: Türkiye satırı yok")
        for position, column in enumerate(columns):
            if column is SKIP:
                continue
            indicator, dims = column
            values = {
                province_id(name): number(cells[position])
                for name, cells in rows.items()
                if name != "Türkiye"
            }
            if printed is not None and indicator not in RATIOS:
                total = number(printed[position])
                read = sum(v for v in values.values() if v is not None)
                if total is None or abs(read - total) > max(2.0, total * 0.002):
                    raise ValueError(
                        f"Sağlık yıllığı {year} {kind} {indicator} {dims}: "
                        f"iller {read:,.0f}, basılı Türkiye {total}"
                    )
            if printed is not None and number(printed[position]) is not None:
                values["TR"] = number(printed[position])
            for area, value in values.items():
                if value is None:
                    continue
                key = (indicator, area, dims, year)
                if key in out and out[key] != value:
                    raise ValueError(
                        f"Sağlık yıllığı: çift anahtar farklı değerle {key}"
                    )
                out[key] = value
    return out


_CACHE: dict[Row, float] = {}


class SaglikYearbook:
    source_id = "saglik_yearbook"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        if not _CACHE:
            for year in YEARS:
                _CACHE.update(read_year(year))
        records = [
            {
                "area_id": area,
                "area_level": "country" if area == "TR" else "province",
                "period_start": dt.date(year, 1, 1),
                "dims": dims,
                "value": value,
            }
            for (indicator, area, dims, year), value in _CACHE.items()
            if indicator == self.indicator_id
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit(UNITS[self.indicator_id]).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit("saglik_yearbook").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


SAGLIK_YEARBOOK_ADAPTERS = {
    indicator: type(
        f"SaglikYearbook_{indicator}", (SaglikYearbook,), {"indicator_id": indicator}
    )
    for indicator in UNITS
}
