r"""Schools, students, teachers and classrooms by school type and ownership (MEB portal).

istatistik.meb.gov.tr publishes the same province counts MEDAS carries (`meb_counts`),
plus what MEDAS drops: public/private, kindergarten classes inside primary schools
(anasınıfı), imam-hatip schools apart from the rest, and open education. Its robots.txt
disallows ClaudeBot, so the user downloads each "Okul Türüne Göre" table with the page's
own Excel button; `scripts/organize_meb_portal.py` files them under
`RAW/meb_portal/<measure>/<year>_<level>.xlsx`.

Four indicators, one per measure, each with `meb_school_type × school_ownership` (and `sex`
for students and teachers). Every province-year in these files was checked against MEDAS
on 2026-09-25: the sums match 81 of 81 provinces in every year, with two known
differences that are MEDAS's own choices, not errors here — MEDAS counts pre-school
*schools, classrooms and teachers* for independent kindergartens only, and it includes
open education in lower- and upper-secondary *students*.

**Totals are not stored.** Each table carries "... Toplam" rows next to the types; they
are used as a check and dropped. Where a province's types do not add up to its own total
the portal has shuffled rows between provinces (teachers, upper secondary, 2013-14:
Karabük and Kilis trade 22; 2014-15: nine provinces). The type rows of that province and
file are dropped and counted, never guessed; `MAX_UNBALANCED` stops the run if a file
has more than a handful.

**2014-15 pre-school students** are read from `..._duzeltilmis.xlsx`: the portal prints
province names in plate order but the kindergarten values in alphabetical order (the row
labelled Amasya holds Aksaray's figures). The corrected copy reassigns them and matches
MEDAS in 81 of 81 provinces; the original is kept beside it and skipped here.

**Primary-school counts** come from the "Tüm Eğitim Kademeleri" summary (one file per
year, public/private by level): primary has a single type, so its per-type file was only
downloaded for one year. **2002-03** is the pre-reform year: primary and lower secondary
are one "İlköğretim", and imam-hatip high schools sit inside vocational.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import openpyxl
import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..schema import format_dims
from .skrs_facilities import upper_tr

FOLDER = RAW / "meb_portal"
SOURCE_ID = "meb_portal"
VINTAGE = "2026-09"
RETRIEVED = dt.date(2026, 9, 25)
MAX_UNBALANCED = 12
#: Files whose "Toplam" row is the faulty side: their types matched MEDAS in 81 of 81
#: provinces on 2026-09-25 while the portal's own total is off (by 6.010 nationally).
TOTAL_ROW_WRONG = {("ogrenci-sayisi", 2015, "ortaogretim")}

TYPES = {
    "Anaokulu": "kindergarten",
    "Anasınıfı": "kindergarten_class",
    "İlkokul Toplam": "primary",  # the level's only type; not a total of several
    "İlköğretim Toplam": "basic_education",  # 2002-03, before the 4+4+4 split
    "Ortaokul": "lower_secondary",
    "İHO ve İHL bünyesindeki İHO": "imam_hatip_lower_secondary",
    "Genel Ortaöğretim": "upper_secondary_general",
    "Meslekî ve Teknik Ortaöğretim": "upper_secondary_vocational",
    "Mesleki ve Teknik Ortaöğretim": "upper_secondary_vocational",
    "Din Öğretimi": "imam_hatip_upper_secondary",
    "Açıköğretim": "open_education",
}
#: Single-type levels whose "Toplam" row is the type itself.
SOLE_TYPES = {"İlkokul Toplam", "İlköğretim Toplam"}
LEVEL_OF_OPEN = {
    "ortaokul": "open_lower_secondary",
    "ortaogretim": "open_upper_secondary",
}

MEASURES = {
    # indicator id: (folder, by sex)
    "schools_by_type": ("kurum-sayisi", False),
    "students_by_type": ("ogrenci-sayisi", True),
    "teachers_by_type": ("ogretmen-sayisi", True),
    "classrooms_by_type": ("derslik-sayisi", False),
}
FILE = re.compile(
    r"^(?P<year>\d{4})-\d{4}_(?P<level>[a-z-]+?)(?P<fixed>_duzeltilmis)?$"
)


def province_index() -> dict[str, str]:
    areas = load_areas().filter(pl.col("area_level") == "province")
    return {
        upper_tr(name): area
        for name, area in zip(areas["name_tr"], areas["area_id"], strict=True)
    }


def read(path: Path) -> list[tuple]:
    book = openpyxl.load_workbook(path, read_only=True)
    try:
        rows = list(book.active.iter_rows(values_only=True))
    finally:
        book.close()
    return rows


def files(folder: str) -> list[tuple[int, str, Path]]:
    """(year, level, path), preferring a corrected copy over the file it corrects."""
    found: dict[tuple[int, str], tuple[bool, Path]] = {}
    for path in sorted((FOLDER / folder).glob("*.xlsx")):
        match = FILE.match(path.stem)
        if not match:
            raise ValueError(f"tanınmayan dosya adı: {path.name}")
        key = (int(match["year"]), match["level"])
        fixed = bool(match["fixed"])
        if key not in found or fixed:
            found[key] = (fixed, path)
    return [(year, level, path) for (year, level), (_, path) in sorted(found.items())]


def type_rows(
    path: Path,
    level: str,
    by_sex: bool,
    provinces: dict[str, str],
    check_totals: bool = True,
) -> tuple[list[dict], int]:
    """Long rows from one "Okul Türüne Göre" table, and how many provinces were dropped."""
    rows = [row for row in read(path)[3:] if row[1]]
    header = [str(cell) for cell in read(path)[2]]
    per_province: dict[str, dict[str, tuple]] = {}
    for row in rows:
        province = provinces.get(upper_tr(str(row[1])))
        if province is None:
            raise KeyError(f"{path.name}: tanınmayan il {row[1]!r}")
        per_province.setdefault(province, {})[str(row[2]).strip()] = row
    if len(per_province) != 81:
        raise ValueError(f"{path.name}: {len(per_province)} il")

    # Columns: # Şehir Tür | R Erkek R Kadın R Toplam Ö Erkek Ö Kadın Ö Toplam Toplam
    #      or: # Şehir Tür | Resmi Özel Toplam
    sexed = header[3] == "R Erkek"
    if sexed != by_sex:
        raise ValueError(f"{path.name}: beklenmeyen sütunlar {header}")

    out, dropped = [], 0
    for province, by_type in per_province.items():
        totals = {
            t: r for t, r in by_type.items() if "Toplam" in t and t not in SOLE_TYPES
        }
        parts = {t: r for t, r in by_type.items() if t not in totals}
        unknown = set(parts) - set(TYPES)
        if unknown:
            raise ValueError(f"{path.name}: tanınmayan okul türü {sorted(unknown)}")
        grand = totals.get(
            next((t for t in totals if "Dâhil Değil" not in t), ""), None
        )
        if grand is not None and check_totals:
            last = len(grand) - 1
            everything = sum(r[last] or 0 for t, r in parts.items())
            closed = sum(r[last] or 0 for t, r in parts.items() if t != "Açıköğretim")
            # 2019-20 lower secondary: the "Toplam" labelled open-education-included
            # leaves open education out, in all 81 provinces (MEDAS follows it). The
            # types are still right; only the label of the check row is.
            if (grand[last] or 0) not in (everything, closed):
                dropped += 1
                continue
        for source_type, row in parts.items():
            kind = TYPES[source_type]
            if kind == "open_education":
                kind = LEVEL_OF_OPEN[level]
            if sexed:
                cells = {
                    ("public", "male"): row[3],
                    ("public", "female"): row[4],
                    ("private", "male"): row[6],
                    ("private", "female"): row[7],
                }
            else:
                cells = {("public", None): row[3], ("private", None): row[4]}
            for (owner, sex), value in cells.items():
                dims = {"meb_school_type": kind, "school_ownership": owner}
                if sex:
                    dims["sex"] = sex
                out.append(
                    {"area_id": province, "dims": dims, "value": float(value or 0)}
                )
    return out, dropped


def primary_schools(provinces: dict[str, str]) -> dict[int, list[dict]]:
    """Primary-school counts by ownership from the yearly level summaries."""
    by_year = {}
    for path in sorted((FOLDER / "okul-sayisi-tum-egitim-kademeleri").glob("*.xlsx")):
        year = int(path.stem[:4])
        rows = [row for row in read(path)[4:] if row[1] and row[1] != "TÜRKİYE"]
        if len(rows) != 81:
            raise ValueError(f"{path.name}: {len(rows)} il")
        if rows[0][5] is None:  # 2002-03: no primary level
            continue
        out = []
        for row in rows:
            province = provinces[upper_tr(str(row[1]))]
            for owner, value in (("public", row[5]), ("private", row[6])):
                dims = {"meb_school_type": "primary", "school_ownership": owner}
                out.append(
                    {"area_id": province, "dims": dims, "value": float(value or 0)}
                )
        by_year[year] = out
    return by_year


class MebPortalMeasure:
    indicator_id: str
    source_id = SOURCE_ID

    def fetch(self) -> Path:
        folder = FOLDER / MEASURES[self.indicator_id][0]
        if not any(folder.glob("*.xlsx")):
            raise FileNotFoundError(folder)
        return folder

    def parse(self, raw: Path) -> pl.DataFrame:
        folder, by_sex = MEASURES[self.indicator_id]
        provinces = province_index()
        rows: list[dict] = []
        years_with_primary: set[int] = set()
        for year, level, path in files(folder):
            trusted = (folder, year, level) in TOTAL_ROW_WRONG
            found, dropped = type_rows(path, level, by_sex, provinces, not trusted)
            if dropped > MAX_UNBALANCED:
                raise ValueError(f"{path.name}: {dropped} ilde türler toplamı tutmuyor")
            if dropped:
                print(
                    f"  {path.name}: {dropped} ilin tür kırılımı atlandı (toplam tutmuyor)"
                )
            if level == "ilkokul":
                years_with_primary.add(year)
            rows.extend({**row, "year": year} for row in found)
        if self.indicator_id == "schools_by_type":
            for year, found in primary_schools(provinces).items():
                if year not in years_with_primary:
                    rows.extend({**row, "year": year} for row in found)

        records = [
            {
                "indicator_id": self.indicator_id,
                "area_id": row["area_id"],
                "area_level": "province",
                "period_start": dt.date(row["year"], 1, 1),
                "frequency": "annual",
                "dims": format_dims(row["dims"]),
                "value": row["value"],
                "unit": "person" if by_sex else "item",
                "quality_flag": "measured",
                "vintage": VINTAGE,
                "source_id": self.source_id,
                "retrieved_at": RETRIEVED,
            }
            for row in rows
        ]
        frame = pl.DataFrame(records)
        doubled = (
            frame.group_by("area_id", "period_start", "dims")
            .len()
            .filter(pl.col("len") > 1)
        )
        if doubled.height:
            raise ValueError(
                f"{self.indicator_id}: çift anahtar {doubled.head(3).rows()}"
            )
        return frame


MEB_PORTAL_ADAPTERS = {
    indicator_id: type(
        f"MebPortal_{indicator_id}", (MebPortalMeasure,), {"indicator_id": indicator_id}
    )
    for indicator_id in MEASURES
}
