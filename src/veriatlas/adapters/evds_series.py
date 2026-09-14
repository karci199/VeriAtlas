"""EVDS groups stored at their published frequency: price indices, monthly property sales by
province, monthly construction and occupancy permits, the 26-region house price archive.

Downloaded by `scripts/fetch_evds_housing.py <group>` into `raw/evds/`. Four shapes:

- **price index trees** (CPI 2025 items, PPI, services PPI, ...): Türkiye only, one
  dimension whose values are the EVDS series codes, labelled with the source's own
  numbered names. Aggregates are stored next to their items — an index does not add up.
- **property sales** (`bie_akonutsat1..4`): "Adana_Konut_İpotekli Satışlar". Provinces
  only; each province sum is checked against the source's Türkiye row, month by month.
  Seasonally adjusted copies (Türkiye only) are not stored.
- **permits** (`bie_inyprh2`, `bie_inypkl2`): owner × building use × measure. Only leaves
  are stored — public / cooperative / private × nine uses and "other" — and their sum is
  checked against the published grand total. The value measure (C) is empty at source.
- **house price index 2017=100** (`bie_hkfe`): Türkiye and all 26 İBBS-2 regions.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get, load
from ..schema import format_dims

DOWNLOADS = RAW / "evds"


def rows_of(payload: dict):
    """(series, period date, value) for every filled cell, periods monthly or quarterly."""
    for series in payload["series"]:
        column = series["SERIE_CODE"].replace(".", "_")
        for item in payload["items"]:
            cell = item.get(column)
            if cell in (None, ""):
                continue
            label = item["Tarih"]
            if "-Q" in label:
                year, quarter = label.split("-Q")
                date = dt.date(int(year), 3 * int(quarter) - 2, 1)
            else:
                year, month = label.split("-")
                date = dt.date(int(year), int(month), 1)
            yield series, date, float(cell)


def item_value(code: str) -> str:
    """Dimension value id from an EVDS series code: its last segments, lower-case."""
    return re.sub(r"[^a-z0-9]+", "_", code.split(".", 1)[1].lower()).strip("_")


# region Price index trees

#: indicator id → (group, dimension)
INDEX_TREES = {
    "cpi_2025_items": ("bie_tukfiy2025", "cpi_2025_item"),
    "cpi_2025_special": ("bie_oktug2025", "cpi_2025_special_item"),
    "ppi_domestic": ("bie_tufe1yi", "ppi_domestic_item"),
    "ppi_export": ("bie_ufeyd", "ppi_export_item"),
    "services_ppi": ("bie_hufe", "services_ppi_item"),
    "agricultural_ppi": ("bie_tarimufe", "agricultural_ppi_item"),
    "agricultural_input_pi": ("bie_tarimgfe", "agricultural_input_item"),
    "istanbul_cpi_ito": ("bie_itouge2023", "istanbul_cpi_item"),
    # Not a price index, but the same shape: one Türkiye series per vehicle type (OSD).
    "vehicle_production": ("bie_uroto", "vehicle_type_produced"),
}


def index_tree(indicator_id: str) -> list[dict]:
    group, dim = INDEX_TREES[indicator_id]
    payload = json.loads((DOWNLOADS / f"{group}.json").read_text(encoding="utf-8"))
    declared = load().dimensions[dim].values_tr
    seen: set[str] = set()
    records = []
    for series, date, value in rows_of(payload):
        key = item_value(series["SERIE_CODE"])
        if key not in declared:
            raise KeyError(
                f"{indicator_id}: sozlukte olmayan kalem {series['SERIE_CODE']}"
            )
        seen.add(key)
        records.append(
            {
                "area_id": "TR",
                "area_level": "country",
                "period_start": date,
                "dims": format_dims({dim: key}),
                "value": value,
            }
        )
    return records


# endregion

# region Property sales by province

SALES_GROUPS = {
    "bie_akonutsat1": "total",
    "bie_akonutsat2": "mortgaged",
    "bie_akonutsat3": "first_hand",
    "bie_akonutsat4": "second_hand",
}
PROPERTY = {"Konut": "dwelling", "İş Yeri": "workplace"}


def property_sales() -> list[dict]:
    provinces = {
        row["name_tr"]: row["area_id"]
        for row in load_areas().filter(pl.col("area_level") == "province").to_dicts()
    }
    records = []
    for group, sale in SALES_GROUPS.items():
        payload = json.loads((DOWNLOADS / f"{group}.json").read_text(encoding="utf-8"))
        country: dict[tuple, float] = {}
        summed: dict[tuple, float] = {}
        for series, date, value in rows_of(payload):
            name = series["SERIE_NAME"]
            if "Mevsim" in name:
                continue
            place, kind, _ = name.split("_")
            key = (PROPERTY[kind], date)
            if place == "Türkiye":
                country[key] = value
                continue
            if place not in provinces:
                raise KeyError("il eslesmedi: " + name)
            summed[key] = summed.get(key, 0.0) + value
            records.append(
                {
                    "area_id": provinces[place],
                    "area_level": "province",
                    "period_start": date,
                    "dims": format_dims({"property_type": key[0], "sale_type": sale}),
                    "value": value,
                }
            )
        off = [k for k, v in country.items() if abs(summed.get(k, 0.0) - v) > 1]
        if off:
            raise ValueError(
                f"{group}: il toplami Turkiye'yi tutmuyor, ornek {off[:3]}"
            )
    return records


# endregion

# region Permits

PERMIT_GROUPS = {"bie_inyprh2": "construction", "bie_inypkl2": "occupancy"}
OWNERS = {"DEV": "public", "KOP": "cooperative", "OZE": "private"}
USES = {
    "EV": "residential_single",
    "APT": "residential_multi",
    "HALK": "residential_communal",
    "OTEL": "hotel",
    "OFIS": "office",
    "TOPTAN": "retail",
    "TRAFIK": "transport_communication",
    "SANAYI": "industrial_storage",
    "KAMU": "public_education_health",
    "DIGER": "other_non_residential",
}
#: measure letter → indicator suffix
MEASURES = {"A": "buildings", "B": "floor_area", "D": "dwellings"}


def permits(indicator_id: str) -> list[dict]:
    kind, _, measure = indicator_id.removesuffix("_monthly").partition("_permit_")
    group = next(g for g, k in PERMIT_GROUPS.items() if k == kind)
    letter = next(k for k, v in MEASURES.items() if v == measure)
    payload = json.loads((DOWNLOADS / f"{group}.json").read_text(encoding="utf-8"))
    totals: dict[dt.date, float] = {}
    summed: dict[dt.date, float] = {}
    records = []
    for series, date, value in rows_of(payload):
        parts = series["SERIE_CODE"].split(".")
        use, owner, code = parts[3], parts[4], parts[5]
        if code != letter:
            continue
        if use == "TOPLAM" and owner == "TOP":
            totals[date] = value
        if use not in USES or owner not in OWNERS:
            continue
        summed[date] = summed.get(date, 0.0) + value
        records.append(
            {
                "area_id": "TR",
                "area_level": "country",
                "period_start": date,
                "dims": format_dims(
                    {"building_use": USES[use], "permit_owner": OWNERS[owner]}
                ),
                "value": value,
            }
        )
    off = [
        d for d, v in totals.items() if abs(summed.get(d, 0.0) - v) > max(2, v * 1e-4)
    ]
    if off:
        raise ValueError(f"{indicator_id}: kalemler toplami tutmuyor, ornek {off[:3]}")
    return records


# endregion

# region House price index 2017=100, 26 regions

REGION = re.compile(r"^TR ?([0-9A-C]\d) \(")


def house_price_regions() -> list[dict]:
    payload = json.loads((DOWNLOADS / "bie_hkfe.json").read_text(encoding="utf-8"))
    records = []
    for series, date, value in rows_of(payload):
        found = REGION.match(series["SERIE_NAME"])
        if found:
            area, level = "TR" + found.group(1), "nuts2"
        elif series["SERIE_NAME"].startswith("Konut Fiyat Endeksi"):
            area, level = "TR", "country"
        else:
            raise KeyError("taninmayan seri: " + series["SERIE_NAME"])
        records.append(
            {
                "area_id": area,
                "area_level": level,
                "period_start": date,
                "dims": "",
                "value": value,
            }
        )
    if len({r["area_id"] for r in records}) != 27:
        raise ValueError("26 bolge + Turkiye beklenirdi")
    return records


# endregion

BUILDERS = {
    **{ident: (lambda i=ident: index_tree(i)) for ident in INDEX_TREES},
    "property_sales_monthly": property_sales,
    **{
        f"{kind}_permit_{measure}_monthly": (
            lambda i=f"{kind}_permit_{measure}_monthly": permits(i)
        )
        for kind in PERMIT_GROUPS.values()
        for measure in MEASURES.values()
    },
    "house_price_index_2017": house_price_regions,
}


class EvdsSeries:
    source_id = "cbrt_evds"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 14)
    indicator_id = ""

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        frame = pl.DataFrame(BUILDERS[self.indicator_id]())
        if frame.select("area_id", "period_start", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni anahtar iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
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


EVDS_SERIES_ADAPTERS = {
    "evds_" + ident: type(
        "Evds" + "".join(p.title() for p in ident.split("_")),
        (EvdsSeries,),
        {"indicator_id": ident},
    )
    for ident in BUILDERS
}
