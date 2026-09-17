r"""TİM (Türkiye İhracatçılar Meclisi) exports by province, 2004-2025.

`scripts/fetch_tim.py` keeps the monthly release workbooks in `C:\veri-ham\tim\<year>\<month>`
with `index.tsv`. The December "İller Bazında" file of each year holds the twelve months by
province; the year is their sum (later files also print it as TOPLAM / KÜMÜLATİF).

The exporter's registered seat decides the province, not where the goods were made: an
İstanbul-registered firm's factory output elsewhere counts for İstanbul. TİM's own warning.

Layouts that differ, all handled here:

* the header row is the one naming OCAK; the name column is the first text cell of a row;
* 2004-2009 print dollars, later years thousands of dollars: a year whose provinces add up to
  more than 10^10 is taken as dollars (Türkiye exports are 60-270 billion dollars a year);
* the Türkiye total is a row named TOPLAM / GENEL TOPLAM, or (2010) an unnamed row of numbers
  under the provinces; the provinces plus any non-province rows must add up to it;
* old names: URFA.

Provinces a year does not list exported nothing that year and are not written.

2004-2005 and 2008 print no Türkiye total: those years rest on each row's own TOPLAM column.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold, province_id

FIRST_YEAR = 2004
#: year -> exports printed without a province (2006-2008), in the file's unit
UNALLOCATED: dict[int, float] = {}
FOLDER = RAW / "tim" if (RAW / "tim").exists() else Path("C:/veri-ham/tim")
NUMBER = re.compile(r"-?\d+(\.\d+)?([eE][+-]?\d+)?")
ALIASES = {"URFA": "Şanlıurfa"}
MONTHS = (
    "ocak",
    "subat",
    "mart",
    "nisan",
    "mayis",
    "haziran",
    "temmuz",
    "agustos",
    "eylul",
    "ekim",
    "kasim",
    "aralik",
)


def december_files() -> dict[int, Path]:
    out: dict[int, Path] = {}
    for line in (FOLDER / "index.tsv").read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        rel = line.split("\t")[1]
        year, month = rel.split("/")[:2]
        name = rel.rsplit("/", 1)[-1].lower()
        if month != "12" or "sektor" in name or "ulke" in name:
            continue
        out.setdefault(int(year), FOLDER / rel)
    return out


def sheet_rows(path: Path) -> list[list[str]]:
    if path.suffix.lower() == ".xls":
        import xlrd

        sheet = xlrd.open_workbook(path).sheet_by_index(0)
        return [
            [str(c).strip() for c in sheet.row_values(i)] for i in range(sheet.nrows)
        ]
    import openpyxl

    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    return [
        ["" if c is None else str(c).strip() for c in r]
        for r in sheet.iter_rows(values_only=True)
    ]


def area_of(name: str) -> str | None:
    try:
        return province_id(ALIASES.get(name.upper(), name))
    except KeyError:
        return None


def read_year(year: int, path: Path) -> dict[str, float]:
    """{province: exports in dollars} for one December file.

    Unnamed rows of numbers: the last one is the Türkiye total when the rest add up to it
    (2006-2010); an earlier one (2006-2008, first row) is exports with no province, counted in
    the check and not written. 2004-2005 print no total at all: there every row's months must
    add up to its own TOPLAM column instead, and 2004, 2005 and 2008 print one unnamed row that is
    not a total but exports without a province (132 million, 5.8 million and 258 million dollars).
    """
    rows = sheet_rows(path)
    # "OCAK", "ocak", 2011's "SUM(OCAK)"
    head = next(i for i, r in enumerate(rows) if any("ocak" in fold(c) for c in r))
    header = [fold(c) for c in rows[head]]
    months = [next(j for j, c in enumerate(header) if m in c) for m in MONTHS]
    year_total = next(
        (j for j, c in enumerate(header) if c in ("toplam", "kumulatif")), None
    )
    provinces: dict[str, float] = {}
    unnamed: list[float] = []
    printed = None
    for r in rows[head + 1 :]:
        cells = [r[j] if j < len(r) else "" for j in months]
        if not any(NUMBER.fullmatch(c) and float(c) for c in cells):
            continue  # 2004 opens with a row of zeros
        value = sum(float(c) for c in cells if NUMBER.fullmatch(c))
        name = next((c for c in r[: months[0]] if c and not NUMBER.fullmatch(c)), "")
        if name.upper() in ("TOPLAM", "GENEL TOPLAM", "TÜRKİYE"):
            if printed is not None:
                raise ValueError(f"TİM {path.name}: iki toplam satırı")
            printed = value
            continue
        if not name:
            unnamed.append(value)
            continue
        area = area_of(name)
        if area is None:
            raise ValueError(f"TİM {path.name}: tanınmayan satır {name}")
        if area in provinces:
            raise ValueError(f"TİM {path.name}: {name} iki kez")
        if (
            year_total is not None
            and year_total < len(r)
            and NUMBER.fullmatch(r[year_total])
        ):
            own = float(r[year_total])
            if abs(own - value) > max(1.0, own * 1e-6):
                raise ValueError(
                    f"TİM {path.name} {name}: aylar {value:,.0f}, TOPLAM {own:,.0f}"
                )
        provinces[area] = value
    named = sum(provinces.values())
    if printed is None and unnamed:
        candidate = unnamed[-1]
        rest = sum(unnamed[:-1])
        if abs(named + rest - candidate) <= max(1.0, candidate * 1e-4):
            printed, unnamed = candidate, unnamed[:-1]
    if printed is None and unnamed and year_total is None:
        raise ValueError(
            f"TİM {path.name}: adsız satırlar toplamla eşleşmiyor {unnamed}"
        )
    if printed is None and year >= 2010:
        printed = summary_total(path, named)
    if printed is not None:
        read = named + sum(unnamed)
        if abs(read - printed) > max(1.0, printed * 1e-4):
            raise ValueError(
                f"TİM {path.name}: iller {read:,.0f}, toplam {printed:,.0f}"
            )
    elif year_total is None:
        raise ValueError(f"TİM {path.name}: ne toplam satırı ne satır toplamı var")
    UNALLOCATED[year] = sum(unnamed)
    scale = 1.0 if named > 1e10 else 1000.0
    return {area: value * scale for area, value in provinces.items()}


def summary_total(path: Path, read: float) -> float:
    """2013-2014 print no total under the provinces; sheet ILLER_GENEL has GENEL TOPLAM.

    Its row holds last year's and this year's December and whole-year figures, in thousands
    of dollars, rounded: the one closest to what was read is returned if within 0.01 %.
    """
    import xlrd

    book = xlrd.open_workbook(path)
    if "ILLER_GENEL" not in book.sheet_names():
        raise ValueError(f"TİM {path.name}: toplam satırı yok")
    sheet = book.sheet_by_name("ILLER_GENEL")
    for i in range(sheet.nrows):
        row = [str(c).strip() for c in sheet.row_values(i)]
        if row and fold(row[0]) == "geneltoplam":
            numbers = [float(c) for c in row[1:] if NUMBER.fullmatch(c)]
            best = min(numbers, key=lambda n: abs(n - read))
            if abs(best - read) <= best * 1e-4:
                return best
            raise ValueError(
                f"TİM {path.name}: iller {read:,.0f}, GENEL TOPLAM {numbers}"
            )
    raise ValueError(f"TİM {path.name}: GENEL TOPLAM yok")


class TimExports:
    source_id = "tim"
    indicator_id = "tim_exports"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "area_id": area,
                "period_start": dt.date(year, 1, 1),
                "dims": "",
                "value": value / 1000,
            }
            for year, path in sorted(december_files().items())
            if year >= FIRST_YEAR
            for area, value in read_year(year, path).items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("thousand_usd").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


TIM_ADAPTERS = {"tim_exports": TimExports}
