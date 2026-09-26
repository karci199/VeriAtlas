"""Car and light commercial vehicle retail sales by brand — ODMD, Türkiye.

ODMD (Otomotiv Distribütörleri ve Mobilite Derneği) publishes one workbook per month and
one per year under "Pazar - Perakende Satışlar" (`neuralnetwork.aspx?type=36`): every
brand's retail sales split into cars and light commercial vehicles, each into domestic
production and imports. Pulled 2026-09-26 into `odmd/perakende/<primary_id>.<ext>`, with
the list page's titles in `liste.json`. The download answers an empty page unless the list
page was fetched first in the same session (ASP.NET session cookie).

Workbooks run from 2014 (and 2007); 2004-2013 are PDFs, read by word position where
the total check passes (`UNREADABLE_PDFS` lists the rest). Two
indicators: the monthly files, and the full-year files. A running total for an unfinished
year ("2026 Yılı (Ocak-Ağustos)") is neither and is skipped.

The nine value columns are found by position under the header row that repeats
YERLİ / İTHAL / TOPLAM three times — zeros are sometimes blank or "-", so a row is read by
column, never by counting its numbers. Every file's brand rows must add up to its TOPLAM
row, and every brand must be in the dictionary; either failing stops the load. Only the
four leaf cells (class × origin) are stored: totals are sums of them.

ODMD's own footnote says the Tesla figures are estimated from public statements; those
rows carry quality flag `estimated`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get, load
from ..schema import format_dims

DOWNLOADS = RAW / "odmd" / "perakende"

MONTHS = {
    "Ocak": 1,
    "Şubat": 2,
    "Mart": 3,
    "Nisan": 4,
    "Mayıs": 5,
    "Haziran": 6,
    "Temmuz": 7,
    "Ağustos": 8,
    "Eylül": 9,
    "Ekim": 10,
    "Kasım": 11,
    "Aralık": 12,
}
#: Column order under the header: car Y/İ/T, light commercial Y/İ/T, total Y/İ/T.
LEAVES = {
    0: ("car", "domestic"),
    1: ("car", "imported"),
    3: ("light_commercial", "domestic"),
    4: ("light_commercial", "imported"),
}
#: The same brand spelled two ways across the years.
ALIASES = {
    "ASTON MARTİN": "ASTON MARTIN",
    "HONQI": "HONGQI",
    "LANDROVER": "LAND ROVER",
    "KG MOBILITY – SSANGYONG": "SSANGYONG",
}
ESTIMATED = {"tesla"}


def brand_code(name: str) -> str:
    name = ALIASES.get(name, name)
    return re.sub(r"[^a-z0-9]+", "_", name.lower().replace("&", "and")).strip("_")


def period(title: str) -> tuple[int, int | None, bool]:
    """(year, month or None for a year file, whether the year file is complete)."""
    year = int(re.search(r"(20\d\d)", title).group(1))
    if "Ocak-" in title:
        return year, None, "Ocak-Aralık" in title
    months = [m for name, m in MONTHS.items() if name in title]
    if not months:
        return year, None, True
    if len(months) > 1:
        raise ValueError("odmd: iki ay adi: " + title)
    return year, months[0], True


def read_rows(path: Path) -> list[list]:
    if path.suffix == ".xlsx":
        import openpyxl

        sheet = openpyxl.load_workbook(path, data_only=True, read_only=True).worksheets[
            0
        ]
        return [list(r) for r in sheet.iter_rows(values_only=True)]
    import xlrd

    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    return [sheet.row_values(i) for i in range(sheet.nrows)]


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_file(path: Path, title: str) -> list[tuple[str, list[float]]]:
    rows = read_rows(path)
    columns = None
    for row in rows:
        idx = [
            i
            for i, c in enumerate(row)
            if isinstance(c, str) and c.strip().upper() in ("YERLİ", "İTHAL", "TOPLAM")
        ]
        if len(idx) >= 9 and sum(row[i].strip().upper() == "YERLİ" for i in idx) == 3:
            columns = idx[:9]
            break
    if columns is None:
        raise ValueError("odmd: baslik satiri yok: " + title)
    brands, total = [], None
    for row in rows:
        if len(row) <= max(columns):
            continue
        name = next(
            (c for c in row[: columns[0]] if isinstance(c, str) and c.strip()), None
        )
        values = [row[i] for i in columns]
        if not name or not any(is_number(v) for v in values):
            continue
        values = [float(v) if is_number(v) else 0.0 for v in values]
        name = name.strip()
        if name.upper().startswith("TOPLAM"):
            total = values
        elif name.upper() not in ("MARKA", "YERLİ"):
            brands.append((name, values))
    if total is None:
        raise ValueError("odmd: TOPLAM satiri yok: " + title)
    sums = [sum(v[i] for _, v in brands) for i in range(9)]
    if any(abs(s - t) > 0.5 for s, t in zip(sums, total, strict=True)):
        raise ValueError(f"odmd: markalar toplami tutmuyor: {title} {sums} {total}")
    return brands


#: 2004-2013 PDFs whose brand rows cannot be placed in columns from the text: blank cells
#: are simply missing (2010-2012) or the table runs past what the text layer holds. Any
#: other PDF that fails the total check stops the load.
UNREADABLE_PDFS = frozenset(
    [
        "640",
        "546",
        "545",
        "524",
        "517",
        "475",
        "427",
        "444",
        "347",
        "348",
        "349",
        "350",
        "351",
        "352",
        "353",
        "354",
        "355",
        "356",
        "357",
        "358",
        "359",
        "360",
        "366",
    ]
)
NUMBER = re.compile(r"^\d{1,3}(?:\.\d{3})*$")


def parse_pdf(path: Path, title: str) -> list[tuple[str, list[float]]]:
    """A 2004-2013 PDF: numbers are put in the column whose header they sit under."""
    import pdfplumber

    lines: dict[tuple, list] = {}
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages):
            for w in page.extract_words():
                lines.setdefault((page_no, round(w["top"] / 3)), []).append(w)
    rows = [sorted(v, key=lambda w: w["x0"]) for _, v in sorted(lines.items())]
    heads = ("YERLİ", "YERLI", "İTHAL", "ITHAL", "TOPLAM")
    header = max(rows, key=lambda r: sum(w["text"].upper() in heads for w in r))
    columns = [(w["x0"] + w["x1"]) / 2 for w in header if w["text"].upper() in heads]
    if len(columns) != 9:
        raise ValueError(f"odmd: {len(columns)} sutun, 9 bekleniyordu: {title}")
    brands, total = [], None
    for row in rows:
        numbers = [w for w in row if NUMBER.match(w["text"])]
        name = " ".join(
            w["text"]
            for w in row
            if not NUMBER.match(w["text"]) and w["x1"] < columns[0] - 5
        ).strip()
        if not numbers or not name:
            continue
        values = [0.0] * 9
        for w in numbers:
            centre = (w["x0"] + w["x1"]) / 2
            i = min(range(9), key=lambda k: abs(columns[k] - centre))
            values[i] += float(w["text"].replace(".", ""))
        if name.upper().startswith("TOPLAM"):
            total = values
        else:
            brands.append((name, values))
    if total is None:
        raise ValueError("odmd: TOPLAM satiri yok: " + title)
    sums = [sum(v[i] for _, v in brands) for i in range(9)]
    if any(abs(s - t) > 0.5 for s, t in zip(sums, total, strict=True)):
        raise ValueError(f"odmd: markalar toplami tutmuyor: {title} {sums} {total}")
    return brands


class OdmdRetailBase:
    source_id = "odmd"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 26)
    indicator_id = ""
    annual = False

    def fetch(self) -> Path:
        if not (DOWNLOADS / "liste.json").exists():
            raise FileNotFoundError("ODMD perakende dokumu yok: " + str(DOWNLOADS))
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        titles = json.loads((raw / "liste.json").read_text(encoding="utf-8"))
        known = set(load().dimensions["vehicle_brand"].values_tr)
        records = []
        for pid, title in titles.items():
            files = [p for p in raw.glob(pid + ".*") if p.suffix in (".xlsx", ".xls")]
            pdf = raw / (pid + ".pdf")
            if not files and (pid in UNREADABLE_PDFS or not pdf.exists()):
                continue
            year, month, complete = period(title)
            if self.annual != (month is None) or not complete:
                continue
            start = dt.date(year, month or 1, 1)
            brands = parse_file(files[0], title) if files else parse_pdf(pdf, title)
            for name, values in brands:
                code = brand_code(name)
                if code not in known:
                    raise KeyError("odmd: sozlukte olmayan marka: " + name)
                for i, (vclass, origin) in LEAVES.items():
                    records.append(
                        (
                            start,
                            format_dims(
                                {
                                    "production_origin": origin,
                                    "vehicle_brand": code,
                                    "vehicle_class": vclass,
                                }
                            ),
                            values[i],
                            "estimated" if code in ESTIMATED else "measured",
                        )
                    )
        frame = pl.DataFrame(
            records,
            schema=["period_start", "dims", "value", "quality_flag"],
            orient="row",
        )
        if frame.is_empty():
            raise ValueError(self.indicator_id + ": satir yok")
        # Two spellings of one brand in the same file would land on the same key.
        frame = frame.group_by("period_start", "dims", "quality_flag").agg(
            pl.col("value").sum()
        )
        if frame.select("period_start", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni donem-kirilim iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).select(
            "indicator_id",
            "area_id",
            "area_level",
            "period_start",
            "frequency",
            "dims",
            "value",
            "unit",
            "quality_flag",
            "vintage",
            "source_id",
            "retrieved_at",
        )


class OdmdRetailSales(OdmdRetailBase):
    indicator_id = "odmd_retail_sales"


class OdmdRetailSalesAnnual(OdmdRetailBase):
    indicator_id = "odmd_retail_sales_annual"
    annual = True


ODMD_ADAPTERS = {
    "odmd_retail_sales": OdmdRetailSales,
    "odmd_retail_sales_annual": OdmdRetailSalesAnnual,
}
