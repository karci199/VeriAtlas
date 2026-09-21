"""Births and deaths per district, from MEDAS.

These come from measures of their own — `İlçelere göre doğum sayısı` and `İlçelere göre
ölüm sayısı (İkametgah yeri)` — not from the province measures asked for at a finer level.
MEDAS gives each of the four exactly one set of levels and they do not overlap: the
province measures offer Türkiye through İBBS3 and no district, these offer İlçe Düzeyi and
nothing else. So the district numbers are a second download (`scripts/
fetch_medas_vital_districts.py`) and a second reader, not a wider run of the first.

Both are by **place of residence**. The death measure carries it in its name; the birth
one is the residence series by construction, since the occurrence series is province-only
and stops in 2008. Residence is the reading that belongs next to a population count — a
district with a hospital in it registers events belonging to the districts around it.

Spans differ, and the difference is the source's: **deaths 2009-2025, births 2014-2025.**
Nothing before 2014 is published for births at this level.

Sex is mandatory in both measures, and the two indicators do different things with it:

* **Deaths** keep it. The province series already carries a `sex` dim (K19), so the
  district rows have the same shape and the screen's "Tümü (topla)" adds them up.
* **Births** are summed to the year's total, because the province series has no sex split
  — MEDAS does not offer one on that measure. Storing the split here and not there would
  give the indicator a breakdown that exists at one level and not the other, and every
  province would then vanish the moment a reader picked "Erkek". The raw file keeps the
  split, so the day the province side gains one this becomes a re-parse rather than a
  re-download (K8).

The file is transposed the way the province vital exports are — districts across the
header, breakdown and year down the rows — so the shape of the reading is `tuik_vital`'s,
while the area join is the district one.

**The join is on MEDAS's code and the year, not on the name.** Two districts were renamed
inside the span (Kazan → Kahramankazan in 2017, Eyüp → Eyüpsultan in 2018) and the
registry holds each as its own area with a validity range, sharing the code. The code
alone would be ambiguous for those two, and the name alone would miss them silently.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..areas import load_districts
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .tuik_simple import read_text

DOWNLOADS = RAW / "medas" / "ilce-vital"

#: `Adana(Aladağ)-1757` in the header — the province, the district, MEDAS's own code.
LABEL = re.compile(r"^(?P<province>[^(]+)\((?P<district>[^)]*)\)-(?P<code>\d+)$")

#: `Cinsiyet:Erkek`, `Ölenin cinsiyeti:Kadın` — the two measures word it differently, so
#: the match is on the value rather than on the whole label.
SEX_IN_LABEL = re.compile(r"insiyet\w*\s*:\s*(?P<sex>Erkek|Kadın)")

SEXES = {"Erkek": "male", "Kadın": "female"}

#: file stem → (adapter name, indicator id, the dim kept from the row label). `None`
#: means the rows of a year are summed together — see the note on births above.
MEASURES = {
    "dogum": ("district_births", "births", None),
    "olum": ("district_deaths", "deaths", "sex"),
}


def validity(rows: list[dict]) -> dict[str, list[dict]]:
    """MEDAS code → the registry rows carrying it, newest validity last."""
    by_code: dict[str, list[dict]] = {}
    for row in rows:
        by_code.setdefault(str(row["medas_code"]), []).append(row)
    return by_code


def area_of(by_code: dict[str, list[dict]], code: str, year: int) -> str | None:
    """The area a MEDAS code stood for in a given year.

    One row for the code is the ordinary case and the year does not matter. Where there
    are two, they are a rename and their validity ranges do not overlap — so exactly one
    of them can claim the year, and a year no row claims is left unresolved rather than
    guessed at.
    """
    candidates = by_code.get(code)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]["area_id"]

    matched = [
        row["area_id"]
        for row in candidates
        if (row["valid_from"] is None or year >= row["valid_from"])
        and (row["valid_to"] is None or year <= row["valid_to"])
    ]
    if len(matched) == 1:
        return matched[0]
    return None


def header_of(lines: list[str]) -> dict[int, str]:
    """Column index → MEDAS code.

    Found by looking for area labels rather than by counting cells: the preamble's width
    is not fixed. The line naming the most areas is the header — below it the labels are
    gone and only numbers remain, so nothing else can win.
    """
    best: dict[int, str] = {}
    for line in lines:
        found = {
            index: match["code"]
            for index, cell in enumerate(line.split("|"))
            if (match := LABEL.match(cell.strip()))
        }
        if len(found) > len(best):
            best = found
    return best


def read_export(path: Path, dim: str | None) -> list[dict]:
    """One transposed export, summed to one row per district-year-dims.

    Summed because both measures are counts: with `dim` set the sum is over nothing (one
    row per sex per year), and with it unset it is the two sexes added together.
    """
    lines = read_text(path).splitlines()
    header = header_of(lines)
    if not header:
        raise KeyError("dosyada ilce sutunu bulunamadi: " + path.name)

    totals: dict[tuple[str, int, str], float] = {}
    label = ""
    for line in lines:
        cells = line.split("|")
        if len(cells) < 4:
            continue
        stamp = cells[2].strip()
        if not (stamp.isdigit() and len(stamp) == 4):
            continue
        year = int(stamp)

        # The breakdown is written once, on the first year of its block, and the years
        # under it leave that cell blank. Read literally this keeps one year in each
        # block and drops the rest — which is exactly how the province deaths first
        # arrived with one period out of seventeen (K19). So the label carries down.
        if cells[1].strip():
            label = cells[1].strip()

        if dim == "sex":
            sex = SEX_IN_LABEL.search(label)
            if not sex:
                # A row whose breakdown cannot be placed must not be folded into a total.
                continue
            dims = format_dims({"sex": SEXES[sex.group("sex")]})
        else:
            dims = ""

        for index, code in header.items():
            if index >= len(cells):
                continue
            cell = cells[index].strip()
            if not cell:
                # Withheld or not yet a district: a gap, not a zero.
                continue
            try:
                value = float(cell)
            except ValueError:
                continue
            key = (code, year, dims)
            totals[key] = totals.get(key, 0.0) + value

    return [
        {"medas_code": code, "year": year, "dims": dims, "value": value}
        for (code, year, dims), value in totals.items()
    ]


class DistrictVital:
    """One measure, one indicator — the contract the other adapters keep."""

    source_id = "tuik_medas"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 15)

    stem = ""
    spec: tuple = ()

    @property
    def indicator_id(self) -> str:
        return self.spec[1]

    def fetch(self) -> Path:
        path = DOWNLOADS / ("ilce-" + self.stem + ".csv")
        if not path.exists():
            raise FileNotFoundError(
                "indirilmemis: once 'uv run python scripts/"
                "fetch_medas_vital_districts.py " + self.stem + "'"
            )
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = read_export(raw / ("ilce-" + self.stem + ".csv"), self.spec[2])
        if not records:
            raise ValueError("dosyada satir yok: " + self.stem)

        by_code = validity(load_districts().to_dicts())
        for record in records:
            record["area_id"] = area_of(by_code, record["medas_code"], record["year"])

        # An unresolved code is a district we would draw as a hole in the map,
        # indistinguishable from a real gap — so it stops the load rather than being
        # dropped (the same rule the district population loader keeps).
        missing = sorted({r["medas_code"] for r in records if r["area_id"] is None})
        if missing:
            raise KeyError(
                self.indicator_id
                + ": kayitta karsiligi olmayan MEDAS ilce kodu ("
                + str(len(missing))
                + "): "
                + ", ".join(missing[:20])
                + (" …" if len(missing) > 20 else "")
            )

        indicator = get(self.indicator_id)
        return (
            pl.DataFrame(records)
            .with_columns(
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit("district").alias("area_level"),
                pl.date(pl.col("year").cast(pl.Int32), 1, 1).alias("period_start"),
                pl.lit(indicator.frequency).alias("frequency"),
                pl.lit(indicator.unit.unit_id).alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit(self.vintage).alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(self.retrieved_at).alias("retrieved_at"),
            )
            .select(
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
        )


#: One adapter class per measure, built from the table above.
DISTRICT_VITAL_ADAPTERS = {
    "tuik_" + spec[0]: type(
        "Tuik" + "".join(part.title() for part in spec[0].split("_")),
        (DistrictVital,),
        {"stem": stem, "spec": spec, "__doc__": "MEDAS district vital: " + spec[0]},
    )
    for stem, spec in MEASURES.items()
}
