"""SGK active insured of 4/b and 4/c by single age and sex, Türkiye, 2012-2025.

The yearbooks print "4-1/b (4-1/c) Kapsamındaki Aktif Sigortalıların Yaş ve Cinsiyete Göre
Dağılımı": a row per age (18 up, the oldest ages closed by "65+" or "80 ve üzeri") and sex
columns — for 4/b from 2020 also split into non-agricultural, agricultural and muhtar
groups, which are added. 4/a is printed only crossed with contribution days and tenure
(another table) and is not read here.

Checks (K16): every column's ages add up to its Toplam row; where groups are printed, the
groups add up to the Toplam group column.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

import polars as pl

from .sgk_national import CELLS
from .sgk_pensions_granted import plain, scheme_of

SEXES = (("male", r"^erkek"), ("female", r"^kadin"), ("total", r"^(genel )?toplam"))


def tables() -> pl.DataFrame:
    cells = pl.scan_parquet(CELLS).collect()
    wanted = [
        t
        for t in cells.select("title").unique()["title"].to_list()
        if re.search(r"aktif sigortalilarin yas ve cinsiyet", plain(t))
    ]
    return cells.filter(pl.col("title").is_in(wanted))


_CACHE: dict[tuple[int, str, str, str, str], float] = {}


def read_all() -> dict[tuple[int, str, str, str, str], float]:
    if _CACHE:
        return _CACHE
    for (year, title), cells in tables().group_by("year", "title"):
        scheme = scheme_of(title)
        if scheme == "4c":
            continue  # read from the sheets, see raw_4c
        oldest = (
            cells.filter(pl.col("code").str.contains(r"^\d+$"))["code"].cast(int).max()
        )
        ages: dict[tuple[str, str, str], float] = defaultdict(float)  # group, sex, age
        printed: dict[tuple[str, str], float] = {}
        for code, label, header, value in cells.select(
            "code", "label", "header", "value"
        ).iter_rows():
            if value is None:
                continue
            parts = [plain(p) for p in header.split(" > ")]
            sex = next(
                (s for s, pattern in SEXES if re.search(pattern, parts[-1])), None
            )
            if sex is None:
                raise ValueError(f"{year} {scheme}: tanınmayan sütun {header}")
            group = (
                parts[-2]
                if len(parts) > 1 and not parts[-2].startswith("tablo")
                else ""
            )
            group = "" if group.startswith("table") else group
            top = re.match(r"(\d+) ?(\+|ve uzeri)", plain(label))
            if str(code).isdigit():
                ages[(group, sex, str(int(code)))] += value
            elif top and (oldest is None or oldest < int(top.group(1))):
                ages[(group, sex, top.group(1) + "+")] += value
            elif re.match(r"toplam", plain(label)):
                printed[(group, sex)] = value
        sums: dict[tuple[str, str], float] = defaultdict(float)
        for (group, sex, _age), value in ages.items():
            sums[(group, sex)] += value
        for key, total in printed.items():
            if abs(sums.get(key, 0.0) - total) > max(1.0, total * 0.001):
                raise ValueError(
                    f"{year} {scheme} {key}: yaşlar {sums.get(key)}, Toplam {total}"
                )
        groups = {g for g, _s, _a in ages}
        # "Toplam" is the compulsory subtotal where voluntary insured are printed beside
        # it (2020-2022 4/b), "Genel toplam" the whole
        leaves = {g for g in groups if not re.match(r"(genel )?toplam", g)}
        for (group, sex, age), value in ages.items():
            if group in leaves and sex != "total":
                kind = "voluntary" if "istege" in group else "compulsory"
                key = (year, scheme, kind, sex, age)
                _CACHE[key] = _CACHE.get(key, 0.0) + value
        whole = sorted(g for g in groups if re.match(r"(genel )?toplam", g))
        if whole:
            for sex in ("male", "female"):
                got = sum(
                    v for (g, s, _a), v in ages.items() if g in leaves and s == sex
                )
                want = sum(
                    v for (g, s, _a), v in ages.items() if g == whole[0] and s == sex
                )
                if abs(got - want) > max(1.0, want * 0.001):
                    raise ValueError(
                        f"{year} {scheme} {sex}: gruplar {got}, Toplam {want}"
                    )
    _CACHE.update(raw_4c())
    _CACHE.update(read_4a())
    return _CACHE


def raw_4c() -> dict[tuple[int, str, str, str, str], float]:
    """4/c from the sheets themselves: each yearbook prints several years side by side
    (a year row over the sex row), which the cell extract flattens into one block. A
    year is taken from the latest yearbook printing it."""
    import glob
    import os

    import fastexcel

    books = (
        tables()
        .filter(pl.col("title").map_elements(scheme_of, return_dtype=pl.String) == "4c")
        .select("year", "file", "sheet")
        .unique()
        .sort("year")
    )
    out: dict[tuple[int, str, str, str, str], float] = {}
    for _book, file, sheet in books.iter_rows():
        name = os.path.basename(file.replace("\\", "/"))
        paths = glob.glob(str(CELLS.parent / "**" / name), recursive=True)
        if not paths:
            raise FileNotFoundError(name)
        rows = fastexcel.read_excel(paths[0]).load_sheet_by_name(sheet, header_row=None)
        rows = [list(r) for r in rows.to_polars().rows()]

        def year_of(cell) -> int | None:
            found = re.match(r"((?:19|20)\d\d)(\.0)?\b", str(cell or "").strip())
            return int(found.group(1)) if found else None

        heads = [
            i
            for i, r in enumerate(rows[:10])
            if sum(bool(year_of(c)) for c in r[1:]) >= 2
        ]
        if heads:
            head = heads[0]
            years, year = {}, None
            for j, c in enumerate(rows[head]):
                year = year_of(c) or year
                if j and year:
                    years[j] = year
        else:  # one year only (2012): the sex row is the header
            head = (
                next(
                    i
                    for i, r in enumerate(rows)
                    if any(plain(c or "").startswith("erkek") for c in r)
                )
                - 1
            )
            years = {j: _book for j in range(1, len(rows[head + 1]))}
        sexes = {
            j: next(
                (s for s, pattern in SEXES if re.search(pattern, plain(c or ""))), None
            )
            for j, c in enumerate(rows[head + 1])
        }
        per: dict[tuple[int, str, str], float] = defaultdict(float)
        printed: dict[tuple[int, str], float] = {}
        for r in rows[head + 2 :]:
            label = plain(r[0] or "").strip()
            top = re.match(r"(\d+) ?(\+|ve uzeri)", label)
            age = (
                str(int(float(label)))
                if re.fullmatch(r"\d+(\.0)?", label)
                else (top.group(1) + "+" if top else None)
            )
            for j, value in enumerate(r):
                if j not in years or sexes.get(j) is None or value in (None, ""):
                    continue
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if age:
                    per[(years[j], sexes[j], age)] += number
                elif label.startswith("toplam"):
                    printed[(years[j], sexes[j])] = number
        for (year, sex), total in printed.items():
            got = sum(v for (y, s, _a), v in per.items() if (y, s) == (year, sex))
            if abs(got - total) > max(1.0, total * 0.001):
                raise ValueError(
                    f"4c {sheet} {year} {sex}: yaşlar {got}, Toplam {total}"
                )
        for (year, sex, age), value in per.items():
            if sex != "total":
                out[(year, "4c", "compulsory", sex, age)] = value
    return out


def read_4a() -> dict[tuple[int, str, str, str, str], float]:
    """4/a from "Zorunlu Sigortalıların Yaş, Cinsiyet, Birikimli Prim Ödeme Gün Sayısı ve
    Sigortalılık Süresine Göre Dağılımı": only the insured-person columns are read (the
    other two are days and years). The youngest row is "14 ve altı"."""
    cells = pl.scan_parquet(CELLS).collect()
    wanted = [
        t
        for t in cells.select("title").unique()["title"].to_list()
        # 2012 on ("zorunlu sigortalıların"); 2007-2011 print unknown ages and an 81+ band overlapping 81
        if re.search(r"prim odeme gun", plain(t))
        and re.search(r"zorunlu sigortali", plain(t))
    ]
    out: dict[tuple[int, str, str, str, str], float] = {}
    for (year, title), table in cells.filter(pl.col("title").is_in(wanted)).group_by(
        "year", "title"
    ):
        oldest = (
            table.filter(pl.col("code").str.contains(r"^\d+$"))["code"].cast(int).max()
        )
        ages: dict[tuple[str, str], float] = defaultdict(float)
        printed: dict[str, float] = {}
        for code, label, header, value in table.select(
            "code", "label", "header", "value"
        ).iter_rows():
            parts = [plain(x) for x in header.split(" > ")]
            if (
                value is None
                or len(parts) < 2
                or not re.match(r"sigortali ", parts[-1])
            ):
                continue
            sex = next(
                (s for s, pattern in SEXES if re.search(pattern, parts[-2])), None
            )
            if sex is None:
                raise ValueError(f"4a {year}: tanınmayan sütun {header}")
            text = plain(label)
            top = re.match(r"(\d+) ?(\+|ve uzeri)", text)
            low = re.match(r"(\d+) ve alti", text)
            if str(code).isdigit():
                ages[(sex, str(int(code)))] += value
            elif top and (oldest is None or oldest < int(top.group(1))):
                ages[(sex, top.group(1) + "+")] += value
            elif low:
                ages[(sex, low.group(1) + "-")] += value
            elif text.startswith("toplam"):
                printed[sex] = value
        for sex, total in printed.items():
            got = sum(v for (s, _a), v in ages.items() if s == sex)
            if abs(got - total) > max(1.0, total * 0.001):
                raise ValueError(f"4a {year} {sex}: yaşlar {got}, Toplam {total}")
        for sex in ("male", "female"):
            both = sum(v for (s, _a), v in ages.items() if s in ("male", "female"))
            if "total" in printed and abs(both - printed["total"]) > max(
                1.0, printed["total"] * 0.001
            ):
                raise ValueError(
                    f"4a {year}: erkek+kadın {both}, genel toplam {printed['total']}"
                )
        for (sex, age), value in ages.items():
            if sex != "total":
                out[(year, "4a", "compulsory", sex, age)] = value
    return out


class SgkInsuredByAge:
    source_id = "sgk"
    indicator_id = "sgk_active_insured_by_age"

    def fetch(self) -> Path:
        return CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": f"age={age};insurance_type={kind};scheme={scheme};sex={sex}",
                "value": value,
            }
            for (year, scheme, kind, sex, age), value in read_all().items()
            if value
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit("annual").alias("frequency"),
            pl.lit("person").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-09").alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(dt.date(2026, 9, 14)).alias("retrieved_at"),
        )


SGK_INSURED_BY_AGE_ADAPTERS = {"sgk_active_insured_by_age": SgkInsuredByAge}
