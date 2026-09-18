r"""TÜİK's population portal: the commonest names given to babies born in a year.

`scripts/fetch_tuik_names.py` saves one JSON file per province, sex and birth year in
`C:\veri-ham\tuik_isim\`, straight from the portal's own table endpoint. The rows carry
the plate code, so the province needs no name matching — which matters here, because the
portal's own select box misspells Siirt as SİİRT.

What the numbers are: the 30 commonest names among babies born in that province in that
year, and how many babies got each. Not the whole distribution — a name outside a
province's top 30 is simply absent, so the rows do not add up to the births of the year
and a name's national total is not the sum of its provinces. Türkiye is fetched as its own
row (plate code 0) for exactly that reason, and is stored at country level.

Files hold more than 30 rows where the 30th place is tied, and fewer than 30 where the
province runs out of names first: TÜİK does not publish a name given to fewer than three
babies, so Tunceli, Bayburt and Ardahan stop at 18-25 names. Every row the portal returns
is kept, and `Sira` is the portal's own ranking, not ours.
"""

from __future__ import annotations

import datetime as dt
import json
from functools import cache
from pathlib import Path

import polars as pl

from ..config import RAW

FOLDER = (
    RAW / "tuik_isim" if (RAW / "tuik_isim").exists() else Path("C:/veri-ham/tuik_isim")
)
SEXES = {1: "male", 2: "female"}
RETRIEVED = dt.date(2026, 9, 18)
VINTAGE = "2026-03"  # the portal stamps its rows 31.03.2026


@cache
def rows() -> pl.DataFrame:
    """Every saved file as one frame: area, year, name, sex, count."""
    records = []
    for path in sorted(FOLDER.glob("*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            code = int(row["IlKodu"])
            name = str(row["Isim"]).strip()
            if ";" in name or "=" in name:
                raise ValueError(f"isim dims'i bozar: {name}")
            records.append(
                {
                    "area_id": "TR" if code == 0 else f"TR-{code:02d}",
                    "area_level": "country" if code == 0 else "province",
                    "year": int(row["DogumYil"]),
                    "dims": f"given_name={name};sex={SEXES[int(row['Cinsiyet'])]}",
                    "value": float(row["Sayi"]),
                }
            )
    if not records:
        raise FileNotFoundError(
            f"isim dosyası yok: {FOLDER} (scripts/fetch_tuik_names.py)"
        )
    frame = pl.DataFrame(records)
    provinces = frame.filter(pl.col("area_level") == "province")["area_id"].n_unique()
    if provinces != 81:
        raise ValueError(f"TÜİK isim: {provinces} il")
    return frame


class BabyNames:
    """The 30 commonest names among the year's newborns, by province and sex."""

    indicator_id = "baby_names"
    source_id = "tuik_nip"
    unit = "person"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        return (
            rows()
            .with_columns(
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.date(pl.col("year"), 1, 1).alias("period_start"),
                pl.lit("annual").alias("frequency"),
                pl.lit(self.unit).alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit(VINTAGE).alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(RETRIEVED).alias("retrieved_at"),
            )
            .select(
                "indicator_id",
                "area_id",
                "area_level",
                "period_start",
                "frequency",
                "value",
                "unit",
                "dims",
                "quality_flag",
                "vintage",
                "source_id",
                "retrieved_at",
            )
        )


TUIK_NAMES_ADAPTERS = {"baby_names": BabyNames}
