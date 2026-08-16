"""Births and deaths at district level: a separate measure, not a lower level.

MEDAS publishes `İlçelere göre doğum sayısı` beside `İkametgah yerine göre doğum sayısı`
and the district level exists only on the first. So this is a second download and a
second adapter, not `tuik_vital` asked for another level — and the two do not even span
the same years: districts start in **2014** for births and **2009** for deaths, against
2009 and 2001 for the province series. A shorter district series is the source's shape,
not a gap in ours.

The file is transposed the way the province exports are — districts across the header,
the measure down — but the header labels carry a different kind of code:

    province:  `Adana-1`              the plate number, which is the registry's own id
    district:  `Adana(Aladağ)-1757`   a MEDAS district code, which is nobody else's id

Reading a district file with the province rule turns `1757` into the province TR-17. That
is why `area_of` is not reused here: the same shape of label means something else.

**The year picks the identity.** A renamed district keeps its MEDAS code and gets a second
registry row (Kazan → Kahramankazan in 2017, Eyüp → Eyüpsultan in 2018), so a code alone
resolves to two areas. The registry's `valid_from` / `valid_to` say which one was current,
and the file's year chooses between them. Resolved without the year, the early years of
those districts would land on an id the population series does not use — and the district
would draw as "veri yok" for exactly the years it has data.

Deaths arrive split by the sex of the deceased and MEDAS will not close that breakdown,
so it is stored as one: `deaths` already carries a sex dim at province level and the
district rows join it unchanged.

Checked on load against what the fact table already holds: district births sum to the
national count for all twelve years, deaths for all seventeen and for each sex, and
births minus deaths to the province natural increase for all 972 province-years.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas, load_districts
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .tuik_simple import LABEL, read_text

DOWNLOADS = RAW / "medas" / "basit"

#: `nufus-dogum-ilce-district-2019.csv` — one file per year, because a year is what fits.
FILE = re.compile(r"-district-(?P<year>\d{4})\.csv$")

SEX_IN_LABEL = re.compile(r"cinsiyeti\s*:\s*(?P<sex>Erkek|Kadın)")
SEXES = {"Erkek": "male", "Kadın": "female"}

#: stem → (adapter name, indicator id, the dim carried in the row label or None)
MEASURES = {
    "dogum-ilce": ("births_district", "births", None),
    "olum-ilce": ("deaths_district", "deaths", "sex"),
}


def districts_by_code() -> dict[str, list[dict]]:
    """MEDAS district code to the registry rows that have claimed it."""
    found: dict[str, list[dict]] = {}
    for row in load_districts().to_dicts():
        code = row.get("medas_code")
        if code in (None, ""):
            continue
        found.setdefault(str(int(code)), []).append(row)
    return found


def area_at(candidates: list[dict], year: int) -> str | None:
    """Which of the areas sharing a code was the district in that year."""
    for row in candidates:
        starts = row.get("valid_from")
        ends = row.get("valid_to")
        if starts is not None and year < starts:
            continue
        if ends is not None and year > ends:
            continue
        return row["area_id"]
    return None


def read_export(path: Path, spec: tuple, codes: dict[str, list[dict]]) -> list[dict]:
    """One year's district export, as fact-table rows."""
    indicator_id, dim = spec[1], spec[2]
    year_in_name = FILE.search(path.name)
    if not year_in_name:
        raise ValueError("dosya adinda yil yok: " + path.name)
    year = int(year_in_name.group("year"))

    lines = read_text(path).splitlines()

    # The header is the line that names the most districts. Counted rather than assumed:
    # the leading blank cells have moved between exports before.
    header: dict[int, str] = {}
    unknown: set[str] = set()
    for line in lines:
        found: dict[int, str] = {}
        missing: set[str] = set()
        for index, cell in enumerate(line.split("|")):
            label = LABEL.match(cell.strip())
            if not label:
                continue
            code = label.group("code")
            if not code.isdigit():
                continue
            area = area_at(codes.get(code, []), year)
            if area:
                found[index] = area
            else:
                missing.add(cell.strip())
        if len(found) > len(header):
            header, unknown = found, missing
    if not header:
        raise KeyError(indicator_id + ": dosyada ilce sutunu bulunamadi: " + path.name)
    if unknown:
        # Named rather than skipped: a district silently dropped takes its births with it
        # and the year still looks complete.
        raise KeyError(
            indicator_id
            + ": kayitta karsiligi olmayan ilce ("
            + str(len(unknown))
            + ") "
            + path.name
            + ": "
            + ", ".join(sorted(unknown)[:10])
        )

    rows: list[dict] = []
    label = ""
    for line in lines:
        cells = line.split("|")
        if len(cells) < 4:
            continue
        stamp = cells[2].strip()
        if not (stamp.isdigit() and len(stamp) == 4):
            continue
        if cells[1].strip():
            label = cells[1].strip()

        if dim == "sex":
            sex = SEX_IN_LABEL.search(label)
            if not sex:
                continue
            dims = format_dims({dim: SEXES[sex.group("sex")]})
        else:
            dims = ""

        for index, area_id in header.items():
            if index >= len(cells):
                continue
            cell = cells[index].strip()
            if not cell:
                # Withheld, not zero.
                continue
            rows.append(
                {
                    "area_id": area_id,
                    "area_level": "district",
                    "year": int(stamp),
                    "dims": dims,
                    "value": float(cell),
                }
            )
    # The year is in the file name and in every row, and they have to agree: the files are
    # fetched one year per query and named by the year asked for, so a mismatch means the
    # download answered for a different year than the one it is filed under.
    inside = {row["year"] for row in rows}
    if inside - {year}:
        raise ValueError(
            path.name
            + ": dosya adindaki yil "
            + str(year)
            + ", icindeki yil "
            + ", ".join(str(y) for y in sorted(inside))
        )
    return rows


class DistrictVital:
    """One district measure, one indicator — the same contract the others keep."""

    source_id = "tuik_medas"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 16)

    stem = ""
    spec: tuple = ()

    @property
    def indicator_id(self) -> str:
        return self.spec[1]

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        codes = districts_by_code()
        records: list[dict] = []
        for path in sorted(raw.glob("nufus-" + self.stem + "-district-*.csv")):
            records.extend(read_export(path, self.spec, codes))
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

        # The last year must be whole. An early year missing districts is the country
        # having had fewer of them; the newest year missing one is a download that went
        # short, and that is the one worth stopping for.
        last = frame.select(pl.col("year").max()).item()
        expected = {
            row["area_id"]
            for row in load_districts().to_dicts()
            if row.get("valid_to") is None
        }
        found = set(frame.filter(pl.col("year") == last)["area_id"])
        if expected - found:
            raise KeyError(
                self.indicator_id
                + ": son yilda ("
                + str(last)
                + ") karsiligi olmayan ilce ("
                + str(len(expected - found))
                + "): "
                + ", ".join(sorted(expected - found)[:10])
            )

        # Every district belongs to a province the registry knows. Cheap, and it is the
        # check that would have caught reading a district code as a plate number.
        provinces = set(
            load_areas().filter(pl.col("area_level") == "province")["area_id"]
        )
        parents = {area[:5] for area in found}
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


#: One adapter class per district measure, built from the table above.
DISTRICT_VITAL_ADAPTERS = {
    "tuik_" + spec[0]: type(
        "Tuik" + "".join(part.title() for part in spec[0].split("_")),
        (DistrictVital,),
        {"stem": stem, "spec": spec, "__doc__": "MEDAS district measure: " + spec[0]},
    )
    for stem, spec in MEASURES.items()
}
