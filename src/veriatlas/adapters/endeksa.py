"""Endeksa: a neighbourhood-level snapshot, elections and origin provinces.

Endeksa (endeksa.com) sells a property-market view of Türkiye, and under it sits a
neighbourhood table nobody else publishes at that level: five-year age bands by sex,
education, marital status, a socio-economic grade, household income and spending, the
neighbourhood's area in km², and every election since 2011 with the electorate and
turnout. `scripts/endeksa_fetch.js` pulls it district by district into
`raw/endeksa/<district_id>/` (docs/endeksa.md says how); this module turns those files
into fact-table rows.

What is measured and what is modelled is kept apart by `quality_flag`. Age, sex,
education, marital status and household counts reproduce TÜİK ADNKS 2024 to the person
(İznik: 45.208 against 45.208; Beyler 1.442 = 317 + 1.125), so they are `measured`.
The SES grade, income, spending and owner/tenant shares are Endeksa's own model and are
stored `estimated`, which is the badge the screen shows for them.

Three things a reader of these files must know:

* **Placeholders.** In a small former village Endeksa has no neighbourhood data and
  answers with a template — household count 0, income 4.885, every age band 0. Those
  rows are not small numbers, they are no numbers, and they are skipped for every
  demographic measure. Elections and origin provinces are real in those places and
  are kept. The rule is `HouseholdCount == 0`.
* **One year.** The snapshot is 2024 and nothing else; the time series is TÜİK's. The
  only series Endeksa carries are property sales and listings, 2012-2024, and those are
  stored per year.
* **Names, once.** Endeksa's `DistrictId` is its own; the identity here is the MEDAS
  code (K15), found by matching the neighbourhood name within the district. A name that
  does not match is refused, not dropped — a neighbourhood silently missing from the
  map looks exactly like "no data".

The contract is one adapter per indicator (see `tuik_simple`), so the classes at the
bottom are generated from `MEASURES`; the shared reader runs once per process.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import polars as pl

from ..areas import load_areas, load_neighbourhoods
from ..config import RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "endeksa"

SNAPSHOT_YEAR = 2024

AGE_BANDS = {
    "0_4": "0-4",
    "5_9": "5-9",
    "10_14": "10-14",
    "15_19": "15-19",
    "20_24": "20-24",
    "25_29": "25-29",
    "30_34": "30-34",
    "35_39": "35-39",
    "40_44": "40-44",
    "45_49": "45-49",
    "50_54": "50-54",
    "55_59": "55-59",
    "60_64": "60-64",
    "65": "65+",
}
SEXES = {"Total": None, "Male": "male", "Female": "female"}
MARITAL = {
    "MarriedNever": "never_married",
    "Married": "married",
    "Divorced": "divorced",
    "Widow": "widowed",
}
EDUCATION = {
    "EduNonLiterated": "illiterate",
    "EduLiteratedUntutored": "literate_no_school",
    "EduPrimarySchool": "primary_school",
    "EduPrimaryEducation": "primary_education",
    "EduMiddleSchool": "middle_school",
    "EduHighSchool": "high_school",
    "EduLicenseDegree": "bachelor",
    "EduGraduate": "master",
    "EduDoctorate": "doctorate",
    "EduUnknown": "unknown",
}
SES = {
    "SesGroupAPlus": "a_plus",
    "SesGroupA": "a",
    "SesGroupB": "b",
    "SesGroupC": "c",
    "SesGroupD": "d",
}
EXPENSE = {
    "ExpenseFood": "food",
    "ExpenseAlcoholAndSmoking": "alcohol_tobacco",
    "ExpenseClothing": "clothing",
    "ExpenseShelter": "housing",
    "ExpenseFurniture": "furnishing",
    "ExpenseHealth": "health",
    "ExpenseTransportation": "transport",
    "ExpenseCommunication": "communication",
    "ExpenseEntertainment": "recreation",
    "ExpenseEducation": "education",
    "ExpenseRestaurant": "restaurants",
    "ExpenseOther": "other",
}
DWELLING_TYPES = {
    "HousingCount": "dwelling",
    "SummerResortCount": "summer_house",
    "CommercialCount": "commercial",
}

#: Endeksa's election codes → (election id, polling day). The id is the fact-table value;
#: the date is `period_start`, so two contests held the same day (2018, 2023, 2024) are
#: told apart by the `election` dimension, not by the period.
ELECTIONS: dict[str, tuple[str, dt.date]] = {
    "2011genelsecim": ("general_2011", dt.date(2011, 6, 12)),
    "2014yerel": ("local_2014", dt.date(2014, 3, 30)),
    "2014cumhurbaskani": ("president_2014", dt.date(2014, 8, 10)),
    "2015haziran": ("general_2015_06", dt.date(2015, 6, 7)),
    "2015kasim": ("general_2015_11", dt.date(2015, 11, 1)),
    "2017anayasa": ("referendum_2017", dt.date(2017, 4, 16)),
    "2018cumhurbaskani": ("president_2018", dt.date(2018, 6, 24)),
    "2018genel": ("general_2018", dt.date(2018, 6, 24)),
    "2019yerelseçimilçebelediye": ("local_2019_district", dt.date(2019, 3, 31)),
    "2019yerelseçimbelediyemeclisi": ("local_2019_council", dt.date(2019, 3, 31)),
    "2019yerelseçimbüyükşehir": ("local_2019_metro", dt.date(2019, 3, 31)),
    # İl genel meclisi: in the neighbourhood records of the 51 non-metropolitan
    # provinces, never in the district's own.
    "2019yerelseçimilbelediyemeclisi": ("local_2019_provincial", dt.date(2019, 3, 31)),
    "2023genel": ("general_2023", dt.date(2023, 5, 14)),
    "2023CumhurTur1": ("president_2023_r1", dt.date(2023, 5, 14)),
    "2023CumhurTur2": ("president_2023_r2", dt.date(2023, 5, 28)),
    "2024yerelseçimbelediyebaşkanlığı": ("local_2024_district", dt.date(2024, 3, 31)),
    "2024yerelseçimbelediyemeclisüyeliği": ("local_2024_council", dt.date(2024, 3, 31)),
    "2024yerelseçimbüyükşehirbelediyebaşkanlığı": (
        "local_2024_metro",
        dt.date(2024, 3, 31),
    ),
}

#: Electorate figures carried on every election record, by indicator.
ELECTORATE = {
    "electorate": "KayitliSecmen",
    "votes_cast": "KullanilanOy",
    "valid_votes": "GecerliOy",
    "invalid_votes": "GecersizOy",
    "ballot_boxes": "SandikSayisi",
}


# region Reading


def norm(s: str) -> str:
    """Turkish-aware lowercase with the settlement suffix dropped, for name matching."""
    s = s.replace("I", "ı").replace("İ", "i").lower()
    return re.sub(r"\s*(mah\.|mahallesi|mah)$", "", s).strip()


def slug(s: str) -> str:
    """A dimension value from a label: `AK Parti` → `ak_parti`, `İYİ` → `iyi`."""
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    return re.sub(r"[^a-z0-9]+", "_", s.translate(tr).lower()).strip("_")


@dataclass(frozen=True)
class Quarter:
    area_id: str
    district_id: str
    endeksa_id: str
    demography: dict
    placeholder: bool
    elections: list[dict]
    fellows: list[dict]


@dataclass(frozen=True)
class District:
    district_id: str
    demography: dict
    elections: list[dict]
    fellows: list[dict]
    quarters: tuple[Quarter, ...]


def read_district(folder: Path, known: dict[tuple[str, str], str]) -> District:
    """One `raw/endeksa/<district>/` folder to records, refusing unmatched names."""
    district_id = folder.name
    county = json.loads((folder / "county.json").read_text("utf-8"))
    election = json.loads((folder / "election.json").read_text("utf-8"))
    fellows = json.loads((folder / "fellowcountryman.json").read_text("utf-8"))

    quarters: list[Quarter] = []
    missing: list[str] = []
    for path in sorted(folder.glob("*.json")):
        if not path.name[0].isdigit():
            continue
        demo = json.loads(path.read_text("utf-8"))["Demography"]
        did = str(demo["DistrictId"])
        area_id = known.get((district_id, norm(demo["DistrictName"])))
        if area_id is None:
            missing.append(demo["DistrictName"])
            continue
        quarters.append(
            Quarter(
                area_id=area_id,
                district_id=district_id,
                endeksa_id=did,
                demography=demo,
                placeholder=demo["HouseholdCount"] == 0,
                elections=election["quarters"].get(did, []),
                fellows=fellows["quarters"].get(did, {}).get("FellowCountryman", [])
                or [],
            )
        )
    if missing:
        raise KeyError(
            district_id
            + ": MEDAS kaydinda karsiligi olmayan mahalle ("
            + str(len(missing))
            + "): "
            + ", ".join(missing)
        )
    return District(
        district_id=district_id,
        demography=county["Demography"],
        elections=election["county"] or [],
        fellows=(fellows["county"] or {}).get("FellowCountryman", []) or [],
        quarters=tuple(quarters),
    )


@lru_cache(maxsize=1)
def read_all() -> tuple[District, ...]:
    """Every downloaded district, read once per process."""
    folders = sorted(
        p for p in DOWNLOADS.iterdir() if p.is_dir() and (p / "county.json").exists()
    )
    if not folders:
        raise FileNotFoundError("indirilmis Endeksa ilcesi yok: " + str(DOWNLOADS))
    known = {
        (row["parent_id"], norm(row["name_tr"])): row["area_id"]
        for row in load_neighbourhoods().to_dicts()
    }
    return tuple(read_district(folder, known) for folder in folders)


@lru_cache(maxsize=1)
def province_ids() -> dict[str, str]:
    """`bilecik` → `TR-11`, for the origin-province dimension."""
    provinces = load_areas().filter(pl.col("area_level") == "province")
    return {norm(row["name_tr"]): row["area_id"] for row in provinces.to_dicts()}


# endregion

# region Measures
#
# Each extractor takes a demography dict (a quarter's or the district's) and yields
# (dims, value). `None` values are skipped. The flag says whether the number is TÜİK's
# or Endeksa's model; the reader above decides placeholders, which never reach here.

Row = tuple[dict[str, str] | None, float | None]
Extractor = Callable[[dict], list[Row]]


def age_sex(d: dict) -> list[Row]:
    out: list[Row] = []
    for key, band in AGE_BANDS.items():
        for suffix, sex in SEXES.items():
            dims = {"age": band} | ({"sex": sex} if sex else {})
            out.append((dims, d[f"Age_{key}_{suffix}"]))
    out.append(({"sex": "male"}, d["PopulationMale"]))
    out.append(({"sex": "female"}, d["PopulationFemale"]))
    out.append((None, d["PopulationTotal"]))
    return out


def by_map(mapping: dict[str, str], dim: str) -> Extractor:
    return lambda d: [({dim: value}, d[key]) for key, value in mapping.items()]


def scalar(key: str, scale: float = 1.0) -> Extractor:
    return lambda d: [(None, d[key] * scale if d.get(key) is not None else None)]


def tenure(d: dict) -> list[Row]:
    return [
        ({"tenure": "owner"}, d["OwnerShare"]),
        ({"tenure": "tenant"}, d["RentedShare"]),
    ]


@dataclass(frozen=True)
class Measure:
    indicator_id: str
    extract: Extractor
    quality_flag: str  # measured | estimated
    district_too: bool = True  # also store the district's own Endeksa figure


MEASURES: tuple[Measure, ...] = (
    # TÜİK-origin counts. The district figure is not stored: TÜİK's own is already in
    # the warehouse and the two differ by a few dozen people (institutional population).
    Measure("population", age_sex, "measured", district_too=False),
    Measure(
        "marital_status", by_map(MARITAL, "marital"), "measured", district_too=False
    ),
    Measure(
        "household_count", scalar("HouseholdCount"), "measured", district_too=False
    ),
    Measure("education_level", by_map(EDUCATION, "education"), "measured"),
    # Geography and stock.
    Measure("area", scalar("Area"), "measured"),
    Measure("dwelling_stock", by_map(DWELLING_TYPES, "dwelling_type"), "measured"),
    # Endeksa's model.
    Measure("ses_group", by_map(SES, "ses"), "estimated"),
    Measure("household_income", scalar("HouseIncomeTotal"), "estimated"),
    Measure("income_per_capita", scalar("HouseIncome"), "estimated"),
    Measure("household_saving", scalar("SavingTotal"), "estimated"),
    Measure("household_expense", by_map(EXPENSE, "expense_item"), "estimated"),
    Measure("housing_tenure", tenure, "estimated"),
    Measure("vehicle_count", scalar("CarCount"), "estimated"),
)

#: Yearly property series: indicator → (field prefix, dims). Stored per year, not as the
#: 2024 snapshot, because these are the one thing Endeksa publishes over time.
SERIES: dict[str, tuple[str, dict[str, str]]] = {
    "property_sales": ("Total_BB_Sale_", {"property_type": "dwelling"}),
    "property_sales_land": ("Total_AT_Sale_", {"property_type": "land"}),
    "property_listings": ("Total_Listing_", {}),
}
SERIES_YEARS = range(2012, 2025)

# endregion

# region Adapters


def _common(
    indicator_id: str, vintage: str, retrieved_at: dt.date, flag: str | None = None
) -> dict:
    indicator = get(indicator_id)
    cols = {
        "indicator_id": pl.lit(indicator_id),
        "frequency": pl.lit(indicator.frequency),
        "unit": pl.lit(indicator.unit.unit_id),
        "vintage": pl.lit(vintage),
        "source_id": pl.lit("endeksa"),
        "retrieved_at": pl.lit(retrieved_at),
    }
    if flag:
        cols["quality_flag"] = pl.lit(flag)
    return cols


SCHEMA = {
    "area_id": pl.String,
    "area_level": pl.String,
    "period_start": pl.Date,
    "dims": pl.String,
    "value": pl.Float64,
}
ORDER = [
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
]


class EndeksaBase:
    source_id = "endeksa"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 22)
    indicator_id = ""

    def fetch(self) -> Path:
        if not DOWNLOADS.exists():
            raise FileNotFoundError("indirilmis Endeksa dokumu yok: " + str(DOWNLOADS))
        return DOWNLOADS

    def frame(self, records: list[tuple], flag: str | None = None) -> pl.DataFrame:
        if not records:
            raise ValueError(self.indicator_id + ": dokumde satir yok")
        frame = pl.DataFrame(records, schema=list(SCHEMA), orient="row").cast(SCHEMA)
        return frame.with_columns(
            **_common(self.indicator_id, self.vintage, self.retrieved_at, flag)
        ).select(ORDER)


class SnapshotMeasure(EndeksaBase):
    """One 2024 figure per neighbourhood (and per district where Endeksa's own is kept)."""

    measure: Measure

    @property
    def indicator_id(self) -> str:  # type: ignore[override]
        return self.measure.indicator_id

    def parse(self, raw: Path) -> pl.DataFrame:
        start = dt.date(SNAPSHOT_YEAR, 1, 1)
        records: list[tuple] = []
        for district in read_all():
            targets = [
                (q.area_id, "neighbourhood", q.demography)
                for q in district.quarters
                if not q.placeholder
            ]
            if self.measure.district_too:
                targets.append((district.district_id, "district", district.demography))
            for area_id, level, demo in targets:
                for dims, value in self.measure.extract(demo):
                    if value is None:
                        continue
                    records.append(
                        (area_id, level, start, format_dims(dims), float(value))
                    )
        return self.frame(records, self.measure.quality_flag)


class PropertySeries(EndeksaBase):
    """Sales or listings, one row per year 2012-2024."""

    series: str

    @property
    def indicator_id(self) -> str:  # type: ignore[override]
        return self.series

    def parse(self, raw: Path) -> pl.DataFrame:
        prefix, dims = SERIES[self.series]
        records: list[tuple] = []
        for district in read_all():
            targets = [
                (q.area_id, "neighbourhood", q.demography) for q in district.quarters
            ]
            targets.append((district.district_id, "district", district.demography))
            for area_id, level, demo in targets:
                for year in SERIES_YEARS:
                    value = demo.get(prefix + str(year))
                    if value is None:
                        continue
                    records.append(
                        (
                            area_id,
                            level,
                            dt.date(year, 1, 1),
                            format_dims(dims),
                            float(value),
                        )
                    )
        return self.frame(records, "measured")


class Votes(EndeksaBase):
    """Votes by option, every election, neighbourhood and district."""

    indicator_id = "votes"

    def parse(self, raw: Path) -> pl.DataFrame:
        records: list[tuple] = []
        for district in read_all():
            targets = [
                (q.area_id, "neighbourhood", q.elections) for q in district.quarters
            ]
            targets.append((district.district_id, "district", district.elections))
            for area_id, level, elections in targets:
                for e in elections:
                    if e["Code"] not in ELECTIONS:
                        raise KeyError("taninmayan secim kodu: " + e["Code"])
                    election, day = ELECTIONS[e["Code"]]
                    for s in e["Secenekler"]:
                        # A null count is an option the source lists but did not count
                        # here (independents, "Diğer" in 2015) — not a zero.
                        if s["OySayisi"] is None:
                            continue
                        dims = format_dims(
                            {"election": election, "option": slug(s["Secenek"])}
                        )
                        records.append(
                            (area_id, level, day, dims, float(s["OySayisi"]))
                        )
        return self.frame(records, "measured")


class ElectorateMeasure(EndeksaBase):
    """Registered voters, votes cast, valid, invalid, ballot boxes — one adapter each."""

    field: str

    def parse(self, raw: Path) -> pl.DataFrame:
        records: list[tuple] = []
        for district in read_all():
            targets = [
                (q.area_id, "neighbourhood", q.elections) for q in district.quarters
            ]
            targets.append((district.district_id, "district", district.elections))
            for area_id, level, elections in targets:
                for e in elections:
                    election, day = ELECTIONS[e["Code"]]
                    value = e.get(self.field)
                    if value is None:
                        continue
                    records.append(
                        (
                            area_id,
                            level,
                            day,
                            format_dims({"election": election}),
                            float(value),
                        )
                    )
        return self.frame(records, "measured")


class OriginProvince(EndeksaBase):
    """Residents by province of civil registry — Endeksa's top ten per area."""

    indicator_id = "registry_origin"

    def parse(self, raw: Path) -> pl.DataFrame:
        start = dt.date(SNAPSHOT_YEAR, 1, 1)
        ids = province_ids()
        records: list[tuple] = []
        for district in read_all():
            targets = [
                (q.area_id, "neighbourhood", q.fellows) for q in district.quarters
            ]
            targets.append((district.district_id, "district", district.fellows))
            for area_id, level, fellows in targets:
                for f in fellows:
                    origin = ids.get(norm(f["CitizenCity"]))
                    if origin is None:
                        raise KeyError("taninmayan il adi: " + f["CitizenCity"])
                    records.append(
                        (
                            area_id,
                            level,
                            start,
                            format_dims({"origin": origin}),
                            float(f["CountOf"]),
                        )
                    )
        return self.frame(records, "measured")


def _cls(name: str, base: type, **attrs) -> type:
    return type(name, (base,), attrs | {"__doc__": base.__doc__})


ENDEKSA_ADAPTERS: dict[str, type] = {
    **{
        "endeksa_" + m.indicator_id: _cls(
            "Endeksa" + "".join(p.title() for p in m.indicator_id.split("_")),
            SnapshotMeasure,
            measure=m,
        )
        for m in MEASURES
    },
    **{
        "endeksa_" + s: _cls(
            "Endeksa" + "".join(p.title() for p in s.split("_")),
            PropertySeries,
            series=s,
        )
        for s in SERIES
    },
    "endeksa_votes": Votes,
    **{
        "endeksa_" + k: _cls(
            "Endeksa" + "".join(p.title() for p in k.split("_")),
            ElectorateMeasure,
            indicator_id=k,
            field=v,
        )
        for k, v in ELECTORATE.items()
    },
    "endeksa_registry_origin": OriginProvince,
}

# endregion
