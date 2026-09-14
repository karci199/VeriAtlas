"""CBRT housing and commercial property prices and rents, from EVDS3.

Downloaded by `scripts/fetch_evds_housing.py`, one JSON per EVDS data group under
`raw/evds/`. Stored at the frequency EVDS publishes — monthly indices, quarterly unit
prices and rents, annual shop and office unit prices — never summed or averaged to years.

Three kinds of area, told apart by the series itself:

- the Türkiye series, whose code ends in `.TR`;
- regions, named `TR10 (İstanbul)` or `TR 10 (İstanbul)`. The house price and rent indices
  mix levels: the west in İBBS-2 regions (`TR10`), the east in İBBS-1 regions (`TR7`),
  so the level is read from the length of the code, not assumed;
- provinces, whose name starts with the province (`Kahramanmaraş Konut Birim Kiraları`).

A series EVDS lists but refuses to serve (office unit prices of Osmaniye and Düzce) is
recorded in the raw file under `refused` and simply has no rows.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get

DOWNLOADS = RAW / "evds"

#: EVDS data group → indicator id.
GROUPS = {
    "bie_kfe": "house_price_index",
    "bie_ykfe": "new_house_price_index",
    "bie_yokfend": "existing_house_price_index",
    "bie_ykke": "new_tenant_rent_index",
    "bie_birimfiyat": "housing_unit_price",
    "bie_bk": "housing_unit_rent",
    "bie_tgfe": "commercial_property_price_index",
    "bie_dfe": "shop_price_index",
    "bie_ofe": "office_price_index",
    "bie_dbfy": "shop_unit_price",
    "bie_obfy": "office_unit_price",
}

FREQUENCY = {"AYLIK": "monthly", "ÜÇ AYLIK": "quarterly", "YILLIK": "annual"}
REGION = re.compile(r"^TR ?([0-9A-C]+) \(")


def province_ids() -> dict[str, str]:
    """Turkish province name → area id."""
    provinces = load_areas().filter(pl.col("area_level") == "province")
    return {row["name_tr"]: row["area_id"] for row in provinces.to_dicts()}


def area_of(series: dict, provinces: dict[str, str]) -> tuple[str, str]:
    """Area of a series, read from its Turkish name.

    Not from the code: the codes abbreviate at random (`IST`, `AFYON`) while the names
    spell every province out (`Afyonkarahisar Konut Birim Fiyatları`).
    """
    code, name = series["SERIE_CODE"], series["SERIE_NAME"]
    if code.rsplit(".", 1)[1] == "TR":
        return "TR", "country"
    found = REGION.match(name)
    if found:
        region = "TR" + found.group(1)
        return region, "nuts2" if len(found.group(1)) == 2 else "nuts1"
    matches = [p for p in provinces if name.startswith(p + " ")]
    if len(matches) == 1:
        return provinces[matches[0]], "province"
    raise KeyError("taninmayan EVDS serisi: " + code + " " + name)


def period_of(label: str, frequency: str) -> dt.date:
    if frequency == "monthly":
        year, month = label.split("-")
        return dt.date(int(year), int(month), 1)
    if frequency == "quarterly":
        year, quarter = label.split("-Q")
        return dt.date(int(year), 3 * int(quarter) - 2, 1)
    return dt.date(int(label), 1, 1)


class EvdsHousing:
    source_id = "cbrt_evds"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 14)
    group = ""
    indicator_id = ""

    def fetch(self) -> Path:
        return DOWNLOADS / (self.group + ".json")

    def parse(self, raw: Path) -> pl.DataFrame:
        payload = json.loads(raw.read_text(encoding="utf-8"))
        indicator = get(self.indicator_id)
        provinces = province_ids()
        records: list[dict] = []
        for series in payload["series"]:
            if series["SERIE_CODE"] in payload["refused"]:
                continue
            frequency = FREQUENCY[series["FREQUENCY_STR"]]
            if frequency != indicator.frequency:
                raise ValueError(
                    self.indicator_id + ": sozlukteki siklik farkli: " + frequency
                )
            area, level = area_of(series, provinces)
            column = series["SERIE_CODE"].replace(".", "_")
            for item in payload["items"]:
                if item.get(column) in (None, ""):
                    continue
                records.append(
                    {
                        "area_id": area,
                        "area_level": level,
                        "period_start": period_of(item["Tarih"], frequency),
                        "value": float(item[column]),
                    }
                )
        frame = pl.DataFrame(records)
        if frame.select("area_id", "period_start").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni alan-donem iki kez")
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit("").alias("dims"),
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


EVDS_HOUSING_ADAPTERS = {
    "evds_" + ident: type(
        "Evds" + "".join(p.title() for p in ident.split("_")),
        (EvdsHousing,),
        {"indicator_id": ident, "group": group},
    )
    for group, ident in GROUPS.items()
}
