"""SGK pensions granted in the year, by single age, pension type and recipient, 2014-2025.

Every yearbook prints, for 4/a, 4/b and (from 2019) 4/c, "Yıl İçinde Aylık Bağlananların
Yaş(lar)a ve Aylık Türüne Göre Dağılımı": a row per age, columns per pension type —
invalidity, old-age (by sex) and survivor's pension (by the survivor: husband, wife, son,
daughter, father, mother). 4/b is printed in two parts, 1479 and 2926 (2014-2018) or
non-agricultural and agricultural (from 2020); the parts are added into 4/b.

Cells come from `raw/sgk/national_cells.parquet`; a column is recognised by the words of
its header path. Printed totals are checks, not rows: every column must add up over the
ages to its Toplam row, and male + female to the Toplam column (K16). The tables with
work-injury incomes ("gelir bağlanan") and deaths of pensioners are different tables and
not read here.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

import polars as pl

from .sgk_national import CELLS

TYPES = (("invalidity", "malul"), ("old_age", "yasli"), ("survivor_pension", "olum"))
RECIPIENTS = (
    ("husband", r"erkek es"),
    ("wife", r"kadin es"),
    ("son", r"erkek cocuk"),
    ("daughter", r"kiz cocuk"),
    ("father", r"^baba"),
    ("mother", r"^ana"),
    ("male", r"^erkek"),
    ("female", r"^kadin"),
    ("total", r"^toplam"),
)


def plain(text: str) -> str:
    """Lower case without Turkish marks, so AYLIK / Aylık / aylik meet."""
    table = str.maketrans("çğıöşüâî", "cgiosuai")
    return (
        str(text)
        .replace("İ", "i")
        .replace("I", "ı")
        .lower()
        .replace("i̇", "i")
        .translate(table)
    )


def scheme_of(title: str) -> str:
    found = re.search(r"4[-/](?:1[-/ ]?)?([abc])\b", plain(title))
    if not found:
        raise ValueError(f"kapsam okunamadı: {title}")
    return "4" + found.group(1)


def column(header: str) -> tuple[str, str] | None:
    """(pension type, recipient) of a header path, None for the grand total column."""
    parts = [plain(p) for p in header.split(" > ")]
    kind = next((k for k, w in TYPES for p in parts[-2:] if w in p), None)
    if kind is None:
        return None
    who = next((r for r, pattern in RECIPIENTS if re.search(pattern, parts[-1])), None)
    if who is None:
        raise ValueError(f"tanınmayan sütun: {header}")
    return kind, who


#: family -> title words: pensions granted in the year, and pensioners at year end
FAMILIES = {"granted": r"aylik baglananlar", "stock": r"aylik alanlar"}


def tables(family: str = "granted") -> pl.DataFrame:
    cells = pl.scan_parquet(CELLS).collect()
    titles = cells.select("title").unique()["title"].to_list()
    wanted = [
        t
        for t in titles
        if re.search(FAMILIES[family], plain(t))
        and re.search(r"tur", plain(t))
        and re.search(r"\byas", plain(t))
        and not re.search(r"olen|gelir (baglanan|alan)", plain(t))
    ]
    return cells.filter(pl.col("title").is_in(wanted))


_CACHES: dict[str, dict[tuple[int, str, str, str, str], float]] = {}


def read_all(family: str = "granted") -> dict[tuple[int, str, str, str, str], float]:
    if family in _CACHES:
        return _CACHES[family]
    _CACHE = _CACHES[family] = {}
    for (year, title), cells in tables(family).group_by("year", "title"):
        scheme = scheme_of(title)
        ages: dict[tuple[str, str, str, str], float] = defaultdict(float)
        printed: dict[tuple[str, str, str], float] = {}
        # "80 ve üzeri" is an open band in some tables and a subtotal of the single
        # ages printed above it in others; it counts only where no age at or above it is
        # printed on its own
        oldest = (
            cells.filter(pl.col("code").str.contains(r"^\d+$"))["code"].cast(int).max()
        )
        for code, label, header, value in cells.select(
            "code", "label", "header", "value"
        ).iter_rows():
            if value is None:
                continue
            col = column(header)
            if col is None:
                continue
            # the column's parent keeps agri / non-agri and ordinary / duty apart
            branch = header.rsplit(" > ", 1)[0]
            top = re.match(r"(\d+) ?(\+|ve uzeri)", plain(label))
            if str(code).isdigit():
                ages[(branch, *col, str(int(code)))] += value
            elif top and (oldest is None or oldest < int(top.group(1))):
                ages[(branch, *col, top.group(1) + "+")] += value
            elif re.match(r"toplam", plain(label)):
                printed[(branch, *col)] = value
        sums: dict[tuple[str, str, str], float] = defaultdict(float)
        for (branch, kind, who, _age), value in ages.items():
            sums[(branch, kind, who)] += value
        for key, total in printed.items():
            if abs(sums.get(key, 0.0) - total) > max(1.0, total * 0.001):
                raise ValueError(
                    f"{year} {scheme} {key[1:]}: yaşlar {sums.get(key)}, Toplam {total}"
                )
        for (branch, kind, who, age), value in ages.items():
            if who == "total":
                continue
            key = (year, scheme, kind, who, age)
            _CACHE[key] = _CACHE.get(key, 0.0) + value
        for (branch, kind, age), total in {
            (b, k, a): v for (b, k, w, a), v in ages.items() if w == "total"
        }.items():
            parts = sum(
                v
                for (b, k, w, a), v in ages.items()
                if (b, k, a) == (branch, kind, age) and w != "total"
            )
            # 2016 4/b prints age 120 as 2 + 0 = 0: a slip of a person or two
            if abs(parts - total) > 2:
                raise ValueError(
                    f"{year} {scheme} {kind} yaş {age}: parçalar {parts}, Toplam {total}"
                )
    return _CACHE


class SgkPensionsGranted:
    source_id = "sgk"
    indicator_id = "sgk_pensions_granted"
    family = "granted"

    def fetch(self) -> Path:
        return CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": f"age={age};benefit={kind};recipient={who};scheme={scheme}",
                "value": value,
            }
            for (year, scheme, kind, who, age), value in read_all(self.family).items()
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


class SgkPensionersByAge(SgkPensionsGranted):
    indicator_id = "sgk_pensioners_by_age"
    family = "stock"


SGK_PENSIONS_GRANTED_ADAPTERS = {
    "sgk_pensions_granted": SgkPensionsGranted,
    "sgk_pensioners_by_age": SgkPensionersByAge,
}
