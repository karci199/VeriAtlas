"""Crop product balance sheets, Türkiye, marketing years 2000/01 onwards (TÜİK).

Source: TÜİK data portal, "Bitkisel Ürün Denge Tabloları", downloaded 2026-09-18 into
`raw/tuik_portal/dosya/tablo/`: cereals and other crops (00284, 24 products) and
vegetables (00285, 22 products). One block per product, latest marketing year first;
the Turkish name sits on the block's first row, the English one below it. A marketing
year is stored at the year it starts (2024/25 → 2024).

Three indicators, split by unit: the balance in tonnes (production to exports, one
dimension value per column), human consumption per person (kg) and the degree of
self-sufficiency (%). The sown-area column is left out: it is `field_crop_sown_area`'s.

What the balance measures and what it assumes (read before using the consumption
columns): harvest losses are a fixed share of production, and for vegetables human
consumption is a fixed share of domestic use (90 % to 2014, 85 % from 2015; the rest is
"losses") — consumption is what is left, not a measurement. Foreign trade follows the
general trade system from 2018/19.

Cells: "..." not available and "." not applicable are left out; "-" is zero.
Checks, per product and year, where every term is published: usable production =
production − harvest losses; supply = usable production + imports; domestic use =
supply − exports − stock change; domestic use = the sum of its uses; self-sufficiency =
usable production ÷ domestic use. All hold, except domestic use for the cereals total in
2008-2012 (`KNOWN_MISMATCH`), kept as published.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW

FILES = RAW / "tuik_portal" / "dosya" / "tablo"
TABLES = (
    "00284_Tahıllar ve Diğer Bitkisel Ürünler Denge Tabloları.xls",
    "00285_Sebzeler Denge Tabloları.xls",
)
#: Turkish product name in the table → dimension value.
PRODUCTS = {
    "Tahıl (toplam)": "cereals_total",
    "Arpa": "barley",
    "Buğday (toplam)": "wheat_total",
    "Buğday (diğer)": "wheat_other",
    "Buğday (durum)": "wheat_durum",
    "Mısır": "maize",
    "Yulaf": "oats",
    "Çavdar": "rye",
    "Diğer tahıllar (2)": "other_cereals",
    "Pirinç": "rice",
    "Patates": "potato",
    "Kuru baklagil (toplam) (3)": "dried_pulses_total",
    "Kuru fasulye": "dry_bean",
    "Kırmızı mercimek": "red_lentil",
    "Nohut": "chickpea",
    "Yeşil mercimek": "green_lentil",
    "Ayçiçeği": "sunflower",
    "Kenevir": "hemp",
    "Keten": "flax",
    "Kolza": "rapeseed",
    "Pamuk (çiğit)": "cotton_seed",
    "Soya (1)": "soybean",
    "Şeker": "sugar",
    "Şeker pancarı": "sugar_beet",
    "Sebze (toplam)(1)": "vegetables_total",
    "Bakla (taze)": "green_broad_bean",
    "Bamya": "okra",
    "Bezelye (taze)": "green_pea",
    "Biber": "pepper",
    "Domates": "tomato",
    "Fasulye (taze)": "green_bean",
    "Havuç": "carrot",
    "Hıyar": "cucumber",
    "Ispanak": "spinach",
    "Kabak (sakız)": "squash",
    "Karpuz": "watermelon",
    "Kavun": "melon",
    "Lahana": "cabbage",
    "Marul": "lettuce",
    "Patlıcan": "eggplant",
    "Pırasa": "leek",
    "Sarımsak (kuru)": "garlic_dry",
    "Semizotu": "purslane",
    "Soğan (kuru)": "onion_dry",
    "Soğan (taze)": "onion_green",
    "Turp": "radish",
}
#: Column (0-based) → balance item, tonnes. Column 3 (area sown, ha) is left out.
TONNES = {
    2: "production",
    4: "harvest_losses",
    5: "supply",
    6: "usable_production",
    7: "imports",
    8: "imports_eu",
    9: "domestic_use",
    10: "human_consumption",
    11: "seed_use",
    12: "feed_use",
    13: "processing",
    14: "industrial_use",
    15: "losses",
    16: "exports",
    17: "exports_eu",
    18: "stock_change",
}
PER_CAPITA, SELF_SUFFICIENCY = 19, 20
#: (product, marketing year, check) published inconsistent in the source.
KNOWN_MISMATCH = {
    ("cereals_total", y, "domestic_use") for y in (2008, 2009, 2011, 2012)
}


def number(cell) -> float | None:
    text = str(cell).strip()
    if text == "-":
        return 0.0
    if text in ("", ".", "...", "…"):
        return None
    return float(text)


def read_table(path: Path) -> dict[tuple[str, int], list[float | None]]:
    """{(product, year): the 21 cells as numbers} for one file."""
    from python_calamine import CalamineWorkbook

    book = CalamineWorkbook.from_path(path)
    rows = book.get_sheet_by_name(book.sheet_names[0]).to_python()
    head = next(i for i, r in enumerate(rows) if str(r[0]).startswith("Ürün"))
    body = [r for r in rows[head + 1 :] if str(r[1]).strip()]
    latest = str(body[0][1]).strip()
    out: dict[tuple[str, int], list[float | None]] = {}
    product = None
    for r in body:
        label = str(r[1]).strip()
        if label == latest:
            name = " ".join(str(r[0]).split())
            if name not in PRODUCTS:
                raise KeyError(f"denge tablosu {path.name}: tanınmayan ürün {name!r}")
            product = PRODUCTS[name]
        year = int(label[:4])
        if (product, year) in out:
            raise ValueError(f"denge tablosu {path.name}: {product} {label} iki kez")
        cells = [None, None] + [number(c) for c in r[2:21]]
        check(product, year, cells)
        out[(product, year)] = cells
    return out


def check(product: str, year: int, v: list[float | None]) -> None:
    uses = [v[c] for c in (10, 11, 12, 13, 14, 15)]
    tests = {
        "usable_production": (v[6], None if None in (v[2], v[4]) else v[2] - v[4]),
        "supply": (v[5], None if None in (v[6], v[7]) else v[6] + v[7]),
        "domestic_use": (
            v[9],
            None if None in (v[5], v[16]) else v[5] - v[16] - (v[18] or 0),
        ),
        "uses": (
            v[9],
            sum(u for u in uses if u is not None)
            if any(u is not None for u in uses)
            else None,
        ),
        "self_sufficiency": (v[20], v[6] / v[9] * 100 if v[6] and v[9] else None),
    }
    for name, (printed, derived) in tests.items():
        if (
            printed is None
            or derived is None
            or (product, year, name) in KNOWN_MISMATCH
        ):
            continue
        if abs(printed - derived) > max(2.0, abs(derived) * 0.005):
            raise ValueError(
                f"denge tablosu {product} {year} {name}: {printed:,.1f} ≠ {derived:,.1f}"
            )


def read_all() -> dict[tuple[str, int], list[float | None]]:
    out: dict[tuple[str, int], list[float | None]] = {}
    for name in TABLES:
        for key, cells in read_table(FILES / name).items():
            if key in out:
                raise ValueError(f"denge tablosu: {key} iki dosyada")
            out[key] = cells
    return out


class CropBalance:
    source_id = "tuik_portal"
    indicator_id = ""
    unit = ""

    def fetch(self) -> Path:
        return FILES

    def records(self) -> list[dict]:
        raise NotImplementedError

    def parse(self, raw: Path) -> pl.DataFrame:
        return pl.DataFrame(
            self.records(), schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit(self.unit).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-03").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 18)).alias("retrieved_at"),
        )


class CropBalanceTonnes(CropBalance):
    indicator_id = "crop_balance"
    unit = "tonne"

    def records(self) -> list[dict]:
        return [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": f"balance_item={item};balance_product={product}",
                "value": cells[col],
            }
            for (product, year), cells in read_all().items()
            for col, item in TONNES.items()
            if cells[col] is not None
        ]


class CropColumn(CropBalance):
    column = 0

    def records(self) -> list[dict]:
        return [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": f"balance_product={product}",
                "value": cells[self.column],
            }
            for (product, year), cells in read_all().items()
            if cells[self.column] is not None
        ]


class CropConsumptionPerCapita(CropColumn):
    indicator_id = "crop_consumption_per_capita"
    unit = "kg_per_person_year"
    column = PER_CAPITA


class CropSelfSufficiency(CropColumn):
    indicator_id = "crop_self_sufficiency"
    unit = "percent"
    column = SELF_SUFFICIENCY


CROP_BALANCE_ADAPTERS = {
    c.indicator_id: c
    for c in (CropBalanceTonnes, CropConsumptionPerCapita, CropSelfSufficiency)
}
