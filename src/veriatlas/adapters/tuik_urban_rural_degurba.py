r"""Urban/rural population of Türkiye by DEGURBA (TÜİK ADNKS, 31 December 2025).

TÜİK's ADNKS annual release ("FavoriRaporlar.xlsx", downloaded by the user; a copy is
kept at `raw/tuik/adnks/FavoriRaporlar-2025.xlsx`) carries a sheet not published before:
"KENT-KIR SINIFLAMASI", the EU's Degree of Urbanisation (DEGURBA) classification of every
mahalle and köy — dense urban centre, semi-dense (intermediate) urban cluster, or rural —
built from 1 km² population-density grids (MAKS + ADNKS), independent of the pre-2013
legal city/village boundary this indicator's `_legal` sibling still uses.

This is the first classification that also splits büyükşehir (metropolitan) provinces,
which the legal definition counts as 100% "şehir" since the 2012 law erased their
belde/köy status. DEGURBA finds real rural population inside every büyükşehir (Ordu 41%,
Şanlıurfa 33%; the 30 büyükşehir average 12.5%, against 0% under the legal method) — see
`docs/degurba.md`.

Each mahalle/köy row is joined to its population by national registry number
("MAHALLE KAYIT NO" / "KÖY KAYIT NO"), never by name: both are unique nation-wide (no
duplicates in either sheet), but many names repeat (every ilçe has a "Merkez" mahalle),
so a name join would silently cross-wire population between provinces.

Row counts: population sheets carry the whole country (32,254 mahalle + 18,183 köy =
50,437); the classification sheet matches exactly, so the join drops nothing.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import openpyxl
import polars as pl

from ..config import RAW
from .kgm import province_id

FILE = RAW / "tuik" / "adnks" / "FavoriRaporlar-2025.xlsx"
CLASS_SHEET = "KENT-KIR SINIFLAMASI"
CODE = {
    "YOĞUN KENT": "dense_urban",
    "ORTA YOĞUN KENT": "semi_dense_urban",
    "KIR": "rural",
}


def read_all() -> pl.DataFrame:
    """One row per mahalle/köy: province, DEGURBA class, population."""
    book = openpyxl.load_workbook(FILE, read_only=True, data_only=True)

    def sheet_rows(name: str, header_row: int) -> list[tuple]:
        return [
            r
            for r in book[name].iter_rows(min_row=header_row, values_only=True)
            if r[0]
        ]

    mahalle_pop = {r[4]: r[10] for r in sheet_rows("MAHALLE NÜFUSU", 7)}
    koy_pop = {r[3]: r[7] for r in sheet_rows("KÖY NÜFUSU", 7)}
    classification = sheet_rows(CLASS_SHEET, 7)

    records = []
    for row in classification:
        il, mahalle_id, koy_id, klass = row[5], row[4], row[3], row[12]
        population = mahalle_pop.get(mahalle_id) if mahalle_id else koy_pop.get(koy_id)
        if population is None:
            raise ValueError(
                f"{il}: nüfusa bağlanamayan kayıt (mahalle {mahalle_id}, köy {koy_id})"
            )
        records.append({"il": il, "klass": CODE[klass], "population": population})
    book.close()

    # TÜİK's own gap, not a join bug: Adana(Aladağ)-Akören (id 176887, pop 872) is in the
    # population sheet but missing from the classification sheet entirely. One settlement
    # out of 50,437 (0.002% of population); tolerated rather than dropped silently.
    missing = len(mahalle_pop) + len(koy_pop) - len(classification)
    if not (0 <= missing <= 1):
        raise ValueError(
            f"sınıflama {len(classification)} satır, nüfus tabloları "
            f"{len(mahalle_pop) + len(koy_pop)} satır (beklenmeyen fark)"
        )
    return pl.DataFrame(records)


class UrbanRuralDegurba:
    source_id = "tuik_adnks"
    indicator_id = "urban_rural_degurba"

    def fetch(self) -> Path:
        return FILE

    def parse(self, raw: Path) -> pl.DataFrame:
        frame = read_all()
        grouped = frame.group_by("il", "klass").agg(
            pl.col("population").sum().alias("value")
        )
        ids = {il: province_id(il) for il in grouped["il"].unique().to_list()}
        grouped = grouped.with_columns(
            pl.col("il").replace_strict(ids).alias("area_id")
        )
        return grouped.select(
            pl.lit(self.indicator_id).alias("indicator_id"),
            "area_id",
            pl.lit("province").alias("area_level"),
            pl.date(2025, 12, 31).alias("period_start"),
            ("degurba=" + pl.col("klass")).alias("dims"),
            pl.col("value").cast(pl.Float64),
            pl.lit("annual").alias("frequency"),
            pl.lit("person").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 27)).alias("retrieved_at"),
        )


URBAN_RURAL_DEGURBA_ADAPTERS = {"urban_rural_degurba": UrbanRuralDegurba}
