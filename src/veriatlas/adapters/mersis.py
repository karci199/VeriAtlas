"""Active businesses and monthly openings/closings by legal form, Türkiye (MERSİS).

Source: Ministry of Trade, "Şirket Bilgileri" → "MERSİS Verileri.pdf", one page, the
Central Registry (MERSİS) counts by legal form: joint stock, limited, collective and
commandite companies, cooperatives, sole traders ("ticari işletme"), branches and joint
ship-owning. Two tables per year: active businesses at each month's end, and the month's
openings and closings (with the year's total beside them).

The file is overwritten at one address every quarter and keeps only the current and the
previous year, so earlier years come from Wayback copies of the same address
(`raw/ticaret/mersis_verileri_<date>.pdf`, the date being the copy's). Of the copies,
2024-06-09 (January-March 2024) and the 2026-09-26 download (January 2025 - June 2026)
read cleanly; 2025-05-21 and 2025-11-25 print their rows as vertical text that comes out
of the PDF scrambled and are not read — both are covered by the 2026 file. April-December
2024 is in no copy.

Checks: every column's TOPLAM row equals the sum of the legal forms, and the year-total
columns of the openings table equal the sum of the months.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold

FILES = RAW / "ticaret"
READABLE = ("mersis_verileri_2024-06-09.pdf", "mersis_verileri_2026-09-26.pdf")
TYPES = {
    "anonimsirket": "joint_stock",
    "limitedsirket": "limited",
    "kollektifsirket": "collective",
    "komanditsirket": "commandite",
    "kooperatif": "cooperative",
    "ticariisletme": "sole_trader",
    "sube": "branch",
    "donatmaistiraki": "joint_shipowning",
}
NUMBER = re.compile(r"^\d{1,3}(\.\d{3})*$|^\d+$")


def split_row(line: str) -> tuple[str, list[float]] | None:
    tokens = line.split()
    values: list[float] = []
    while tokens and NUMBER.match(tokens[-1]):
        values.insert(0, float(tokens.pop().replace(".", "")))
    if not values:
        return None
    return fold(" ".join(tokens)), values


def read_pdf(path: Path) -> tuple[dict, dict]:
    """({(type, month): active}, {(type, event, month): count}) for one file."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        lines = [
            line.strip()
            for page in pdf.pages
            for line in (page.extract_text() or "").splitlines()
        ]
    stock: dict[tuple[str, dt.date], float] = {}
    flows: dict[tuple[str, str, dt.date], float] = {}
    table = year = None
    rows: dict[str, list[float]] = {}

    def close() -> None:
        if table is None:
            return
        if set(rows) != set(TYPES) | {"toplam"}:
            raise ValueError(
                f"MERSİS {path.name} {year} {table}: satırlar {sorted(rows)}"
            )
        width = {len(v) for v in rows.values()}
        if len(width) != 1:
            raise ValueError(f"MERSİS {path.name} {year} {table}: uzunluklar {width}")
        for j in range(width.pop()):
            parts = sum(rows[k][j] for k in TYPES)
            if parts != rows["toplam"][j]:
                raise ValueError(
                    f"MERSİS {path.name} {year} {table} sütun {j}: türler {parts:,.0f}, "
                    f"TOPLAM {rows['toplam'][j]:,.0f}"
                )
        if table == "stock":
            for key, name in TYPES.items():
                for m, value in enumerate(rows[key], start=1):
                    stock[(name, dt.date(year, m, 1))] = value
            return
        months = len([m for _, m in stock if m.year == year]) // len(TYPES)
        n = len(rows["toplam"])
        if n not in (2 * months, 2 * months + 2):
            raise ValueError(
                f"MERSİS {path.name} {year}: {n} sütun, stok tablosunda {months} ay"
            )
        for key, name in TYPES.items():
            values = rows[key]
            for m in range(months):
                month = dt.date(year, m + 1, 1)
                flows[(name, "established", month)] = values[2 * m]
                flows[(name, "closed", month)] = values[2 * m + 1]
            if n == 2 * months + 2:
                opened = sum(values[0 : 2 * months : 2])
                closed = sum(values[1 : 2 * months : 2])
                if (opened, closed) != (values[-2], values[-1]):
                    raise ValueError(
                        f"MERSİS {path.name} {year} {name}: aylar {opened:,.0f}/{closed:,.0f}, "
                        f"yıl toplamı {values[-2]:,.0f}/{values[-1]:,.0f}"
                    )

    for line in lines:
        key = fold(line)
        heading = re.search(r"(20\d\d)", line)
        if heading and ("mevcutaktif" in key or "kurulankapanan" in key):
            close()
            table = "stock" if "mevcutaktif" in key else "flows"
            year = int(heading.group(1))
            rows = {}
            continue
        if table is None:
            continue
        split = split_row(line)
        if split is None:
            continue
        label, values = split
        if label in TYPES or label == "toplam":
            if label in rows:
                raise ValueError(f"MERSİS {path.name} {year} {table}: {label} iki kez")
            rows[label] = values
    close()
    return stock, flows


def read_all() -> tuple[dict, dict]:
    stock: dict = {}
    flows: dict = {}
    for name in READABLE:
        s, f = read_pdf(FILES / name)
        for key, value in s.items():
            if key in stock and stock[key] != value:
                raise ValueError(f"MERSİS {key}: {stock[key]:,.0f} / {value:,.0f}")
        stock |= s
        flows |= f
    return stock, flows


def _frame(records: list[dict], indicator_id: str) -> pl.DataFrame:
    return pl.DataFrame(records, schema_overrides={"value": pl.Float64}).with_columns(
        pl.lit(indicator_id).alias("indicator_id"),
        pl.lit("TR").alias("area_id"),
        pl.lit("country").alias("area_level"),
        pl.lit("monthly").alias("frequency"),
        pl.lit("business").alias("unit"),
        pl.lit("measured").alias("quality_flag"),
        pl.lit("2026-06").alias("vintage"),
        pl.lit("mersis").alias("source_id"),
        pl.lit(dt.date(2026, 9, 26)).alias("retrieved_at"),
    )


class MersisActiveBusinesses:
    source_id = "mersis"
    indicator_id = "mersis_active_businesses"

    def fetch(self) -> Path:
        return FILES

    def parse(self, raw: Path) -> pl.DataFrame:
        stock, _ = read_all()
        return _frame(
            [
                {"period_start": m, "dims": f"business_type={t}", "value": v}
                for (t, m), v in stock.items()
            ],
            self.indicator_id,
        )


class MersisBusinessFlows:
    source_id = "mersis"
    indicator_id = "mersis_business_flows"

    def fetch(self) -> Path:
        return FILES

    def parse(self, raw: Path) -> pl.DataFrame:
        _, flows = read_all()
        return _frame(
            [
                {
                    "period_start": m,
                    "dims": f"business_type={t};company_event={e}",
                    "value": v,
                }
                for (t, e, m), v in flows.items()
            ],
            self.indicator_id,
        )


MERSIS_ADAPTERS = {
    "mersis_active_businesses": MersisActiveBusinesses,
    "mersis_business_flows": MersisBusinessFlows,
}
