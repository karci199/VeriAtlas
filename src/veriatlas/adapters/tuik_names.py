r"""TÜİK's population portal: the commonest names given to babies born in a year.

`scripts/fetch_tuik_names.py` saves one JSON file per province, sex and birth year in
`C:\veri-ham\tuik_isim\`, straight from the portal's own table endpoint. The rows carry
the plate code, so the province needs no name matching — which matters here, because the
portal's own select box misspells Siirt as SİİRT.

Three tables share the endpoint, and this module reads all three: the names given to the
year's newborns, the commonest first names among everyone alive, and the commonest
surnames.

How much each table gives is not the same, although all three pages promise "the first
30". Asked for 300 rows, the newborn table hands over every name above TÜİK's floor — up
to 266 names for a province-year, 18 for the smallest — while the other two really do stop
at 30, give or take a tie. So the newborn series is close to the whole distribution and the
other two are a top cut. Not the whole distribution — a name outside a
province's top 30 is simply absent, so the rows do not add up to the births of the year
and a name's national total is not the sum of its provinces. Türkiye is fetched as its own
row (plate code 0) for exactly that reason, and is stored at country level.

TÜİK does not publish a name carried by fewer than three people, which is what cuts the
newborn lists off: Tunceli, Bayburt and Ardahan run out at 18-25 names. Every row the
portal returns is kept, and `Sira` is its ranking, not ours.
"""

from __future__ import annotations

import datetime as dt
import json
from functools import cache
from pathlib import Path

import polars as pl

from ..config import RAW

ROOT = (
    RAW / "tuik_isim" if (RAW / "tuik_isim").exists() else Path("C:/veri-ham/tuik_isim")
)
SEXES = {1: "male", 2: "female"}
RETRIEVED = dt.date(2026, 9, 18)
VINTAGE = "2026-03"  # the portal stamps its rows 31.03.2026


@cache
def rows(folder: str, field: str, dim: str, year_field: str) -> pl.DataFrame:
    """One dataset's saved files as a frame: area, year, dims, value.

    `field` is the portal's column for the name itself, `year_field` its column for the
    year — the newborn table calls it DogumYil and the other two Yil.
    """
    where = ROOT / folder
    records = []
    for path in sorted(where.glob("*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            code = int(row["IlKodu"])
            name = str(row[field]).strip()
            if ";" in name or "=" in name:
                raise ValueError(f"ad dims'i bozar: {name}")
            dims = f"{dim}={name}"
            sex = int(row.get("Cinsiyet") or 0)  # surnames carry a 0 here, not a sex
            if sex:
                dims += f";sex={SEXES[sex]}"
            records.append(
                {
                    "area_id": "TR" if code == 0 else f"TR-{code:02d}",
                    "area_level": "country" if code == 0 else "province",
                    "year": int(row[year_field]),
                    "dims": dims,
                    "value": float(row["Sayi"]),
                }
            )
    if not records:
        raise FileNotFoundError(f"dosya yok: {where} (scripts/fetch_tuik_names.py)")
    frame = pl.DataFrame(records)
    provinces = frame.filter(pl.col("area_level") == "province")["area_id"].n_unique()
    if provinces != 81:
        raise ValueError(f"TÜİK {folder}: {provinces} il")
    return frame


class BabyNames:
    """The 30 commonest names among the year's newborns, by province and sex."""

    indicator_id = "baby_names"
    source_id = "tuik_nip"
    unit = "person"
    folder = "bebek"
    field = "Isim"
    dim = "given_name"
    year_field = "DogumYil"

    def fetch(self) -> Path:
        return ROOT / self.folder

    def parse(self, raw: Path) -> pl.DataFrame:
        return (
            rows(self.folder, self.field, self.dim, self.year_field)
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


class CommonNames(BabyNames):
    """The commonest first names among everyone alive, by province and sex.

    The same cut as the newborn table — a top 30 with a three-person floor — but over the
    living population, so it moves slowly: it is the stock the birth table is the flow of.
    """

    indicator_id = "common_names"
    folder = "isim"
    year_field = "Yil"


class CommonSurnames(BabyNames):
    """The commonest surnames, by province. The portal publishes no sex breakdown here."""

    indicator_id = "common_surnames"
    folder = "soyisim"
    field = "SoyIsim"
    dim = "surname"
    year_field = "Yil"


TUIK_NAMES_ADAPTERS = {
    "baby_names": BabyNames,
    "common_names": CommonNames,
    "common_surnames": CommonSurnames,
}
