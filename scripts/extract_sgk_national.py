"""Flatten the SGK yearbook tables that have no province breakdown into one long file.

The counterpart of `extract_sgk_provinces.py` for the Türkiye-level tables: by month,
hour, age, activity, occupation, injury, benefit type and so on. A data row is a row whose
label cells (a code and/or a text in the first three columns) are followed by numbers;
the header of a block is the rows between the previous block and its first data row, read
with the same carry rules as the province extractor.

Output: `$VERIATLAS_RAW/sgk/national_cells.parquet` with year, file, sheet, title, block,
row, col, code, label, header, value. Sheets already read as province tables are skipped.

Run:  uv run python scripts/extract_sgk_national.py
"""

from __future__ import annotations

import re
import sys

import polars as pl
from python_calamine import CalamineWorkbook

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from extract_sgk_provinces import RAW, ROOT, header_paths, number, title_of


def label_cells(row: list) -> tuple[str, str, int] | None:
    """(code, label, first value column) when the row starts with labels then numbers."""
    code, label = "", ""
    for i, cell in enumerate(row[:4]):
        if cell in (None, ""):
            continue
        text = re.sub(r"\s+", " ", str(cell)).strip()
        if number(cell) is not None and not isinstance(cell, str):
            if (
                i == 0
                and float(cell).is_integer()
                and 0 <= cell < 10000
                and len(row) > 2
            ):
                code = str(int(cell))
                continue
            return (code, label, i) if (code or label) else None
        if re.fullmatch(r"\d{1,4}(\.\d)?", text) and not label:
            code = text
            continue
        if label:
            label = label + " | " + text
        else:
            label = text
    return None


def sheet_cells(rows: list[list]) -> list[dict]:
    width = max((len(r) for r in rows), default=0)
    out: list[dict] = []
    block, previous_end, headers, in_block = 0, 0, [], False
    for r, row in enumerate(rows):
        found = label_cells(row)
        values = [(c, number(v)) for c, v in enumerate(row) if found and c >= found[2]]
        values = [(c, v) for c, v in values if v is not None]
        if not found or len(values) < 1:
            if in_block and all(v in (None, "") for v in row):
                in_block = False
                previous_end = r + 1
            elif in_block and not found:
                in_block = False
                previous_end = r
            continue
        if not in_block:
            block += 1
            headers = header_paths(rows[previous_end:r], width)
            in_block = True
        code, label, _ = found
        if re.match(r"(tablo|table)\b", label, re.IGNORECASE):
            continue
        for col, value in values:
            header = headers[col] if col < len(headers) else ""
            if not header:
                continue
            out.append(
                {
                    "block": block,
                    "row": r + 1,
                    "col": col + 1,
                    "code": code,
                    "label": label,
                    "header": header,
                    "value": value,
                }
            )
        previous_end = r + 1
    return out


def main() -> None:
    provinces = (
        pl.read_parquet(RAW / "sgk" / "province_cells.parquet")
        .select("year", "file", "sheet")
        .unique()
    )
    done = {tuple(r) for r in provinces.iter_rows()}
    frames = []
    for year_dir in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        year = int(year_dir.name)
        for path in sorted(year_dir.rglob("*")):
            if path.suffix.lower() not in {".xls", ".xlsx"}:
                continue
            rel = str(path.relative_to(ROOT))
            workbook = CalamineWorkbook.from_path(str(path))
            for sheet in workbook.sheet_names:
                if (year, rel, sheet) in done:
                    continue
                rows = workbook.get_sheet_by_name(sheet).to_python()
                title = title_of(rows)
                if not title:
                    continue
                cells = sheet_cells(rows)
                if not cells:
                    continue
                frames.append(
                    pl.DataFrame(cells).with_columns(
                        pl.lit(year).alias("year"),
                        pl.lit(rel).alias("file"),
                        pl.lit(sheet).alias("sheet"),
                        pl.lit(title).alias("title"),
                    )
                )
        print(year, sum(f.height for f in frames), flush=True)
    result = pl.concat(frames, how="vertical_relaxed")
    target = RAW / "sgk" / "national_cells.parquet"
    result.write_parquet(target)
    print(
        target, result.height, result.select("year", "sheet").unique().height, "tablo"
    )


if __name__ == "__main__":
    main()
