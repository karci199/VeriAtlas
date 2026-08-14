"""Births and deaths: the vital events, as counts and as the two mortality rates.

`scripts/fetch_medas_simple.py` pulls these alongside the narrow measures, but they do not
share `tuik_simple`'s parser, because MEDAS turned the table on its side for them. In the
narrow exports the areas run down the rows; here they run across the header and the rows
carry the breakdown and the year instead. Same source, same download script, transposed
file — so the reading of it lives here.

What is loaded and what is deliberately not:

* **Doğum sayısı** — published by month, stored as the year's total. Twelve rows of a
  province-year summed into one. Seasonality is a real question and this throws it away;
  the raw file keeps it, so asking it later needs no new download, only a dim.
* **Ölüm sayısı** — published by sex × month, stored by sex, months summed the same way.
* **Bebek ölüm hızı**, **beş yaş altı ölüm hızı** — no breakdown, one value per year.
* **Evlenme** and **boşanma sayısı** — one value per year, twenty-five of them, with
  every breakdown left closed (see the indicator's note). Counted by the place the event
  happened rather than where the couple lives, which is how TÜİK publishes them.
* **Kaba doğum hızı**, **kaba ölüm hızı**, **kaba evlenme/boşanma hızı** are *not* loaded. Both are an exact function
  of rows we already hold — the event count over the population — and K12 says such a
  number is a derivation, not a second download that can drift out of step with the first.
  The page's "Alan nüfusunun %'si" mode already draws them. The published files stay in
  `raw/` as a check, as the dependency ratios do.

Both counts are by **place of residence**, not place of occurrence. MEDAS publishes both
and they answer different questions: a province with a large maternity hospital records
the births of the provinces around it, and one with a large hospital records their deaths.
Residence is the reading that belongs next to a population count — and it runs seventeen
years against the other's eight.
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
from .tuik_simple import LABEL, read_text

DOWNLOADS = RAW / "medas" / "basit"

#: The row label names the sex as `Ölenin cinsiyeti:Erkek ve …`. Matched on the word
#: rather than on the whole label, because the rest of it is the month and the month is
#: summed away.
SEX_IN_LABEL = re.compile(r"cinsiyeti\s*:\s*(?P<sex>Erkek|Kadın)")

SEXES = {"Erkek": "male", "Kadın": "female"}

#: file stem → (adapter name, indicator id, the dim read from the row label or None to sum
#: every row of the year, and the dims the file carries as a whole).
#:
#: That last field is for the measures MEDAS splits into separate *files* rather than
#: separate rows: the average age at marriage is published as "erkeğin" and "kadının",
#: four files that are two indicators by sex. The breakdown is a fact about which file
#: this is, so it is stated here rather than looked for in a row label that does not
#: carry it. Two files feeding one indicator is also why the adapter name is written out
#: instead of derived from the indicator id — they would collide.
MEASURES = {
    "dogum": ("births", "births", None, {}),
    "olum": ("deaths", "deaths", "sex", {}),
    "bebek-olum-hizi": ("infant_mortality", "infant_mortality", None, {}),
    "bes-yas-alti-olum-hizi": ("under5_mortality", "under5_mortality", None, {}),
    "evlenme": ("marriages", "marriages", None, {}),
    "bosanma": ("divorces", "divorces", None, {}),
    "evlenme-yasi-erkek": (
        "mean_marriage_age_male",
        "mean_marriage_age",
        None,
        {"sex": "male"},
    ),
    "evlenme-yasi-kadin": (
        "mean_marriage_age_female",
        "mean_marriage_age",
        None,
        {"sex": "female"},
    ),
    "ilk-evlenme-yasi-erkek": (
        "mean_first_marriage_age_male",
        "mean_first_marriage_age",
        None,
        {"sex": "male"},
    ),
    "ilk-evlenme-yasi-kadin": (
        "mean_first_marriage_age_female",
        "mean_first_marriage_age",
        None,
        {"sex": "female"},
    ),
}


def header_of(lines: list[str], single: dict[str, str]) -> dict[int, tuple[str, str]]:
    """Column index to `(area_id, level)`.

    Found by looking for area labels rather than by counting cells: the country file has
    one column and the province file has eighty-one, and the two differ in how many empty
    cells precede them. The line that names the most areas is the header — no other line
    names any, since below it the labels are gone and only numbers remain.
    """
    best: dict[int, tuple[str, str]] = {}
    for line in lines:
        found: dict[int, tuple[str, str]] = {}
        for index, cell in enumerate(line.split("|")):
            label = LABEL.match(cell.strip())
            if not label:
                continue
            area = area_of(label.group("code"), single)
            if area:
                found[index] = area
        if len(found) > len(best):
            best = found
    return best


def read_export(path: Path, spec: tuple, single: dict[str, str]) -> list[dict]:
    """One transposed export, summed to one row per area-year-dims.

    Summed — which is only right for a count. The rates in this file (infant mortality,
    the average age at marriage) arrive one row per area-year, so the sum is a sum of one
    and the same code reads both. If that ever stops being true — MEDAS adds a breakdown,
    or a measure is fetched with one open by mistake — a mortality rate of 9 and one of 11
    would quietly become 20. So the unit decides: what does not add up is not allowed to
    arrive twice.
    """
    indicator_id, dim, fixed = spec[1], spec[2], spec[3]
    additive = get(indicator_id).unit.additive
    lines = read_text(path).splitlines()
    header = header_of(lines, single)
    if not header:
        raise KeyError(indicator_id + ": dosyada alan sutunu bulunamadi: " + path.name)

    #: (area_id, level, year, dims) → running total. A month is a row, and the year is the
    #: sum of its months, so the file is accumulated rather than mapped row by row.
    totals: dict[tuple[str, str, int, str], float] = {}
    year = None
    label = ""
    for line in lines:
        cells = line.split("|")
        if len(cells) < 4:
            continue
        stamp = cells[2].strip()
        if not (stamp.isdigit() and len(stamp) == 4):
            continue
        year = int(stamp)

        # The breakdown is written once, on the first year of its block, and the sixteen
        # rows under it are blank in that cell. Read literally, that dropped every year
        # but 2009 and left deaths with one period out of seventeen — so the label carries
        # down until the file names a new one.
        if cells[1].strip():
            label = cells[1].strip()

        if dim == "sex":
            sex = SEX_IN_LABEL.search(label)
            if not sex:
                # A row whose breakdown we cannot place must not be folded into a total
                # silently.
                continue
            dims = format_dims({**fixed, dim: SEXES[sex.group("sex")]})
        else:
            dims = format_dims(fixed) if fixed else ""

        for index, (area_id, level) in header.items():
            if index >= len(cells):
                continue
            cell = cells[index].strip()
            if not cell:
                # Withheld, not zero.
                continue
            try:
                value = float(cell)
            except ValueError:
                continue
            key = (area_id, level, year, dims)
            if key in totals and not additive:
                raise ValueError(
                    indicator_id
                    + ": toplanamayan birim ayni alan-yil icin iki deger aldi ("
                    + area_id
                    + " "
                    + str(year)
                    + "), dosya: "
                    + path.name
                )
            totals[key] = totals.get(key, 0.0) + value

    return [
        {
            "area_id": area_id,
            "area_level": level,
            "year": year,
            "dims": dims,
            "value": value,
        }
        for (area_id, level, year, dims), value in totals.items()
    ]


class VitalMeasure:
    """One measure, one indicator — the same contract `NarrowMeasure` keeps."""

    source_id = "tuik_medas"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 14)

    #: Filled in by the subclasses below.
    stem = ""
    spec: tuple = ()

    @property
    def indicator_id(self) -> str:
        return self.spec[1]

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        single = single_province_regions()

        records: list[dict] = []
        for level in ("country", "province"):
            path = raw / ("nufus-" + self.stem + "-" + level + ".csv")
            if path.exists():
                records.extend(read_export(path, self.spec, single))
        if not records:
            raise ValueError("dosya bulunamadi ya da bos: " + self.stem)

        indicator = get(self.indicator_id)
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

        # Every province or none: one quietly absent draws as "veri yok" in the middle of
        # the map, indistinguishable from a real gap.
        expected = set(
            load_areas().filter(pl.col("area_level") == "province")["area_id"]
        )
        found = set(frame.filter(pl.col("area_level") == "province")["area_id"])
        if expected - found:
            raise KeyError(
                self.indicator_id
                + ": dosyada karsiligi olmayan il ("
                + str(len(expected - found))
                + "): "
                + ", ".join(sorted(expected - found))
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


#: One adapter class per measure, built from the table above.
VITAL_ADAPTERS = {
    "tuik_" + spec[0]: type(
        "Tuik" + "".join(part.title() for part in spec[0].split("_")),
        (VitalMeasure,),
        {"stem": stem, "spec": spec, "__doc__": "MEDAS vital measure: " + spec[0]},
    )
    for stem, spec in MEASURES.items()
}

#: Adapters that write into the same indicator from different files, and so must run
#: together or not at all. Loading `mean_marriage_age_male` alone would publish an
#: indicator whose sex breakdown has one value in it, which is not a smaller version of
#: the truth — it is a chart with the women missing.
PAIRED = {
    "mean_marriage_age": (
        "tuik_mean_marriage_age_male",
        "tuik_mean_marriage_age_female",
    ),
    "mean_first_marriage_age": (
        "tuik_mean_first_marriage_age_male",
        "tuik_mean_first_marriage_age_female",
    ),
}
