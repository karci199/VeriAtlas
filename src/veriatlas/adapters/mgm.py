r"""MGM climate normals and records by province.

`scripts/fetch_mgm.py` saves the provincial pages of
mgm.gov.tr/veridegerlendirme/il-ve-ilceler-istatistik.aspx to
`C:\veri-ham\mgm\iklim.json` — one entry per province, the HTML tables as rows of cells.

Two sets of normals are published and both are loaded, told apart by the ``normals_period``
dimension:

* ``station`` — the average over the station's whole measurement period, which differs by
  province (Ankara 1927-2025, Şırnak 1970-2025). The first and last year are loaded as
  ``mgm_measurement_period`` so that a reader can see what the average covers.
* ``1991_2020`` — the standard 30-year normals, published for 79 of the 81 provinces.

Monthly figures carry ``month=1…12``; the yearly column of the page is empty in the data rows
and is not loaded. The station-period table also prints the highest and lowest temperature
ever measured in each month (``record_max``, ``record_min``).

The records at the bottom of the page — the heaviest daily rainfall, the fastest wind and the
deepest snow — are single events, so they are loaded with their own date as the period.

The two tables punctuate differently (station "0,4", 1991-2020 "0.9"); both are read.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..config import RAW

FOLDER = RAW / "mgm" if (RAW / "mgm").exists() else Path("C:/veri-ham/mgm")
PERIOD = re.compile(r"Ölçüm Periyodu\s*\(\s*(\d{4})\s*-\s*(\d{4})\s*\)")
DATE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
# row label -> (indicator, dims without the month)
ROWS = {
    "Ortalama Sıcaklık (°C)": ("mgm_temperature", "temperature_measure=mean"),
    "Ortalama En Yüksek Sıcaklık (°C)": (
        "mgm_temperature",
        "temperature_measure=mean_max",
    ),
    "Ortalama En Düşük Sıcaklık (°C)": (
        "mgm_temperature",
        "temperature_measure=mean_min",
    ),
    "En Yüksek Sıcaklık (°C)": ("mgm_temperature", "temperature_measure=record_max"),
    "En Düşük Sıcaklık (°C)": ("mgm_temperature", "temperature_measure=record_min"),
    "Ortalama Güneşlenme Süresi (saat)": ("mgm_sunshine", ""),
    "Ortalama Yağışlı Gün Sayısı": ("mgm_rainy_days", ""),
    "Aylık Toplam Yağış Miktarı Ortalaması (mm)": ("mgm_precipitation", ""),
}
#: the three records, in the order the page prints them: (indicator, unit suffix)
RECORDS = (
    ("mgm_record_daily_precipitation", "mm"),
    ("mgm_record_wind_speed", "m/sn"),
    ("mgm_record_snow_depth", "cm"),
)
UNITS = {
    "mgm_temperature": "celsius",
    "mgm_sunshine": "hour",
    "mgm_rainy_days": "day",
    "mgm_precipitation": "mm",
    "mgm_measurement_period": "years",
    "mgm_record_daily_precipitation": "mm",
    "mgm_record_wind_speed": "metre_per_second",
    "mgm_record_snow_depth": "cm",
}
NORMALS = {"A": "station", "H": "1991_2020"}
Row = tuple[
    str, str, str, dt.date, str
]  # indicator, area, dims, period start, frequency


def number(cell: str) -> float | None:
    cell = cell.replace(",", ".").strip()
    return float(cell) if re.fullmatch(r"-?\d+(\.\d+)?", cell) else None


def load_pages() -> dict:
    path = FOLDER / "iklim.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} yok (scripts/fetch_mgm.py)")
    return json.loads(path.read_text(encoding="utf-8"))


def read_province(area: str, entry: dict) -> dict[Row, float]:
    out: dict[Row, float] = {}
    for kind, rows in entry["tables"].items():
        normals = NORMALS[kind]
        table = rows[0]
        if len(table[0]) < 13:
            raise ValueError(f"MGM {area} {kind}: başlık {table[0][:3]}")
        years = None
        for row in table[1:]:
            period = PERIOD.search(row[0])
            if period:
                years = (int(period.group(1)), int(period.group(2)))
                continue
            found = ROWS.get(row[0])
            if found is None or len(row) < 13:
                continue
            indicator, measure = found
            for month, cell in enumerate(row[1:13], start=1):
                value = number(cell)
                if value is None:
                    continue
                dims = ";".join(
                    filter(
                        None, (measure, f"month={month}", f"normals_period={normals}")
                    )
                )
                # the normals have no year of their own: they are filed under the last year
                # of the period they average (2020 for the standard normals)
                end = years[1] if years else 2020
                out[(indicator, area, dims, dt.date(end, 1, 1), "annual")] = value
        if years:
            for bound, year in zip(("start", "end"), years, strict=True):
                out[
                    (
                        "mgm_measurement_period",
                        area,
                        f"period_bound={bound}",
                        dt.date(years[1], 1, 1),
                        "annual",
                    )
                ] = float(year)
        if kind == "A" and len(rows) > 1 and len(rows[1]) > 1:
            cells = rows[1][1]
            for index, (indicator, suffix) in enumerate(RECORDS):
                date_cell, value_cell = cells[2 * index : 2 * index + 2]
                stamp = DATE.match(date_cell.strip())
                value = number(value_cell.replace(suffix, ""))
                if not stamp or value is None:
                    continue
                day, month, year = (int(g) for g in stamp.groups())
                out[(indicator, area, "", dt.date(year, month, day), "daily")] = value
    return out


def load_all() -> dict[Row, float]:
    pages = load_pages()
    if len(pages) < 81:
        raise ValueError(f"MGM: {len(pages)} il")
    out: dict[Row, float] = {}
    for area, entry in pages.items():
        out.update(read_province(area, entry))
    return out


_CACHE: dict[Row, float] = {}


class Mgm:
    source_id = "mgm"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        if not _CACHE:
            _CACHE.update(load_all())
        records = [
            {
                "area_id": area,
                "period_start": start,
                "frequency": frequency,
                "dims": dims,
                "value": value,
            }
            for (indicator, area, dims, start, frequency), value in _CACHE.items()
            if indicator == self.indicator_id
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit("province").alias("area_level"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(UNITS[self.indicator_id]).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit("mgm").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


MGM_ADAPTERS = {
    indicator: type(f"Mgm_{indicator}", (Mgm,), {"indicator_id": indicator})
    for indicator in UNITS
}
