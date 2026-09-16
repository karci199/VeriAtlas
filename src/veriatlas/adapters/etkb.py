r"""Power capacity added each year by province and source (Ministry of Energy, EİGM).

`scripts/fetch_etkb.py` keeps one workbook per year in `C:\veri-ham\etkb` (2003-2025). Each
row is a power plant whose units were provisionally accepted that year: province, source,
unit size, number of units and the capacity this added ("İLAVE KURULU GÜÇ MWe"). Summing the
rows gives how much generating capacity each province gained in a year, by source — the
province-level counterpart of the national capacity series.

The layout is stable across the 23 workbooks, so the columns are taken from the header row
("SIRA NO", "İL", "KAYNAK" or "YAKIT CİNSİ", "İLAVE KURULU GÜÇ"). Below the plants every
workbook prints the year's total by broad source group; that total is the check on the
reading (the groups themselves are coarser than the plants' own labels, so only the total is
compared) and those rows are skipped, as is any row whose province cell is not a province.

Plants that straddle two provinces are written as "EDİRNE-TEKİRDAĞ"; the capacity is filed
under the first province named.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import province_id

FOLDER = RAW / "etkb" if (RAW / "etkb").exists() else Path("C:/veri-ham/etkb")
#: canonical source code -> pattern matched against the workbook's own label
SOURCES = (
    ("hydro", r"^HES|HİDRO"),
    ("wind", r"^RES|RÜZGAR"),
    ("solar", r"^GES|GÜNEŞ"),
    ("geothermal", r"JEOTERMAL|^JES"),
    ("biomass", r"BİYOKÜTLE|BİYOGAZ|ÇÖP|ATIK(?! ISI)"),
    ("waste_heat", r"ATIK ISI|BACA GAZI|PROSES"),
    ("natural_gas", r"^DG|DOĞ|LNG"),
    ("coal_import", r"İTHAL KÖMÜR|İTHAL LİNYİT"),
    ("coal_local", r"LİNYİT|LINYIT|YERLİ KÖMÜR|TAŞ ?KÖMÜR|ASFALTİT|^KÖMÜR"),
    ("fuel_oil", r"^FO\b|FUEL|MOTORİN|NAFTA|LPG|MAZOT|PİROLİTİK"),
    ("multi_fuel", r"\+|/"),
    ("other", r"^TERMİK|DİĞER|SIVI"),
)
UNITS = {"etkb_added_capacity": "mw", "etkb_added_plants": "facility"}
TOTAL = re.compile(r"^TOPLAM")


def source_code(label: str) -> str | None:
    text = label.upper().strip()
    for code, pattern in SOURCES:
        if re.search(pattern, text):
            return code
    return None


def number(cell) -> float | None:
    if isinstance(cell, bool) or cell is None:
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    text = str(cell).strip().replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})+,\d+", text):  # 1.234,5
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    return float(text) if re.fullmatch(r"-?\d+(\.\d+)?", text) else None


def rows_of(path: Path) -> list[list]:
    if path.suffix == ".xlsx":
        import openpyxl

        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows = [
            list(row) for row in book[book.sheetnames[0]].iter_rows(values_only=True)
        ]
        book.close()
        return rows
    import xlrd

    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    return [sheet.row_values(index) for index in range(sheet.nrows)]


def read_year(path: Path) -> tuple[dict[tuple[str, str], list[float]], float | None]:
    """{(province, source): capacities} of one workbook, and the printed yearly total."""
    rows = rows_of(path)
    header = next(
        (
            i
            for i, row in enumerate(rows[:12])
            if any("SIRA" in str(cell).upper() for cell in row if cell)
        ),
        None,
    )
    if header is None:
        raise ValueError(f"{path.name}: başlık satırı yok")
    labels = [
        re.sub(r"\s+", " ", str(cell).strip().upper()) if cell else ""
        for cell in rows[header]
    ]
    province_column = next((i for i, label in enumerate(labels) if label == "İL"), None)
    source_column = next(
        (
            i
            for i, label in enumerate(labels)
            if label in ("KAYNAK", "YAKIT CİNSİ", "YAKIT TÜRÜ")
        ),
        None,
    )
    capacity_column = next(
        (i for i, label in enumerate(labels) if label.startswith("İLAVE")), None
    )
    if None in (province_column, source_column, capacity_column):
        raise ValueError(f"{path.name}: sütunlar bulunamadı {labels[:12]}")
    found: dict[tuple[str, str], list[float]] = {}
    total = None
    for row in rows[header + 1 :]:
        cells = [str(cell).strip() if cell is not None else "" for cell in row]
        if any(TOTAL.match(cell.upper()) for cell in cells):
            total = next(
                (number(cell) for cell in row if number(cell) and number(cell) < 30000),
                total,
            )
            continue
        if province_column >= len(row) or not cells[province_column]:
            continue
        try:
            province = province_id(cells[province_column].split("-")[0])
        except KeyError:
            continue  # the summary block by source, not a plant
        source = source_code(cells[source_column]) if source_column < len(row) else None
        capacity = number(row[capacity_column]) if capacity_column < len(row) else None
        if source is None or capacity is None:
            continue
        found.setdefault((province, source), []).append(capacity)
    if not found:
        raise ValueError(f"{path.name}: satır okunamadı")
    return found, total


def load_all() -> tuple[dict[tuple[str, str, str, int], float], list[tuple]]:
    paths = sorted(FOLDER.glob("*.xls*"))
    if len(paths) < 20:
        raise FileNotFoundError(f"{FOLDER}: {len(paths)} dosya (scripts/fetch_etkb.py)")
    out: dict[tuple[str, str, str, int], float] = {}
    checks: list[tuple] = []
    for path in paths:
        year = int(path.stem)
        found, total = read_year(path)
        for (province, source), capacities in found.items():
            out[("etkb_added_capacity", province, source, year)] = sum(capacities)
            out[("etkb_added_plants", province, source, year)] = float(len(capacities))
        read = sum(
            value
            for (indicator, _p, _s, y), value in out.items()
            if indicator == "etkb_added_capacity" and y == year
        )
        checks.append((year, read, total))
    return out, checks


_CACHE: dict[tuple[str, str, str, int], float] = {}


class Etkb:
    source_id = "etkb"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        if not _CACHE:
            figures, checks = load_all()
            for year, read, total in checks:
                # the workbook's own yearly total, where it prints one
                if total and abs(read - total) > max(5.0, total * 0.02):
                    raise ValueError(
                        f"ETKB {year}: satırlar {read:,.0f} MW, basılı toplam {total:,.0f} MW"
                    )
            _CACHE.update(figures)
        records = [
            {
                "area_id": province,
                "period_start": dt.date(year, 1, 1),
                "dims": f"energy_source={source}",
                "value": value,
            }
            for (indicator, province, source, year), value in _CACHE.items()
            if indicator == self.indicator_id
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit("province").alias("area_level"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit(UNITS[self.indicator_id]).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit("etkb").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


ETKB_ADAPTERS = {
    indicator: type(f"Etkb_{indicator}", (Etkb,), {"indicator_id": indicator})
    for indicator in UNITS
}
