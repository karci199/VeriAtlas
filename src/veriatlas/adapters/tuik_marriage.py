"""Marriage and divorce at the levels the province files do not reach.

Three measures, downloaded by `scripts/fetch_medas_marriage.py`:

* **İlçelere göre evlenmeler** — district, 2014-2025, counted **where the wedding was**.
* **Erkeğin ikametgah yeri** — district, 2014-2025: divorces counted at **the man's
  registered address**. TÜİK publishes no other district-level divorce series.
* **Yaş grubuna göre ilk defa evlenen** — province, 2001-2025, by the **bride's** age.

The first two share a level, and a check settled what to say about them: both sum to the
province totals **exactly**, in all twelve years and to the person. So they are not two
different counts — they are the same events, allocated to districts by two different
rules. Nationally they agree; inside one district the marriage figure answers "where were
the weddings" and the divorce figure answers "where do the men live", which is why the
ratio of one to the other is the thing to avoid and the definitions say so.

The third is by the woman's age band alone. MEDAS offers the groom's bands as a separate
breakdown and the export came back with eleven indicators rather than a hundred and
twenty-one, so what is here is the bride's age — which is also the side that pairs with a
denominator we hold, since the marital-status table is read for women (see
`build_marriage_excel`). The groom's side is a second download, not a rearrangement of
this one.

The file shape is the transposed one `tuik_vital` already reads: areas across the header,
the breakdown and the year down the rows. What differs is the header — a district is
written `Adana(Aladağ)-1757`, where the number is MEDAS's own code and not a plate number
— so the area lookup is the one thing this module adds.
"""

from __future__ import annotations

import datetime as dt
import re
from functools import cache
from pathlib import Path

import polars as pl

from ..areas import load_districts
from ..config import RAW
from ..indicators import get
from ..schema import FACT_COLUMNS, format_dims
from .tuik_median_age import area_of, single_province_regions
from .tuik_vital import read_export

DOWNLOADS = RAW / "medas" / "evlenme"

#: `Kadının yaş grubu:16-19` — the side and the band in one label.
BRIDE_AGE = re.compile(
    r"(?P<taraf>Kadının|Erkeğin)\s+yaş\s+grubu\s*:\s*(?P<age>[^ ]+(?:\+)?)"
)

SIDES = {"Kadının": "female", "Erkeğin": "male"}

#: `Kadının eğitim durumu:Lise Ve Dengi Meslek Okulu` — the second half of the education
#: file's label. Read from its own pattern rather than by splitting on " ve ", because the
#: school names contain that word ("Lise Ve Dengi…") and splitting would cut one in half.
BRIDE_EDUCATION = re.compile(r"eğitim\s+durumu\s*:\s*(?P<egitim>.+?)\s*$")

#: TÜİK's school names to ids. `İlkokul` and `İlköğretim` both appear and are **not** the
#: same thing: the first is the five-year school of the old system and the second the
#: eight-year one that replaced it in 1997. Someone who finished one did not finish the
#: other, and folding them together would erase the reform from the series.
EDUCATION = {
    "Okuma Yazma Bilmeyen": "illiterate",
    "Okuma Yazma Bilen Fakat Bir Okul Bitirmeyen": "literate_no_school",
    "İlkokul": "primary_5",
    "İlköğretim": "basic_8",
    "Ortaokul Veya Dengi Meslek Ortaokul": "lower_secondary",
    "Lise Ve Dengi Meslek Okulu": "upper_secondary",
    "Yüksek Öğretim": "higher",
    "Bilinmeyen": "unknown",
}


@cache
def district_codes() -> dict[str, str]:
    """MEDAS's district code to our area id.

    The registry carries `medas_code` for exactly this: TÜİK's district numbering is its
    own and matches nothing else, and matching on the name instead would collide on the
    forty-odd districts called Merkez.
    """
    rows = load_districts().filter(pl.col("medas_code").is_not_null())
    return {
        str(int(code)): area_id
        for area_id, code in rows.select("area_id", "medas_code").iter_rows()
    }


def resolve(code: str, single: dict[str, str]) -> tuple[str, str] | None:
    """A code from the header to `(area_id, level)`.

    Districts are tried first and provinces second, and the order is the whole of the
    correctness here: a plate number is one or two digits and a MEDAS district code is
    four, but `area_of` accepts any digits as a plate, so `1757` would quietly become
    "TR-1757" — an id no registry has, joined to nothing, dropped without a word.
    """
    districts = district_codes()
    if code in districts:
        return (districts[code], "district")
    return area_of(code, single)


#: file stem → (adapter name, indicator id, how the row label is read, fixed dims, levels)
MEASURES = {
    "ilce-evlenme": ("district_marriages", "district_marriages", None, {}),
    "ilce-bosanma": ("district_divorces", "district_divorces", None, {}),
    "ilk-evlenme-yas": (
        "first_marriages_by_age",
        "first_marriages_by_age",
        "bride_age",
        {},
    ),
    "ilk-evlenme-egitim": (
        "first_marriages_by_education",
        "first_marriages_by_education",
        "bride_age_education",
        {},
    ),
}


def read_label(label: str, dim: str | None, fixed: dict) -> str | None:
    """The dims a row carries, or None when the row cannot be placed.

    None is a refusal, not a zero: a row whose breakdown we cannot read must not be folded
    into a total, because the total would then be right for the wrong reason and the
    breakdown short by an amount nothing reports.
    """
    if dim is None:
        return format_dims(fixed) if fixed else ""
    found = BRIDE_AGE.search(label)
    if not found:
        return None
    values = {}
    if dim == "bride_age_education":
        school = BRIDE_EDUCATION.search(label)
        if not school or school.group("egitim") not in EDUCATION:
            # An unread school is a refusal for the same reason an unread age band is: it
            # would fall into whatever total the caller sums next, and the distribution
            # would come up short by an amount nothing reports.
            return None
        values["education"] = EDUCATION[school.group("egitim")]
    return format_dims(
        {
            **fixed,
            **values,
            "sex": SIDES[found.group("taraf")],
            # `Bilinmeyen` is kept as a band for the reason the death file's is: dropping it
            # makes the age groups sum to less than the published total and says nothing.
            "age": "unknown"
            if found.group("age").strip() == "Bilinmeyen"
            else found.group("age").strip(),
        }
    )


class MarriageMeasure:
    """One measure, one indicator — the contract every adapter keeps."""

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
        path = raw / ("nufus-" + self.stem + ".csv")
        if not path.exists():
            raise FileNotFoundError("indirilmemis: " + str(path))

        records = read_export(
            path,
            self.spec,
            single_province_regions(),
            resolve=resolve,
            label=read_label,
        )
        if not records:
            raise ValueError("dosya bos: " + path.name)

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
        return frame.select(FACT_COLUMNS)


MARRIAGE_ADAPTERS = {
    "tuik_" + spec[0]: type(
        "Tuik" + "".join(part.title() for part in spec[0].split("_")),
        (MarriageMeasure,),
        {"stem": stem, "spec": spec, "__doc__": "MEDAS marriage measure: " + spec[0]},
    )
    for stem, spec in MEASURES.items()
}
