"""Completed education level and literacy by district — MEDAS, 2008-2025.

Pulled 2026-09-12 (`fetch_medas_districts.py --konu egitim`, branch koy-kaydi) one province
and one year per file: `medas/ilce/egitim-duzeyi-il16-ilce-kirilim-2025.csv`,
`okuma-yazma-il16-ilce-kirilim-2025.csv`. The export is the transposed MEDAS table with
district columns (`Bilecik(Bozüyük)-1210`) and a `sex ve age ve level` row label, the
same shape the topic adapter already reads; its reader is reused, district codes resolved
per year.

TÜİK changed the level list over the years (İlköğretim appears alongside İlkokul and
Ortaokul; Doktora and Yüksek Lisans are separate from 2014), so the levels are stored as
published and not folded.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get
from . import tuik_topics
from .tuik_median_age import single_province_regions
from .tuik_vital_district import districts_by_code

DOWNLOADS = RAW / "medas" / "ilce"

EDUCATION = {
    "Okuma Yazma Bilmeyen": "illiterate",
    "Okuma Yazma Bilen Fakat Bir Okul Bitirmeyen": "literate_no_school",
    "İlkokul": "primary",
    "İlköğretim": "basic_8_year",
    "Ortaokul Veya Dengi Meslek Ortaokul": "lower_secondary",
    "Lise Ve Dengi Meslek Okulu": "upper_secondary",
    "Yüksekokul Veya Fakülte": "higher",
    "Yüksek Lisans (5 Veya 6 Yıllık Fakülteler Dahil)": "masters",
    "Doktora": "doctorate",
    "Bilinmeyen": "unknown",
}
LITERACY = {
    "Okuma Yazma Bilen": "literate",
    "Okuma Yazma Bilmeyen": "illiterate",
    "Bilinmeyen": "unknown",
}
AGES = [
    "6-13",
    "14-17",
    "18-21",
    "22-24",
    "25-29",
    "30-34",
    "35-39",
    "40-44",
    "45-49",
    "50-54",
    "55-59",
    "60-64",
    "65+",
]

tuik_topics.NAMES["education_level"] = EDUCATION
tuik_topics.NAMES["literacy"] = LITERACY
tuik_topics.NAMES["age"] = {a: a for a in AGES}

#: indicator id → (file prefix, dims in label order)
SPECS = {
    "education_level_district": ("egitim-duzeyi", ("sex", "age", "education_level")),
    "literacy_district": ("okuma-yazma", ("sex", "age", "literacy")),
}


class DistrictEducation:
    source_id = "tuik_medas"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 12)
    indicator_id = ""

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        prefix, dims = SPECS[self.indicator_id]
        codes = districts_by_code()
        single = single_province_regions()
        records: list[dict] = []
        for path in sorted(raw.glob(prefix + "-il*-ilce-kirilim-*.csv")):
            records.extend(
                tuik_topics.read_export(
                    path, self.indicator_id, dims, single, "", codes
                )
            )
        if not records:
            raise ValueError("dosya yok: " + self.indicator_id)
        frame = pl.DataFrame(records)
        # The province files overlap nowhere; a repeat means a district column was read
        # under two provinces' files.
        if frame.select("area_id", "year", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni ilce-yil-kirilim iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
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


EDUCATION_DISTRICT_ADAPTERS = {
    "tuik_" + ident: type(
        "Tuik" + "".join(p.title() for p in ident.split("_")),
        (DistrictEducation,),
        {"indicator_id": ident},
    )
    for ident in SPECS
}
