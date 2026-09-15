"""EPDK earlier years: the province tables inside the yearly Word reports (2014-2024).

`scripts/extract_epdk_docx_tables.py` flattens every table of the Word reports into
`raw/epdk/docx_cells.parquet` with the caption above it. The English editions carry the same
tables with no Turkish caption, so selecting by Turkish caption reads each year once.

The indicators are the ones `epdk.py` fills from the 2025 Excel annexes; these adapters add the
earlier years to them. Where a year is in both (electricity 2024), the two must agree cell by
cell. Every table is checked against its own printed totals.

Breaks in definition:

* electricity consumer types before 2022 are the old tariff groups — "Ticarethane" (commerce
  and public services together) and "Tarımsal Sulama" (irrigation) — stored under the same
  codes as the new groups; the step in 2022 is the reform, not consumption;
* the report year is read from the report's own captions ("2019 Yılı Sonu"), because a table
  caption can carry the wrong year (the 2024 report titles its consumer table "2023").
"""

from __future__ import annotations

import re
from collections import Counter
from functools import cache
from pathlib import Path

import polars as pl

from ..config import RAW
from .epdk import (
    CONSUMER_TYPES,
    FILES,
    PETROL_PRODUCTS,
    Epdk,
    EpdkElectricityConsumers,
    EpdkElectricityConsumption,
    EpdkFuelSales,
    EpdkGasSales,
    EpdkGasSubscribers,
    EpdkLpgSales,
    TotalMismatch,
    close,
    fact,
    row,
)
from .kgm import fold, province_id

DOCX_CELLS = RAW / "epdk" / "docx_cells.parquet"

#: (indicator, cells revised, largest relative revision) — filled while parsing.
REVISIONS: list[tuple[str, int, float]] = []

OLD_CONSUMER_TYPES = {
    "tarimsalsulama": "agricultural",
    "ticarethane": "commercial_public",
    **CONSUMER_TYPES,
}
GAS_SUPPLY = {
    "borugazi": "pipeline",
    "lng": "lng",
    "cng": "cng",
    "cngdiger": "cng",
    "otocng": "auto_cng",
    "cngotogaz": "auto_cng",
    "otolng": "auto_lng",
}


def number_tr(text: str | None) -> float | None:
    text = (text or "").strip().replace("%", "")
    if not text or text in ("-", "–"):
        return None
    return float(text.replace(".", "").replace(",", "."))


@cache
def docx_tables() -> dict[tuple[str, int], tuple[str, list[list[str]]]]:
    cells = pl.read_parquet(DOCX_CELLS)
    out: dict[tuple[str, int], tuple[str, list[list[str]]]] = {}
    for (file, table), group in cells.group_by(["file", "table"]):
        rows: dict[int, dict[int, str]] = {}
        for r, c, t in group.select("row", "col", "text").iter_rows():
            rows.setdefault(r, {})[c] = t
        grid = [
            [rows[r].get(c, "") for c in range(max(rows[r]) + 1)] for r in sorted(rows)
        ]
        out[(file, table)] = (group["caption"][0], grid)
    return out


@cache
def report_year(file: str) -> int:
    years: Counter = Counter()
    for (f, _), (caption, _) in docx_tables().items():
        if f == file:
            for y in re.findall(r"(20\d\d)\s*[Yy]ılı", caption):
                years[int(y)] += 1
    if not years:
        raise ValueError(f"{file}: rapor yılı bulunamadı")
    return years.most_common(1)[0][0]


def find(caption_part: str, market: str) -> list[tuple[str, int, list[list[str]]]]:
    found = []
    for (file, _table), (caption, grid) in docx_tables().items():
        if caption_part in caption and (FILES / market / file).exists():
            found.append((file, report_year(file), grid))
    years = [y for _, y, _ in found]
    if len(years) != len(set(years)):
        raise ValueError(f"{caption_part}: aynı yıl iki raporda {sorted(years)}")
    return found


def province_or_none(name: str) -> str | None:
    try:
        return province_id(name)
    except KeyError:
        return None


def near(a: float, b: float, what: str, rounding: float) -> None:
    """`close`, allowing for tables printed rounded (million Sm3 to three decimals, tonnes)."""
    if abs(a - b) > max(1.0, abs(b) * 1e-6, rounding):
        raise TotalMismatch(f"{what}: parçalar {a:,.3f}, basılı toplam {b:,.3f}")


def wide_table(
    grid, kinds: dict[str, str], what: str, rounding: float = 0.0
) -> dict[str, dict[str, float]]:
    """Province rows × kind columns, checked against row totals and the grand total row.

    Rows that are neither provinces nor totals (gas used inside the grid, a header repeated
    after a page break) count toward the national check but are not returned. İstanbul is
    printed as two rows, Avrupa and Anadolu, in 2017-2021 (and as those two plus TÜMÜ in the
    PDF): the two sides are added, and a TÜMÜ row, when there is one, replaces them. Taking
    the rows one by one kept only the second side and lost half of İstanbul.
    """
    header = [fold(h) for h in grid[0]]
    cols = {kinds[h]: i for i, h in enumerate(header) if h in kinds}
    total_col = next(
        (i for i, h in enumerate(header) if h.startswith(("geneltoplam", "toplam"))),
        None,
    )
    out: dict[str, dict[str, float]] = {}
    whole: set[str] = set()
    other = 0.0
    grand = None
    for line in grid[1:]:
        name = fold(line[0]) if line else ""
        if name in ("geneltoplam", "toplam"):
            grand = line
            continue
        if not name or name in ("iladi", "il", "iller"):
            continue
        values = {
            k: number_tr(line[i]) or 0.0 for k, i in cols.items() if i < len(line)
        }
        total = (
            number_tr(line[total_col])
            if total_col is not None and total_col < len(line)
            else None
        )
        if total is not None:
            near(sum(values.values()), total, f"{what} {line[0]}", rounding)
        pid = province_or_none(line[0])
        if pid is None:
            other += total if total is not None else sum(values.values())
            continue
        if "tumu" in name:
            out[pid] = values
            whole.add(pid)
        elif pid in out and pid not in whole:
            out[pid] = {k: out[pid].get(k, 0.0) + v for k, v in values.items()}
        elif pid not in whole:
            out[pid] = values
    if len(out) != 81:
        raise ValueError(f"{what}: {len(out)} il")
    if grand is not None and total_col is not None:
        national = sum(sum(v.values()) for v in out.values()) + other
        near(national, number_tr(grand[total_col]), f"{what} Türkiye", rounding * 81)
    return out


def long_table(grid, kinds: dict[str, str], what: str) -> dict[str, dict[str, float]]:
    """İl Adı | Tüketici Türü | Miktar, the province carried down, İl Toplam checked."""
    out: dict[str, dict[str, float]] = {}
    province = None
    national = 0.0
    for line in grid[1:]:
        label = fold(line[1]) if len(line) > 1 else ""
        if label == "geneltoplam":
            close(national, number_tr(line[2]), f"{what} Türkiye")
            continue
        if line[0].strip():
            province = province_id(line[0])
        if label == "iltoplam":
            close(sum(out[province].values()), number_tr(line[2]), f"{what} {province}")
            national += number_tr(line[2])
        elif label in kinds and province:
            out.setdefault(province, {})[kinds[label]] = number_tr(line[2]) or 0.0
    if len(out) != 81:
        raise ValueError(f"{what}: {len(out)} il")
    return out


def records(tables: dict[int, dict[str, dict[str, float]]], dim: str) -> list[dict]:
    return [
        row(pid, year, f"{dim}={kind}", value)
        for year, table in tables.items()
        for pid, kinds in table.items()
        for kind, value in kinds.items()
    ]


def merge_years(current: pl.DataFrame, history: list[dict], what: str) -> pl.DataFrame:
    """Earlier years next to the Excel annex; a year in both must agree cell by cell."""
    older = fact(history, current["indicator_id"][0], current["unit"][0], "2026-06")
    overlap = current.join(
        older, on=["area_id", "period_start", "dims"], suffix="_docx"
    )
    # Companies may correct what they reported (EPDK's own note), so the later publication
    # can revise a year. The newer figure is kept and the revision reported; a revision
    # larger than 5 % of the cell is not a correction but a misread, and stops the load.
    off = overlap.filter(
        (pl.col("value") - pl.col("value_docx")).abs() > 1
    ).with_columns(
        (
            (pl.col("value") - pl.col("value_docx")).abs()
            / pl.col("value_docx").abs().clip(1)
        ).alias("rel")
    )
    if off.height:
        REVISIONS.append((what, off.height, float(off["rel"].max())))
        # Looked at one by one and accepted as a revision: Mardin agricultural electricity
        # 2024, 222.0 GWh in the 2024 report and 253.7 GWh in the 2025 annex (+14 %).
        off = off.filter(
            ~(
                (pl.col("area_id") == "TR-47")
                & (pl.col("dims") == "consumer=agricultural")
                & (pl.col("period_start").dt.year() == 2024)
            )
        )
        if off.height and off["rel"].max() > 0.05:
            raise TotalMismatch(
                f"{what}: Excel ile Word %5'ten fazla farklı: {off.sort('rel').row(-1)}"
            )
    older = older.join(
        current.select("period_start").unique(), on="period_start", how="anti"
    )
    return pl.concat([current, older.select(current.columns)])


class ElectricityConsumptionHistory(EpdkElectricityConsumption):
    def parse(self, raw: Path) -> pl.DataFrame:
        tables = {}
        for _, year, grid in find(
            "Faturalanan Tüketimin İllere ve Tüketici Türüne", "elektrik_yillik"
        ):
            if fold(grid[0][1]) == "tuketicituru":
                tables[year] = long_table(grid, OLD_CONSUMER_TYPES, f"elektrik {year}")
            else:
                # Whole MWh per cell in the wide layout: the row total can differ by a few.
                tables[year] = wide_table(
                    grid, OLD_CONSUMER_TYPES, f"elektrik {year}", rounding=5.0
                )
        return merge_years(
            super().parse(raw), records(tables, "consumer"), "elektrik tüketimi"
        )


class ElectricityConsumersHistory(EpdkElectricityConsumers):
    def parse(self, raw: Path) -> pl.DataFrame:
        tables = {
            year: long_table(grid, OLD_CONSUMER_TYPES, f"elektrik abone {year}")
            for _, year, grid in find(
                "Tüketici Sayısının İl ve Tüketici Türü", "elektrik_yillik"
            )
        }
        return merge_years(
            super().parse(raw), records(tables, "consumer"), "elektrik abone"
        )


class GasConsumption(Epdk):
    """Tablo 8.3: consumption by province and supply form (million Sm3 → m3), 2017-2024."""

    indicator_id = "epdk_natural_gas_consumption"

    def parse(self, raw: Path) -> pl.DataFrame:
        tables = {}
        for _, year, grid in find(
            "İl Bazında Tüketim Miktarları(Milyon Sm3)", "dogalgaz_yillik"
        ):
            # Million Sm3 to three decimals: each printed cell is off by up to 0.0005.
            table = wide_table(
                grid, GAS_SUPPLY, f"doğalgaz tüketim {year}", rounding=0.005
            )
            tables[year] = {
                p: {k: v * 1e6 for k, v in d.items()} for p, d in table.items()
            }
        return fact(records(tables, "gas_supply"), self.indicator_id, "m3", "2026-05")


class GasSubscribersHistory(EpdkGasSubscribers):
    def parse(self, raw: Path) -> pl.DataFrame:
        history = []
        for _, year, grid in find(
            "İl ve Dağıtım Şirketi bazında Abone", "dogalgaz_yillik"
        ):
            provinces: dict[str, list[float]] = {}
            companies: dict[str, list[float]] = {}
            current = None
            grand = None
            for line in grid[1:]:
                name = line[0].strip()
                if not name or fold(name) in ("ilsirket", "iladi"):
                    continue
                if fold(name) == "geneltoplam":
                    grand = number_tr(line[1])
                    continue
                values = [number_tr(line[1]) or 0.0, number_tr(line[2]) or 0.0]
                pid = province_or_none(name)
                if pid:
                    current = pid
                    provinces[pid] = values
                    companies[pid] = [0.0, 0.0]
                elif current:
                    companies[current][0] += values[0]
                    companies[current][1] += values[1]
            # Provinces reached by the gas network grew year by year (77 in 2017); the ones
            # missing are the ones without a distribution licence, checked by the national total.
            if len(provinces) < 70:
                raise ValueError(f"doğalgaz abone {year}: {len(provinces)} il")
            if grand is not None:
                close(
                    sum(v[0] for v in provinces.values()),
                    grand,
                    f"doğalgaz abone {year} Türkiye",
                )
            for pid, (subs, eligible) in provinces.items():
                close(companies[pid][0], subs, f"doğalgaz abone {year} {pid}")
                history += [
                    row(pid, year, "gas_customer=subscriber", subs),
                    row(pid, year, "gas_customer=eligible_consumer", eligible),
                ]
        return merge_years(super().parse(raw), history, "doğalgaz abone")


class FuelSalesHistory(EpdkFuelSales):
    def parse(self, raw: Path) -> pl.DataFrame:
        tables = {}
        for pattern in (
            "İllere Göre Yurt İçi Satış Miktarları",
            "İllere Göre Yurt İçi Satışları",
        ):
            for _, year, grid in find(pattern, "petrol_yillik"):
                tables[year] = wide_table(grid, PETROL_PRODUCTS, f"akaryakıt {year}")
        return merge_years(
            super().parse(raw), records(tables, "fuel_product"), "akaryakıt"
        )


class LpgSalesHistory(EpdkLpgSales):
    def parse(self, raw: Path) -> pl.DataFrame:
        tables = {}
        for _, year, grid in find(
            "LPG Satışlarının İllere ve Ürün Türlerine", "lpg_yillik"
        ):
            out = {}
            national = 0.0
            for line in grid[2:]:
                if fold(line[0]) == "toplam":
                    # Whole tonnes per province, rounded again in the total.
                    near(national, number_tr(line[7]), f"LPG {year} Türkiye", 81.0)
                    continue
                pid = province_or_none(line[0])
                if not pid:
                    continue
                values = {
                    "cylinder": number_tr(line[1]) or 0.0,
                    "bulk": number_tr(line[3]) or 0.0,
                    "autogas": number_tr(line[5]) or 0.0,
                }
                near(sum(values.values()), number_tr(line[7]), f"LPG {year} {pid}", 2.0)
                national += number_tr(line[7])
                out[pid] = values
            if len(out) != 81:
                raise ValueError(f"LPG {year}: {len(out)} il")
            tables[year] = out
        return merge_years(super().parse(raw), records(tables, "lpg_product"), "LPG")


EPDK_HISTORY_ADAPTERS = {
    "epdk_electricity_consumption": ElectricityConsumptionHistory,
    "epdk_electricity_consumers": ElectricityConsumersHistory,
    "epdk_natural_gas_consumption": GasConsumption,
    "epdk_natural_gas_subscribers": GasSubscribersHistory,
    "epdk_fuel_sales": FuelSalesHistory,
    "epdk_lpg_sales": LpgSalesHistory,
}


#: The 2006-2015 LPG reports as PDF: file -> (report year, pages of the province × product
#: table). The year is not in a machine-readable place: it was read from each cover ("2008
#: Yılı Sektör Raporu", "TÜRKİYE LPG PİYASASI BÜYÜKLÜKLERİ (2009)") and, for the three reports
#: whose covers cite several years (2011-2013), from their licence tables and the world data
#: they quote; autogas then rises every year 2009-2016, which the order would break if two
#: were swapped.
LPG_PDFS = {
    "mCrcaNTln84_": (2006, (30, 31)),
    "DYGIdjqtHqk_": (2007, (25, 26)),
    "dd6mSfa0pZQ_": (2008, (22, 23)),
    "OUHfpoxVFx8_": (2009, (21, 22)),
    "Z35HY3UyDx8_": (2010, (21, 22)),
    "eEB0nJQ2OZc_": (2011, (20, 21)),
    "icsaPKY6fJU_": (2012, (32, 33)),
    "qV0pokY56Gg_": (2013, (36, 37)),
    "b5KW7ZIgO9g_": (2014, (36, 37)),
    "ClrL1VI5wIY_": (2015, (34, 35)),
}


def lpg_pdf_table(
    path: Path, pages: tuple[int, int], year: int
) -> dict[str, dict[str, float]]:
    """Rows "İl  tüplü pay  dökme pay  otogaz pay  toplam [pay]", totals checked."""
    import pdfplumber

    with pdfplumber.open(path) as document:
        lines = [
            line
            for p in pages
            for line in (document.pages[p].extract_text() or "").splitlines()
        ]
    out: dict[str, dict[str, float]] = {}
    national = None
    pending = ""
    held: list[str] = []
    for line in lines:
        # 2009-2010 fonts print İ as Đ; a long name (KAHRAMANMARAŞ, 2013) can sit alone on
        # the line above its numbers.
        words = line.replace("Đ", "İ").split()
        start = next((i for i, w in enumerate(words) if re.match(r"^[%\d]", w)), None)
        if start is None:
            if held and province_or_none(pending + "".join(words)):
                words = (pending + "".join(words)).split() + held
                start = 1
                held = []
            else:
                pending = " ".join(words)
                continue
        if start == 0:
            if not province_or_none(pending):
                # "KAHRAMANMAR" above the numbers and "AŞ" below (2013): the numbers wait
                # for the rest of the name on the next line.
                held = words
                continue
            words = pending.split() + words
            start = len(pending.split())
        pending = ""
        name = " ".join(words[:start])
        if fold(name) in ("toplam", "geneltoplam", "turkiye"):
            numbers = [number_tr(w) for w in words[start:] if "%" not in w]
            national = [v for v in numbers if v not in (100.0,)]
            continue
        pid = province_or_none(name)
        if not pid:
            continue
        # Shares follow each quantity; with the % sign gone they are the small numbers
        # in alternate positions.
        quantities = [number_tr(w) for w in words[start:][0::2]]
        if len(quantities) < 4:
            raise ValueError(f"LPG {year} {name}: {line}")
        cylinder, bulk, autogas, total = quantities[:4]
        near(cylinder + bulk + autogas, total, f"LPG {year} {pid}", 3.0)
        out[pid] = {"cylinder": cylinder, "bulk": bulk, "autogas": autogas}
    if len(out) != 81:
        raise ValueError(f"LPG {year}: {len(out)} il")
    if national:
        near(
            sum(sum(v.values()) for v in out.values()),
            national[-1] if len(national) < 4 else national[3],
            f"LPG {year} Türkiye",
            81 * 3.0,
        )
    return out


class LpgSalesLong(LpgSalesHistory):
    def parse(self, raw: Path) -> pl.DataFrame:
        recent = super().parse(raw)
        tables = {
            year: lpg_pdf_table(FILES / "lpg_yillik" / f"{name}.pdf", pages, year)
            for name, (year, pages) in LPG_PDFS.items()
        }
        return merge_years(recent, records(tables, "lpg_product"), "LPG 2006-2015")


EPDK_HISTORY_ADAPTERS["epdk_lpg_sales"] = LpgSalesLong


GAS_SECTOR_COLUMNS = {
    "donusumcevrimsektoru": "conversion",
    "enerjisektoru": "energy",
    "ulasimsektoru": "transport",
    "sanayisektoru": "industry",
    "hizmetsektoru": "services",
    "konutlar": "residential",
    "diger": "other",
}


GAS_SECTOR_NATIONAL_MISSES: list[tuple[str, str, float, float]] = []


def gas_sector_tables(file: str) -> dict[str, dict[str, float]]:
    """Section 10 of a Word gas report: one table per province, company rows × sector.

    Read in document order, because a province block can run over two Word tables (a page
    break) with the second one carrying no header: rows belong to the last province named
    until its TOPLAM row. The block's company rows must add up to TOPLAM in every sector; the
    provinces plus DİĞER (gas used in the grid, no province) must add up to TÜRKİYE.
    """
    tables = sorted(
        (tb, grid) for (f, tb), (_, grid) in docx_tables().items() if f == file
    )
    out: dict[str, dict[str, float]] = {}
    national: dict[str, float] = {}
    other: dict[str, float] = {}
    header: list[str | None] | None = None
    current: str | None = None
    sums: dict[str, float] = {}
    for _tb, grid in tables:
        for line in grid:
            if len(line) > 1 and fold(line[1]) == "lisanstipi":
                header = [GAS_SECTOR_COLUMNS.get(fold(c)) for c in line]
                name = fold(line[0].rstrip("*"))
                if not name:  # header repeated after a page break, province unchanged
                    continue
                current = (
                    "TR"
                    if name == "turkiye"
                    else "other"
                    if name == "diger"
                    else province_id(line[0])
                )
                sums = {}
                continue
            if header is None or current is None:
                continue
            # Cells are aligned from the right: a row whose company name spans the licence
            # column (or is missing) has one cell fewer or more on the left.
            # The last len(header) - 2 cells are the sector values and the grand total.
            width = len(header) - 2
            if len(line) < width + 1:
                if any(re.search(r"\d", c) for c in line):
                    raise ValueError(f"doğalgaz sektör {file}: kısa satır {line}")
                continue
            cells = line[-width:]
            try:
                values = {
                    sec: number_tr(cell) or 0.0
                    for sec, cell in zip(header[2:], cells, strict=True)
                    if sec
                }
            except ValueError:
                # A label-only row ("DİĞER" under its own header) carries no numbers.
                if any(re.search(r"\d", c) for c in cells):
                    raise ValueError(f"doğalgaz sektör {file}: {line}") from None
                continue
            if any(fold(c) == "toplam" for c in line[:2]):
                for sector, value in values.items():
                    if current != "TR":
                        near(
                            sums.get(sector, 0.0),
                            value,
                            f"doğalgaz sektör {file} {current} {sector}",
                            1.0,
                        )
                if current == "TR":
                    # Some reports leave DİĞER out of the TÜRKİYE total, and the 2023 report
                    # prints a transport total its own company rows do not add up to; the
                    # province blocks are checked above, so a national miss is reported, not
                    # fatal.
                    for sector, value in values.items():
                        parts = national.get(sector, 0.0)
                        if (
                            abs(parts - value) > 81
                            and abs(parts - other.get(sector, 0.0) - value) > 81
                        ):
                            GAS_SECTOR_NATIONAL_MISSES.append(
                                (file, sector, parts, value)
                            )
                else:
                    for sector, value in values.items():
                        national[sector] = national.get(sector, 0.0) + value
                    if current == "other":
                        other = values
                    else:
                        out[current] = values
                current = None
                continue
            for sector, value in values.items():
                sums[sector] = sums.get(sector, 0.0) + value
    if len(out) < 75:
        raise ValueError(f"doğalgaz sektör {file}: {len(out)} il")
    return out


class GasSalesHistory(EpdkGasSales):
    def parse(self, raw: Path) -> pl.DataFrame:
        files = {
            f
            for (f, _), (_, grid) in docx_tables().items()
            if (FILES / "dogalgaz_yillik" / f).exists()
            and grid
            and len(grid[0]) > 1
            and fold(grid[0][1]) == "lisanstipi"
        }
        tables = {}
        for f in files:
            year = report_year(f)
            if year in tables:
                raise ValueError(f"doğalgaz sektör {year}: iki rapor")
            tables[year] = gas_sector_tables(f)
        return merge_years(
            super().parse(raw), records(tables, "gas_sector"), "doğalgaz sektör"
        )


EPDK_HISTORY_ADAPTERS["epdk_natural_gas_sales"] = GasSalesHistory
