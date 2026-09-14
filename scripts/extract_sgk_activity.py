"""Read the SGK table of 4/a workplaces and insured by activity division and province.

The one province table the general extractor cannot read: provinces run across the
columns (a workplace and an insured column each), NACE Rev.2 divisions down the rows.
2008-2025; 2007's table uses the older 43-code grouping and is left out.

Every value is checked twice against the table's own margins: the province columns of a
division must sum to its "Genel toplam", and the divisions of a province to its "Toplam"
row. A table that fails stops the run.

Output: `$VERIATLAS_RAW/sgk/activity_cells.parquet` (year, division, division name,
plate, measure, value), plus the margins as plate 0 / division "total".

Run:  uv run python scripts/extract_sgk_activity.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict

import polars as pl
from python_calamine import CalamineWorkbook

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from extract_sgk_provinces import ROOT, fold, key, provinces

TITLE = re.compile(
    r"faaliyet grup\w* ve il|faaliyet grubu ve ile|faaliyet gruplarina ve illere"
)


def measure_of(cell) -> str | None:
    text = fold(str(cell or ""))
    if re.match(r"is ?yeri", text):
        return "workplaces"
    if re.match(r"sigortali", text):
        return "insured"
    return None


def read(rows: list[list], names: dict[str, int]) -> list[dict]:
    header = next(
        i
        for i, r in enumerate(rows)
        if sum(isinstance(c, str) and key(c) in names for c in r) > 40
    )
    plate_at: dict[int, int] = {}
    current = None
    width = max(len(r) for r in rows)
    for col in range(2, width):
        cell = rows[header][col] if col < len(rows[header]) else None
        if isinstance(cell, str) and cell.strip():
            if re.match(r"kod|faaliyet", fold(cell)):
                # 2008-2009 repeat the code and name columns at each printed page.
                current = None
                continue
            current = names.get(key(cell), 0 if "toplam" in fold(cell) else None)
            if current is None:
                raise KeyError(f"il sütunu tanınmadı: {cell!r}")
        if current is not None:
            plate_at[col] = current
    measures = rows[header + 1]
    out = []
    for r in rows[header + 2 :]:
        if not r or all(c in (None, "") for c in r[:3]):
            continue
        first, label = str(r[0]).strip(), str(r[1] if len(r) > 1 else "").strip()
        code = first.replace(".0", "")
        if re.fullmatch(r"\d{1,2}", code):
            division, name = code.zfill(2), label
        elif re.match(r"\W*ek-9", fold(first)):
            # From 2017 domestic workers under Ek-9 get a row of their own, no code.
            division, name = "ek9", "Ek-9 ev hizmetlerinde 10 günden fazla çalışanlar"
        elif "toplam" in fold(first + " " + label):
            division, name = "total", "Toplam"
        else:
            continue
        for col, plate in plate_at.items():
            measure = measure_of(measures[col] if col < len(measures) else None)
            value = r[col] if col < len(r) else None
            if measure is None or value in (None, ""):
                continue
            out.append(
                {
                    "division": division,
                    "name": name,
                    "plate": plate,
                    "measure": measure,
                    "value": float(value),
                }
            )
    return out


def check(cells: list[dict], label: str) -> None:
    for measure in ("workplaces", "insured"):
        grid = defaultdict(float)
        for c in cells:
            if c["measure"] == measure:
                grid[(c["division"], c["plate"])] = c["value"]
        divisions = {d for d, _ in grid}
        plates = {p for _, p in grid}
        if plates - {0} != set(range(1, 82)):
            raise ValueError(f"{label}: il eksik {sorted(set(range(1, 82)) - plates)}")
        bad = []
        for d in divisions:
            s = sum(grid[(d, p)] for p in range(1, 82))
            if abs(s - grid[(d, 0)]) > 0.5:
                bad.append(("division", d, s, grid[(d, 0)]))
        for p in plates:
            s = sum(grid[(d, p)] for d in divisions if d != "total")
            if abs(s - grid[("total", p)]) > 0.5:
                bad.append(("province", p, s, grid[("total", p)]))
        if bad:
            raise ValueError(
                f"{label} {measure}: {len(bad)} toplam tutmuyor, ör. {bad[:3]}"
            )


def main() -> None:
    names = provinces()
    frames = []
    for year_dir in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        year = int(year_dir.name)
        for path in sorted(year_dir.rglob("*")):
            if path.suffix.lower() not in {".xls", ".xlsx"}:
                continue
            workbook = CalamineWorkbook.from_path(str(path))
            for sheet in workbook.sheet_names:
                rows = workbook.get_sheet_by_name(sheet).to_python()
                title = next(
                    (
                        c
                        for r in rows[:8]
                        for c in r
                        if isinstance(c, str) and re.match(r"\s*tablo", c, re.IGNORECASE)
                    ),
                    "",
                )
                if not TITLE.search(fold(title)) or year < 2008:
                    continue
                cells = read(rows, names)
                check(cells, f"{year}/{sheet}")
                frames.append(
                    pl.DataFrame(cells).with_columns(
                        pl.lit(year).alias("year"), pl.lit(sheet).alias("sheet")
                    )
                )
                print(year, sheet, len(cells), "hücre, toplamlar tuttu")
    result = pl.concat(frames)
    target = ROOT.parent / "activity_cells.parquet"
    result.write_parquet(target)
    print(target, result.height)


if __name__ == "__main__":
    main()
