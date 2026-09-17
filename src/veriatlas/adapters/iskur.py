r"""İŞKUR yearbook tables: general activities by province, 2003-2025.

The yearbooks' Excel tables are kept in `C:\veri-ham\iskur\<year>-yillik.xlsx|xls` (2004-2011
are zips of one workbook per table, read from inside the zip). Each year has one table of the year's
activities by province, under a different number every few years (2012-2016 "Tablo 2: <year>
yılı illere göre ...", 2020 "Tablo 35", 2025 "Tablo 37": "İllere göre genel çalışmalar"). The
three-year comparison table beside it is not read.

Columns are matched by order, not position: the measures are read left to right from the header
row that names most of them (2012-2017 split the Turkish names over two rows, so there the
English row wins), and the Erkek / Kadın / Toplam row splits into groups closed by each Toplam.
Measures: applications (2012-2017), vacancies (total only), placements, registered labour
force (2012-2020), registered unemployed (2012-2024) and, from 2025, registered job seekers,
which replaces both. "Takdim" (presentations to employers) is left out.

Checks: every row's male + female equals its total; every column's provinces add up to the
Türkiye row.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold, province_id

FOLDER = RAW / "iskur" if (RAW / "iskur").exists() else Path("C:/veri-ham/iskur")
YEARS = range(2003, 2026)
#: folded Turkish header fragment -> indicator (None: read and dropped)
MEASURES = {
    "basvuru": "iskur_applications",
    "acikis": "iskur_vacancies",
    "takdim": None,
    "yerlestirme": "iskur_placements",
    "kayitliisgucu": "iskur_registered_labour_force",
    "kayitliissiz": "iskur_registered_unemployed",
    # 2003-2008: "<year>'e devreden işgücü", "devreden işgücünden işsizler" (işsiz first)
    "issiz": "iskur_registered_unemployed",
    "devredenisgucu": "iskur_registered_labour_force",
    "isarayan": "iskur_registered_job_seekers",
    # 2012-2017 split the Turkish names over two rows; the English row has them whole
    # "placement" before "vacanc": 2017 heads the placements column "Placements to Vacancies"
    "application": "iskur_applications",
    "presentation": None,
    "placement": "iskur_placements",
    "vacanc": "iskur_vacancies",
    "labourforce": "iskur_registered_labour_force",
    "laborforce": "iskur_registered_labour_force",
    "unemployed": "iskur_registered_unemployed",
    "jobseeker": "iskur_registered_job_seekers",
    # 2004-2008 English: "The Manpower Turnover To <year>"; "The Unemployed Among This Manpower"
    # matches "unemployed" above first
    "manpower": "iskur_registered_labour_force",
}
SEXES = {"erkek": "male", "kadin": "female", "toplam": "total"}
#: 2006 prints some vacancies with decimals (1254.120223671): a cell rejected here would drop
#: silently, provinces and Türkiye row alike, so the check could not catch it
NUMBER = re.compile(r"-?\d+(\.\d+)?")


def workbook_sheets(path: Path):
    if path.suffix == ".zip":
        import zipfile

        archive = zipfile.ZipFile(path)
        for member in sorted(archive.namelist()):
            if not member.lower().endswith((".xls", ".xlsx")):
                continue
            yield from sheets_of(archive.read(member), member.lower().endswith(".xlsx"))
        return
    yield from sheets_of(path.read_bytes(), path.suffix == ".xlsx")


def sheets_of(data: bytes, xlsx: bool):
    if xlsx:
        import io

        import openpyxl

        book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        for sheet in book.worksheets:
            yield [
                ["" if c is None else str(c).strip() for c in r]
                for r in sheet.iter_rows(values_only=True)
            ]
    else:
        import xlrd

        book = xlrd.open_workbook(file_contents=data)
        for sheet in book.sheets():
            yield [
                [str(c).strip() for c in sheet.row_values(i)]
                for i in range(sheet.nrows)
            ]


def find_table(year: int) -> list[list[str]]:
    path = next(
        p
        for p in FOLDER.glob(f"{year}-yillik.*")
        if p.suffix in (".xls", ".xlsx", ".zip")
    )
    for rows in workbook_sheets(path):
        title = fold(" ".join(" ".join(r) for r in rows[:2]))
        if (
            "illeregore" not in title
            or "son3" in title
            or "karsilastir" in title
            or "mukayese" in title
        ):
            continue
        if "genelcalisma" in title or f"{year}yiliilleregore" in title:
            return rows
    raise ValueError(f"İŞKUR {year}: il genel çalışmalar tablosu yok")


def measure_of(text: str) -> str | None | bool:
    key = fold(text)
    for fragment, indicator in MEASURES.items():
        if fragment in key:
            return indicator
    return False


def sex_of(text: str) -> str | None:
    # "Erkek / Male", "Erkek" and "Male" on two lines, 2003 "Erkek  Male": the first word
    first = text.split("/")[0].split()[0] if text.split() else ""
    key = fold(first)
    return SEXES.get(key)


def read_year(year: int) -> dict[tuple[str, str, str], float]:
    """{(indicator, area, sex): value}

    The measures are taken in column order from the header row that names most of them; the
    Erkek / Kadın / Toplam row below splits into groups, each closed by a Toplam, and the
    groups are matched to the measures in order. Their counts must agree.
    """
    rows = find_table(year)
    head = next(i for i, r in enumerate(rows) if r and fold(r[0]).startswith("iller"))
    sex_row = next(
        i for i in range(head, head + 10) if sum(bool(sex_of(c)) for c in rows[i]) >= 3
    )
    named = max(
        range(head, sex_row),
        key=lambda i: sum(measure_of(c) is not False for c in rows[i][1:]),
    )
    measures = [m for c in rows[named][1:] if c and (m := measure_of(c)) is not False]
    groups: list[list[tuple[int, str]]] = [[]]
    for j, cell in enumerate(rows[sex_row]):
        sex = sex_of(cell) if j else None
        if not sex:
            continue
        groups[-1].append((j, sex))
        if sex == "total":
            groups.append([])
    groups = [g for g in groups if g]
    if len(groups) != len(measures):
        raise ValueError(
            f"İŞKUR {year}: {len(measures)} ölçü, {len(groups)} sütun grubu"
        )
    columns = {
        j: (indicator, sex)
        for indicator, group in zip(measures, groups, strict=True)
        if indicator
        for j, sex in group
    }
    out: dict[tuple[str, str, str], float] = {}
    printed: dict[tuple[str, str], float] = {}
    for r in rows[sex_row + 1 :]:
        if (
            not r
            or not r[0]
            or not any(j < len(r) and NUMBER.fullmatch(r[j]) for j in columns)
        ):
            continue
        name = r[0].splitlines()[0]
        values = {
            key: float(r[j])
            for j, key in columns.items()
            if j < len(r) and NUMBER.fullmatch(r[j])
        }
        key_name = fold(name)
        if key_name.startswith(("toplam", "geneltoplam", "turkiye")):
            printed = values
            continue
        try:
            area = province_id(name)
        except KeyError:
            continue  # English header repeats and footnotes
        for (indicator, sex), value in values.items():
            key = (indicator, area, sex)
            if key in out:
                raise ValueError(f"İŞKUR {year}: {key} iki kez")
            out[key] = value
    areas = {a for _, a, _ in out}
    if len(areas) != 81:
        raise ValueError(f"İŞKUR {year}: {len(areas)} il")
    if not printed:
        raise ValueError(f"İŞKUR {year}: Türkiye satırı yok")
    for indicator in {i for i, _, _ in out}:
        for area in areas:
            m, f, t = (
                out.get((indicator, area, s)) for s in ("male", "female", "total")
            )
            if None not in (m, f, t) and abs(m + f - t) > 0.5:
                raise ValueError(
                    f"İŞKUR {year} {indicator} {area}: erkek+kadın {m + f}, toplam {t}"
                )
        for sex in ("male", "female", "total"):
            if (indicator, sex) not in printed:
                continue
            read = sum(v for (i, _, s), v in out.items() if i == indicator and s == sex)
            if abs(read - printed[(indicator, sex)]) > 0.5:
                raise ValueError(
                    f"İŞKUR {year} {indicator} {sex}: iller {read:,.0f}, "
                    f"Türkiye {printed[(indicator, sex)]:,.0f}"
                )
    for (indicator, sex), value in printed.items():
        out[(indicator, "TR", sex)] = value
    return out


_CACHE: dict[int, dict[tuple[str, str, str], float]] = {}


class Iskur:
    source_id = "iskur"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        if not _CACHE:
            for year in YEARS:
                _CACHE[year] = read_year(year)
        records = [
            {
                "area_id": area,
                "area_level": "country" if area == "TR" else "province",
                "period_start": dt.date(year, 1, 1),
                "dims": f"sex={sex}",
                "value": value,
            }
            for year, table in _CACHE.items()
            for (indicator, area, sex), value in table.items()
            if indicator == self.indicator_id
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit("person" if "vacancies" not in self.indicator_id else "item").alias(
                "unit"
            ),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 17)).alias("retrieved_at"),
        )


ISKUR_ADAPTERS = {
    indicator: type(f"Iskur_{indicator}", (Iskur,), {"indicator_id": indicator})
    for indicator in sorted({i for i in MEASURES.values() if i})
}
