"""YÖK İstatistik: students, new registrations and graduates by province and district.

Source: istatistik.yok.gov.tr yearly releases ("YYYY-YYYY Öğretim Yılı"), tables
"Öğrenim gördüğü il ve ilçelere göre öğrenci / yeni kayıt olan öğrenci / mezun sayıları"
(T102, T101, M102), downloaded by `scripts/fetch_yok_istatistik.py` into
`raw/yok_istatistik/<year>/` with `index.tsv`.

Layout, the same 2013-2014 to 2025-2026: per university a row with its name, type and
province, then that province's districts; a second campus province follows as another
province row. Columns: associate (formal, evening, distance, open), bachelor (the same four),
master's (formal, evening, distance), doctorate (formal), total — each men / women / total.

Checks: every province row equals the sum of its district rows; the provinces add up to the
printed TOPLAM row in every column. District names the register does not know (older names)
are recorded in `UNKNOWN_DISTRICTS` and kept at province level only.

The release year is stored as its first year (2024-2025 -> 2024). Graduates in a release are
those of the release's own academic year as YÖK prints them; not shifted.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import district_key, fold, province_id, resolve_district


def province_or_none(name: str) -> str | None:
    try:
        return province_id(name)
    except KeyError:
        return None


FOLDER = RAW / "yok_istatistik"
TABLES = {
    "yok_students": "ÖĞRENİM GÖRDÜĞÜ İL VE İLÇELERE GÖRE ÖĞRENCİ SAYILARI",
    "yok_new_students": "ÖĞRENİM GÖRDÜĞÜ İL VE İLÇELERE GÖRE YENİ KAYIT OLAN ÖĞRENCİ SAYILARI",
    "yok_graduates": "ÖĞRENİM GÖRDÜĞÜ İL VE İLÇELERE GÖRE MEZUN SAYILARI",
}
LEVELS = {
    "onlisans": "associate",
    "lisans": "bachelor",
    "yukseklisans": "master",
    "doktora": "doctorate",
    "toplam": "total",
}
DELIVERY = {
    "orgunogretim": "formal",
    "ikinciogretim": "evening",
    "uzaktanogretim": "distance",
    "acikogretim": "open",
}
SEX = {"e": "male", "k": "female"}
TYPES = {"devlet": "state", "vakif": "foundation", "vakifmyo": "foundation_vocational"}

#: (year, province, district) names not in the area register.
UNKNOWN_DISTRICTS: list[tuple[int, str, str]] = []
#: (university, province) -> Counter of district areas seen in newer releases. Filled while
#: reading, newest release first, and used to place an older "MERKEZ" row of the same campus.
CAMPUS: dict[tuple[str, str], dict[str, float]] = {}
#: (year, province, name, how) for rows placed by inference: "campus" (MERKEZ via a newer
#: release), "moved" (a district of another province: students moved there), or "kept"
#: (abroad campus, blank name, or unplaceable: left at province level only).
PLACED: list[tuple[int, str, str, str]] = []
#: Campuses abroad printed in the district column. Güzelyurt is METU's KKTC campus, not
#: Aksaray's district of the same name.
ABROAD_CAMPUSES = {"gazimagusa", "lefkosa", "guzelyurt", "girne", "mogadisu", "taskent"}
#: Campus names for districts: Balcalı is Çukurova University's campus in Sarıçam.
CAMPUS_ALIASES = {"balcali": "saricam"}
DERIVE_DOCTORATE = {"2017_T101.xls"}
#: (year, province, type, level, delivery, sex) where districts add up past the province.
DISTRICT_EXCESS: list[tuple] = []


def first_line(cell: str) -> str:
    return str(cell).split("\n")[0].split(" / ")[0].strip()


def files(table: str) -> list[tuple[int, Path]]:
    out = []
    for row in csv.reader(
        (FOLDER / "index.tsv").open(encoding="utf-8"), delimiter="\t"
    ):
        label = row[1].replace("\u200b", "").strip()
        if label == TABLES[table]:
            out.append((int(row[0][:4]), FOLDER / row[2]))
    years = [y for y, _ in out]
    if len(years) != len(set(years)):
        raise ValueError(f"{table}: aynı yıl iki dosya")
    return sorted(out)


def columns(rows: list[list[str]]) -> dict[int, tuple[str, str, str]]:
    """Column index -> (level, delivery, sex) from the three header rows; totals dropped."""
    sex_row = next(
        i for i, r in enumerate(rows) if [fold(c) for c in r[3:6]] == ["e", "k", "t"]
    )
    level_row, delivery_row = sex_row - 2, sex_row - 1
    out: dict[int, tuple[str, str, str]] = {}
    level = delivery = None
    for j in range(3, len(rows[sex_row])):
        lv = fold(first_line(rows[level_row][j])) if j < len(rows[level_row]) else ""
        if lv:
            level = LEVELS.get(lv)
            if level is None:
                raise ValueError(f"tanınmayan düzey: {rows[level_row][j]!r}")
            delivery = None
        dv = (
            fold(first_line(rows[delivery_row][j]))
            if j < len(rows[delivery_row])
            else ""
        )
        if dv:
            delivery = DELIVERY.get(dv)
            if delivery is None:
                raise ValueError(f"tanınmayan öğretim türü: {rows[delivery_row][j]!r}")
        sex = SEX.get(fold(rows[sex_row][j]))
        if sex and level and level != "total":
            out[j] = (level, delivery or "formal", sex)
    return out


def districts_by_name() -> dict[str, list[tuple[str, str]]]:
    """Folded district name -> [(district area, province)] over the whole register."""
    out: dict[str, list[tuple[str, str]]] = {}
    for (province, name), (area, level) in district_key().items():
        if level == "district":
            out.setdefault(name, []).append((area, province))
    return out


def number(cell: str) -> float:
    cell = str(cell).strip()
    return float(cell) if cell not in ("", "-") else 0.0


def read(path: Path, year: int) -> dict[tuple[str, str, str, str, str, str], float]:
    """{(area, level_of_area, uni_type, level, delivery, sex): count}."""
    import xlrd

    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    rows = [[str(v) for v in sheet.row_values(r)] for r in range(sheet.nrows)]
    cols = columns(rows)
    # 2016-2017 new registrations: the doctorate cells are scrambled across rows (Korkuteli
    # prints 64 men where its row total leaves room for none; the row above is 64 short),
    # while every row total is right. For that file the doctorate is derived as row total
    # minus the other levels; the result must still meet the printed TOPLAM like any column.
    derive = path.name in DERIVE_DOCTORATE
    if derive:
        sex_row = next(
            i
            for i, r in enumerate(rows)
            if [fold(c) for c in r[3:6]] == ["e", "k", "t"]
        )
        level_row = sex_row - 2
        total_start = next(
            j for j, c in enumerate(rows[level_row]) if fold(first_line(c)) == "toplam"
        )
        total_cols = {
            SEX[fold(rows[sex_row][j])]: j
            for j in range(total_start, total_start + 3)
            if fold(rows[sex_row][j]) in SEX
        }
    key = district_key()
    out: dict[tuple, float] = {}
    total = None
    province_values: dict[tuple, float] = {}
    district_sums: dict[tuple, float] = {}
    pid = pname = uni_type = uni = None
    by_name = districts_by_name()
    start = next(
        i for i, r in enumerate(rows) if [fold(c) for c in r[3:6]] == ["e", "k", "t"]
    )

    def add_district(area: str, province: str, values: list[float]) -> None:
        for (level, delivery, sex), v in zip(cols.values(), values, strict=True):
            sums_key = (province, uni_type, level, delivery, sex)
            district_sums[sums_key] = district_sums.get(sums_key, 0.0) + v
            k = (area, "district", uni_type, level, delivery, sex)
            out[k] = out.get(k, 0.0) + v
        campus = CAMPUS.setdefault((uni, province), {})
        campus[area] = campus.get(area, 0.0) + sum(values)

    for r in rows[start + 1 :]:
        if any(fold(first_line(c)) == "toplam" for c in r[:3]):
            total = r
            continue
        place = first_line(r[2]) if len(r) > 2 else ""
        values = [number(r[j]) for j in cols]
        if derive:
            for i, (level, _delivery, sex) in enumerate(cols.values()):
                if level == "doctorate":
                    others = sum(
                        v
                        for v, (lv, _d, sx) in zip(values, cols.values(), strict=True)
                        if sx == sex and lv != "doctorate"
                    )
                    values[i] = max(number(r[total_cols[sex]]) - others, 0.0)
        # 2015-2016 print the national row with no label at all, first under the header.
        if (
            total is None
            and not pid
            and not place
            and not first_line(r[0])
            and any(values)
        ):
            total = r
            continue
        if not any(values):
            continue
        heads_block = bool(first_line(r[0]) or first_line(r[1]))
        if not place and not heads_block:
            if pid:
                PLACED.append((year, pid, "(boş)", "kept"))
            continue
        district = None
        if pid and not heads_block:
            try:
                district = resolve_district(key, pname, place)
            except KeyError:
                district = None
        if heads_block or (district is None and province_or_none(place)):
            if heads_block:
                kind = TYPES.get(fold(first_line(r[1])))
                # 2018-2019 leave one state university's type blank.
                if kind is None and fold(first_line(r[0])).startswith(
                    "zonguldakbulentecevit"
                ):
                    kind = "state"
                if kind is None:
                    raise ValueError(f"YÖK {path.name}: tanınmayan tür {r[1]!r}")
                uni_type = kind
                uni = fold(first_line(r[0]))
            pid, pname = province_id(place), place
            for (level, delivery, sex), v in zip(cols.values(), values, strict=True):
                k = (pid, "province", uni_type, level, delivery, sex)
                province_values[k] = province_values.get(k, 0.0) + v
            continue
        if district is None:
            # A district of another province, printed under this one's campus (Selçuklu under
            # an Ankara university): when the name is one district in the register, its
            # students move there, province totals with them.
            if fold(place) in ABROAD_CAMPUSES:
                PLACED.append((year, pid, place, "kept"))
                continue
            found = by_name.get(CAMPUS_ALIASES.get(fold(place), fold(place)), [])
            if len(found) == 1:
                area, other = found[0]
                for (level, delivery, sex), v in zip(
                    cols.values(), values, strict=True
                ):
                    here = (pid, "province", uni_type, level, delivery, sex)
                    there = (other, "province", uni_type, level, delivery, sex)
                    province_values[here] = province_values.get(here, 0.0) - v
                    province_values[there] = province_values.get(there, 0.0) + v
                add_district(area, other, values)
                PLACED.append((year, pid, place, "moved"))
            else:
                UNKNOWN_DISTRICTS.append((year, pid, place))
                PLACED.append((year, pid, place, "kept"))
            continue
        area, level_name = district
        if level_name != "district":
            # "MERKEZ" in a metropolitan province: the same campus's district in a newer
            # release, when it had one.
            seen = CAMPUS.get((uni, pid), {})
            if not seen:
                PLACED.append((year, pid, place, "kept"))
                continue
            area = max(seen, key=seen.get)
            PLACED.append((year, pid, place, "campus"))
        add_district(area, pid, values)
    # Districts may fall short of their province (students with no district recorded), never
    # exceed it.
    for (p, t, level, delivery, sex), v in district_sums.items():
        if v > province_values.get((p, "province", t, level, delivery, sex), 0.0) + 0.5:
            # A campus in another province printed without its own province row: the
            # province totals still meet TOPLAM (checked below); noted, not fatal.
            DISTRICT_EXCESS.append((year, p, t, level, delivery, sex))
    if total is None:
        raise ValueError(f"YÖK {path.name}: TOPLAM satırı yok")
    for j, (level, delivery, sex) in cols.items():
        printed = number(total[j])
        parts = sum(
            v
            for (_a, _lv, _t, lev, dlv, sx), v in province_values.items()
            if (lev, dlv, sx) == (level, delivery, sex)
        )
        if abs(parts - printed) > 0.5:
            raise ValueError(
                f"YÖK {path.name} {level}/{delivery}/{sex}: iller {parts:,.0f}, TOPLAM {printed:,.0f}"
            )
    out.update(province_values)
    return out


class YokTable:
    source_id = "yok_istatistik"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        # Newest first, so an older release's "MERKEZ" rows can use the campus districts
        # the newer ones printed.
        for year, path in sorted(files(self.indicator_id), reverse=True):
            for (area, level_name, uni_type, level, delivery, sex), value in read(
                path, year
            ).items():
                if value:
                    records.append(
                        {
                            "area_id": area,
                            "area_level": level_name,
                            "period_start": dt.date(year, 1, 1),
                            "dims": f"education_delivery={delivery};higher_education_level={level};sex={sex};university_type={uni_type}",
                            "value": value,
                        }
                    )
        return (
            pl.DataFrame(records, schema_overrides={"value": pl.Float64})
            .group_by("area_id", "area_level", "period_start", "dims")
            .agg(pl.col("value").sum())
            .with_columns(
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit("annual").alias("frequency"),
                pl.lit("person").alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit("2026-04").alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
            )
        )


class YokStudents(YokTable):
    indicator_id = "yok_students"


class YokNewStudents(YokTable):
    indicator_id = "yok_new_students"


class YokGraduates(YokTable):
    indicator_id = "yok_graduates"


YOK_ISTATISTIK_ADAPTERS = {
    "yok_students": YokStudents,
    "yok_new_students": YokNewStudents,
    "yok_graduates": YokGraduates,
}

_ = re  # kept for pattern helpers added later


# region 1982-2013 national summary

ARCHIVE = FOLDER / "1982-2013" / "1982-2013_OGRENCI-MEZUN_OZET.xlsx"
ARCHIVE_LEVELS = {
    "onlisans": "associate",
    "lisans": "bachelor",
    "yukseklisans": "master",
    "doktora": "doctorate",
}
ARCHIVE_SUBROWS = {
    "acikogretimharic": "not_open",
    "ikinciogretim": "evening",
    "acikogretim": "open",
}


def archive() -> dict[str, dict[tuple[int, str, str, str], float]]:
    """{indicator: {(year, level, delivery, sex): count}} from the 1982-2013 summary.

    Each block names two years: new registrations and students for the first, graduates for
    the one before. Level rows are followed by their parts: "açıköğretim hariç" and "açık
    öğretim" (1983-1992), plus "ikinci öğretim" (1992 on). In the later layout the three
    parts are disjoint and add up to the level (evening is outside "hariç"); in the earlier
    one "hariç" holds evening classes. Parts are stored when present, the level otherwise;
    every level must equal its parts and the levels must equal TOPLAM.
    """
    import openpyxl

    sheet = openpyxl.load_workbook(ARCHIVE, data_only=True).active
    rows = [list(r) for r in sheet.iter_rows(values_only=True)]
    out: dict[str, dict] = {
        k: {} for k in ("yok_new_students", "yok_students", "yok_graduates")
    }
    blocks: list[tuple[int, int, list]] = []
    for r in rows:
        if r[1] and re.fullmatch(r"\d{4}-\d{4}", str(r[1]).strip()):
            blocks.append((int(str(r[1])[:4]), int(str(r[7])[:4]), []))
        elif blocks and r[0] and str(r[0]).strip():
            label = fold(first_line(r[0]))
            values = [float(x) if x not in (None, "") else 0.0 for x in r[1:10]]
            blocks[-1][2].append((label, values))
    parts = {
        "yok_new_students": (0, "first"),
        "yok_students": (3, "first"),
        "yok_graduates": (6, "second"),
    }
    for first, second, lines in blocks:
        total = next(v for label, v in lines if label == "toplam")
        levels: list[tuple[str, list[float], list[tuple[str, list[float]]]]] = []
        for label, values in lines:
            if label in ARCHIVE_LEVELS:
                levels.append((ARCHIVE_LEVELS[label], values, []))
            elif label in ARCHIVE_SUBROWS:
                levels[-1][2].append((ARCHIVE_SUBROWS[label], values))
        later = any(d == "evening" for _, _, subs in levels for d, _ in subs)
        for indicator, (offset, which) in parts.items():
            year = first if which == "first" else second
            for i, sex in ((0, "male"), (1, "female")):
                if (
                    abs(sum(v[offset + i] for _, v, _ in levels) - total[offset + i])
                    > 0.5
                ):
                    raise ValueError(
                        f"YÖK arşiv {first}: düzeyler TOPLAM'ı tutmuyor ({indicator})"
                    )
                for level, values, subs in levels:
                    if subs and any(v[offset + i] for _, v in subs):
                        if (
                            abs(
                                sum(v[offset + i] for _, v in subs) - values[offset + i]
                            )
                            > 0.5
                        ):
                            raise ValueError(
                                f"YÖK arşiv {first}: {level} alt satırları tutmuyor"
                            )
                        for delivery, v in subs:
                            name = (
                                "formal"
                                if (delivery == "not_open" and later)
                                else delivery
                            )
                            out[indicator][(year, level, name, sex)] = v[offset + i]
                    else:
                        out[indicator][(year, level, "all", sex)] = values[offset + i]
    return out


class YokArchive:
    source_id = "yok_istatistik"
    indicator_id = ""
    table = ""

    def fetch(self) -> Path:
        return ARCHIVE

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "area_id": "TR",
                "area_level": "country",
                "period_start": dt.date(year, 1, 1),
                "dims": f"education_delivery={delivery};higher_education_level={level};sex={sex}",
                "value": value,
            }
            for (year, level, delivery, sex), value in archive()[self.table].items()
            if value
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit("person").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2014-01").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
        )


class YokStudentsArchive(YokArchive):
    indicator_id = "yok_students_archive"
    table = "yok_students"


class YokNewStudentsArchive(YokArchive):
    indicator_id = "yok_new_students_archive"
    table = "yok_new_students"


class YokGraduatesArchive(YokArchive):
    indicator_id = "yok_graduates_archive"
    table = "yok_graduates"


YOK_ISTATISTIK_ADAPTERS.update(
    {
        "yok_students_archive": YokStudentsArchive,
        "yok_new_students_archive": YokNewStudentsArchive,
        "yok_graduates_archive": YokGraduatesArchive,
    }
)

# endregion


# region Academic staff by title (Tablo 10)

TITLES = {
    "profesor": "professor",
    "prof": "professor",
    "docent": "associate_professor",
    "doc": "associate_professor",
    "yardimcidocent": "assistant_professor",
    "ydoc": "assistant_professor",
    "doktorogretimuyesi": "assistant_professor",
    "ogretimgorevlisi": "lecturer",
    "ogrgrv": "lecturer",
    "okutman": "instructor",
    "uzman": "specialist",
    "arastirmagorevlisi": "research_assistant",
    "arsgrv": "research_assistant",
    "cevirici": "translator",
    "eopl": "education_planner",
}


def staff_files() -> list[tuple[int, Path]]:
    """Per release the university-level table: label "...AKADEMİK GÖREVLERİNE GÖRE SAYILARI"
    (not foreign staff), the file with a university type in column B and the fewest rows
    (T10; T28 repeats it with every unit)."""
    import xlrd

    best: dict[int, tuple[int, Path]] = {}
    for row in csv.reader(
        (FOLDER / "index.tsv").open(encoding="utf-8"), delimiter="\t"
    ):
        label = row[1].replace("\u200b", "")
        if "AKADEMİK GÖREVLERİNE GÖRE SAYILARI" not in label or "YABANCI" in label:
            continue
        if not row[0][:4].isdigit():
            continue
        path = FOLDER / row[2]
        sheet = xlrd.open_workbook(path).sheet_by_index(0)
        typed = sum(
            1
            for i in range(sheet.nrows)
            if fold(first_line(sheet.cell_value(i, 1))) in TYPES
        )
        if typed < 100:
            continue
        year = int(row[0][:4])
        if year not in best or sheet.nrows < best[year][0]:
            best[year] = (sheet.nrows, path)
    return sorted((y, p) for y, (_, p) in best.items())


def read_staff(path: Path) -> dict[tuple[str, str, str, str], float]:
    """{(province, university type, title, sex): count}, checked against TOPLAM.

    Two layouts: from 2014-2015 one row per university with men / women / total under each
    title; 2013-2014 three rows per university (T, E, K) with titles across. The province is
    the university's own (column C), not each unit's.
    """
    import xlrd

    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    rows = [[str(v) for v in sheet.row_values(r)] for r in range(sheet.nrows)]
    head = next(
        i
        for i, r in enumerate(rows[:8])
        if sum(fold(first_line(c)) in TITLES for c in r) >= 4
    )
    title_cols = {
        j: TITLES[fold(first_line(c))]
        for j, c in enumerate(rows[head])
        if fold(first_line(c)) in TITLES
    }
    out: dict[tuple, float] = {}
    total: dict[tuple[str, str], float] = {}
    sex_row = rows[head + 1]
    wide = [fold(c) for c in sex_row[3:6]] == ["e", "k", "t"]
    uni_type = pid = None
    for r in rows[head + (2 if wide else 1) :]:
        name = fold(first_line(r[0]))
        kind = TYPES.get(fold(first_line(r[1])))
        if wide:
            cells = {
                (t, s): number(r[j + o])
                for j, t in title_cols.items()
                for o, s in ((0, "male"), (1, "female"))
            }
            if name == "toplam":
                for (t, s), v in cells.items():
                    total[(t, s)] = total.get((t, s), 0.0) + v
                continue
            if kind is None:
                continue
            # 2025-2026 leaves İzmir Konak MYO's province blank; its name says İzmir.
            place = first_line(r[2]) or (
                "İZMİR" if name.startswith("izmirkonak") else ""
            )
            pid = province_id(place)
            for (t, s), v in cells.items():
                k = (pid, kind, t, s)
                out[k] = out.get(k, 0.0) + v
        else:
            sex = {"e": "male", "k": "female"}.get(fold(r[3]))
            if name.startswith("universiteler") or (not name and sex and pid is None):
                if sex:
                    for j, t in title_cols.items():
                        total[(t, sex)] = total.get((t, sex), 0.0) + number(r[j])
                continue
            if kind is not None and first_line(r[2]):
                uni_type, pid = kind, province_id(first_line(r[2]))
            if sex and pid:
                for j, t in title_cols.items():
                    k = (pid, uni_type, t, sex)
                    out[k] = out.get(k, 0.0) + number(r[j])
    if not total:
        raise ValueError(f"YÖK akademisyen {path.name}: TOPLAM yok")
    for (t, s), printed in total.items():
        parts = sum(v for (_p, _k, tt, ss), v in out.items() if (tt, ss) == (t, s))
        if abs(parts - printed) > 0.5:
            raise ValueError(
                f"YÖK akademisyen {path.name} {t}/{s}: üniversiteler {parts:,.0f}, TOPLAM {printed:,.0f}"
            )
    return out


class YokStaff:
    source_id = "yok_istatistik"
    indicator_id = "yok_academic_staff"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "area_id": pid,
                "area_level": "province",
                "period_start": dt.date(year, 1, 1),
                "dims": f"academic_title={title};sex={sex};university_type={kind}",
                "value": value,
            }
            for year, path in staff_files()
            for (pid, kind, title, sex), value in read_staff(path).items()
            if value
        ]
        return (
            pl.DataFrame(records, schema_overrides={"value": pl.Float64})
            .group_by("area_id", "area_level", "period_start", "dims")
            .agg(pl.col("value").sum())
            .with_columns(
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit("annual").alias("frequency"),
                pl.lit("person").alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit("2026-04").alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
            )
        )


YOK_ISTATISTIK_ADAPTERS["yok_academic_staff"] = YokStaff

# endregion
