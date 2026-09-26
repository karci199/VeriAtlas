r"""Urban/rural population by the pre-2013 legal definition (TÜİK ADNKS, 2007-2025).

Before DEGURBA (`tuik_urban_rural_degurba.py`), TÜİK split ADNKS population into "Şehir"
(province and district *centre* population, "il/ilçe merkezi") and "Köy" (everything
else — belde and köy). Two workbooks the user downloaded from the ADNKS pivot tool carry
this split every year 2007-2025, at province ("İllere Göre Kent Kır Nüfusu.xls") and
district level ("İlçelere Göre Kent Kır Nüfusu.xls"); copies at
`raw/tuik/adnks/il-kent-kir-nufusu-2007-2025.xls` and `ilce-...`.

This series is not a rival to DEGURBA, it is a different, administrative question:
whether a settlement was legally a merkez or not, not how dense it actually is. It
answers "was Kalecik's centre kent" for 2007-2012 in exactly the sense the question
means — an answer DEGURBA (built for today, density-based) cannot give for past years.

**The break the law made, not a data fault:** the 2012 metropolitan-municipality law
(6360) abolished belde and köy status inside büyükşehir provinces from March 2014, so
from 2013 their "Köy" cell is blank — not zero, *no longer a legal category* — and every
resident of a büyükşehir counts as "Şehir" from then on, however rural the place. This is
`urban_rural_legal_no_village_category` in `dims`, kept as a flag rather than silently
turned into a 0 that would claim those provinces had no rural population.

District rows are labelled "İl(İlçe)-<MEDAS kodu>"; the MEDAS code is resolved to the
district that held it in that year (`tuik_vital_district.districts_by_code`/`area_at`),
the same lookup the crop adapters use, because codes have been reassigned over time.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl
import xlrd

from ..config import RAW
from .kgm import province_id
from .tuik_vital_district import area_at, districts_by_code

FOLDER = (
    RAW / "tuik" / "adnks"
    if (RAW / "tuik" / "adnks").exists()
    else Path("C:/veri-ham/tuik/adnks")
)
PROVINCE_FILE = FOLDER / "il-kent-kir-nufusu-2007-2025.xls"
DISTRICT_FILE = FOLDER / "ilce-kent-kir-nufusu-2007-2025.xls"
NO_VILLAGE_CATEGORY_FROM = 2013


def rows_of(path: Path) -> list[tuple[int, str, float | None, float]]:
    """(year, label, village_population_or_None, town_population) per data row."""
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    header = (
        next(i for i in range(sheet.nrows) if sheet.cell_value(i, 0) == "Satırlar") + 3
    )
    out = []
    year = None
    for i in range(header, sheet.nrows):
        cell_year = sheet.cell_value(i, 0)
        if cell_year != "":
            year = int(cell_year)
        label = sheet.cell_value(i, 1)
        if not label:
            continue
        village = sheet.cell_value(i, 2)
        town = sheet.cell_value(i, 3)
        out.append(
            (year, label, (None if village == "" else float(village)), float(town))
        )
    return out


def province_rows() -> list[dict]:
    records = []
    for year, label, village, town in rows_of(PROVINCE_FILE):
        name = re.sub(r"-\d+$", "", label)
        area_id = province_id(name)
        records += _pair(area_id, year, village, town)
    return records


def district_rows() -> list[dict]:
    codes = districts_by_code()
    records = []
    for year, label, village, town in rows_of(DISTRICT_FILE):
        code = re.search(r"-(\d+)$", label).group(1)
        candidates = codes.get(code)
        if not candidates:
            raise ValueError(f"{label}: MEDAS kodu tanınmadı")
        area_id = area_at(candidates, year)
        if area_id is None:
            raise ValueError(f"{label} {year}: bu yıl için ilçe eşleşmedi")
        records += _pair(area_id, year, village, town)
    return records


def _pair(area_id: str, year: int, village: float | None, town: float) -> list[dict]:
    period = dt.date(year, 1, 1)
    rows = [
        {
            "area_id": area_id,
            "period_start": period,
            "dims": "settlement=town",
            "value": town,
        }
    ]
    if village is None and year >= NO_VILLAGE_CATEGORY_FROM:
        # the law abolished the category everywhere in a büyükşehir, regardless of
        # whether this particular district had any village population before it
        rows.append(
            {
                "area_id": area_id,
                "period_start": period,
                "dims": "settlement=urban_rural_legal_no_village_category",
                "value": 1.0,
            }
        )
    elif village is None:
        # a district that was always fully urban (a central ilçe: Çankaya, Etimesgut,
        # Yenimahalle in 2007) prints no village row at all — a real zero, not missing
        rows.append(
            {
                "area_id": area_id,
                "period_start": period,
                "dims": "settlement=village",
                "value": 0.0,
            }
        )
    else:
        rows.append(
            {
                "area_id": area_id,
                "period_start": period,
                "dims": "settlement=village",
                "value": village,
            }
        )
    return rows


class UrbanRuralLegal:
    source_id = "tuik_adnks"
    indicator_id = "urban_rural_legal"
    area_level = ""
    rows_fn = staticmethod(province_rows)

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        frame = pl.DataFrame(self.rows_fn())
        return frame.select(
            pl.lit(self.indicator_id).alias("indicator_id"),
            "area_id",
            pl.lit(self.area_level).alias("area_level"),
            "period_start",
            "dims",
            pl.col("value").cast(pl.Float64),
            pl.lit("annual").alias("frequency"),
            pl.lit("person").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 27)).alias("retrieved_at"),
        )


class UrbanRuralLegalProvince(UrbanRuralLegal):
    area_level = "province"
    rows_fn = staticmethod(province_rows)


class UrbanRuralLegalDistrict(UrbanRuralLegal):
    indicator_id = "urban_rural_legal_district"
    area_level = "district"
    rows_fn = staticmethod(district_rows)


URBAN_RURAL_LEGAL_ADAPTERS = {
    "urban_rural_legal": UrbanRuralLegalProvince,
    "urban_rural_legal_district": UrbanRuralLegalDistrict,
}
