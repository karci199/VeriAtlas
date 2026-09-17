r"""Muhasebat: general budget revenue by province, accrued and collected, 2004-2025.

`scripts/fetch_muhasebat.py` keeps one workbook per province and year (plus 00-Merkez, revenue
booked centrally, not written) in `C:\veri-ham\muhasebat\genel_butce_gelirleri\<year>\`. Folder
2008 also holds the 2006 and 2007 files; the year is read from the file name. 2026 is a year to
date and is not loaded.

Each workbook has one sheet a month, cumulative; ARALIK (December) is the year. Where a file has
no ARALIK sheet (2007 Bitlis stops at KASIM) the year is not written for that province.

The label column is the one left of the "Tahakkuk" header (2015 and 2020 files start a column
later). Kept lines, by their label: the general budget total, tax revenue, income tax, corporate
tax, domestic VAT, special consumption tax (ÖTV) and motor vehicle tax (from 2006; 2004-2005
print no such line). A label can recur further down (2018 Çankırı: "Gelir Vergisi" again in
another block); the first printing is kept. 2004-2005 print "Dahilde Alınan Katma Değer Vergisi"
twice before ÖTV, the group and the tax itself indented under it: the later one is kept.

Units: thousand lira throughout ("Milyar TL" in 2004-2005 is a thousand new lira, "Bin YTL"
2005-2008 likewise).

Checks: every province has one file a year; each kept line appears; tax ≤ total and
income + corporate tax ≤ tax, on accruals (collections net off refunds, so a part can exceed the
whole: 2018 Çankırı collected 92,906 of tax and 138,504 of income and corporate tax). A
province-year that breaks the check is left out whole; more than MAX_PROBLEMS stops the load.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold

FOLDER = (
    RAW / "muhasebat" / "genel_butce_gelirleri"
    if (RAW / "muhasebat").exists()
    else Path("C:/veri-ham/muhasebat/genel_butce_gelirleri")
)
LAST_YEAR = 2025
#: revenue line -> folded label, optional roman or letter prefix
LINES = {
    "total": r"genelbutcegelirleri",
    "tax": r"i?vergigelirleri",
    "income_tax": r"a?gelirvergisi",
    "corporate_tax": r"b?kurumlarvergisi",
    "domestic_vat": r"a?dahildealinankatmadegervergisi",
    "special_consumption_tax": r"b?ozeltuketimvergisi",
    "motor_vehicle_tax": r"b?motorlutasitlarvergisi",
}
OPTIONAL = {"motor_vehicle_tax"}  # not printed in 2004-2005
MEASURES = ("accrued", "collected")
#: province-years left out because the file contradicts itself (see load_all)
PROBLEMS: list[str] = []
MAX_PROBLEMS = 20


def files() -> dict[tuple[str, int], Path]:
    out: dict[tuple[str, int], Path] = {}
    for path in FOLDER.glob("*/*.xls*"):
        found = re.match(r"(\d{2}).*?[-_](20\d\d)", path.name)
        if not found:
            raise ValueError(f"Muhasebat: dosya adı okunamadı {path.name}")
        code, year = found.group(1), int(found.group(2))
        if code == "00" or year > LAST_YEAR:
            continue
        key = (f"TR-{code}", year)
        if key in out:
            raise ValueError(f"Muhasebat: {key} iki dosya")
        out[key] = path
    return out


def read(path: Path) -> dict[tuple[str, str], float] | None:
    """{(line, measure): thousand lira} from the December sheet, None if there is none."""
    from python_calamine import CalamineWorkbook

    book = CalamineWorkbook.from_path(path)
    december = [n for n in book.sheet_names if fold(n) == "aralik"]
    if not december:
        return None
    rows = book.get_sheet_by_name(december[0]).to_python()
    header = next(
        (i, j)
        for i, row in enumerate(rows)
        for j, cell in enumerate(row)
        if fold(str(cell)) == "tahakkuk"
    )
    label_col = header[1] - 1
    matches: dict[str, list[tuple[int, list]]] = {}
    for i, row in enumerate(rows[header[0] + 1 :]):
        label = re.sub(r"^\d+", "", fold(str(row[label_col])))
        for line, pattern in LINES.items():
            if re.fullmatch(pattern, label):
                matches.setdefault(line, []).append((i, row))
    out: dict[tuple[str, str], float] = {}
    for line, found in matches.items():
        # The first printing, except domestic VAT: 2004-2005 print the group and, indented
        # under it and before the special consumption tax, the tax itself.
        chosen = found[0][1]
        if line == "domestic_vat" and "special_consumption_tax" in matches:
            before = [
                r for i, r in found if i < matches["special_consumption_tax"][0][0]
            ]
            chosen = before[-1] if before else chosen
        for k, measure in enumerate(MEASURES):
            cell = chosen[header[1] + k]
            out[(line, measure)] = float(cell) if cell not in ("", None) else 0.0
    missing = {line for line in LINES if (line, "accrued") not in out} - OPTIONAL
    if missing:
        raise ValueError(f"Muhasebat {path.name}: satır yok {sorted(missing)}")
    # Collections net off refunds (VAT refunds turn lines negative), so a part can exceed its
    # whole there; the check is made on accruals.
    for measure in ("accrued",):
        total, tax = out[("total", measure)], out[("tax", measure)]
        parts = out[("income_tax", measure)] + out[("corporate_tax", measure)]
        if tax > total + 1 or parts > tax + 1:
            PROBLEMS.append(
                f"{path.name} {measure}: toplam {total:,.0f}, vergi {tax:,.0f}, "
                f"gelir+kurumlar {parts:,.0f}"
            )
            return None
    return out


def load_all() -> list[dict]:
    found = files()
    years = {year for _, year in found}
    for year in years:
        have = {area for area, y in found if y == year}
        if len(have) != 81:
            raise ValueError(f"Muhasebat {year}: {len(have)} il")
    rows = []
    PROBLEMS.clear()
    for (area, year), path in sorted(found.items()):
        values = read(path)
        if values is None:
            continue
        for (line, measure), value in values.items():
            rows.append(
                {
                    "area_id": area,
                    "period_start": dt.date(year, 1, 1),
                    "dims": f"budget_measure={measure};revenue_line={line}",
                    "value": value,
                }
            )
    if len(PROBLEMS) > MAX_PROBLEMS:
        raise ValueError(f"Muhasebat: {len(PROBLEMS)} tutarsız il-yıl: {PROBLEMS[:5]}")
    return rows


class MuhasebatRevenue:
    source_id = "muhasebat"
    indicator_id = "budget_revenue_by_province"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        return pl.DataFrame(
            load_all(), schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("thousand_try").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


MUHASEBAT_ADAPTERS = {"budget_revenue_by_province": MuhasebatRevenue}


# --- Central government and local government budgets by province -------------------------
#
# Two more Muhasebat pages, fetched by the same script into
# `C:\veri-ham\muhasebat\{merkezi,mahalli}_yonetim_butcesi\<year>\`. Unlike the revenue page
# these are national workbooks: one file a table, one sheet a cumulative period, one row a
# province. The first sheet is the latest period, so a year is read only when its title names
# December.
#
# Central: "Merkezi Yönetim Kümülatif Bütçe Gelirleri Tahsilatı" (collections, 2004-) and
# "... Bütçe Giderleri" (expenditure, 2004-), the latter carrying both the economic and the
# functional classification. Local: "İller İtibarıyla Mahalli İdareler Bütçe Gelirleri" and
# "... Giderleri" (2006-). The balance table is revenue minus expenditure and is not read.

CENTRAL_FOLDER = FOLDER.parent / "merkezi_yonetim_butcesi"
LOCAL_FOLDER = FOLDER.parent / "mahalli_yonetim_butcesi"

#: column header -> revenue line. The classification changed in 2007: until then non-tax
#: revenue is one column, and 2004-2005 print the pre-2006 consolidated budget, with the
#: annexed budgets own revenue, instead of the central government budget.
REVENUE_COLUMNS = {
    "merkezibutce": "total",
    "merkeziyonetim": "total",
    "konsolidebutce": "total",
    "butcegelirleri": "total",  # local government
    "genelbutce": "general_budget",
    "ozelbutce": "special_budget",
    "duzenleyicivedenetleyicikurbutce": "regulatory_budget",
    "duzenleyicivedenetleyicikurumlar": "regulatory_budget",
    "katmabutceozgelirleri": "annexed_budget",
    "vergigelirleri": "tax",
    "vergidisigelirler": "non_tax",
    "tesebbusvemulkiyetgelirleri": "enterprise_property",
    "alinanbagisveyardimlar": "grants",
    "faizlerpaylarvecezalar": "interest_shares_fines",
    "sermayegelirleri": "capital_revenue",
    "alacaklardantahsilatlar": "receivables",
}
#: revenue lines that add up to the general budget (to the total, for local government)
REVENUE_PARTS = (
    "tax",
    "non_tax",
    "enterprise_property",
    "grants",
    "interest_shares_fines",
    "capital_revenue",
    "receivables",
)
#: revenue lines that add up to the total, where the year prints them
REVENUE_BUDGETS = (
    "general_budget",
    "special_budget",
    "regulatory_budget",
    "annexed_budget",
)

#: column header -> expenditure line, classification
EXPENDITURE_COLUMNS = {
    "toplam": ("total", "economic"),
    "persgiderleri": ("personnel", "economic"),
    "sosyalguvkurod": ("social_security", "economic"),
    "malvehizmetalimlari": ("goods_services", "economic"),
    "faizharc": ("interest", "economic"),
    "caritrans": ("current_transfers", "economic"),
    "sermayegiderleri": ("capital_expenditure", "economic"),
    "sermayetrans": ("capital_transfers", "economic"),
    "borcverme": ("lending", "economic"),
    "yedekod": ("reserve", "economic"),
    "genelkamuhiz": ("general_public_services", "functional"),
    "savunmahiz": ("defence", "functional"),
    "kamuduzeniveguv": ("public_order", "functional"),
    "ekonomikislervehiz": ("economic_affairs", "functional"),
    "cevrekorumahiz": ("environmental_protection", "functional"),
    "iskanvetoplumrefhiz": ("housing_community", "functional"),
    "saglikhiz": ("health", "functional"),
    "dinlenkulturvedinhiz": ("recreation_culture_religion", "functional"),
    "egitimhiz": ("education", "functional"),
    "sosguvsosyalyarhiz": ("social_protection", "functional"),
}


def number(cell: object) -> float | None:
    """The cell as a number, None where it is empty or a note."""
    if cell is None or cell == "" or isinstance(cell, bool):
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    text = str(cell).strip().replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def table(
    path: Path, columns: dict[str, object]
) -> tuple[list[list], dict[int, object]]:
    """The latest sheet of a national workbook: its rows below the header, and the header
    as {column index: value of `columns`}."""
    from python_calamine import CalamineWorkbook

    book = CalamineWorkbook.from_path(path)
    sheet = book.sheet_names[0]
    rows = book.get_sheet_by_name(sheet).to_python()
    title = fold(" ".join(str(c) for row in rows[:4] for c in row))
    if "aralik" not in title and len(book.sheet_names) > 1:
        raise ValueError(f"Muhasebat {path.name}: yıl sayfası değil ({sheet})")
    for i, row in enumerate(rows[:12]):
        header = {
            j: columns[fold(str(cell))]
            for j, cell in enumerate(row)
            if fold(str(cell)) in columns
        }
        if len(header) >= 4:
            return rows[i + 1 :], header
    raise ValueError(f"Muhasebat {path.name}: başlık satırı yok")


#: the one province these tables abbreviate
NAME_ALIASES = {"urfa": "Şanlıurfa"}


def by_province(
    path: Path, columns: dict[str, object]
) -> dict[str, dict[object, float]]:
    """{area_id: {header value: number}}. The Merkez row (revenue and spending booked
    centrally, not a province) is left out, as are the notes printed below the table: they
    carry no number in any of the header's columns."""
    from .kgm import province_id

    body, header = table(path, columns)
    out: dict[str, dict[object, float]] = {}
    for row in body:
        label = fold(str(row[0]))
        if label in ("toplam", "geneltoplam"):
            break
        values = {
            value: cell
            for j, value in header.items()
            if j < len(row) and (cell := number(row[j])) is not None
        }
        if not label or not values or label == "merkez":
            continue
        area = province_id(NAME_ALIASES.get(label, str(row[0])))
        if area in out:
            raise ValueError(f"Muhasebat {path.name}: {area} iki satır")
        out[area] = values
    return out


def year_files(folder: Path, pattern: str) -> dict[int, Path]:
    """{year: file}: the one file a year whose name matches; the year is the folder's name and
    the year to date is left out."""
    out: dict[int, Path] = {}
    for path in sorted(folder.glob("*/*.xls*")):
        if not re.search(pattern, fold(path.name)):
            continue
        year = int(path.parent.name)
        if year > LAST_YEAR:
            continue
        if year in out:
            raise ValueError(f"Muhasebat {folder.name} {year}: iki dosya {path.name}")
        out[year] = path
    return out


def load_revenue(folder: Path, pattern: str) -> list[dict]:
    """Budget revenue by province and line. Checks that the sub-budgets add up to the total
    (local government prints none) and the economic lines to the general budget; a
    province-year that breaks either is left out."""
    rows = []
    for year, path in sorted(year_files(folder, pattern).items()):
        found = by_province(path, REVENUE_COLUMNS)
        if len(found) != 81:
            raise ValueError(f"Muhasebat {path.name}: {len(found)} il")
        for area, values in found.items():
            total = values.get("total")
            parts = sum(values.get(line, 0.0) for line in REVENUE_PARTS)
            budgets = sum(values.get(line, 0.0) for line in REVENUE_BUDGETS)
            whole = values.get("general_budget", total)
            if total is None:
                PROBLEMS.append(f"{path.name} {area}: toplam yok")
                continue
            if budgets and abs(budgets - total) > max(1.0, abs(total) * 1e-4):
                PROBLEMS.append(
                    f"{path.name} {area}: bütçeler {budgets:,.0f}, toplam {total:,.0f}"
                )
                continue
            if abs(parts - whole) > max(1.0, abs(whole) * 1e-4):
                PROBLEMS.append(
                    f"{path.name} {area}: kalemler {parts:,.0f}, bütçe {whole:,.0f}"
                )
                continue
            for line, value in values.items():
                rows.append(
                    {
                        "area_id": area,
                        "period_start": dt.date(year, 1, 1),
                        "dims": f"budget_revenue_item={line}",
                        "value": value,
                    }
                )
    return rows


def load_expenditure(folder: Path, pattern: str) -> list[dict]:
    """Budget expenditure by province, by economic and (central only) functional line. Each
    classification has to add up to the printed total; a province-year that does not is left
    out."""
    rows = []
    for year, path in sorted(year_files(folder, pattern).items()):
        found = by_province(path, EXPENDITURE_COLUMNS)
        if len(found) != 81:
            raise ValueError(f"Muhasebat {path.name}: {len(found)} il")
        for area, values in found.items():
            total = values.get(("total", "economic"))
            sums = {
                kind: sum(
                    v
                    for (line, k), v in values.items()
                    if k == kind and line != "total"
                )
                for kind in ("economic", "functional")
            }
            if total is None:
                PROBLEMS.append(f"{path.name} {area}: toplam yok")
                continue
            bad = [
                f"{kind} {s:,.0f}"
                for kind, s in sums.items()
                if s and abs(s - total) > max(1.0, abs(total) * 1e-4)
            ]
            if bad:
                PROBLEMS.append(
                    f"{path.name} {area}: toplam {total:,.0f}, " + ", ".join(bad)
                )
                continue
            for (line, kind), value in values.items():
                rows.append(
                    {
                        "area_id": area,
                        "period_start": dt.date(year, 1, 1),
                        "dims": f"budget_classification={kind};budget_expenditure_item={line}",
                        "value": value,
                    }
                )
    return rows


class ProvinceBudget:
    """Shared frame for the four province budget tables."""

    source_id = "muhasebat"
    indicator_id: str
    folder: Path
    pattern: str

    def fetch(self) -> Path:
        return self.folder

    def rows(self) -> list[dict]:
        raise NotImplementedError

    def parse(self, raw: Path) -> pl.DataFrame:
        PROBLEMS.clear()
        rows = self.rows()
        if len(PROBLEMS) > MAX_PROBLEMS:
            raise ValueError(
                f"Muhasebat: {len(PROBLEMS)} tutarsız il-yıl: {PROBLEMS[:5]}"
            )
        return pl.DataFrame(rows, schema_overrides={"value": pl.Float64}).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("thousand_try").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


class CentralRevenue(ProvinceBudget):
    indicator_id = "central_budget_revenue_by_province"
    folder = CENTRAL_FOLDER
    pattern = r"butcegelirleri"

    def rows(self) -> list[dict]:
        return load_revenue(self.folder, self.pattern)


class CentralExpenditure(ProvinceBudget):
    indicator_id = "central_budget_expenditure_by_province"
    folder = CENTRAL_FOLDER
    pattern = r"butcegiderleri"

    def rows(self) -> list[dict]:
        return load_expenditure(self.folder, self.pattern)


class LocalRevenue(ProvinceBudget):
    indicator_id = "local_budget_revenue_by_province"
    folder = LOCAL_FOLDER
    pattern = r"butcegelirleri"

    def rows(self) -> list[dict]:
        return load_revenue(self.folder, self.pattern)


class LocalExpenditure(ProvinceBudget):
    indicator_id = "local_budget_expenditure_by_province"
    folder = LOCAL_FOLDER
    pattern = r"butcegiderleri"

    def rows(self) -> list[dict]:
        return load_expenditure(self.folder, self.pattern)


MUHASEBAT_ADAPTERS.update(
    {
        "central_budget_revenue_by_province": CentralRevenue,
        "central_budget_expenditure_by_province": CentralExpenditure,
        "local_budget_revenue_by_province": LocalRevenue,
        "local_budget_expenditure_by_province": LocalExpenditure,
    }
)
