"""Annual industrial products statistics (PRODCOM), Türkiye, 2005 onwards (TÜİK).

Source: TÜİK data portal tables, downloaded 2026-09-18 into
`raw/tuik_portal/dosya/tablo/`: production quantity (00365), sales quantity (00213),
sales value (00214), number of enterprises (00211) and the code list (00212). One row
per product code at three nested levels — CPA (6 digits), PRODCOM (8), PRODTR (10) —
so a parent and its children must never be added together; the code is the dimension
and the level is its length.

Each product has one unit in the code list (kg, items, m², kWh ...); quantities are
stored with that unit as a second dimension, so kilograms and pieces never meet.
Products measured in lira have no quantity ("."), confidential cells are "c", "-" is
no production: none of them is a zero, all are left out. 2025 is provisional.

Checks: every code is in the code list, once; the unit column matches the code list;
where every child of a code is published, the children add up to the parent. They do
everywhere except `28.42.24` in sales value (2018, 2022-2025: the children exceed the
parent in TÜİK's own table), which is kept as published and listed in `KNOWN_MISMATCH`.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW

FILES = RAW / "tuik_portal" / "dosya" / "tablo"
CODE_LIST = "00212_Yıllık Sanayi Ürün İstatistikleri Kod Listesi.xls"
TABLES = {
    "industrial_product_output": (
        "00365_Sanayi Ürünleri Üretim Miktarı.xls",
        "source_unit",
    ),
    "industrial_product_sales_quantity": (
        "00213_Sanayi Ürünleri Satış Miktarı.xls",
        "source_unit",
    ),
    "industrial_product_sales_value": ("00214_Sanayi Ürünleri Satış Değeri.xls", "try"),
    "industrial_product_enterprises": (
        "00211_Sanayi Ürünleri Girişim Sayısı.xls",
        "item",
    ),
}
CODE = re.compile(r"\d\d(\.\d\d){2,4}")
NUMBER = re.compile(r"-?\d+(\.\d+)?")
MISSING = {"c", ".", "-", ""}
#: (indicator, parent code): children add up to more than the parent in the source.
KNOWN_MISMATCH = {("industrial_product_sales_value", "28.42.24")}


def unit_id(english: str) -> str:
    """Dimension value for a unit: its English name, lower-case, underscores."""
    return re.sub(r"[^a-z0-9]+", "_", english.lower()).strip("_")


def rows(path: Path) -> list[list]:
    from python_calamine import CalamineWorkbook

    book = CalamineWorkbook.from_path(path)
    return book.get_sheet_by_name(book.sheet_names[0]).to_python()


def code_list() -> dict[str, dict]:
    """{code: {level, name_tr, name_en, unit_tr, unit}} from the code list."""
    out: dict[str, dict] = {}
    for r in rows(FILES / CODE_LIST):
        code = str(r[0]).strip()
        if not CODE.fullmatch(code):
            continue
        if code in out:
            raise ValueError(f"PRODCOM kod listesi: {code} iki kez")
        out[code] = {
            "level": str(r[1]).strip(),
            "name_tr": " ".join(str(r[2]).split()),
            "name_en": " ".join(str(r[3]).split()),
            "unit_tr": " ".join(str(r[4]).split()),
            "unit": unit_id(str(r[5])),
        }
    return out


def read_table(indicator: str, codes: dict[str, dict]) -> dict[tuple[str, int], float]:
    """{(code, year): value}; the value table also carries the "total" row."""
    table = rows(FILES / TABLES[indicator][0])
    head = next(i for i, r in enumerate(table) if str(r[0]).startswith("Ürün Kodu"))
    years = {
        j: int(str(c)[:4])
        for j, c in enumerate(table[head])
        if re.match(r"(19|20)\d\d", str(c))
    }
    # The value table prints "Turkish Lira" on every row; only quantities carry the
    # product's own unit.
    has_unit = TABLES[indicator][1] == "source_unit"
    out: dict[tuple[str, int], float] = {}
    seen: set[str] = set()
    for r in table[head + 1 :]:
        first = str(r[0]).strip()
        if first.startswith("Toplam"):
            code = "total"
        elif CODE.fullmatch(first):
            code = first
            if code not in codes:
                raise KeyError(f"PRODCOM {indicator}: kod listesinde yok: {code}")
            # Compared on the English unit column: the Turkish one is spelt differently
            # between files ("Türk Lirası" / "Türk Lirası (TL)").
            if has_unit and unit_id(str(r[2])) != codes[code]["unit"]:
                raise ValueError(
                    f"PRODCOM {indicator} {code}: birim {r[2]!r} ≠ kod listesi"
                )
        else:
            continue
        if code in seen:
            raise ValueError(f"PRODCOM {indicator}: {code} iki kez")
        seen.add(code)
        for j, year in years.items():
            cell = str(r[j]).strip()
            if cell in MISSING:
                continue
            if not NUMBER.fullmatch(cell):
                raise ValueError(
                    f"PRODCOM {indicator} {code} {year}: tanınmayan hücre {cell!r}"
                )
            out[(code, year)] = float(cell)
    check_hierarchy(indicator, out, seen)
    return out


def check_hierarchy(
    indicator: str, table: dict[tuple[str, int], float], listed: set[str]
) -> None:
    """Children are taken from every row listed, not only rows with a value: a child
    that is confidential in every year still makes its siblings an incomplete set."""
    by_code: dict[str, dict[int, float]] = {code: {} for code in listed}
    for (code, year), value in table.items():
        by_code[code][year] = value
    children: dict[str, list[str]] = {}
    for code in by_code:
        if code != "total" and code.count(".") > 2:
            children.setdefault(code.rsplit(".", 1)[0], []).append(code)
    for parent, kids in children.items():
        if parent not in by_code or (indicator, parent) in KNOWN_MISMATCH:
            continue
        for year, value in by_code[parent].items():
            parts = [by_code[k].get(year) for k in kids]
            # Only a complete set of children can be compared (confidential cells hide some).
            if None in parts:
                continue
            if indicator == "industrial_product_enterprises":
                # An enterprise making two child products is counted under both: the
                # parent lies between the largest child and the children's sum.
                if not max(parts) <= value <= sum(parts):
                    raise ValueError(
                        f"PRODCOM {indicator} {parent} {year}: üst {value:,.0f}, "
                        f"alt kodlar en çok {max(parts):,.0f}, toplam {sum(parts):,.0f}"
                    )
            elif abs(sum(parts) - value) > max(1.0, abs(value) * 1e-6):
                raise ValueError(
                    f"PRODCOM {indicator} {parent} {year}: alt kodlar {sum(parts):,.0f}, üst {value:,.0f}"
                )


class ProdcomTable:
    source_id = "tuik_portal"
    indicator_id = ""

    def fetch(self) -> Path:
        return FILES / TABLES[self.indicator_id][0]

    def parse(self, raw: Path) -> pl.DataFrame:
        codes = code_list()
        quantity = TABLES[self.indicator_id][1] == "source_unit"
        records = [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": f"industrial_product={code}"
                + (f";product_unit={codes[code]['unit']}" if quantity else ""),
                "value": value,
            }
            for (code, year), value in read_table(self.indicator_id, codes).items()
            if not (quantity and code == "total")
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit(TABLES[self.indicator_id][1]).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 18)).alias("retrieved_at"),
        )


PRODCOM_ADAPTERS = {
    ident: type(
        "Prodcom" + "".join(p.title() for p in ident.split("_")),
        (ProdcomTable,),
        {"indicator_id": ident},
    )
    for ident in TABLES
}
