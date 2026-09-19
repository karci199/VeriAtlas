r"""EPDK's electric vehicle charging station registry, by district.

Every charging station in Türkiye needs a licence, and EPDK's licence database lists them
one by one. This is not a scrape of somebody's store finder: it is the register, so the
count is the count — unlike `chain_stores`, where a brand's own finder is the only source
and a missing branch is invisible.

**The query is behind a reCAPTCHA**, so the files are exported by hand from
`lisans.epdk.gov.tr/epvys-web/faces/pages/lisans/elektrikSarjAgiIsletmeci/sarjIstasyonuOzetSorgula.xhtml`
(Sorgula → sayfa boyutu 500 → Raporla, one file per page) and dropped into
`C:\veri-ham\epdk\sarj_istasyonu\`. 34 pages on the 2026-09-19 export.

Two things the export does that a careless reading would get wrong:

* **Pages overlap.** Station `ŞRJ/9055` appears in more than one file, so rows are keyed on
  the station number rather than counted — 4.154 rows across the first eight files were
  3.500 distinct stations.
* **There is no province column.** The province and district are at the tail of the free
  text address: `… Beykoz / İSTANBUL`. 16.345 of 16.376 parse; the 31 that do not are
  addresses that simply stop early, and they are dropped rather than guessed at.

Each station also carries a socket table under it in the same sheet, which is why the row
count of a file is not its station count. Sockets are not read here: they are a measure of
capacity, not of presence, and they belong in their own indicator if we ever want them.
"""

from __future__ import annotations

import datetime as dt
import re
from functools import cache
from pathlib import Path

import polars as pl
import xlrd

from ..config import RAW
from .kgm import district_key, province_id, resolve_district

FOLDER = RAW / "epdk" / "sarj_istasyonu"
SOURCE = "epdk_lisans"

#: The snapshot's own date — the day the pages were exported.
SNAPSHOT = dt.date(2026, 9, 19)
RETRIEVED = dt.date(2026, 9, 19)

#: `... No:151 Beykoz / İSTANBUL` — district before the slash, province after it, both at
#: the very end. The province is written in capitals by the source, the district is not.
TAIL = re.compile(
    r"([A-Za-zÇĞİÖŞÜçğıöşü.\-\s]+?)\s*/\s*([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s]+?)\s*$"
)

#: Column positions in the export; it has no header row we can rely on.
STATION_NO = 1
ADDRESS = 8

#: Addresses that stop before naming a place. Measured at 31 of 16.376 (0,2%); a jump
#: would mean the export's address column changed shape.
MAX_UNPLACED = 0.02


@cache
def stations() -> dict[str, list[str]]:
    """Station number -> its row, deduplicated across the overlapping page exports."""
    files = sorted(FOLDER.glob("*.xls"))
    if not files:
        raise FileNotFoundError(
            f"EPDK şarj istasyonu dökümü yok: {FOLDER} — sorgu reCAPTCHA arkasında, "
            "sayfalar elle indiriliyor (docs/epdk.md)"
        )
    found: dict[str, list[str]] = {}
    for path in files:
        sheet = xlrd.open_workbook(path).sheet_by_index(0)
        for row in range(sheet.nrows):
            number = str(sheet.cell_value(row, STATION_NO)).strip()
            if number.startswith("ŞRJ"):
                found[number] = [
                    str(sheet.cell_value(row, column)) for column in range(sheet.ncols)
                ]
    return found


@cache
def by_district() -> tuple[dict[str, int], int]:
    """(area_id -> station count, unplaced rows)."""
    key = district_key()
    counts: dict[str, int] = {}
    unplaced = 0
    for row in stations().values():
        tail = TAIL.search(row[ADDRESS].strip())
        if not tail:
            unplaced += 1
            continue
        district, province = tail.group(1).strip(), tail.group(2).strip()
        try:
            area, _ = resolve_district(key, province, district.split()[-1])
        except (KeyError, IndexError):
            # A district the registry does not know under that spelling. Kept at province
            # level rather than dropped: the station is real and the province is certain.
            try:
                area = province_id(province)
            except KeyError:
                unplaced += 1
                continue
        counts[area] = counts.get(area, 0) + 1
    total = len(stations())
    if unplaced / total > MAX_UNPLACED:
        raise ValueError(
            f"EPDK şarj: {unplaced}/{total} adresten yer okunamadı "
            f"(sınır %{MAX_UNPLACED:.0%}) — adres sütunu değişmiş olabilir"
        )
    return counts, unplaced


class ChargingStations:
    """Licensed charging stations, per district and rolled up to the province."""

    indicator_id = "charging_stations"
    source_id = SOURCE

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        counts, _ = by_district()
        districts = {a: n for a, n in counts.items() if len(a) > 5}
        provinces: dict[str, int] = {}
        for area, count in counts.items():
            provinces[area[:5]] = provinces.get(area[:5], 0) + count
        records = [
            {"area_id": area, "area_level": level, "value": float(count)}
            for level, rows in (("district", districts), ("province", provinces))
            for area, count in sorted(rows.items())
        ]
        return pl.DataFrame(records).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(dt.date(SNAPSHOT.year, 1, 1)).alias("period_start"),
            pl.lit("annual").alias("frequency"),
            pl.lit("").alias("dims"),
            pl.lit("item").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(SNAPSHOT.strftime("%Y-%m")).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(RETRIEVED).alias("retrieved_at"),
        )


EPDK_SARJ_ADAPTERS = {"charging_stations": ChargingStations}
