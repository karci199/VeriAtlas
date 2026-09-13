"""Vehicle-kilometres — TÜİK Veri Portalı (not in MEDAS), Türkiye, yearly 2015-2024.

Pulled 2026-09-13 from `veriportali.tuik.gov.tr/api/tr/dataflows/<id>/file/csv` inside a
browser session (the API answers "Erişim engellendi" to a plain client):
`DF_TASIT_KILOMETRE_TASIT_CINS_V2` → `tasit_km_tasit_cins.psv` and
`DF_TASIT_KILOMETRE_YAS_GRUP_V2` → `tasit_km_yas_grup.psv`, reduced to the columns that
vary (the rest are "Türkiye", "Yıllık" and empty).

The vehicle-type column of the first file mixes two lists: vehicle types, and under
"Otomobil" the car's fuels. They are split into separate indicators, never summed
together. Vehicle counts in these files are not loaded — the MEDAS series already has them.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "tuik_portal"

TYPES = {
    "Otomobil": "car",
    "Minibüs": "minibus",
    "Otobüs": "bus",
    "Kamyonet": "pickup",
    "Kamyon": "truck",
    "Çekici": "tractor_unit",
    "Motosiklet": "motorcycle",
    "Özel Amaçlı": "special_purpose",
}
FUELS = {
    "Benzinli": "petrol",
    "Dizel": "diesel",
    "LPG": "lpg",
    "Hibrit": "hybrid",
    "Elektrik": "electric",
}
AGES = {"0-1", "2-4", "5-9", "10-14", "15-19", "20-24", "25+"}
KM = "Taşıt-Km (Milyon)"
MEAN = "Ortalama Yıl-Km"


def rows_by_type(path: Path) -> list[dict]:
    out = []
    frame = pl.read_csv(path, separator="|", infer_schema=False)
    known = set(TYPES) | set(FUELS) | {"Toplam"}
    unknown = set(frame["tasit"]) - known
    if unknown:
        raise KeyError(
            "tasit-km: taninmayan tasit/yakit: " + ", ".join(sorted(unknown))
        )
    for row in frame.iter_rows(named=True):
        name, measure = row["tasit"], row["gosterge"]
        if name == "Toplam" or measure not in (KM, MEAN) or not row["deger"]:
            continue
        if name in TYPES:
            ident = "vehicle_km" if measure == KM else "vehicle_mean_annual_km"
            dims = {"vehicle_type": TYPES[name]}
        else:
            ident = "car_km_by_fuel" if measure == KM else "car_mean_annual_km_by_fuel"
            dims = {"fuel": FUELS[name]}
        out.append(
            {
                "indicator_id": ident,
                "year": int(row["yil"]),
                "dims": format_dims(dims),
                "value": float(row["deger"]),
            }
        )
    return out


def rows_by_age(path: Path) -> list[dict]:
    out = []
    frame = pl.read_csv(path, separator="|", infer_schema=False)
    for row in frame.iter_rows(named=True):
        if (
            row["gosterge"] != KM
            or row["tasit"] == "Toplam"
            or row["yas"] == "Toplam"
            or not row["deger"]
        ):
            continue
        if row["tasit"] not in TYPES or row["yas"] not in AGES:
            raise KeyError(
                "tasit-km yas: taninmayan: " + row["tasit"] + " / " + row["yas"]
            )
        dims = {"vehicle_type": TYPES[row["tasit"]], "vehicle_age_band": row["yas"]}
        out.append(
            {
                "indicator_id": "vehicle_km_by_age",
                "year": int(row["yil"]),
                "dims": format_dims(dims),
                "value": float(row["deger"]),
            }
        )
    return out


class VehicleKm:
    source_id = "tuik_veri_portali"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 13)
    indicator_id = ""

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = rows_by_type(raw / "tasit_km_tasit_cins.psv") + rows_by_age(
            raw / "tasit_km_yas_grup.psv"
        )
        frame = pl.DataFrame(
            [r for r in records if r["indicator_id"] == self.indicator_id]
        )
        if frame.is_empty():
            raise ValueError("satir yok: " + self.indicator_id)
        if frame.select("year", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni yil-kirilim iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
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


VEHICLE_KM_ADAPTERS = {
    "tuik_" + ident: type(
        "Tuik" + "".join(p.title() for p in ident.split("_")),
        (VehicleKm,),
        {"indicator_id": ident},
    )
    for ident in (
        "vehicle_km",
        "vehicle_mean_annual_km",
        "car_km_by_fuel",
        "car_mean_annual_km_by_fuel",
        "vehicle_km_by_age",
    )
}
