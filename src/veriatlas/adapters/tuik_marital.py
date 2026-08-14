"""Marital status by sex and age group, from the MEDAS exports.

One CSV per level and run of years, pulled by `scripts/fetch_medas_marital.py`. The third
line is the header and it packs all three breakdowns into each cell::

    ||Erkek ve 15-19 ve Boşandı|Erkek ve 15-19 ve Eşi Öldü|Erkek ve 15-19 ve Evli|…
    2024|Adana-1|2.0||166.0|92538.0|…
        |Adıyaman-2|||42.0|27723.0|…

So the column *is* the dimension tuple, read in the order MEDAS wrote it, and the year is
filled in only when it changes. The join is on the code in the label (`Adana-1`, `TR62`,
`Türkiye-TR`), never the name — K15, and the same `area_of` the median age adapter uses.

Three things the shape of this export will catch anyone out with:

* **The column set is not the same in every file.** `Bilinmeyen` disappears from the
  recent years, so the 2024-2025 province file has 131 value columns where the country
  file has 151. Reading positionally off a remembered header would shift every value one
  place along. Each file's own header is the only thing that says what its columns are.
* **The encoding is not the same as the other MEDAS exports.** District and neighbourhood
  come back ISO-8859-9; this one is UTF-8 with a BOM (docs/medas.md). Detected, not
  assumed.
* **An empty cell is a suppressed count, not a zero.** TÜİK withholds small ones, and a
  zero would say "nobody", which is a different claim.

Age starts at 15: marital status is only published for the population old enough to have
one, so there is no 0-14 band missing — there is none to miss.

**The İBBS files are fetched but not stored.** `area_of` keeps the country and the
provinces and drops the multi-province regions, so the İBBS levels reach the page the way
every other rolled-up level does — summed from provinces — rather than arriving twice by
two routes that could disagree. What the downloads are for is checking that they do not:
over 2008-2011 the province sums equal TÜİK's own country and İBBS-1 totals to the
person, zero difference in every year. Kept on disk so the check can be run again.
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
from .tuik_median_age import area_of, single_province_regions

DOWNLOADS = RAW / "medas" / "medeni"

#: `Adana-1`, `Türkiye-TR`, `Batı Marmara-TR2`
LABEL = re.compile(r"^(?P<name>.+)-(?P<code>[A-Z0-9]+)$")

#: A header cell: sex, age band and marital status joined by " ve ".
HEADER = re.compile(r"^(?P<sex>[^|]+?) ve (?P<age>[\d\-+]+) ve (?P<marital>.+)$")

#: MEDAS's Turkish values to the ids the fact table stores (K1: identifiers in English,
#: the Turkish belongs in the dictionary). `Bilinmeyen` is kept rather than dropped — it
#: is people, and folding them into another status would be inventing an answer.
SEXES = {"Erkek": "male", "Kadın": "female"}
MARITAL = {
    "Hiç Evlenmedi": "never_married",
    "Evli": "married",
    "Boşandı": "divorced",
    "Eşi Öldü": "widowed",
    "Bilinmeyen": "unknown",
}


def read_text(path: Path) -> str:
    """The file's text, whichever of the two encodings MEDAS used for it."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "iso-8859-9"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("dosyanin kodlamasi cozulemedi: " + str(path))


def read_export(path: Path, single: dict[str, str]) -> list[dict]:
    """One export to rows of (year, area_id, area_level, sex, age, marital, value)."""
    lines = read_text(path).splitlines()

    # The header is the first line whose cells parse as dimension tuples. Found rather
    # than counted to, because a stray blank line at the top would shift a fixed index.
    columns: dict[int, tuple[str, str, str]] = {}
    for line in lines:
        found = {}
        for index, cell in enumerate(line.split("|")):
            match = HEADER.match(cell.strip())
            if match:
                found[index] = (
                    match.group("sex"),
                    match.group("age"),
                    match.group("marital"),
                )
        if found:
            columns = found
            break

    if not columns:
        raise ValueError("baslik satiri bulunamadi: " + str(path))

    unknown_sex = {s for s, _, _ in columns.values()} - set(SEXES)
    unknown_marital = {m for _, _, m in columns.values()} - set(MARITAL)
    if unknown_sex or unknown_marital:
        # A value we have no id for would otherwise be dropped, and the totals would come
        # up short by exactly the people in it.
        raise KeyError(
            "sozlukte karsiligi olmayan deger: "
            + ", ".join(sorted(unknown_sex | unknown_marital))
        )

    rows: list[dict] = []
    year = None
    for line in lines:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3:
            continue
        if cells[0].isdigit() and len(cells[0]) == 4:
            year = int(cells[0])

        label = LABEL.match(cells[1])
        if not label or year is None:
            continue
        area = area_of(label.group("code"), single)
        if not area:
            continue

        for index, (sex, age, marital) in columns.items():
            if index >= len(cells) or not cells[index]:
                # Withheld. Absent from the table rather than present as a zero.
                continue
            try:
                value = float(cells[index])
            except ValueError:
                continue
            rows.append(
                {
                    "year": year,
                    "area_id": area[0],
                    "area_level": area[1],
                    "sex": SEXES[sex],
                    "age": age,
                    "marital": MARITAL[marital],
                    "value": value,
                }
            )
    return rows


class TuikMarital:
    """Marital status by sex and age band, country through province."""

    source_id = "tuik_medas"
    indicator_id = "marital_status"

    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 14)

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        single = single_province_regions()

        # Only the levels this adapter stores. The İBBS files are on disk for the
        # cross-check and reading them here would double three provinces: a one-province
        # İBBS region *is* that province, so `area_of` resolves `İstanbul-TR1`,
        # `Ankara-TR51` and `İzmir-TR31` to provinces the province files already carry.
        # The key check caught it, which is what it is for.
        records: list[dict] = []
        for path in sorted(raw.glob("nufus-medeni-*.csv")):
            if not re.match(r"nufus-medeni-(country|province)-", path.name):
                continue
            records.extend(read_export(path, single))
        if not records:
            raise ValueError("dosyada satir yok: " + str(raw))

        frame = pl.DataFrame(records)

        # Every province or none, the same guard the other adapters keep. A province
        # quietly absent draws as "veri yok" in the middle of the map, which nobody can
        # tell from a real gap.
        expected = set(
            load_areas().filter(pl.col("area_level") == "province")["area_id"]
        )
        found = set(frame.filter(pl.col("area_level") == "province")["area_id"])
        if expected - found:
            raise KeyError(
                "dosyada karsiligi olmayan il ("
                + str(len(expected - found))
                + "): "
                + ", ".join(sorted(expected - found))
            )

        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.struct("sex", "age", "marital")
            .map_elements(
                lambda row: format_dims(
                    {"sex": row["sex"], "age": row["age"], "marital": row["marital"]}
                ),
                return_dtype=pl.String,
            )
            .alias("dims"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).select(
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
