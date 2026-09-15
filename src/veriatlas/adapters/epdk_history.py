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
ELECTRICITY_2016 = ("ZeM0_S9N9E8_.docx", 14)
ENGLISH_CONSUMER_TYPES = {
    "lighting": "lighting",
    "household": "residential",
    "industry": "industrial",
    "agriculturalirrigation": "agricultural",
    "commerce": "commercial_public",
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
    grid,
    kinds: dict[str, str],
    what: str,
    rounding: float = 0.0,
    provinces: int = 81,
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
    if len(out) != provinces:
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
        # 2016: the Turkish Word report has no province table; the English edition does
        # (table 14, MWh, kinds in the header's second row).
        _, grid = docx_tables()[(ELECTRICITY_2016[0], ELECTRICITY_2016[1])]
        if fold(grid[0][0]) != "province" or len(grid) not in (84, 85):
            raise ValueError("elektrik 2016: İngilizce tablo beklenen biçimde değil")
        header = ["il", *grid[1][1:-1], "Grand Total"]
        rows = [
            [
                {
                    "grandtotal": "toplam",
                    "istasya": "İSTANBUL",
                    "istavrupa": "İSTANBUL",
                }.get(fold(r[0]), r[0]),
                *r[1:],
            ]
            for r in grid[2:]
        ]
        tables[2016] = wide_table(
            [header, *rows], ENGLISH_CONSUMER_TYPES, "elektrik 2016", rounding=5.0
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
        for year, (file, first, count) in GAS_CONSUMPTION_PDFS.items():
            grid = pdf_grid(
                FILES / "dogalgaz_yillik" / f"{file}.pdf", first, "Tablo 8.4"
            )
            table = wide_table(
                grid, GAS_SUPPLY, f"doğalgaz tüketim {year}", 0.02, provinces=count
            )
            tables[year] = {
                p: {k: v * 1e6 for k, v in d.items()} for p, d in table.items()
            }
        return fact(records(tables, "gas_supply"), self.indicator_id, "m3", "2026-05")


#: Year -> (PDF, page of Tablo 8.3 / 8.2). 2014 prints the province total only.
#: Year -> (PDF, page, provinces listed). Tunceli has no row in 2015 (no gas used there).
GAS_CONSUMPTION_PDFS = {2015: ("Jo_r3O_Xi5s_", 65, 80), 2016: ("zd_qHXQpFYw_", 76, 81)}
NUMBER = re.compile(r"\d{1,3}(\.\d{3})*,\d+")


def pdf_grid(path: Path, first: int, stop: str) -> list[list[str]]:
    """A province table rebuilt from word positions, as rows of cell strings.

    Plain text loses empty cells. Here the header words are merged into columns (words on
    one line less than 8 pt apart, or stacked over each other, belong to one header), and
    every number goes to the column whose header centre is nearest. A row is the words
    sharing a baseline; rows whose label does not start at the table's left edge (a chart
    drawn over the page, its axis labels) are dropped. `wide_table` then checks each row
    against its printed total, so a number put in the wrong column cannot pass.
    """
    import pdfplumber

    rows: list[list[str]] = []
    header: list[str] | None = None
    centres: list[float] = []
    with pdfplumber.open(path) as document:
        for raw_page in document.pages[first : first + 4]:
            # The 2015 report carries the table twice, a second text layer in another
            # font drawn offset over the first, and the two interleave letter by letter
            # ("BATMBAİNNGÖ L"). Keep only the font size the table body is set in.
            sizes = Counter(
                round(c["size"]) for c in raw_page.chars if c["text"].isdigit()
            )
            body = sizes.most_common(1)[0][0] if sizes else None
            page = raw_page.filter(
                lambda o, body=body: (
                    o.get("object_type") != "char" or round(o["size"]) == body
                )
            )
            words = page.extract_words()
            if rows and stop in (page.extract_text() or ""):
                cut = min(w["top"] for w in words if w["text"] == stop.split()[0])
                words = [w for w in words if w["top"] < cut]
            # The 2015 report draws the table twice, once with the header garbled into
            # the title; the copy to read is the ADANA with a clean "Boru" header above.
            anchor = next(
                (
                    w
                    for w in words
                    if w["text"] == "ADANA"
                    and any(
                        fold(o["text"]) == "boru" and 3 < w["top"] - o["top"] < 30
                        for o in words
                    )
                ),
                None,
            )
            if header is None:
                if anchor is None:
                    continue
                band = [
                    w
                    for w in words
                    if anchor["top"] - 30 < w["top"] < anchor["top"] - 3
                    and not NUMBER.fullmatch(w["text"])
                    and w["x0"] > 150
                ]
                groups: list[list[dict]] = []
                for w in sorted(band, key=lambda w: w["x0"]):
                    for g in groups:
                        if any(
                            (abs(w["top"] - o["top"]) < 3 and w["x0"] - o["x1"] < 8)
                            or (w["x0"] < o["x1"] and o["x0"] < w["x1"])
                            for o in g
                        ):
                            g.append(w)
                            break
                    else:
                        groups.append([w])
                groups.sort(key=lambda g: min(w["x0"] for w in g))
                header = ["İl"] + [
                    " ".join(
                        w["text"]
                        for w in sorted(g, key=lambda w: (round(w["top"]), w["x0"]))
                    )
                    for g in groups
                ]
                centres = [
                    (min(w["x0"] for w in g) + max(w["x1"] for w in g)) / 2
                    for g in groups
                ]
                left = anchor["x0"]
            # A continuation page can sit the table elsewhere: its left edge is where its
            # first province name starts, and the columns shift with it.
            first_name = next((w for w in words if province_or_none(w["text"])), None)
            if first_name is None:
                continue
            shift = first_name["x0"] - left
            left = first_name["x0"]
            centres = [c + shift for c in centres]
            lines: dict[float, list[dict]] = {}
            for w in sorted(words, key=lambda w: w["top"]):
                key = next((k for k in lines if abs(k - w["top"]) < 2), w["top"])
                lines.setdefault(key, []).append(w)
            for key in sorted(lines):
                ws = sorted(lines[key], key=lambda w: w["x0"])
                if abs(ws[0]["x0"] - left) > 4 or NUMBER.fullmatch(ws[0]["text"]):
                    continue
                label = " ".join(
                    w["text"] for w in ws if not NUMBER.fullmatch(w["text"])
                )
                cells = [""] * len(centres)
                for w in ws:
                    if NUMBER.fullmatch(w["text"]):
                        centre = (w["x0"] + w["x1"]) / 2
                        i = min(
                            range(len(centres)), key=lambda i: abs(centres[i] - centre)
                        )
                        if cells[i]:
                            raise ValueError(
                                f"{path.name}: {label} iki sayı bir sütunda"
                            )
                        cells[i] = w["text"]
                if any(cells):
                    rows.append([label, *cells])
            if rows and stop in (page.extract_text() or ""):
                break
    if header is None:
        raise ValueError(f"{path.name}: tablo bulunamadı")
    return [header, *rows]


#: Year -> (PDF, first page of Tablo 7.3). 2014 prints residential subscribers only.
GAS_SUBSCRIBER_PDFS = {2015: ("Jo_r3O_Xi5s_", 47), 2016: ("zd_qHXQpFYw_", 57)}


def gas_subscriber_pdf(file: str, first: int, year: int) -> dict[str, list[float]]:
    """Tablo 7.3 of the 2015-2016 PDF reports, read by word position.

    Plain text drops empty cells, so a province with no free consumers prints one number
    and nothing says which column it belongs to. Each number is instead placed under the
    header "Sayısı" nearest to its centre. Province rows are told from company rows by
    their name resolving to a province; company rows are summed per province and must equal
    it, and the provinces must add up to the printed Genel Toplam.
    """
    import pdfplumber

    provinces: dict[str, list[float]] = {}
    companies: dict[str, list[float]] = {}
    grand = None
    current = None
    with pdfplumber.open(FILES / "dogalgaz_yillik" / f"{file}.pdf") as document:
        for page in document.pages[first : first + 10]:
            words = page.extract_words()
            heads = [w for w in words if re.fullmatch(r"Sayısı\*?", w["text"])]
            if heads:
                # Only the header row: a chart further down repeats the word.
                heads = [h for h in heads if h["top"] < heads[0]["top"] + 3]
                centres = sorted((h["x0"] + h["x1"]) / 2 for h in heads)
                subs_x, eligible_x = centres[0], centres[-1]
                start = heads[0]["top"] + 5
            elif provinces:
                start = (
                    60  # continuation page: header not repeated, running title above
                )
            else:
                continue
            # The next table (7.4) starts on the page after the last province.
            if grand is not None or (provinces and "Tablo 7.4" in page.extract_text()):
                break
            lines: dict[int, list[dict]] = {}
            for w in words:
                # Below the table the page number sits under the free-consumer column.
                if start < w["top"] < page.height - 45:
                    lines.setdefault(round(w["top"] / 3), []).append(w)
            for key in sorted(lines):
                ws = sorted(lines[key], key=lambda w: w["x0"])
                label = " ".join(
                    w["text"] for w in ws if not re.fullmatch(r"[\d.]+", w["text"])
                )
                nums = [w for w in ws if re.fullmatch(r"\d{1,3}(\.\d{3})*", w["text"])]
                if not nums:
                    continue
                values = [0.0, 0.0]
                for w in nums:
                    centre = (w["x0"] + w["x1"]) / 2
                    if abs(centre - subs_x) < 20:
                        values[0] = number_tr(w["text"])
                    elif abs(centre - eligible_x) < 20:
                        values[1] = number_tr(w["text"])
                if fold(label) in ("geneltoplam", "toplam"):
                    grand = values
                    break
                pid = province_or_none(label)
                if pid and pid in provinces:
                    raise ValueError(f"doğalgaz abone PDF {year}: {label} iki kez")
                if pid:
                    current = pid
                    provinces[pid] = values
                    companies[pid] = [0.0, 0.0]
                elif current:
                    companies[current][0] += values[0]
                    companies[current][1] += values[1]
    if len(provinces) < 65:
        raise ValueError(f"doğalgaz abone PDF {year}: {len(provinces)} il")
    for pid, values in provinces.items():
        close(companies[pid][0], values[0], f"doğalgaz abone {year} {pid}")
        close(companies[pid][1], values[1], f"doğalgaz serbest {year} {pid}")
    # 2016 prints no Genel Toplam; its provinces rest on the company rows alone.
    if grand is not None:
        close(
            sum(v[0] for v in provinces.values()), grand[0], f"doğalgaz abone {year} TR"
        )
        close(
            sum(v[1] for v in provinces.values()),
            grand[1],
            f"doğalgaz serbest {year} TR",
        )
    return provinces


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
            # 2017-2019 add a "Konut Abone" column between the two: the free consumers
            # are the column so headed, not the third cell. Read as the third cell, the
            # residential subscribers had been stored as free consumers (13,6 mn in 2017).
            eligible_col = next(
                i for i, h in enumerate(grid[0]) if "serbest" in fold(h)
            )
            for line in grid[1:]:
                name = line[0].strip()
                if not name or fold(name) in ("ilsirket", "iladi"):
                    continue
                if fold(name) == "geneltoplam":
                    grand = number_tr(line[1])
                    continue
                values = [
                    number_tr(line[1]) or 0.0,
                    number_tr(line[eligible_col]) or 0.0,
                ]
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
                close(companies[pid][1], eligible, f"doğalgaz serbest {year} {pid}")
                history += [
                    row(pid, year, "gas_customer=subscriber", subs),
                    row(pid, year, "gas_customer=eligible_consumer", eligible),
                ]
        for year, (file, page) in GAS_SUBSCRIBER_PDFS.items():
            for pid, (subs, eligible) in gas_subscriber_pdf(file, page, year).items():
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


#: Header anchor word -> sector, for the PDF section 10 tables.
GAS_SECTOR_ANCHORS = {
    "donusum": "conversion",
    "enerji": "energy",
    "ulasim": "transport",
    "sanayi": "industry",
    "hizmet": "services",
    "konutlar": "residential",
    "diger": "other",
    "genel": "total",
}


def gas_sector_pdf(file: str, first: int, year: int) -> dict[str, dict[str, float]]:
    """Section 10 of the 2015-2016 PDF reports: each province's TOPLAM row by sector.

    Only the TOPLAM row of each province block is read. Its numbers go to the header
    column whose anchor word ("Enerji", "Sanayi", "Konutlar"…) is nearest, the header being
    repeated on every page. Checked: the seven sectors add up to the row's Genel Toplam,
    and that total must equal the province's total in the consumption table (Tablo 8.3),
    read separately — a number put in the wrong column breaks the first check, a row given
    to the wrong province breaks the second.
    """
    import pdfplumber

    out: dict[str, dict[str, float]] = {}
    province = None
    headers: list[tuple[int, float, dict[str, float]]] = []
    with pdfplumber.open(FILES / "dogalgaz_yillik" / f"{file}.pdf") as document:
        for raw_page in document.pages[first:]:
            sizes = Counter(
                round(c["size"]) for c in raw_page.chars if c["text"].isdigit()
            )
            common = sizes.most_common(2)
            # 2015 only: a second text layer. The 2016 report sets tables in two sizes
            # on one page, which the same test would take for a layer and drop.
            if year == 2015 and len(common) == 2 and common[1][1] > 50:
                # The second layer is Times New Roman at 13.8 pt; the report itself is
                # Swiss 721 at 6-10 pt. Drop that layer by its font, not by a size count.
                page = raw_page.filter(
                    lambda o: (
                        o.get("object_type") != "char"
                        or not ("Times" in o["fontname"] and o["size"] > 12)
                    )
                )
            else:
                page = raw_page
            text = page.extract_text() or ""
            if out and not re.search(r"Tablo 10\.\d+|Lisans Tipi", text):
                break
            words = page.extract_words()
            # A page can hold two province tables with their headers set differently, so
            # every header row ("Lisans" and its sector words) is kept with its height and
            # each TOPLAM row reads the nearest header above it.
            for lisans in (w for w in words if fold(w["text"]) == "lisans"):
                found: dict[str, float] = {}
                for w in words:
                    key = fold(
                        w["text"].split("/")[0]
                    )  # "Dönüşüm/" or "Dönüşüm/Çevrim"
                    if (
                        key in GAS_SECTOR_ANCHORS
                        and abs(w["top"] - lisans["top"]) < 25
                        and w["x0"] > lisans["x1"]
                    ):
                        found.setdefault(
                            GAS_SECTOR_ANCHORS[key], (w["x0"] + w["x1"]) / 2
                        )
                headers.append((raw_page.page_number, lisans["top"], found))
            events = []
            for m in re.finditer(r"Tablo 10\.\d+:? ?(.+)", text):
                events.append(("name", m.group(1).strip()))
            titles = [
                (
                    w["top"],
                    " ".join(
                        o["text"]
                        for o in words
                        if abs(o["top"] - w["top"]) < 2
                        and o["x0"] > w["x1"]
                        and not re.fullmatch(r"10\.\d+:?", o["text"])
                    ),
                )
                for w in words
                if w["text"] == "Tablo"
            ]
            items = [(t, "name", n) for t, n in titles]
            for w in words:
                if w["text"] == "TOPLAM" and not any(
                    fold(o["text"]) == "genel" and abs(o["top"] - w["top"]) < 2
                    for o in words
                ):
                    items.append((w["top"], "total", w))
            for top, kind, item in sorted(items, key=lambda x: x[0]):
                if kind == "name":
                    name = re.sub(r"^10\.\d+:?\s*", "", item).strip()
                    province = (
                        "other"
                        if fold(name).startswith("diger")
                        else "TR"
                        if fold(name) == "turkiye"
                        else province_id(name)
                    )
                    continue
                anchors = next(
                    (
                        h
                        for n, t, h in reversed(headers)
                        if n < raw_page.page_number or t < top
                    ),
                    {},
                )
                if len(anchors) != 8 or province is None:
                    raise ValueError(
                        f"doğalgaz sektör PDF {year}: sayfa {raw_page.page_number} "
                        f"başlık {sorted(anchors)} il {province}"
                    )
                values: dict[str, float] = {}
                for w in words:
                    if abs(w["top"] - top) < 2 and NUMBER.fullmatch(w["text"]):
                        centre = (w["x0"] + w["x1"]) / 2
                        sector = min(anchors, key=lambda k: abs(anchors[k] - centre))
                        if sector in values:
                            raise ValueError(
                                f"doğalgaz sektör PDF {year} {province}: {sector} iki kez"
                            )
                        values[sector] = number_tr(w["text"])
                total = values.pop("total", None)
                if (
                    not values and total is None
                ):  # a province with no sales (Tunceli 2015)
                    province = None
                    continue
                if total is None:
                    raise ValueError(
                        f"doğalgaz sektör PDF {year} {province}: genel toplam yok"
                    )
                full = {k: values.get(k, 0.0) for k in GAS_SECTOR_COLUMNS.values()}
                near(
                    sum(full.values()),
                    total,
                    f"doğalgaz sektör {year} {province}",
                    total * 1e-5,
                )
                if province not in ("other", "TR"):
                    if province in out:
                        raise ValueError(
                            f"doğalgaz sektör PDF {year}: {province} iki kez"
                        )
                    out[province] = full
                province = None
    return out


#: Year -> (PDF, first page of section 10).
GAS_SECTOR_PDFS = {2015: ("Jo_r3O_Xi5s_", 77), 2016: ("zd_qHXQpFYw_", 92)}


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
        consumption = GasConsumption().parse(raw)
        for year, (file, first) in GAS_SECTOR_PDFS.items():
            table = gas_sector_pdf(file, first, year)
            used = consumption.filter(pl.col("period_start").dt.year() == year)
            totals = dict(
                used.group_by("area_id").agg(pl.col("value").sum()).iter_rows()
            )
            if set(table) != set(totals):
                raise ValueError(
                    f"doğalgaz sektör {year}: il kümesi tüketim tablosundan farklı "
                    f"{sorted(set(table) ^ set(totals))}"
                )
            for pid, sectors in table.items():
                # Tablo 8.3 is in million Sm3 to two decimals: 5,000 m3 of rounding a cell.
                near(
                    sum(sectors.values()),
                    totals[pid],
                    f"doğalgaz sektör/tüketim {year} {pid}",
                    25_000.0,
                )
            tables[year] = table
        return merge_years(
            super().parse(raw), records(tables, "gas_sector"), "doğalgaz sektör"
        )


EPDK_HISTORY_ADAPTERS["epdk_natural_gas_sales"] = GasSalesHistory
