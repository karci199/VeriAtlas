r"""Ministry of Culture and Tourism accommodation statistics by province and district.

yigm.ktb.gov.tr publishes one workbook a year for establishments licensed by the Ministry
(1996-2021; 2007-2008 PDF only) and one for those licensed by municipalities (2000-2022, no 2001,
2007; 2008 PDF). Kept in `C:\veri-ham\ktb` under their own names.

Each sheet lists districts under their province, then the province's "Toplam" row, and ends with
GENEL TOPLAM. Columns: arrivals, nights, average length of stay and occupancy rate, each for
foreigners, citizens and total. The province name sits either in its own row (older files) or in
the first column of its first district row (newer files).

Arrivals and nights are counts; average stay and occupancy are printed ratios, kept only at
province level (the "Toplam" row), since they cannot be added up.

A ratio with nothing to divide (no foreign guests) is printed "-". Such a row is read by column and
the undefined ratio is not written; skipping the row had lost whole provinces (2010: Hakkari,
exactly the gap to GENEL TOPLAM) and kept ministry 2000-2015 out.

Checks: the provinces add up to GENEL TOPLAM (a year that fails is not loaded: municipal 2000-2006,
whose columns differ); foreigners + citizens = total on every row. Districts are written only for
years whose districts add up to their province's Toplam (ministry 2000-2005, 2009-2011, 2013-2015,
2018-2021; municipal 2009-2011, 2013-2022); the others have a few provinces whose districts fall
short, listed in MISMATCHES. 1996-1999 files have a different layout and are not read.

Loaded: ministry-licensed 2000-2006, 2009-2021 (2007-2008 are PDF only); municipality-licensed
2009-2022.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import district_key, fold, province_id, resolve_district

FOLDER = RAW / "ktb" if (RAW / "ktb").exists() else Path("C:/veri-ham/ktb")
NUMBER = re.compile(r"-?\d+(\.\d+)?([eE][+-]?\d+)?")
GUESTS = ("foreign", "citizen", "total")
NAN = float("nan")
#: measure blocks in column order, three columns each
BLOCKS = ("arrivals", "nights", "average_stay", "occupancy")
#: (file, province, block, guest, districts, printed Toplam) where the districts fall short
MISMATCHES: list[tuple] = []


def files(licence: str) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for path in FOLDER.glob("*.xls*"):
        name = path.name
        match = re.match(r"(\d{4})", name)
        if not match:
            continue
        is_municipal = "belediye" in name
        if is_municipal != (licence == "municipal"):
            continue
        year = int(match.group(1))
        if year in out:
            raise ValueError(f"KTB {licence} {year}: iki dosya")
        out[year] = path
    return out


def sheet_rows(path: Path) -> list[list[str]]:
    if path.suffix == ".xls":
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


def province_or_none(name: str) -> str | None:
    try:
        return province_id(name)
    except KeyError:
        return None


def read(path: Path):
    """Province totals, district rows, the printed grand total and unresolved names.

    Returns (provinces, districts, grand, unresolved): provinces {area: {(block, guest): v}},
    districts {(province, district name): {(block, guest): v}}.
    """
    rows = sheet_rows(path)
    first_data = None
    for i, r in enumerate(rows):
        numbers = [c for c in r if NUMBER.fullmatch(c)]
        if len(numbers) >= 12:
            first_data = i
            break
    if first_data is None:
        raise ValueError(f"KTB {path.name}: veri satırı yok")
    columns = [j for j, c in enumerate(rows[first_data]) if NUMBER.fullmatch(c)]
    provinces: dict[str, dict] = {}
    districts: dict[tuple[str, str], dict] = {}
    grand = None
    current = None
    for r in rows[max(0, first_data - 3) :]:
        texts = [c for c in r[: min(3, columns[0])] if c and not NUMBER.fullmatch(c)]
        numbers = [float(c) for c in r if NUMBER.fullmatch(c)]
        cells = [r[j] if j < len(r) else "" for j in columns]
        if (
            len(numbers) < 12
            and len(columns) == 12
            and all(c == "-" or NUMBER.fullmatch(c) for c in cells[:6])
            and all(c in ("-", "") or NUMBER.fullmatch(c) for c in cells[6:])
            and sum(1 for c in cells[:6] if NUMBER.fullmatch(c)) >= 3
            and any(t != "-" for t in texts)
        ):
            # A ratio with nothing to divide (no foreign guests) is printed "-" (ministry)
            # or left empty (municipal 2009), and a zero count can be "-" too. Such rows were
            # skipped whole (2010: Hakkari; municipal 2009: Hakkari, Yozgat, Batman, exactly
            # the gaps to GENEL TOPLAM). Read by column: a count "-" is 0, an undefined ratio
            # is not written.
            numbers = [
                (NAN if j >= 6 else 0.0) if c in ("-", "") else float(c)
                for j, c in enumerate(cells)
            ]
        if len(numbers) < 12:
            if len(texts) == 1 and province_or_none(texts[0]):
                current = province_or_none(texts[0])
            continue
        values = {
            (block, guest): numbers[b * 3 + g]
            for b, block in enumerate(BLOCKS)
            for g, guest in enumerate(GUESTS)
        }
        label = texts[-1] if texts else ""
        if len(texts) == 2 and province_or_none(texts[0]):
            current = province_or_none(texts[0])
        # "GENEL TOPLAM", "GENEL TOPLAM - Grand Total" (municipal files), in any of the first cells
        if any(fold(t).startswith("geneltoplam") for t in r[:3]):
            grand = values
            continue
        if current is None:
            raise ValueError(f"KTB {path.name}: il bilinmeden satır {r[:3]}")
        if fold(label) == "toplam":
            if current in provinces and provinces[current] == values:
                continue  # municipal 2013 prints Afyonkarahisar's Toplam twice, identical
            if current in provinces:
                raise ValueError(f"KTB {path.name}: {current} iki Toplam")
            provinces[current] = values
            continue
        key = (current, label)
        if key in districts:
            raise ValueError(f"KTB {path.name}: {key} iki kez")
        districts[key] = values
    if grand is None:
        raise ValueError(f"KTB {path.name}: GENEL TOPLAM yok")
    for block in ("arrivals", "nights"):
        for guest in GUESTS:
            read_sum = sum(v[(block, guest)] for v in provinces.values())
            if not abs(read_sum - grand[(block, guest)]) <= 1.0:  # NaN fails too
                raise ValueError(
                    f"KTB {path.name} {block} {guest}: iller {read_sum:,.0f}, GENEL TOPLAM {grand[(block, guest)]:,.0f}"
                )
            for province, total in provinces.items():
                parts = sum(
                    v[(block, guest)]
                    for (p, _), v in districts.items()
                    if p == province
                )
                if abs(parts - total[(block, guest)]) > 1.0:
                    MISMATCHES.append(
                        (
                            path.name,
                            province,
                            block,
                            guest,
                            parts,
                            total[(block, guest)],
                        )
                    )
        for where, v in [*provinces.items(), *districts.items()]:
            if (
                abs(v[(block, "foreign")] + v[(block, "citizen")] - v[(block, "total")])
                > 1.0
            ):
                raise ValueError(
                    f"KTB {path.name} {where} {block}: yabancı+yerli ≠ toplam"
                )
    return provinces, districts, grand


def province_name(area: str) -> str:
    from ..areas import load_areas

    areas = load_areas()
    return areas.filter(pl.col("area_id") == area)["name_tr"][0]


def resolve(districts: dict) -> tuple[dict, list]:
    key = district_key()
    out: dict[str, dict] = {}
    unresolved = []
    for (province, name), values in districts.items():
        try:
            area, level = resolve_district(key, province_name(province), name)
        except KeyError:
            unresolved.append((province, name))
            continue
        if level != "district":
            unresolved.append((province, name))
            continue
        out[area] = values
    return out, unresolved


#: tourism centres printed as districts that are not districts (Alsancak, Büyükada, Uludağ …):
#: {(file, province, name)}, kept for the note; their nights stay in the province total only
UNRESOLVED: set[tuple[str, str, str]] = set()
INDICATORS = {
    "ktb_arrivals": ("arrivals", "person"),
    "ktb_nights": ("nights", "item"),
    "ktb_average_stay": ("average_stay", "day"),
    "ktb_occupancy": ("occupancy", "percent"),
}
_CACHE: list[dict] = []


def load_all() -> list[dict]:
    """Rows for every licence and year that pass the grand-total check.

    Province totals are written for those years; district rows only for years whose districts
    add up to their provinces, and only for names that resolve to a district. Ratios (average
    stay, occupancy) at province level only.
    """
    rows: list[dict] = []
    for licence in ("ministry", "municipal"):
        for year, path in sorted(files(licence).items()):
            before = len(MISMATCHES)
            try:
                provinces, districts, _ = read(path)
            except ValueError:
                continue  # layout or grand total does not hold: year not loaded
            clean = len(MISMATCHES) == before
            dims_base = f"licence={licence}"
            for area, values in provinces.items():
                for (block, guest), value in values.items():
                    rows.append(
                        {
                            "block": block,
                            "area_id": area,
                            "area_level": "province",
                            "period_start": dt.date(year, 1, 1),
                            "dims": f"guest={guest};{dims_base}",
                            "value": value,
                        }
                    )
            if not clean:
                continue
            resolved, unresolved = resolve(districts)
            UNRESOLVED.update((path.name, p, n) for p, n in unresolved)
            for area, values in resolved.items():
                for (block, guest), value in values.items():
                    if block not in ("arrivals", "nights"):
                        continue
                    rows.append(
                        {
                            "block": block,
                            "area_id": area,
                            "area_level": "district",
                            "period_start": dt.date(year, 1, 1),
                            "dims": f"guest={guest};{dims_base}",
                            "value": value,
                        }
                    )
    return rows


class KtbAccommodation:
    source_id = "ktb"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        if not _CACHE:
            _CACHE.extend(load_all())
        block, unit = INDICATORS[self.indicator_id]
        records = [
            {k: v for k, v in r.items() if k != "block"}
            for r in _CACHE
            if r["block"] == block
            and r["value"] == r["value"]  # not an undefined ratio
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit(unit).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


KTB_ADAPTERS = {
    indicator: type(
        f"Ktb_{indicator}", (KtbAccommodation,), {"indicator_id": indicator}
    )
    for indicator in INDICATORS
}
