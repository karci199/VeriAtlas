"""Convicts admitted to and released from prison — MEDAS, province and Türkiye, 1990-2020.

Pulled 2026-09-14/15 (`fetch_medas_topic.py ceza-giren=... ceza-cikan=...`) as
`medas/basit/nufus-ceza-<giren|cikan>-<measure>-k<breakdown>-<province|country>[-part].csv`.

Four indicators, each a province table counted two ways:

* admitted (`giren`) and released (`cikan`),
* by the province the convict lives in (measure 02) or where the offence was committed
  (measure 03).

Every file is one breakdown (sex, offence group, single age, age group, occupation,
nationality), so a stored row carries exactly one breakdown dimension. The breakdowns are
slices of the same total, not levels of one another: adding an offence row to an age row
counts the same convict twice. MEDAS splits a big breakdown over several part files (the
offence table by year ranges); a part that repeats a cell another part already gave stops
the load.

Two traps the loader guards:

* **`Yabancı Ülke-98`** is a column in the province files that is not a province: convicts
  who live abroad. It is not stored under a province, only counted in the check below.
* **The provinces fall short of Türkiye**, by design of the source: a convict with no
  province of residence (most foreign nationals, a few per cent of the age and offence
  slices) is in the Türkiye row and in no column. The short fall is one-sided, so the check
  is that the provinces never *exceed* Türkiye — which is what a part file read twice or a
  column counted under two provinces would do. The Türkiye row stays the full total.
* **A label that is not known** stops the load (an unknown offence, occupation or column)
  rather than dropping a row, since the rows must add up to what TÜİK publishes.

Measure 01 (Türkiye only, nine breakdowns crossed in one label) and the release reasons
are not loaded: they are not province data and their crossed labels would need their own
reading. They stay in `raw/`.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .tuik_median_age import area_of, single_province_regions
from .tuik_simple import LABEL, read_text

DOWNLOADS = RAW / "medas" / "basit"

#: indicator id -> (direction in the file name, measure number)
FILES = {
    "prison_admissions_by_residence": ("giren", "02"),
    "prison_admissions_by_offence_place": ("giren", "03"),
    "prison_releases_by_residence": ("cikan", "02"),
    "prison_releases_by_offence_place": ("cikan", "03"),
}

#: breakdown number in the file name -> (label MEDAS puts in front of the value, dimension)
BREAKDOWNS = {
    "01": ("Cinsiyet", "sex"),
    "02": ("Suç türü", "prison_offence"),
    "03": ("Yaş", "offender_age"),
    "04": ("Yaş grubu", "offender_age_band"),
    "05": ("İş durumu", "offender_occupation"),
    "07": ("Uyruk", "nationality_status"),
}

SEXES = {"Erkek": "male", "Kadın": "female"}
NATIONALITY = {"T.C.": "citizen", "Yabancı": "foreign", "Bilinmeyen": "unknown"}
#: `32. (Uyuşturucu Veya ...)` -> group 32; the Turkish text lives in the dimension's values
NUMBERED = re.compile(r"^(\d+)\. \(.*\)$")
#: The one column of the province files that is not a province.
ABROAD = "98"


def value_id(dimension: str, raw: str) -> str:
    raw = " ".join(raw.split())
    if dimension == "sex":
        return SEXES[raw]
    if dimension == "nationality_status":
        return NATIONALITY[raw]
    if dimension in ("prison_offence", "offender_occupation"):
        found = NUMBERED.match(raw)
        if not found:
            raise KeyError(raw)
        return f"g{int(found.group(1)):02d}"
    if raw == "Bilinmeyen":
        return "unknown"
    return raw


def read_file(path: Path, dimension: str, label_name: str, single: dict[str, str]):
    """Rows of one export: (area_id, abroad, year, dim value id, value)."""
    lines = read_text(path).splitlines()
    head = next(
        i for i, line in enumerate(lines) if line.split("|")[0].strip() == "Satırlar"
    )
    columns = [c.strip() for c in lines[head].split("|")]
    targets: dict[int, tuple[str | None, bool]] = {}
    for index, name in enumerate(columns):
        if index < 3 or not name:
            continue
        found = LABEL.match(name)
        if not found:
            raise KeyError(f"{path.name}: sutun adi cozulemedi: {name}")
        if found.group("code") == ABROAD:
            targets[index] = (None, True)
            continue
        area = area_of(found.group("code"), single)
        if not area:
            raise KeyError(f"{path.name}: tanimsiz alan sutunu: {name}")
        targets[index] = (area[0], False)

    rows = []
    label = None
    for line in lines[head + 1 :]:
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 4:
            continue
        if cells[1]:
            name, _, value = cells[1].partition(":")
            if name.strip() != label_name:
                raise KeyError(
                    f"{path.name}: beklenen kirilim '{label_name}', dosyada '{cells[1]}'"
                )
            label = value_id(dimension, value)
        if label is None or not (cells[2].isdigit() and len(cells[2]) == 4):
            continue
        year = int(cells[2])
        for index, (area, abroad) in targets.items():
            if index >= len(cells) or not cells[index]:
                continue
            rows.append((area, abroad, year, label, float(cells[index])))
    return rows


def read_indicator(indicator_id: str, raw: Path) -> pl.DataFrame:
    direction, measure = FILES[indicator_id]
    single = single_province_regions()
    cells: dict[tuple, float] = {}
    abroad: dict[tuple, float] = {}
    for number, (label_name, dimension) in BREAKDOWNS.items():
        paths = sorted(raw.glob(f"nufus-ceza-{direction}-{measure}-k{number}-*.csv"))
        for path in paths:
            for area, is_abroad, year, label, value in read_file(
                path, dimension, label_name, single
            ):
                key = (area, year, dimension, label)
                if is_abroad:
                    abroad[(year, dimension, label)] = (
                        abroad.get((year, dimension, label), 0) + value
                    )
                    continue
                if key in cells:
                    raise ValueError(
                        f"{indicator_id}: ayni hucre iki kez ({path.name}): {key}"
                    )
                cells[key] = value

    # the provinces and the people abroad must never exceed Türkiye, slice by slice
    by_slice: dict[tuple, float] = defaultdict(float)
    for (area, year, dimension, label), value in cells.items():
        if area != "TR":
            by_slice[(year, dimension, label)] += value
    off = []
    for (year, dimension, label), total in by_slice.items():
        country = cells.get(("TR", year, dimension, label))
        if country is None:
            continue
        gap = country - total - abroad.get((year, dimension, label), 0)
        if gap < 0:
            off.append(
                (
                    year,
                    dimension,
                    label,
                    country,
                    total,
                    abroad.get((year, dimension, label), 0),
                )
            )
    if off:
        raise ValueError(
            f"{indicator_id}: iller + yabanci ulke Turkiye toplamini asiyor ({len(off)}): {off[:6]}"
        )

    records = [
        {
            "area_id": area,
            "area_level": "country" if area == "TR" else "province",
            "year": year,
            "dims": format_dims({dimension: label}),
            "value": value,
        }
        for (area, year, dimension, label), value in cells.items()
    ]
    if not records:
        raise ValueError("dosya bulunamadi ya da bos: " + indicator_id)
    return pl.DataFrame(records)


class PrisonMeasure:
    source_id = "tuik_medas"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 15)
    indicator_id = ""

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        frame = read_indicator(self.indicator_id, raw)
        indicator = get(self.indicator_id)
        return frame.select(
            pl.lit(self.indicator_id).alias("indicator_id"),
            "area_id",
            "area_level",
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            "dims",
            "value",
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        )


PRISON_ADAPTERS = {
    "tuik_" + ident: type(
        "Tuik" + "".join(p.title() for p in ident.split("_")),
        (PrisonMeasure,),
        {"indicator_id": ident},
    )
    for ident in FILES
}
