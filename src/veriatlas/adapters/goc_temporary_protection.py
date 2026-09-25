r"""Syrians under temporary protection by province (Presidency of Migration Management).

ADNKS, and so every population figure in the warehouse, leaves out people under
temporary protection. goc.gov.tr/gecici-koruma5638 publishes their number by province
as an image; its robots.txt allows the page but disallows `/kurumlar`, where the image
file sits, so the table was read off the rendered page and typed into
`RAW/goc/gecici_koruma_il_<date>.csv` (2026-09-25). Three checks passed on that
transcription: 81 provinces summing to the page's own total (2.210.644); in every row
Syrians + province population = "people living in the province"; and the page's
province population equals ADNKS 2025 in all 81 provinces.

A snapshot: the page shows one date and keeps no series, so rows are filed under the
snapshot's year and replaced when a newer table is typed in.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from .skrs_facilities import upper_tr

FOLDER = RAW / "goc"
SOURCE_ID = "goc_idaresi"
PAGE_TOTAL = 2_210_644


def dump() -> Path:
    found = sorted(FOLDER.glob("gecici_koruma_il_*.csv"))
    if not found:
        raise FileNotFoundError(f"geçici koruma tablosu yok: {FOLDER}")
    return found[-1]


class TemporaryProtection:
    indicator_id = "temporary_protection_syrians"
    source_id = SOURCE_ID

    def fetch(self) -> Path:
        return dump()

    def parse(self, raw: Path) -> pl.DataFrame:
        snapshot = dt.date.fromisoformat(raw.stem.rsplit("_", 1)[1])
        areas = load_areas().filter(pl.col("area_level") == "province")
        index = {
            upper_tr(n): a
            for n, a in zip(areas["name_tr"], areas["area_id"], strict=True)
        }
        with raw.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        values = {}
        for row in rows:
            area = index.get(upper_tr(row["il"]))
            if area is None:
                raise KeyError(f"tanınmayan il: {row['il']!r}")
            count, population = int(row["kayitli_suriyeli"]), int(row["il_nufusu"])
            if count + population != int(row["ilde_yasayan_toplam"]):
                raise ValueError(f"{row['il']}: satır toplamı tutmuyor")
            values[area] = count
        if len(values) != 81:
            raise ValueError(f"81 il yerine {len(values)}")
        if sum(values.values()) != PAGE_TOTAL and raw.stem.endswith("2026-09-17"):
            raise ValueError("toplam sayfadaki 2.210.644 ile tutmuyor")
        records = [
            {
                "indicator_id": self.indicator_id,
                "area_id": area,
                "area_level": level,
                "period_start": dt.date(snapshot.year, 1, 1),
                "frequency": "annual",
                "dims": "",
                "value": float(value),
                "unit": "person",
                "quality_flag": "measured",
                "vintage": snapshot.strftime("%Y-%m"),
                "source_id": self.source_id,
                "retrieved_at": dt.date(2026, 9, 25),
            }
            for level, items in (
                ("province", values.items()),
                ("country", [("TR", sum(values.values()))]),
            )
            for area, value in items
        ]
        return pl.DataFrame(records)


GOC_ADAPTERS = {"temporary_protection_syrians": TemporaryProtection}
