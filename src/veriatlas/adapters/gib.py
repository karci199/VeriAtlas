"""Active taxpayers by province and month, 2002 onwards (Revenue Administration, GİB).

Source: gib.gov.tr "İstatistikler", topic "Aylar itibariyle mükellef sayıları", one folder
per year (`raw/gib/mukellef/<year>/`, `scripts/fetch_gib.py`). The even tables (2002-2003:
the `-A` ones and 50, 52) list the 81 provinces with the year's twelve months and the
previous December beside them, one table per tax: income tax, income withholding, rental
income (GMSİ), simple-method income tax, corporate tax and VAT. The odd tables are the
Türkiye series of the same counts and are not read: the provincial TOPLAM row is checked
instead.

The tax is read from the table's title, not its number (the numbering changed in 2004).
Each month is taken from its own year's file; the previous-December column is only
compared with the year before, and a difference stops the load. Months not yet
published in the current year's file are blank and skipped.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold, province_id

FILES = RAW / "gib" / "mukellef"
MONTHS = {
    "ocak": 1,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "eylul": 9,
    "ekim": 10,
    "kasim": 11,
    "aralik": 12,
}
#: Title fragment (folded) → tax; order matters, plain income tax comes last.
TAXES = (
    ("stopaj", "income_withholding"),
    ("gmsi", "rental_income"),
    ("basit", "simple_method"),
    ("kurumlar", "corporate_tax"),
    ("katmadeger", "vat"),
    ("gelirvergisi", "income_tax"),
)

#: (tax, month) left out: the column is shifted between provinces.
DROPPED: list[tuple[str, dt.date]] = []
#: (year folder, file, month) whose TOPLAM is blank or 0: only the continuity check ran.
UNCHECKED: list[tuple[str, str, dt.date]] = []


def tax_of(title: str) -> str:
    key = fold(title)
    return next(tax for fragment, tax in TAXES if fragment in key)


def month_of(label) -> dt.date | None:
    """Header cell → month; 2005 heads its columns with Excel dates, the rest with text."""
    if isinstance(label, dt.date):
        return dt.date(label.year, label.month, 1)
    label = str(label)
    key = fold(label)
    year = re.search(r"(19|20)\d\d", str(label))
    month = next((m for name, m in MONTHS.items() if name in key), None)
    if not year or not month:
        return None
    return dt.date(int(year.group(0)), month, 1)


def number(cell) -> float | None:
    """Counts are whole numbers. Some cells are text in Turkish notation ("\\xa012.630\\xa0"),
    where float() would read the thousands dot as a decimal point: 12.63."""
    if isinstance(cell, str):
        cell = cell.replace("\xa0", "").replace(" ", "").replace(".", "")
    if cell in ("", None, "-"):
        return None
    return float(cell)


def read_table(
    path: Path, year: int
) -> tuple[str, dict[tuple[str, dt.date], float]] | None:
    """(tax, {(area, month): count}) for a provincial table; None for a Türkiye table.

    Months are placed by position (previous December, then January to December of
    `year`) and the header is only checked for the month names: 2021's GMSİ table heads
    its last two columns "KASIM-2020", "ARALIK-2020".
    """
    from python_calamine import CalamineWorkbook

    book = CalamineWorkbook.from_path(path)
    rows = book.get_sheet_by_name(book.sheet_names[0]).to_python()
    title = next(str(c) for c in rows[0] if str(c).strip())
    if "illere" not in fold(title):
        return None
    tax = tax_of(title)
    head = next(i for i, r in enumerate(rows) if fold(str(r[0])).startswith("ilkodu"))
    headed = [j for j, c in enumerate(rows[head]) if month_of(c)]
    expected = [dt.date(year - 1, 12, 1)] + [dt.date(year, m, 1) for m in range(1, 13)]
    if len(headed) != 13 or headed != list(range(headed[0], headed[0] + 13)):
        raise ValueError(f"GİB {path}: ay sütunları {rows[head]}")
    columns = dict(zip(headed, expected, strict=True))
    for j, month in columns.items():
        if month_of(rows[head][j]).month != month.month:
            raise ValueError(f"GİB {path}: {rows[head][j]} sütunu {month} olmalı")
    out: dict[tuple[str, dt.date], float] = {}
    total = None
    for r in rows[head + 1 :]:
        name = str(r[1]).strip()
        if fold(name) == "toplam":
            total = r
            break
        if not name:
            continue
        area = province_id(name)
        if area != f"TR-{int(float(r[0])):02d}":
            raise ValueError(f"GİB {path}: {r[0]} {name} → {area}")
        for j, month in columns.items():
            value = number(r[j])
            if value is None:
                continue
            if (area, month) in out:
                raise ValueError(f"GİB {path}: {name} {month} iki kez")
            out[(area, month)] = value
    if total is None:
        raise ValueError(f"GİB {path}: TOPLAM satırı yok")
    for j, month in columns.items():
        printed = number(total[j])
        cells = [v for (a, m), v in out.items() if m == month]
        if not cells:
            continue
        if len(cells) != 81:
            raise ValueError(f"GİB {path} {month}: {len(cells)} il")
        if not printed:
            # 2026 corporate tax, June: provinces filled, TOPLAM 0. Kept on the
            # continuity check below alone.
            UNCHECKED.append((path.parent.name, path.name, month))
            continue
        if abs(sum(cells) - printed) > 0.5:
            raise ValueError(
                f"GİB {path} {month}: iller {sum(cells):,.0f}, TOPLAM {printed:,.0f}"
            )
    return tax, out


def scrambled(table: dict[tuple[str, dt.date], float]) -> list[dt.date]:
    """Months whose column does not follow the month before it, province by province.

    The TOPLAM check cannot see values moved between provinces: 2026's corporate tax
    table has July shifted by rows (Ankara's count beside Antalya, İstanbul's beside
    Kırşehir) and its total still adds up. A province whose change differs from the
    national change by more than 25 % counts as off; more than five off breaks the pair.

    A month is dropped only when it breaks with both neighbours (the last month: with
    the one before). A real step, such as rental-income taxpayers added unevenly in
    March when the yearly returns are filed, breaks with the month before but holds with
    the month after.
    """

    def breaks(a: dt.date, b: dt.date) -> bool:
        areas = [p for p, m in table if m == a]
        national = sum(table[(p, b)] for p in areas) / sum(table[(p, a)] for p in areas)
        off = sum(
            1
            for p in areas
            if table[(p, a)]
            and abs(table[(p, b)] / table[(p, a)] / national - 1) > 0.25
        )
        return off > 5

    months = sorted({m for _, m in table})
    bad = []
    good: list[dt.date] = []
    for i, month in enumerate(months):
        # Compared with the last month kept, so a shifted July does not take August too.
        before = bool(good) and breaks(good[-1], month)
        after = i + 1 == len(months) or breaks(month, months[i + 1])
        if before and after:
            bad.append(month)
        else:
            good.append(month)
    return bad


def read_all() -> dict[str, dict[tuple[str, dt.date], float]]:
    """{tax: {(area, month): count}}, each month from its own year's file."""
    merged: dict[str, dict[tuple[str, dt.date], float]] = {}
    previous_december: dict[str, dict[tuple[str, dt.date], float]] = {}
    for folder in sorted(p for p in FILES.iterdir() if p.is_dir()):
        year = int(folder.name)
        found = set()
        for path in sorted(folder.glob("*.xls*")):
            read = read_table(path, year)
            if read is None:
                continue
            tax, table = read
            if tax in found:
                raise ValueError(f"GİB {year}: {tax} iki tabloda")
            found.add(tax)
            own = merged.setdefault(tax, {})
            for (area, month), value in table.items():
                if month.year == year:
                    own[(area, month)] = value
                else:
                    previous_december.setdefault(tax, {})[(area, month)] = value
        if len(found) != len(TAXES):
            raise ValueError(f"GİB {year}: {sorted(found)}")
    for tax, table in previous_december.items():
        for key, value in table.items():
            if key in merged[tax] and merged[tax][key] != value:
                raise ValueError(
                    f"GİB {tax} {key}: önceki yıl {merged[tax][key]:,.0f}, sonraki dosya {value:,.0f}"
                )
    # Checked on the whole series, so December is compared with the next January.
    for tax, table in merged.items():
        for month in scrambled(table):
            DROPPED.append((tax, month))
            merged[tax] = table = {k: v for k, v in table.items() if k[1] != month}
    return merged


class GibActiveTaxpayers:
    source_id = "gib"
    indicator_id = "active_taxpayers"

    def fetch(self) -> Path:
        return FILES

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "area_id": area,
                "period_start": month,
                "dims": f"tax_type={tax}",
                "value": value,
            }
            for tax, table in read_all().items()
            for (area, month), value in table.items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("monthly").alias("frequency"),
            pl.lit("taxpayer").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 26)).alias("retrieved_at"),
        )


GIB_ADAPTERS = {"active_taxpayers": GibActiveTaxpayers}
