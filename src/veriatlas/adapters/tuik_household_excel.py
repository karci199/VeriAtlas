"""The NİP workbooks: household size, educational attainment, tenure, building age.

TÜİK's population portal (nip.tuik.gov.tr) draws these from
`POST /Home/GetInformation`, which answers with an HTML table for one province at a
time. Its download button hands over the same numbers with all 81 provinces in one
workbook, so that is what is read — 81 requests per measure avoided, and a file whose
checksum the manifest can record. `docs/nip-hanehalki.md` keeps the endpoint, for the
day a measure appears on the portal that the download does not cover.

Each workbook arrives wide: the breakdown across the header, a province down the rows.

Four things the files do not say about themselves:

* **`tenure` and `building-age` carry no year.** They are one cross-section and which
  one is written nowhere in the file. Their `Toplam` matches the household-type
  workbook's 2021 count in all 81 provinces and no other year, so 2021 it is —
  `check_cross_section_year` re-derives that on every run rather than trusting this
  sentence, because a refreshed download would otherwise be filed under the old date.
* **`education-attainment` ships every row twice.** 28.367 rows, 14.581 distinct. Summed
  as delivered every number doubles, so duplicates are dropped and the remaining count
  checked against years x provinces x levels.
* **`TOPLAM` is a row, not a level**, and `sex=total` is a column, not a sex. Both are
  sums of values stored beside them; keeping either would let "Tümü (topla)" count the
  same people twice. Dropped — and the sex column was checked first: erkek + kadın
  equals toplam in 13.122 of 13.122 province-year-levels.
* **Province names arrive upper-cased.** Turkish upper-casing is not `str.upper`:
  that spells `Siirt` as `SIIRT` and the province stops matching. The registry side is
  cased with `upper_tr` and matched exactly; an unmatched name raises.

Household *type* is not loaded here. `tuik_simple` already brings `household_by_type`
from MEDAS for the same 972 province-years, and a second copy of a number is a second
thing to keep in step. The workbook is still read — `check_cross_section_year` needs its
totals — and `scripts/convert_household_excel.py` compares the two.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .base import cached_copy

#: Where the workbooks are downloaded to by hand, and the copy under `raw/` that every
#: load actually reads. Same arrangement as the other desktop-sourced adapters: the
#: original moves, the copy is the one the manifest describes.
DESKTOP = Path.home() / "OneDrive" / "Desktop" / "demografi"
DOWNLOADS = RAW / "tuik" / "hanehalki"

#: Copy stem to the name the portal gives the file. Kept apart because the download name
#: is Turkish and full of characters that a path should not have to carry (K1).
WORKBOOKS = {
    "household-size": "Hanehalkı Büyüklüğüne Göre Hanehalkı Sayısı.xlsx",
    "household-type": "Hanehalkı Tipi.xlsx",
    "education-attainment": "Eğitim Durumu.xlsx",
    "tenure": "Mülkiyet-Hanehalkı Sayısı.xlsx",
    "building-age": "İnşa Yılı-Hanehalkı Sayısı.xlsx",
}

#: Turkish upper-casing. `str.upper` maps `ı` to `I` correctly and `i` to `I` as well,
#: which is the one case that matters here.
_UPPER = str.maketrans({"i": "İ", "ı": "I"})


def upper_tr(name: str) -> str:
    return name.translate(_UPPER).upper()


def squeeze(text: str) -> str:
    """Collapse the line breaks the workbook wraps long headers with.

    Where a header breaks is a column width, not data, so the maps below are written on
    one line and matched after this.
    """
    return " ".join(text.split())


#: Nine single sizes and an open top band. The band keeps a name that is not `10`, so a
#: reader cannot mistake it for exactly ten.
SIZES = {str(n): str(n) for n in range(1, 10)} | {"10+": "10p"}

#: The four types that partition the whole — same ids as `tuik_simple`, because
#: `scripts/convert_household_excel.py` compares the two sets of rows.
HOUSEHOLD_TYPES = {
    "Tek Kişilik Hanehalkı": "single_person",
    "Tek Çekirdek Aileden Oluşan Hanehalkı": "one_nuclear_family",
    "En Az Bir Çekirdek Aile ve Diğer Kişilerden Oluşan Hanehalkı": "nuclear_and_others",
    "Çekirdek Aile Bulunmayan Birden Fazla Kişiden Oluşan Hanehalkı": "no_nuclear_family",
}

#: Highest level completed, population 6 and over. `İLKÖĞRETİM` is not a spelling of
#: `İLKOKUL`: it is the eight-year basic school that ran alongside the older five-year
#: primary, so the two are different levels and both are kept.
EDUCATION_LEVELS = {
    "OKUMA YAZMA BİLMEYEN": "illiterate",
    "OKUMA YAZMA BİLEN FAKAT BİR OKUL BİTİRMEYEN": "literate_no_diploma",
    "İLKOKUL": "primary",
    "ORTAOKUL VEYA DENGİ MESLEK OKULU": "lower_secondary",
    "İLKÖĞRETİM": "basic_education",
    "LİSE VEYA DENGİ MESLEK OKULU": "upper_secondary",
    "YÜKSEKOKUL VEYA FAKÜLTE": "tertiary",
    "YÜKSEK LİSANS VE ÜZERİ": "postgraduate",
    "BİLİNMEYEN": "unknown",
}

#: A row that is the sum of the nine above, dropped rather than stored.
EDUCATION_TOTAL = "TOPLAM"

#: Column to sex id. `Toplam` is deliberately absent — it is `Erkek` + `Kadın`.
EDUCATION_SEXES = {"male": "male", "female": "female"}

TENURE = {
    "Ev Sahibi": "owner",
    "Kiracı": "tenant",
    "Diğer": "other",
    "Bilinmeyen": "unknown",
}

BUILDING_AGE = {
    "1980 ve Öncesi": "pre_1981",
    "1981 ve 2000 Arası": "between_1981_2000",
    "2001 ve Sonrası": "post_2000",
    "Bilinmeyen": "unknown",
}

#: The year the two year-less workbooks describe. Asserted on every run, not assumed.
CROSS_SECTION_YEAR = 2021


def province_ids() -> dict[str, str]:
    """Upper-cased province name to `area_id`, the way the workbooks spell it."""
    registry = load_areas().filter(pl.col("area_level") == "province")
    return {
        upper_tr(name): area_id
        for name, area_id in zip(registry["name_tr"], registry["area_id"], strict=True)
    }


def to_area_id(frame: pl.DataFrame, column: str = "il") -> pl.DataFrame:
    """Replace the province name with its id, raising on a name the registry lacks.

    Raising rather than dropping: a province quietly absent draws as "veri yok" in the
    middle of the map, which looks exactly like a real gap in the source.
    """
    ids = province_ids()
    names = frame[column].str.strip_chars()
    unknown = sorted(set(names.to_list()) - set(ids))
    if unknown:
        raise KeyError("registryde olmayan il adi: " + ", ".join(unknown))
    return frame.with_columns(names.replace_strict(ids).alias("area_id")).drop(column)


def read_workbook(stem: str, header_row: int | None = 1) -> pl.DataFrame:
    """One workbook, headers squeezed, read from the copy under `raw/`."""
    options: dict = (
        {"header_row": header_row}
        if header_row is not None
        else {"header_row": None, "skip_rows": 2}
    )
    frame = pl.read_excel(DOWNLOADS / f"{stem}.xlsx", read_options=options)
    if header_row is not None:
        frame.columns = [squeeze(name) for name in frame.columns]
    return frame


def unpivot(
    frame: pl.DataFrame, dim: str, columns: dict[str, str], extra: str | None = None
) -> pl.DataFrame:
    """Melt the breakdown columns into one row per observation.

    A column named here that the workbook lacks raises: renamed upstream it would
    contribute nothing, and the totals would come up short with nothing on screen
    saying why. Columns the workbook has and this does not name are dropped — that is
    how `Toplam` stays out.
    """
    missing = set(columns) - set(frame.columns)
    if missing:
        raise KeyError("dosyada olmayan sutun: " + ", ".join(sorted(missing)))

    index = ["area_id", "year"] + ([extra] if extra else [])
    melted = (
        frame.unpivot(
            on=list(columns),
            index=index,
            variable_name="breakdown",
            value_name="value",
        )
        .drop_nulls("value")
        .with_columns(pl.col("breakdown").replace_strict(columns))
    )
    keys = [dim, extra] if extra else [dim]
    return melted.with_columns(
        pl.struct(pl.col("breakdown").alias(dim), *([extra] if extra else []))
        .map_elements(
            lambda row: format_dims({key: row[key] for key in keys}),
            return_dtype=pl.String,
        )
        .alias("dims"),
        pl.col("value").cast(pl.Int64),
        pl.col("year").cast(pl.Int64),
    ).select("area_id", "year", "dims", "value")


def household_types() -> pl.DataFrame:
    """The household-type workbook in long form. Read, never loaded — see the docstring."""
    frame = read_workbook("household-type")
    frame = frame.rename({frame.columns[0]: "year", frame.columns[1]: "il"})
    return unpivot(to_area_id(frame), "household_type", HOUSEHOLD_TYPES)


def check_cross_section_year() -> None:
    """Confirm the year-less workbooks really describe `CROSS_SECTION_YEAR`.

    Their `Toplam` is the household count, which the household-type workbook publishes
    for every year from 2014. Exactly one year can match in all 81 provinces at once; if
    a refreshed download makes it another one, this fails loudly instead of stamping new
    numbers with the old date.
    """
    tenure = read_workbook("tenure")
    totals = (
        tenure.rename({tenure.columns[0]: "il", "Toplam": "total"})
        .pipe(to_area_id)
        .select("area_id", "total")
    )
    matching = (
        household_types()
        .group_by("area_id", "year")
        .agg(pl.col("value").sum().alias("households"))
        .join(totals, on="area_id")
        .filter(pl.col("households") == pl.col("total"))
        .group_by("year")
        .len()
        .filter(pl.col("len") == totals.height)["year"]
        .to_list()
    )
    if matching != [CROSS_SECTION_YEAR]:
        raise ValueError(
            f"kesit yili dogrulanamadi: eslesen yillar {sorted(matching)}, "
            f"{CROSS_SECTION_YEAR} bekleniyordu"
        )


def household_sizes() -> pl.DataFrame:
    """Households by number of members: province x 2012-2025 x 1..9, 10+."""
    frame = read_workbook("household-size", header_row=None)
    frame.columns = ["year", "il", *SIZES]
    return unpivot(to_area_id(frame), "household_size", dict(SIZES))


def education() -> pl.DataFrame:
    """Population 6+ by highest level completed and sex: province x 2008-2025."""
    frame = read_workbook("education-attainment")
    frame.columns = ["year", "il", "level", "total", "male", "female", "_m%", "_f%"]
    frame = frame.drop("_m%", "_f%").drop_nulls("il").unique(keep="first")

    levels = set(frame["level"].unique()) - {EDUCATION_TOTAL}
    unknown = sorted(levels - set(EDUCATION_LEVELS))
    if unknown:
        raise KeyError("taninmayan egitim seviyesi: " + ", ".join(unknown))

    # The duplicate rows are gone by here, so the count is the file's real shape and a
    # missing province-year shows up as a number that is not the product below.
    expected = frame["year"].n_unique() * frame["il"].n_unique() * (len(levels) + 1)
    if len(frame) != expected:
        raise ValueError(
            f"egitim dosyasi eksik ya da fazla: {len(frame)} satir, {expected} bekleniyordu"
        )

    # `Toplam` is dropped rather than stored, and checked before it goes: if the two
    # sexes ever stop adding up to it, dropping it would be losing a number instead of
    # saving a duplicate.
    mismatched = frame.filter(
        pl.col("male") + pl.col("female") != pl.col("total")
    ).height
    if mismatched:
        raise ValueError(f"erkek + kadin toplama esit degil: {mismatched} satir")

    frame = (
        frame.filter(pl.col("level") != EDUCATION_TOTAL)
        .drop("total")
        .with_columns(pl.col("level").replace_strict(EDUCATION_LEVELS))
        .rename({"level": "education_level"})
        .pipe(to_area_id)
    )
    return unpivot(frame, "sex", EDUCATION_SEXES, extra="education_level")


def cross_section(stem: str, dim: str, columns: dict[str, str]) -> pl.DataFrame:
    """One of the two year-less workbooks, stamped with the year that was verified."""
    frame = read_workbook(stem)
    frame = frame.rename({frame.columns[0]: "il"}).with_columns(
        pl.lit(CROSS_SECTION_YEAR).alias("year")
    )
    return unpivot(to_area_id(frame), dim, columns)


class HouseholdWorkbook:
    """One workbook, one indicator — the contract `ingest` validates against.

    Written as one class per measure for the reason `tuik_simple` gives: `ingest` checks
    a frame against *the* indicator its adapter declares, so a frame carrying four of
    them fails on the first dimension check.
    """

    source_id = "tuik_nip"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 30)

    #: Filled in by the subclasses below.
    stem = ""
    indicator_id = ""

    def fetch(self) -> Path:
        return cached_copy(
            DESKTOP / WORKBOOKS[self.stem], DOWNLOADS / f"{self.stem}.xlsx"
        )

    def rows(self) -> pl.DataFrame:
        raise NotImplementedError

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        frame = self.rows().with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        )

        expected = set(
            load_areas().filter(pl.col("area_level") == "province")["area_id"]
        )
        missing = expected - set(frame["area_id"])
        if missing:
            raise KeyError(
                self.indicator_id
                + ": dosyada karsiligi olmayan il ("
                + str(len(missing))
                + "): "
                + ", ".join(sorted(missing))
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


class TuikHouseholdSize(HouseholdWorkbook):
    stem = "household-size"
    indicator_id = "household_by_size"

    def rows(self) -> pl.DataFrame:
        return household_sizes()


class TuikEducationAttainment(HouseholdWorkbook):
    stem = "education-attainment"
    indicator_id = "education_attainment"

    def rows(self) -> pl.DataFrame:
        return education()


class TuikHouseholdTenure(HouseholdWorkbook):
    stem = "tenure"
    indicator_id = "household_by_tenure"

    def rows(self) -> pl.DataFrame:
        check_cross_section_year()
        return cross_section(self.stem, "tenure", TENURE)


class TuikBuildingAge(HouseholdWorkbook):
    stem = "building-age"
    indicator_id = "household_by_building_age"

    def rows(self) -> pl.DataFrame:
        check_cross_section_year()
        return cross_section(self.stem, "building_period", BUILDING_AGE)


#: Registered in `adapters/__init__.py`, run by `scripts/load.py`.
HOUSEHOLD_ADAPTERS = {
    "tuik_household_size": TuikHouseholdSize,
    "tuik_education_attainment": TuikEducationAttainment,
    "tuik_household_tenure": TuikHouseholdTenure,
    "tuik_building_age": TuikBuildingAge,
}
