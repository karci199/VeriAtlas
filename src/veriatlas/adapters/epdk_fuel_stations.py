r"""Fuel stations from EPDK's dealer licence register, by district and distributor.

Every forecourt in Türkiye holds a dealer licence (`BAY/...`) tied to one distributor, and
EPDK lists them all. The register is the count — not a brand's store finder — so every
brand is here at once and none is missing for want of a working finder.

The file is exported by hand (the query sits behind a reCAPTCHA; `Raporla` on the result
page writes every row, not just the 50 shown): `C:\veri-ham\epdk\akaryakit_bayilik\
petrolBayilikLisanslar_2026-09-21.xls`, 12.657 licences in force.

Placement is done by `yerlestir.py` next to the file and read from its output, because it
needs three steps that a reader should be able to audit line by line:

1. the register's own province/district columns — 12.187 rows;
2. a district name in the address — 86 rows. In metropolitan provinces the register
   still writes the pre-2012 district "MERKEZ", which no longer exists;
3. a neighbourhood name in the address that the 2025 neighbourhood register ties to a
   single district — 165 rows. Two districts, no placement.

191 stations (1,5%) stay unplaced and are listed in `yerlesmeyen.csv`. **So the province
total is taken from the register's province column (complete), and the district rows sum
to 98,5% of it.** 28 marine bunkering licences (`İhrakiye`) are not road stations and are
left out.

A cross-check, not a source: Petrol Ofisi's own finder lists 2.631 stations; the register
gives it 2.559.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import unicodedata
from pathlib import Path

import polars as pl
import xlrd

from ..config import RAW
from .networks import Unknown, province

FOLDER = RAW / "epdk" / "akaryakit_bayilik"
EXPORT = FOLDER / "petrolBayilikLisanslar_2026-09-21.xls"
PLACED = FOLDER / "istasyon_ilce.csv"
RETRIEVED = dt.date(2026, 9, 21)
MAX_UNPLACED = 0.02


def key(company: str) -> str:
    """'PETROL OFİSİ ANONİM ŞİRKETİ' -> 'petrol_ofisi': the name before the legal form."""
    name = re.split(r"\s+(?:ANON[İI]M|L[İI]M[İI]TED|A\.Ş\.)", company.strip())[0]
    name = unicodedata.normalize("NFKD", name.replace("İ", "I").replace("ı", "i"))
    return re.sub(
        r"[^a-z0-9]+", "_", name.encode("ascii", "ignore").decode().lower()
    ).strip("_")


class FuelStations:
    indicator_id = "fuel_stations"
    source_id = "epdk_lisans"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        sheet = xlrd.open_workbook(EXPORT).sheet_by_index(0)
        provinces: dict[tuple[str, str], int] = {}
        total = 0
        for r in range(1, sheet.nrows):
            if sheet.cell_value(r, 12) != "Akaryakıt":
                continue
            p = province(sheet.cell_value(r, 8))
            if not p or isinstance(p, Unknown):
                raise ValueError(f"tanınmayan il: {sheet.cell_value(r, 8)}")
            k = (p, key(sheet.cell_value(r, 9)))
            provinces[k] = provinces.get(k, 0) + 1
            total += 1
        districts: dict[tuple[str, str], int] = {}
        placed = 0
        with PLACED.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                k = (row["area_id"], key(row["dagitici"]))
                districts[k] = districts.get(k, 0) + 1
                placed += 1
        if (total - placed) / total > MAX_UNPLACED:
            raise ValueError(f"{total - placed}/{total} istasyon ilçeye yerleşmedi")
        rows = [("province", a, b, n) for (a, b), n in provinces.items()]
        rows += [("district", a, b, n) for (a, b), n in districts.items()]
        return pl.DataFrame(
            {
                "indicator_id": self.indicator_id,
                "area_id": [r[1] for r in rows],
                "area_level": [r[0] for r in rows],
                "period_start": dt.date(RETRIEVED.year, 1, 1),
                "frequency": "annual",
                "dims": [f"fuel_distributor={r[2]}" for r in rows],
                "value": [float(r[3]) for r in rows],
                "unit": "item",
                "quality_flag": "measured",
                "vintage": "2026-09",
                "source_id": self.source_id,
                "retrieved_at": RETRIEVED,
            }
        )


EPDK_FUEL_STATION_ADAPTERS = {"fuel_stations": FuelStations}
