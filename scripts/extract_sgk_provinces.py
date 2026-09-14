"""Flatten every province table in the SGK yearbooks into one long file, untranslated.

The yearbooks renumber their tables from year to year and change the sub-columns, so the
adapter cannot address "table 1.7" or "column 5". This pass keeps what each cell *says*
instead: for every sheet that lists the provinces, one row per (province row, numeric
column) with the sheet title, the header text above the column and any text label on the
row (sex, pension type, ...). The adapter maps titles and headers to indicators.

A province row is a plate number 1-81 followed within two cells by that province's name.
A sheet can hold several province blocks (a second table below the first); each block
takes the header rows between the previous block and its first province.

Output: `$VERIATLAS_RAW/sgk/province_cells.parquet`.

Run:  uv run python scripts/extract_sgk_provinces.py
"""

from __future__ import annotations

import re
import sys

import polars as pl
from python_calamine import CalamineWorkbook

sys.path.insert(0, "src")

from veriatlas.areas import load_areas
from veriatlas.config import RAW

ROOT = RAW / "sgk" / "yillik"
#: Yearbook spellings of province names → ours, keyed without dots and spaces.
ALIASES = {
    "icel": "mersin",
    "afyon": "afyonkarahisar",
    "kmaras": "kahramanmaras",
    "surfa": "sanliurfa",
    "urfa": "sanliurfa",
}


def fold(text: str) -> str:
    text = text.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu", strict=True):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def provinces() -> dict[str, int]:
    frame = load_areas().filter(pl.col("area_level") == "province")
    names = {key(r["name_tr"]): int(r["area_id"][3:]) for r in frame.to_dicts()}
    return names | {alias: names[ours] for alias, ours in ALIASES.items()}


def plate(value) -> int | None:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and 1 <= value <= 81:
        return value
    if isinstance(value, str) and re.fullmatch(r"\s*\d{1,2}\s*", value):
        number = int(value)
        return number if 1 <= number <= 81 else None
    return None


def number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text in {"-", "–"}:
            return 0.0
        if re.fullmatch(r"-?\d+([.,]\d+)?", text):
            return float(text.replace(",", "."))
    return None


def title_of(rows: list[list]) -> str:
    for row in rows[:8]:
        for cell in row:
            if (
                isinstance(cell, str)
                and re.match(r"\s*tablo", cell, re.IGNORECASE)
                and len(cell) > 12
            ):
                return re.sub(r"\s+", " ", cell).strip()
    return ""


def header_paths(block: list[list], width: int) -> list[str]:
    """Join the header rows top to bottom; merged cells arrive only in their first
    column, so a label is carried right until the row above it changes."""
    paths = [[] for _ in range(width)]
    parent_breaks: set[int] = set()
    for row in block:
        carried = ""
        breaks = set(parent_breaks)
        for col in range(width):
            cell = row[col] if col < len(row) else None
            text = (
                re.sub(r"\s+", " ", str(cell)).strip() if cell not in (None, "") else ""
            )
            if re.match(r"(tablo|table)\s*[:\d]", text, re.IGNORECASE) and col > 1:
                # The page marker ("Tablo : 18/1") printed at the right of the title rows
                # is not a column heading; read as one it cuts the label above it short.
                text = ""
            if col in parent_breaks:
                carried = ""
            if text:
                carried = text
                breaks.add(col)
            if carried:
                paths[col].append(carried)
        parent_breaks = breaks
    # Past the last column any header row names, a carried label is not a heading: the
    # yearbooks keep unlabelled working columns there (2007 pensions, 2010 workplaces).
    labelled = [
        col
        for row in block
        for col, cell in enumerate(row)
        if cell not in (None, "")
        and not re.match(r"(tablo|table)\s*[:\d]", str(cell).strip(), re.IGNORECASE)
    ]
    edge = max(labelled, default=-1)
    own = set(labelled)
    out = []
    for col, p in enumerate(paths):
        text = " > ".join(p) if col <= edge else ""
        if text and col not in own and out and out[-1] == text:
            # No heading of its own and the same carried path as its left neighbour: a
            # working column inside the table (2009 pensions repeat 2007 figures there).
            text = ""
        if text and text in out:
            # The same full heading twice in one table: the later column is a copy
            # (2009 pensions carry 2007 figures under a repeated "TOPLAM").
            text = ""
        out.append(text)
    return out


def key(name: str) -> str:
    return re.sub(r"[\s.]", "", fold(name))


def sheet_cells(rows: list[list], names: dict[str, int]) -> list[dict]:
    # row index, name column, province plate, plate as printed
    hits: list[tuple[int, int, int, int]] = []
    for r, row in enumerate(rows):
        for c, cell in enumerate(row[:4]):
            printed = plate(cell)
            if printed is None:
                continue
            for cc in range(c + 1, min(c + 3, len(row))):
                name = row[cc]
                if isinstance(name, str) and key(name) in names:
                    # The name decides: the 2012-2016 size tables number Kırıkkale 72,
                    # the same as Batman.
                    hits.append((r, cc, names[key(name)], printed))
                    break
            else:
                continue
            break
    if len(hits) < 70:
        return []
    width = max(len(row) for row in rows)
    out: list[dict] = []
    block, previous_end, last_plate = 0, 0, 99
    headers: list[str] = []
    for r, c, p, printed in hits:
        # A page break repeats the header and carries on with the next plate; only a
        # restart of the numbering is a new table.
        if p <= last_plate:
            block += 1
            headers = header_paths(rows[previous_end:r], width)
        row = rows[r]
        labels = [
            re.sub(r"\s+", " ", str(v)).strip()
            for i, v in enumerate(row)
            if i > c and isinstance(v, str) and v.strip() and number(v) is None
        ]
        for col in range(c + 1, len(row)):
            value = number(row[col])
            if value is None or col >= len(headers) or not headers[col]:
                continue
            out.append(
                {
                    "block": block,
                    "row": r + 1,
                    "col": col + 1,
                    "plate": p,
                    "printed_plate": printed,
                    "header": headers[col] if col < len(headers) else "",
                    "row_label": " | ".join(labels),
                    "value": value,
                }
            )
        last_plate, previous_end = p, r + 1
    return out


def main() -> None:
    names = provinces()
    frames = []
    for year_dir in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        for path in sorted(year_dir.rglob("*")):
            if path.suffix.lower() not in {".xls", ".xlsx"}:
                continue
            workbook = CalamineWorkbook.from_path(str(path))
            for sheet in workbook.sheet_names:
                rows = workbook.get_sheet_by_name(sheet).to_python()
                cells = sheet_cells(rows, names)
                if not cells:
                    continue
                frame = pl.DataFrame(cells).with_columns(
                    pl.lit(int(year_dir.name)).alias("year"),
                    pl.lit(str(path.relative_to(ROOT))).alias("file"),
                    pl.lit(sheet).alias("sheet"),
                    pl.lit(title_of(rows)).alias("title"),
                )
                frames.append(frame)
                print(year_dir.name, sheet, frame.height, frame["block"].max())
    result = pl.concat(frames, how="vertical_relaxed")
    target = RAW / "sgk" / "province_cells.parquet"
    result.write_parquet(target)
    print(target, result.height)


if __name__ == "__main__":
    main()
