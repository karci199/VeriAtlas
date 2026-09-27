"""SGK marriage allowance paid in the year, by single age, scheme and benefit, 2014-2025.

A daughter drawing a survivor's pension or income loses it when she marries and is paid
a marriage allowance once ("evlenme ödeneği"). The yearbook prints the number paid, by
age, per scheme and per benefit the allowance replaced: survivor's pension ("ölüm
aylığı") or survivor's income from a work injury ("ölüm geliri"). 2014-2018 table 2.15
("kız çocuklarının"), from 2019 table 2.44 ("evlenme ödeneği alanların").

4/b is printed as self-employed and agricultural; the two are added. The scheme and grand
totals are checks, not rows: every column's ages add up to its Toplam row, and the scheme
columns' Toplam rows add up to the grand total's. The oldest row is an open band kept as
printed ("65+" 2014-2018, "80 ve üzeri" from 2019). The 2012-2013 tables use age bands
and are not read.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

import polars as pl

from .sgk_national import CELLS
from .sgk_pensions_granted import plain

BENEFITS = (("survivor_pension", r"olum ayligi"), ("survivor_income", r"olum geliri"))
OPEN_BAND = re.compile(r"^(\d+) ?(\+|ve uzeri)")


def column(header: str) -> tuple[str, str, str] | None:
    """(scheme or "total", branch, benefit) of a header path; None for total columns."""
    parts = [plain(p) for p in header.split(" > ")][2:]
    if not parts:
        return None
    benefit = next((b for b, w in BENEFITS if re.search(w, parts[-1])), None)
    if benefit is None:
        return None
    found = re.search(r"4[-/](?:1[-/ ]?)?([abc])\b", parts[0])
    if found:
        scheme = "4" + found.group(1)
    elif parts[0].startswith("genel toplam"):
        scheme = "total"
    else:
        raise ValueError(f"tanınmayan sütun: {header}")
    return scheme, " > ".join(parts[1:-1]), benefit


def read_all() -> dict[tuple[int, str, str, str], float]:
    cells = pl.read_parquet(CELLS).filter(pl.col("year") >= 2014)
    titles = [
        t for t in cells["title"].unique().to_list() if "evlenme odenegi" in plain(t)
    ]
    out: dict[tuple[int, str, str, str], float] = defaultdict(float)
    for (year, title), table in cells.filter(pl.col("title").is_in(titles)).group_by(
        "year", "title"
    ):
        singles: dict[tuple[str, str, str, str], float] = defaultdict(float)
        bands: dict[tuple[str, str, str, str], float] = defaultdict(float)
        printed: dict[tuple[str, str, str], float] = {}
        for code, label, header, value in table.select(
            "code", "label", "header", "value"
        ).iter_rows():
            if value is None:
                continue
            col = column(header)
            if col is None:
                continue
            band = OPEN_BAND.match(plain(label))
            if str(code).isdigit():
                singles[(*col, str(int(code)))] += value
            elif band:
                bands[(*col, band.group(1))] += value
            elif plain(label).startswith("toplam"):
                printed[col] = value
        if not printed:
            raise ValueError(f"{year}: Toplam satırı yok: {title}")
        # the open band is either the oldest row or a subtotal of single ages printed
        # below it; the reading that adds up to the printed Toplam is the one meant
        starts = {int(k[3]) for k in bands}
        whole = dict(singles)
        cut = {
            k: v for k, v in singles.items() if not starts or int(k[3]) < min(starts)
        }
        cut.update({(*k[:3], k[3] + "+"): v for k, v in bands.items()})
        ages: dict[tuple[str, str, str, str], float] = {}
        for key, total in printed.items():
            tol = max(1.0, total * 0.001)
            chosen = None
            for reading in (whole, cut):
                if (
                    abs(sum(v for k, v in reading.items() if k[:3] == key) - total)
                    <= tol
                ):
                    chosen = reading
                    break
            if chosen is None:
                raise ValueError(f"{year} {key}: yaşlar Toplam {total} tutmuyor")
            ages.update({k: v for k, v in chosen.items() if k[:3] == key})
        # The grand total column is checked at its Toplam only: its single ages drift
        # by a few people from the schemes' (2022: 7 at 80+ in the schemes, 0 in the
        # grand total, the same 20.822 overall).
        for benefit in {k[2] for k in printed}:
            parts = sum(
                v for k, v in printed.items() if k[2] == benefit and k[0] != "total"
            )
            total = printed.get(("total", "", benefit))
            if total is not None and abs(parts - total) > max(1.0, total * 0.001):
                raise ValueError(
                    f"{year} {benefit}: kapsamlar {parts}, genel toplam {total}"
                )
        for (scheme, _branch, benefit, age), value in ages.items():
            if scheme != "total":
                out[(year, scheme, benefit, age)] += value
    return out


class SgkMarriageAllowance:
    source_id = "sgk"
    indicator_id = "sgk_marriage_allowance"

    def fetch(self) -> Path:
        return CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": f"age={age};benefit={benefit};scheme={scheme}",
                "value": value,
            }
            for (year, scheme, benefit, age), value in read_all().items()
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


SGK_MARRIAGE_ALLOWANCE_ADAPTERS = {"sgk_marriage_allowance": SgkMarriageAllowance}
