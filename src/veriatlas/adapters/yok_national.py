"""YÖK İstatistik national cross-tables: nationality, age and field of education.

Same releases as `yok_istatistik.py` (`raw/yok_istatistik/index.tsv`). Families, told apart
by label because the wording changes over the years ("yabancı uyruklu" → "uluslararası"):

* nationality — international students (new registrations, all) and graduates by country
  and level; foreign academic staff by country and title;
* age — new registrations, students and graduates by age, level and delivery;
* field — students, new registrations, graduates and academic staff by field of education
  (ISCED-F 2013 from 2014-2015; the 2013-2014 release uses the older scheme).

One reader for all: the header rows above the first TOPLAM row give every column its
event, level, delivery, title and sex; a header word it does not know stops the load. Row
labels are the categories (country, age, field), stored under a slug of their Turkish name.
Checks per column: categories add up to TOPLAM. Field tables are three-deep (broad, narrow,
detailed) with no codes printed: the depth is recovered from the sums — each broad field's
narrow rows add up to it, each narrow field's detailed rows to that — and a table that does
not resolve stops the load.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path

import polars as pl

from .kgm import fold
from .yok_istatistik import FOLDER, TITLES, first_line, number

EVENTS = {
    "yenikayit": "new",
    "toplamogrencisayisi": "all",
    "ogretimyilimezunu": "graduates",
}
LEVELS = {
    "onlisans": "associate",
    "lisans": "bachelor",
    "yukseklisans": "master",
    "doktora": "doctorate",
    "lisansustu": "postgraduate",
    "tiptavedishekihtisas": "medical_specialty",
}
DELIVERY = {
    "orgun": "formal",
    "orgunogretim": "formal",
    "ikinciogretim": "evening",
    "uzaktanogretim": "distance",
    "acikogretim": "open",
}
TOTAL_WORDS = {"toplam", "total", "totel"}
#: English echoes and captions in header rows: known, carry no meaning of their own.
IGNORED = {
    "assoc",
    "asst",
    "doctorate",
    "edtng",
    "formaled",
    "graduatestudents",
    "instructor",
    "language",
    "master",
    "medicaldentalinterns",
    "newadmissions",
    "opened",
    "others",
    "research",
    "specialist",
    "totalnumberofstudents",
    "translator",
    "undergraduatestudents",
    "voctrainingsch",
    "university",
    "universite",
    "akademikgorev",
    "ogretimyili",
    "diger",
}
SEXES = {"e": "male", "k": "female"}
#: Reader keys to the dictionary's dimension names.
DIM_NAMES = {
    "event": "student_event",
    "level": "higher_education_level",
    "delivery": "education_delivery",
    "title": "academic_title",
    "unit": "staff_unit",
}


def slug(text: str) -> str:
    """Turkish label to a code, digits kept ("17 YAŞ" -> "17_yas"; `fold` drops digits)."""
    table = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")
    text = text.split(" / ")[0].translate(table).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "blank"


def family_files(pattern: str) -> list[tuple[int, str, Path]]:
    out = []
    for row in csv.reader(
        (FOLDER / "index.tsv").open(encoding="utf-8"), delimiter="\t"
    ):
        if row[0][:4].isdigit() and re.search(pattern, row[1].replace("​", "")):
            out.append(
                (int(row[0][:4]), row[1].replace("​", "").strip(), FOLDER / row[2])
            )
    return out


def is_total(label: str) -> bool:
    key = fold(label)
    return key in ("toplam", "toplamtotal", "geneltoplam") or key.startswith(
        "universitelertoplam"
    )


def parse_table(path: Path) -> tuple[list[tuple[str, dict]], dict, dict]:
    """(rows [(category label, {column key: value})], total {key: value}, meta).

    Column keys are tuples of (dimension, value) pairs. Supports sex across columns (an E/K/T
    header row) and sex down rows (2013-2014 staff tables: T/E/K in column B).
    """
    import xlrd

    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    rows = [[str(v) for v in sheet.row_values(r)] for r in range(sheet.nrows)]
    first = next((i for i, r in enumerate(rows) if is_total(first_line(r[0]))), None)
    unlabeled_total = False
    if first is None:
        # 2021-2023 print the TOPLAM row with its label cell empty, right under E/K/T.
        sex_index = next(
            (
                i
                for i, r in enumerate(rows[:10])
                if {fold(c) for c in r[1:] if c.strip()} >= {"e", "k"}
            ),
            None,
        )
        if (
            sex_index is not None
            and sex_index + 1 < len(rows)
            and not rows[sex_index + 1][0].strip()
            and any(
                re.fullmatch(r"\d+(\.0)?", c.strip()) for c in rows[sex_index + 1][1:]
            )
        ):
            first = sex_index + 1
            unlabeled_total = True
    if first is None:
        raise ValueError(f"{path.name}: TOPLAM satırı yok")
    header = rows[1:first]
    sex_row = next(
        (
            h
            for h in reversed(header)
            if {fold(c) for c in h[1:] if c.strip()} >= {"e", "k"}
        ),
        None,
    )
    down = sex_row is None
    width = max(len(r) for r in rows)
    meaning: dict[int, dict[str, str]] = {j: {} for j in range(1, width)}
    group_starts: set[int] = set()
    for h in header:
        if h is sex_row:
            continue
        carry = None
        starts_here = set()
        for j in range(1, width):
            cell = h[j] if j < len(h) else ""
            # A group opening in a row above ends whatever this row was carrying: without
            # this the last "DOKTORA" ran on into the summary columns beside the levels.
            if j in group_starts and not cell.strip():
                carry = None
            if cell.strip():
                starts_here.add(j)
            word = fold(first_line(cell))
            if cell.strip():
                # Year captions ("2013 - 2014 ÖĞRETİM YILI") fold to nothing: no meaning.
                carry = None if re.match(r"\s*\d{4}\s*-\s*\d{4}", cell) else word
            # Year captions ("2013 - 2014 ÖĞRETİM YILI") label the whole table.
            if carry is None or re.match(r"\d{8}", carry):
                continue
            if carry in EVENTS:
                meaning[j]["event"] = EVENTS[carry]
            elif carry in LEVELS:
                meaning[j].setdefault("level", LEVELS[carry])
                if (
                    carry in ("yukseklisans", "doktora")
                    and meaning[j].get("level") == "postgraduate"
                ):
                    meaning[j]["level"] = LEVELS[carry]
            elif carry in DELIVERY:
                meaning[j]["delivery"] = DELIVERY[carry]
            elif carry in TITLES:
                meaning[j]["title"] = TITLES[carry]
            elif carry in TOTAL_WORDS:
                meaning[j]["total"] = "1"
            elif carry in IGNORED or carry in ("e", "k", "t"):
                continue
            else:
                raise ValueError(f"{path.name}: tanınmayan başlık {cell!r}")
        group_starts |= starts_here
    columns: dict[int, tuple] = {}
    sex_col = None
    if down:
        sex_col = next(
            j
            for j in range(1, 4)
            if fold(rows[first][j]) == "t" or fold(rows[first + 1][j]) == "e"
        )
        for j, m in meaning.items():
            if (
                j > sex_col
                and "total" not in m
                and any(rows[first][j].strip() for _ in [0])
            ):
                columns[j] = tuple(sorted(m.items()))
    else:
        for j in range(1, width):
            sex = SEXES.get(fold(sex_row[j]) if j < len(sex_row) else "")
            if sex and "total" not in meaning[j]:
                columns[j] = tuple(sorted({**meaning[j], "sex": sex}.items()))
    # Where columns carry a level, a column without one is a summary beside them (2014 on:
    # "YENİ KAYIT" and "TOPLAM ÖĞRENCİ" totals after the level blocks). Kept, it doubles
    # every count: 663,186 international students for 2023-2024 instead of 331,593.
    if any(dict(k).get("level") for k in columns.values()):
        columns = {j: k for j, k in columns.items() if dict(k).get("level")}
    if len(set(columns.values())) != len(columns):
        raise ValueError(
            f"{path.name}: iki sütun aynı anlamda {sorted(columns.values(), key=str)[:4]}"
        )
    data: list[tuple[str, dict]] = []
    total: dict = {}
    current = None
    for position, r in enumerate(rows[first:]):
        label = first_line(r[0])
        if unlabeled_total and position == 0:
            label = "TOPLAM"
        if down:
            sex = SEXES.get(fold(r[sex_col]))
            if label and not is_total(label):
                current = label
            elif is_total(label):
                current = "__total__"
            if not sex:
                continue
            values = {
                tuple(sorted({**dict(k), "sex": sex}.items())): number(r[j])
                for j, k in columns.items()
            }
            target = total if current == "__total__" else None
            if target is not None:
                target.update(values)
            elif current:
                if data and data[-1][0] == current:
                    data[-1][1].update(values)
                else:
                    data.append((current, values))
            continue
        if not label or label.startswith(("Resmi", "*", "Kaynak", "Not")):
            continue
        values = {k: number(r[j]) if j < len(r) else 0.0 for j, k in columns.items()}
        if is_total(label):
            if not total:
                total = values
            continue
        if not any(values.values()) and not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", label):
            continue
        data.append((label, values))
    return data, total, {"columns": len(columns)}


def check_flat(path: Path, data, total) -> None:
    for key, printed in total.items():
        parts = sum(v.get(key, 0.0) for _, v in data)
        gap = parts - printed
        if abs(gap) > 0.5:
            # A difference of one or two people in a cell of thousands is a printing slip
            # (2015-2016 graduates by age, doctorate women: 2,394 against 2,393); noted.
            if abs(gap) <= 2 and printed > 100:
                NOTES.append(
                    (
                        "",
                        0,
                        path.name,
                        f"{dict(key)}: satırlar {parts:,.0f}, TOPLAM {printed:,.0f}",
                    )
                )
                continue
            raise ValueError(
                f"{path.name} {dict(key)}: satırlar {parts:,.0f}, TOPLAM {printed:,.0f}"
            )


def resolve_tree(path: Path, data, total) -> list[tuple[str, str, dict]]:
    """[(label, depth, values)] with depth broad / narrow / detailed, from the sums.

    Walks the rows once: at each depth, rows are taken until they add up to the parent
    (the TOPLAM row at the top); every row taken above the deepest level first takes its own
    children the same way. Tried three levels deep, then two (older scheme)."""
    # 2021-2022 postgraduate tables print the unclassified field's narrow and detailed rows
    # as "(boş)" in the middle of the table, its broad row (SINIFLANMAMIŞ) at the end:
    # those rows are dropped, SINIFLANMAMIŞ stands alone, and every sum still has to hold.
    blanks = [row for row in data if fold(row[0]) in ("", "bos")]
    if blanks and any(fold(row[0]).startswith("siniflanmamis") for row in data):
        data = [row for row in data if fold(row[0]) not in ("", "bos")]
    keys = list(total)
    vector = [[v.get(k, 0.0) for k in keys] for _, v in data]
    names = ["broad", "narrow", "detailed"]

    for levels in (3, 2):
        position = 0
        assigned: list[tuple[int, int]] = []

        def take(goal: list[float], depth: int, levels: int = levels) -> bool:
            nonlocal position
            acc = [0.0] * len(goal)
            while position < len(vector) and any(
                abs(a - g) > 0.5 for a, g in zip(acc, goal, strict=True)
            ):
                index = position
                row = vector[index]
                position += 1
                assigned.append((index, depth))
                # "SINIFLANMAMIŞ" (unclassified) closes the table as a broad field printed
                # once, with no narrow or detailed rows under it.
                # Printed once in most years, three times (broad, narrow, detailed) in 2024.
                leaf = fold(data[index][0]).startswith(
                    ("siniflanmamis", "bilinmeyen")
                ) and (
                    index + 1 >= len(vector)
                    or fold(data[index + 1][0]) != fold(data[index][0])
                )
                if depth < levels - 1 and not leaf and not take(row, depth + 1):
                    return False
                acc = [a + b for a, b in zip(acc, row, strict=True)]
                if any(a - g > 0.5 for a, g in zip(acc, goal, strict=True)):
                    return False
            return all(abs(a - g) <= 0.5 for a, g in zip(acc, goal, strict=True))

        if take([total[k] for k in keys], 0) and position == len(vector):
            offset = 3 - levels
            return [(data[i][0], names[d + offset], data[i][1]) for i, d in assigned]
    raise ValueError(f"{path.name}: alan hiyerarşisi toplamlardan çözülemedi")


FAMILIES = {
    # indicator: (label pattern, category dim, extra fixed dims, tree?)
    "yok_international_students": (
        r"(YABANCI UYRUKLU|ULUSLARARASI) ÖĞRENCİLERİN UYRUKLARINA",
        "country",
        False,
    ),
    "yok_international_graduates": (
        r"(YABANCI UYRUKLU|ULUSLARARASI) MEZUNLARIN UYRUKLARINA",
        "country",
        False,
    ),
    "yok_foreign_academic_staff": (
        r"YABANCI UYRUKLU ÖĞRETİM ELEMANLARININ UYRUĞUNA",
        "country",
        False,
    ),
    "yok_new_students_by_age": (r"YAŞLARA GÖRE.*YENİ KAYIT", "age_group", False),
    "yok_students_by_age": (
        r"YAŞLARA GÖRE (\d{4} ?- ?\d{4} )?(ÖĞRETİM YILI )?ÖĞRENCİ SAYILARI",
        "age_group",
        False,
    ),
    "yok_graduates_by_age": (r"YAŞLARA GÖRE.*MEZUN", "age_group", False),
    "yok_students_by_field": (
        r"SINIFLAMASINA GÖRE (.*DÜZEYİNDEKİ|LİSANSÜSTÜ) ÖĞRENCİ",
        "field",
        True,
    ),
    "yok_graduates_by_field": (
        r"SINIFLAMASINA GÖRE (.*DÜZEYİNDEKİ|LİSANSÜSTÜ) MEZUN",
        "field",
        True,
    ),
    "yok_academic_staff_by_field": (
        r"GÖREVLİ ÖĞRETİM ELEMANLARININ\s+EĞİTİM VE ÖĞRETİM ALANLARI",
        "field",
        True,
    ),
}
#: Per field table, the level or unit its whole table covers (not in its columns).
TABLE_SCOPE = {
    "ÖNLİSANS": ("level", "associate"),
    "ÖN LİSANS": ("level", "associate"),
    "LİSANSÜSTÜ": ("level", "postgraduate"),
    "LİSANS": ("level", "bachelor"),
    "ENSTİTÜ": ("unit", "institute"),
}

#: (indicator, year, file, note) for the logic checks run over the years.
NOTES: list[tuple[str, int, str, str]] = []


def table_scope(label: str) -> dict[str, str]:
    for word, (dim, value) in TABLE_SCOPE.items():
        if word in label:
            if "GÖREVLİ" in label and dim == "level":
                return {
                    "unit": {
                        "associate": "associate_programmes",
                        "bachelor": "bachelor_programmes",
                    }.get(value, value)
                }
            return {dim: value}
    return {}


class YokNational:
    source_id = "yok_istatistik"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        pattern, category, tree = FAMILIES[self.indicator_id]
        records = []
        seen: set[tuple[int, str]] = set()
        for year, label, path in family_files(pattern):
            scope = table_scope(label) if tree else {}
            key = (year, str(sorted(scope.items())))
            if key in seen:
                continue  # 2013-2014 lists some tables twice (the "DEK" copies)
            if tree and year < 2015:
                # 2013-2014 and 2014-2015 print the field tables in another layout whose
                # hierarchy does not resolve from the sums; left out, noted.
                NOTES.append(
                    (self.indicator_id, year, path.name, "eski düzen, alınmadı")
                )
                continue
            data, total, _ = parse_table(path)
            if tree:
                try:
                    rows = resolve_tree(path, data, total)
                except ValueError:
                    # Postgraduate field tables of 2021-2022 (students, graduates) and
                    # 2025-2026 (graduates) add up to three times the total but their rows
                    # are out of order; left out, noted. Any other table still stops.
                    if scope.get("level") != "postgraduate":
                        raise
                    NOTES.append(
                        (
                            self.indicator_id,
                            year,
                            path.name,
                            "satır sırası çözülemedi, alınmadı",
                        )
                    )
                    continue
            else:
                check_flat(path, data, total)
                rows = [(name, None, values) for name, values in data]
            seen.add(key)
            for name, depth, values in rows:
                for col, value in values.items():
                    if not value:
                        continue
                    code = (
                        country_code(name)
                        if category == "country"
                        else age_code(name)
                        if category == "age_group"
                        else slug(name)
                    )
                    # The table's own scope fills a dimension only where its columns do not
                    # (postgraduate tables split master's and doctorate in their columns).
                    raw_dims = {**scope, **dict(col), category: code}
                    dims = {DIM_NAMES.get(k, k): v for k, v in raw_dims.items()}
                    if depth:
                        dims["field_level"] = depth
                    records.append(
                        {
                            "period_start": dt.date(year, 1, 1),
                            "dims": ";".join(
                                f"{k}={v}" for k, v in sorted(dims.items())
                            ),
                            "value": value,
                            "label": name,
                        }
                    )
        frame = pl.DataFrame(records, schema_overrides={"value": pl.Float64})
        LABELS[self.indicator_id] = dict(
            frame.select(pl.col("dims").str.extract(category + r"=([^;]+)"), "label")
            .unique()
            .iter_rows()
        )
        return (
            frame.group_by("period_start", "dims")
            .agg(pl.col("value").sum())
            .with_columns(
                pl.lit("TR").alias("area_id"),
                pl.lit("country").alias("area_level"),
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit("annual").alias("frequency"),
                pl.lit("person").alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit("2026-04").alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
            )
        )


#: indicator -> {slug: printed Turkish label}, for the dictionary's value labels.
LABELS: dict[str, dict[str, str]] = {}

YOK_NATIONAL_ADAPTERS = {
    name: type(name, (YokNational,), {"indicator_id": name}) for name in FAMILIES
}


# region Country names

#: Words of state form that come and go between releases ("ALMANYA" / "ALMANYA FEDERAL
#: CUMHURİYETİ"): dropped before the name becomes a code.
STATE_WORDS = {
    "cumhuriyeti",
    "cumhuriyet",
    "kralligi",
    "devleti",
    "devletleri",
    "federal",
    "federatif",
    "demokratik",
    "halk",
    "islam",
    "islami",
    "sosyalist",
    "prensligi",
    "sultanligi",
    "emirligi",
    "cokuluslu",
    "bolivarci",
    "adalari",
    "baylorusyanssc",
    "ssc",
    "birligi",
    "dukaligi",
    "buyukdukaligi",
    "topluluklari",
    "federasyonu",
    "hasimi",
    "sivil",
}
#: Names whose first word alone is not the country.
TWO_WORD = {
    "birlesik",
    "amerika",
    "guney",
    "kuzey",
    "orta",
    "yeni",
    "sri",
    "suudi",
    "bosna",
    "kosta",
    "el",
    "papua",
    "ekvator",
    "dogu",
    "sao",
    "saint",
    "trinidad",
    "fildisi",
    "dominik",
    "burkina",
    "sierra",
    "gine",
    "cape",
    "cabo",
    "solomon",
    "marshall",
    "sahra",
    "vatikan",
    "antigua",
    "saintkitts",
    "kongo",
    "buyuk",
}
COUNTRY_ALIASES = {
    "burma": "myanmar",
    "belorussia": "belarus",
    "baylorusya": "belarus",
    "buyukbritanya": "birlesik_krallik",
    "bahama": "bahamalar",
    "birlesik_arap": "birlesik_arap",
    "birlesik_meksika": "meksika",
    "cekya": "cek",
    "makedonya": "kuzey_makedonya",
    "kuzey_kibris": "kktc",
    "bruneidarusselam": "brunei",
    "birlesik_mex": "meksika",
    "kirgiz": "kirgizistan",
    "kore": "guney_kore",
    "etyopya": "etiyopya",
    "gine_bisau": "gine_bissau",
    "komor": "komorlar",
    "baylorusyan": "belarus",
    "buyuk_britanya": "birlesik_krallik",
    "antigua_ve": "antigua_barbuda",
    "papua_yeni": "papua_yeni_gine",
    "slovak": "slovakya",
    "vatansiz": "stateless",
}


def country_code(label: str) -> str:
    """A stable code for a country name printed several ways; stateless persons suffixed."""
    turkish = label.split(" / ")[0]
    words = [fold(w) for w in re.split(r"[\s\-,()]+", turkish) if fold(w)]
    stateless = any(w.startswith("haym") or w.endswith("haym") for w in words)
    # Two Congos: "demokratik" is what tells the DR Congo from the Republic of the Congo.
    if words and words[0] == "kongo":
        joined = "".join(words)
        dr = "demokratik" in words or "demcumh" in joined
        return ("kongo_dc" if dr else "kongo") + ("_stateless" if stateless else "")
    words = [w for w in words if not w.startswith("haym") and w not in STATE_WORDS]
    if not words:
        return "stateless" if stateless else "blank"
    code = words[0]
    if code in TWO_WORD and len(words) > 1:
        code = f"{words[0]}_{words[1]}"
    code = COUNTRY_ALIASES.get(code, code)
    if code.startswith("birlesik_arap"):
        code = "birlesik_arap"
    return code + ("_stateless" if stateless else "")


# endregion


def age_code(label: str) -> str:
    """ "17 YAŞ / 17 YEARS" -> "17"; "16 YAŞIN ALTI" -> "lt16"; "30-34 YAŞLARI" -> "30-34";
    "65 VE ÜZERİ" -> "65+". Anything else stops the load: an age label must not vanish."""
    text = label.upper()
    numbers = re.findall(r"\d+", text.split("/")[0])
    if "ALT" in text and numbers:
        return f"lt{numbers[0]}"
    if any(w in text for w in ("ÜZER", "UZER", "ÜST", "UST", "+")) and numbers:
        return f"{numbers[0]}+"
    if len(numbers) >= 2 and "-" in text.split("/")[0]:
        return f"{numbers[0]}-{numbers[1]}"
    if len(numbers) == 1 or (numbers and numbers[0] == numbers[-1]):
        return numbers[0]
    if "BİLİNMEYEN" in text or "BILINMEYEN" in text:
        return "unknown"
    raise ValueError(f"tanınmayan yaş: {label!r}")
