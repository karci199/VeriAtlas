r"""Schools, students, teachers, classrooms and sections by province and school level.

MEDAS publishes these five counts under "Örgün Eğitim İstatistikleri", 2012-2024, province
level only (TÜİK does not go below province for them). `scripts/fetch_medas_simple.py`
pulled them as `orgun-okul`, `orgun-ogrenci`, `orgun-ogretmen`, `orgun-derslik` and
`orgun-sube` into `raw/medas/basit/`; until 2026-09-25 nothing read them, and four of the
five were only used, from a different copy, as the numerator or denominator of the
ratios in `meb_education`.

The files are pivots: category and year down the rows (`Erkek ve İlkokul`, `2014`), one
column per province headed with its plate code (`Adana-1`, K15).

**The levels are kept apart here, unlike `meb_education`.** That module folds İlkokul and
Ortaokul into `ilkogretim` so its rates line up with the pre-2012 series; counts have no
pre-2012 series to line up with, and "how many middle schools" is a question in its own
right. So `school_level` carries five values that partition the whole:

    preschool · primary · lower_secondary · upper_secondary_general ·
    upper_secondary_vocational

**`Ortaöğretim` is not stored.** It is published as its own row but it is the sum of the
general and vocational rows; storing it too would double upper secondary in any sum over
the dimension. The parser checks the identity for every province-year and stops if it
fails, so dropping it loses nothing.

Every province-year's 81 provinces are also checked against the country file — the
same measure, the same export, a total TÜİK computed itself.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .tuik_median_age import area_of, single_province_regions
from .tuik_simple import read_text

DOWNLOADS = RAW / "medas" / "basit"
SOURCE_ID = "tuik_medas"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 12)

LEVELS = {
    "Okul Öncesi": "preschool",
    "İlkokul": "primary",
    "Ortaokul": "lower_secondary",
    "Genel Ortaöğretim": "upper_secondary_general",
    "Mesleki Ve Teknik Ortaöğretim": "upper_secondary_vocational",
}
#: Published, but the sum of the two upper-secondary rows above; checked, not stored.
UPPER_SECONDARY_TOTAL = "Ortaöğretim"
SEXES = {"Erkek": "male", "Kadın": "female"}
LABEL = re.compile(r"^(?P<name>.+)-(?P<code>[A-Z0-9]+)$")

#: indicator id -> (MEDAS file key, split by sex)
MEASURES = {
    "schools": ("okul", False),
    "students": ("ogrenci", True),
    "teachers": ("ogretmen", True),
    "classrooms": ("derslik", False),
    "class_sections": ("sube", False),
}


def read_pivot(path: Path) -> list[dict]:
    """Rows of `(area_id, area_level, sex, level, year, value)`; `level` is the source label."""
    lines = read_text(path).splitlines()
    header = lines[1].split("|")
    single = single_province_regions()
    columns: dict[int, tuple[str, str]] = {}
    for index, cell in enumerate(header):
        match = LABEL.match(cell.strip())
        if match:
            area = area_of(match.group("code"), single)
            if area is not None:
                columns[index] = area
    if not columns:
        raise ValueError(f"başlıkta alan yok: {path}")

    rows = []
    category = ""
    for line in lines[2:]:
        cells = line.split("|")
        if len(cells) < 3 or not cells[2].strip().isdigit():
            continue
        # The category is written only on the row where it changes; the years below it
        # leave the cell empty.
        category = cells[1].strip() or category
        sex = None
        level_label = category
        if " ve " in category:
            sex_label, level_label = category.split(" ve ", 1)
            sex = SEXES[sex_label.strip()]
        for index, (area_id, level) in columns.items():
            text = cells[index].strip() if index < len(cells) else ""
            if not text:
                continue
            rows.append(
                {
                    "area_id": area_id,
                    "area_level": level,
                    "sex": sex,
                    "level": level_label.strip(),
                    "year": int(cells[2]),
                    "value": float(text),
                }
            )
    return rows


def checked(rows: list[dict], country: list[dict], name: str) -> list[dict]:
    """Drop the upper-secondary total after proving it redundant; check provinces vs TR."""
    by_key: dict[tuple, float] = {}
    for row in rows:
        by_key[(row["area_id"], row["sex"], row["level"], row["year"])] = row["value"]
    for (area, sex, level, year), total in by_key.items():
        if level != UPPER_SECONDARY_TOTAL:
            continue
        parts = sum(
            by_key.get((area, sex, part, year), 0.0)
            for part in ("Genel Ortaöğretim", "Mesleki Ve Teknik Ortaöğretim")
        )
        if abs(parts - total) > 0.5:
            raise ValueError(
                f"{name} {area} {year} {sex}: ortaöğretim {total} ≠ {parts}"
            )

    unknown = {row["level"] for row in rows} - set(LEVELS) - {UPPER_SECONDARY_TOTAL}
    if unknown:
        raise ValueError(f"{name}: tanınmayan düzey {sorted(unknown)}")
    kept = [
        row
        for row in rows
        if row["level"] in LEVELS and row["area_level"] == "province"
    ]

    sums: dict[tuple, float] = {}
    provinces: dict[int, set[str]] = {}
    for row in kept:
        key = (row["sex"], row["level"], row["year"])
        sums[key] = sums.get(key, 0.0) + row["value"]
        provinces.setdefault(row["year"], set()).add(row["area_id"])
    for year, found in provinces.items():
        if len(found) != 81:
            raise ValueError(f"{name} {year}: {len(found)} il")
    for row in country:
        if row["area_level"] != "country" or row["level"] not in LEVELS:
            continue
        key = (row["sex"], row["level"], row["year"])
        if abs(sums.get(key, 0.0) - row["value"]) > 0.5:
            raise ValueError(
                f"{name} {key}: iller {sums.get(key)} ≠ Türkiye {row['value']}"
            )
    return kept


class MebCount:
    indicator_id: str
    source_id = SOURCE_ID

    def _path(self, level: str) -> Path:
        key = MEASURES[self.indicator_id][0]
        return DOWNLOADS / f"nufus-orgun-{key}-{level}.csv"

    def fetch(self) -> Path:
        path = self._path("province")
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    def parse(self, raw: Path) -> pl.DataFrame:
        by_sex = MEASURES[self.indicator_id][1]
        rows = checked(
            read_pivot(raw), read_pivot(self._path("country")), self.indicator_id
        )
        indicator = get(self.indicator_id)
        records = []
        for row in rows:
            if by_sex != (row["sex"] is not None):
                raise ValueError(f"{self.indicator_id}: beklenmeyen cinsiyet kırılımı")
            dims = {"school_level": LEVELS[row["level"]]}
            if row["sex"]:
                dims["sex"] = row["sex"]
            records.append(
                {
                    "indicator_id": self.indicator_id,
                    "area_id": row["area_id"],
                    "area_level": "province",
                    "period_start": dt.date(row["year"], 1, 1),
                    "frequency": indicator.frequency,
                    "dims": format_dims(dims),
                    "value": row["value"],
                    "unit": indicator.unit.unit_id,
                    "quality_flag": "measured",
                    "vintage": VINTAGE,
                    "source_id": self.source_id,
                    "retrieved_at": RETRIEVED,
                }
            )
        return pl.DataFrame(records)


MEB_COUNT_ADAPTERS = {
    indicator_id: type(
        f"MebCount_{indicator_id}", (MebCount,), {"indicator_id": indicator_id}
    )
    for indicator_id in MEASURES
}
