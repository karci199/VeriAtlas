"""University minimum placement rank by province and programme group — YÖK Atlas, 2022-2025.

The 2026 YKS guide in YÖK Atlas (`yokatlas/kilavuz_2026.json`, see `yokatlas.py`) gives, for
every programme still open in 2026, the lowest success rank placed in the last four years:
`basariSirasi` (2025), `basariSirasi1` (2024), `basariSirasi2` (2023), `basariSirasi3`
(2022). A rank, unlike a score, compares across years. Programmes closed before 2026 are not
in the guide, so a group's value covers only its surviving programmes. The value is the
median over programmes of province × programme group × level × university type; KKTC and
abroad programmes (no province) are left out. Rank 0 or empty means no one was placed.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get, load
from ..schema import format_dims
from .osym_programs import slug

GUIDE = RAW / "yokatlas" / "kilavuz_2026.json"
YEARS = {
    "basariSirasi": 2025,
    "basariSirasi1": 2024,
    "basariSirasi2": 2023,
    "basariSirasi3": 2022,
}
LEVELS = {"LISANS": "bachelor", "ÖNLISANS": "associate", "ONLISANS": "associate"}


class YokAtlasMinRank:
    source_id = "yok_atlas"
    vintage = "2026-07"
    retrieved_at = dt.date(2026, 9, 26)
    indicator_id = "university_min_rank"

    def fetch(self) -> Path:
        if not GUIDE.exists():
            raise FileNotFoundError("YOK Atlas kilavuzu yok: " + str(GUIDE))
        return GUIDE

    def parse(self, raw: Path) -> pl.DataFrame:
        rows = json.loads(raw.read_text(encoding="utf-8"))["content"]
        guide = pl.DataFrame(rows, infer_schema_length=None).filter(
            pl.col("ilKodu").is_not_null() & pl.col("ilKodu").is_between(1, 81)
        )
        long = []
        for field, year in YEARS.items():
            part = guide.select(
                pl.col("ilKodu"),
                pl.col("birimGrupAdi"),
                pl.col("birimTuruAdi"),
                pl.col("universiteTuru"),
                pl.col(field).cast(pl.Float64, strict=False).alias("rank"),
            ).with_columns(pl.lit(year).alias("year"))
            long.append(part)
        df = pl.concat(long).filter(pl.col("rank").is_not_null() & (pl.col("rank") > 0))
        unknown_level = set(df["birimTuruAdi"]) - set(LEVELS)
        if unknown_level:
            raise KeyError(
                "yokatlas: taninmayan duzey: " + ", ".join(sorted(unknown_level))
            )
        df = df.with_columns(
            pl.format("TR-{}", pl.col("ilKodu").cast(pl.String).str.zfill(2)).alias(
                "area_id"
            ),
            pl.col("birimGrupAdi")
            .map_elements(slug, return_dtype=pl.String)
            .alias("gcode"),
            pl.col("birimTuruAdi").replace_strict(LEVELS).alias("level"),
            pl.when(pl.col("universiteTuru").str.contains("VAKIF"))
            .then(pl.lit("foundation"))
            .otherwise(pl.lit("state"))
            .alias("utype"),
        )
        known = set(load().dimensions["program_group"].values_tr)
        unknown = set(df["gcode"]) - known
        if unknown:
            raise KeyError(
                "yokatlas: sozlukte olmayan grup: " + ", ".join(sorted(unknown)[:20])
            )
        keys = ["year", "gcode", "level", "utype"]
        prov = df.group_by(["area_id", *keys]).agg(
            pl.col("rank").median().alias("value")
        )
        tr = df.group_by(keys).agg(pl.col("rank").median().alias("value"))
        both = pl.concat(
            [prov, tr.with_columns(pl.lit("TR").alias("area_id")).select(prov.columns)]
        )
        indicator = get(self.indicator_id)
        return both.with_columns(
            pl.when(pl.col("area_id") == "TR")
            .then(pl.lit("country"))
            .otherwise(pl.lit("province"))
            .alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.struct("gcode", "level", "utype")
            .map_elements(
                lambda s: format_dims(
                    {
                        "program_group": s["gcode"],
                        "program_level": s["level"],
                        "university_type": s["utype"],
                    }
                ),
                return_dtype=pl.String,
            )
            .alias("dims"),
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
