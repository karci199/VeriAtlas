"""YÖK Atlas: university programmes, quotas and placement scores.

Source: the YÖK Atlas web application's public API (no login), two requests:
`POST /api/tercih-kilavuz/search {}` — the 2026 ÖSYM guide, one row per programme (21,493:
university, city/district, quota, base score and rank, fee, scholarship, language, academic
staff) — and `POST /api/netler/search {}` — base score, OBP and mean TYT/AYT nets of the
students placed, per programme and year (2023-2025). Saved as `raw/yokatlas/*.json` by
`scripts/fetch_yokatlas.py`.

The data is per programme, not per area. Two outputs:

* `public/yokatlas_programs.parquet` and `public/yokatlas_nets.parquet` — the programme
  tables, flattened (`scripts/build_yokatlas_tables.py`);
* province indicators here: quota and programme count by university type and level, from the
  guide's programme city (`ilKodu`, the plate code). KKTC and abroad programmes have no
  province and are left out of the indicators, kept in the programme table.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..config import RAW

GUIDE = RAW / "yokatlas" / "kilavuz_2026.json"
UNIVERSITY_TYPES = {"DEVLET": "state", "VAKIF": "foundation"}
LEVELS = {"LISANS": "bachelor", "ÖNLISANS": "associate"}


def guide() -> pl.DataFrame:
    rows = json.loads(GUIDE.read_text(encoding="utf-8"))["content"]
    return pl.DataFrame(rows, infer_schema_length=None)


class YokAtlas:
    source_id = "yok_atlas"
    indicator_id = ""
    unit = ""

    def fetch(self) -> Path:
        return GUIDE

    def value(self) -> pl.Expr:
        raise NotImplementedError

    def parse(self, raw: Path) -> pl.DataFrame:
        frame = guide()
        year = frame["yil"].unique().to_list()
        if len(year) != 1:
            raise ValueError(f"YÖK Atlas kılavuzu birden çok yıl: {year}")
        unknown = set(frame["universiteTuru"].unique()) - {
            *UNIVERSITY_TYPES,
            "KKTC",
            "YURTDIŞI",
        }
        if unknown or set(frame["birimTuruAdi"].unique()) - set(LEVELS):
            raise ValueError(f"YÖK Atlas: tanınmayan tür {unknown}")
        # State universities also run programmes abroad (METU and İTÜ in KKTC, code 999;
        # SBÜ Sarajevo, 992): no province, so outside these indicators.
        turkish = frame.filter(pl.col("universiteTuru").is_in(list(UNIVERSITY_TYPES)))
        if turkish["ilKodu"].is_null().any():
            raise ValueError("YÖK Atlas: il kodu boş program")
        abroad = turkish.filter(pl.col("ilKodu") > 81)
        if abroad["ilKodu"].is_in([999, 992]).not_().any():
            raise ValueError(
                f"YÖK Atlas: tanınmayan il kodu {abroad['ilKodu'].unique()}"
            )
        domestic = turkish.filter(pl.col("ilKodu") <= 81)
        out = (
            domestic.group_by("ilKodu", "universiteTuru", "birimTuruAdi")
            .agg(self.value().alias("value"))
            .select(
                pl.format("TR-{}", pl.col("ilKodu").cast(pl.Utf8).str.zfill(2)).alias(
                    "area_id"
                ),
                pl.format(
                    "program_level={};university_type={}",
                    pl.col("birimTuruAdi").replace_strict(LEVELS),
                    pl.col("universiteTuru").replace_strict(UNIVERSITY_TYPES),
                ).alias("dims"),
                pl.col("value").cast(pl.Float64),
            )
        )
        if out["area_id"].n_unique() != 81:
            raise ValueError(f"YÖK Atlas: {out['area_id'].n_unique()} il")
        return out.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.lit(dt.date(year[0], 1, 1)).alias("period_start"),
            pl.lit("annual").alias("frequency"),
            pl.lit(self.unit).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(f"{year[0]}-07").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
        )


class YokAtlasQuota(YokAtlas):
    indicator_id = "university_quota"
    unit = "person"

    def value(self) -> pl.Expr:
        return pl.col("kontenjan").fill_null(0).sum()


class YokAtlasPrograms(YokAtlas):
    indicator_id = "university_programs"
    unit = "program"

    def value(self) -> pl.Expr:
        return pl.len()


YOKATLAS_ADAPTERS = {
    "university_quota": YokAtlasQuota,
    "university_programs": YokAtlasPrograms,
}
