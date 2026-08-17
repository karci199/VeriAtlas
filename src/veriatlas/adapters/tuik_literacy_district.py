"""Literacy status by sex, district level, 15+ population.

A hand-downloaded MEDAS export ("Ulusal Eğitim İstatistikleri" → "Okuma Yazma Durumu"),
district columns exactly like the births/deaths district exports — `Adana(Aladağ)-1757` —
so the same code-to-district resolution applies (`districts_by_code`, `area_at` from
`tuik_vital_district`).

Two things differ from that file's shape:

* **One file, two years.** Births/deaths district exports are one file per year because
  MEDAS's own gösterge × düzey × zaman limit forces that split at 973 districts. This
  measure has only 6 indicators (2 sexes × 3 literacy values), so 2008 and 2025 both fit
  in one query — but that means the year is read from the row, never the filename, and
  `area_at` is called with each row's own year rather than a year fixed for the whole file.
* **Two dims in one row label.** `Erkek ve 15+ Yaş ve Okuma Yazma Bilmeyen` packs sex and
  literacy status together, the same packing `tuik_marital` unpacks for medeni durum — but
  here the label also carries the age threshold ("15+ Yaş"), which is not stored as a dim
  because this pull only ever asked MEDAS for the 15+ population. It says so once, in the
  indicator's definition, rather than as a dim with one value forever.

Only 15+ is loaded. MEDAS also publishes a 6+ Yaş literacy figure and it is a different,
wider population — pulling both into one indicator would need the age threshold as a third
dim, and today's file has only ever asked for one of them.

Province and country are not rolled up here. The two years span a district boundary
change (6360 sayılı yasa) and some 2008 codes have no living successor in the 2025
registry the way `deaths_district` copes with — summing districts to a province total
would need every one of them present, and this file was not checked for that yet.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .base import cached_copy
from .tuik_simple import LABEL, read_text
from .tuik_vital_district import area_at, districts_by_code

SOURCE_FILE = Path(
    r"C:\Users\katan\OneDrive\Desktop\demografi\Egitim"
    r"\ilcelere-gore-okuma-yazma-durumu-cinsiyet-15plus-2008-2025.csv"
)

SEXES = {"Erkek": "male", "Kadın": "female"}
STATUSES = {
    "Okuma Yazma Bilen": "literate",
    "Okuma Yazma Bilmeyen": "illiterate",
    "Bilinmeyen": "unknown",
}

LABEL_IN_ROW = re.compile(r"^(?P<sex>Erkek|Kadın) ve 15\+ Yaş ve (?P<status>.+)$")


class TuikLiteracyDistrict:
    """Literacy status (15+), sex × status, district level, 2008 and 2025."""

    source_id = "tuik_medas"
    indicator_id = "literacy_district"

    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 17)

    def fetch(self) -> Path:
        return cached_copy(SOURCE_FILE, RAW / "tuik_medas" / SOURCE_FILE.name)

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        codes = districts_by_code()
        lines = read_text(raw).splitlines()

        # The header is the line naming the most districts — found rather than assumed,
        # the same rule the district vital exports use, because a blank leading cell has
        # moved before.
        header: dict[int, str] = {}
        unknown_districts: set[str] = set()
        for line in lines:
            found: dict[int, tuple[str, str]] = {}
            missing: set[str] = set()
            for index, cell in enumerate(line.split("|")):
                match = LABEL.match(cell.strip())
                if not match:
                    continue
                code = match.group("code")
                if not code.isdigit():
                    continue
                candidates = codes.get(code, [])
                if candidates:
                    found[index] = code
                else:
                    missing.add(cell.strip())
            if len(found) > len(header):
                header, unknown_districts = found, missing
        if not header:
            raise KeyError(self.indicator_id + ": dosyada ilce sutunu bulunamadi")
        if unknown_districts:
            raise KeyError(
                self.indicator_id
                + ": kayitta karsiligi olmayan ilce ("
                + str(len(unknown_districts))
                + "): "
                + ", ".join(sorted(unknown_districts)[:10])
            )

        records: list[dict] = []
        label = ""
        for line in lines:
            cells = line.split("|")
            if len(cells) < 4:
                continue
            stamp = cells[2].strip()
            if not (stamp.isdigit() and len(stamp) == 4):
                continue
            year = int(stamp)
            if cells[1].strip():
                label = cells[1].strip()

            parsed = LABEL_IN_ROW.match(label)
            if not parsed:
                raise ValueError(
                    self.indicator_id + ": beklenmeyen satir etiketi: " + label
                )
            status = parsed.group("status")
            if status not in STATUSES:
                raise KeyError(
                    self.indicator_id + ": bilinmeyen okuma yazma durumu: " + status
                )
            dims = format_dims(
                {"sex": SEXES[parsed.group("sex")], "literacy_status": STATUSES[status]}
            )

            for index, code in header.items():
                if index >= len(cells):
                    continue
                cell = cells[index].strip()
                if not cell:
                    continue
                area_id = area_at(codes.get(code, []), year)
                if not area_id:
                    # This district's code did not exist under this identity in this
                    # year — the 2008/2025 boundary change the module docstring notes.
                    continue
                records.append(
                    {
                        "area_id": area_id,
                        "area_level": "district",
                        "year": year,
                        "dims": dims,
                        "value": float(cell),
                    }
                )

        if not records:
            raise ValueError(self.indicator_id + ": dosyada satir yok")

        frame = pl.DataFrame(records).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        )

        # Every district belongs to a province the registry knows — the check that would
        # have caught a district code misread as something else.
        provinces = set(
            load_areas().filter(pl.col("area_level") == "province")["area_id"]
        )
        parents = {area[:5] for area in frame["area_id"].unique()}
        if parents - provinces:
            raise KeyError(
                self.indicator_id
                + ": taninmayan il: "
                + ", ".join(sorted(parents - provinces))
            )

        return frame.select(
            "indicator_id",
            "area_id",
            "area_level",
            "period_start",
            "frequency",
            "dims",
            "value",
            "unit",
            "quality_flag",
            "vintage",
            "source_id",
            "retrieved_at",
        )
