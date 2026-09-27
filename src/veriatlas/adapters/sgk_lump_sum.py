"""SGK lump-sum payments in the year, by single age and sex, 2014-2025.

A member who reaches pension age without the days for a pension is paid the premiums back
once ("yaşlılık toptan ödemesi"); when an insured person dies without the days for a
survivor's pension, the survivors are paid once ("ölüm toptan ödemesi"). Every yearbook
prints both, per scheme, by age and sex: 4/a table 2.14, 4/b 2.29 (and 2.43 for the
second 4/b law in 2014-2018), 4/c 2.43 or 2.57. The death payment is counted in survivors,
with the survivor's age and sex.

Cells come from `raw/sgk/national_cells.parquet`. 4/b is printed in parts (1479 and 2926
until 2018, agricultural and non-agricultural from 2019); the parts are added. The oldest
row is an open band whose start moves: "75+" 2014-2017, "65+" 2018, "80 ve üzeri" from
2019; it is kept as printed. Printed totals are checks, not rows: each column's ages add
up to its Toplam row, and male + female to the Toplam column. "Ağırlıklı ortalama yaş"
rows are derived and not read. The 2007-2013 tables use age bands and cover 4/a only;
they are not read here.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

import polars as pl

from .sgk_national import CELLS
from .sgk_pensions_granted import plain, scheme_of

KINDS = (("old_age", r"yaslilik"), ("death", r"olum"))
SEXES = (("male", r"^erkek"), ("female", r"^kadin"), ("total", r"^toplam"))
#: 2016 is not read. Its lump-sum tables do not add up in any reading: the Toplam
#: column disagrees with male + female (4/a deaths 919 + 1346 against 2252), single ages
#: follow a "75+" row the Toplam leaves out, and cells repeat 6, 7, 8 as if perturbed.
SKIP_YEARS = {2016}
OPEN_BAND = re.compile(r"^(\d+) ?(\+|ve uzeri)")


def column(header: str) -> tuple[str, str, str] | None:
    """(branch, payment kind, sex) of a header path; None for the all-payments columns."""
    parts = [plain(p) for p in header.split(" > ")]
    if len(parts) < 2:
        return None
    kind = next((k for k, w in KINDS if re.search(w, parts[-2])), None)
    if kind is None:
        return None
    sex = next((s for s, w in SEXES if re.search(w, parts[-1])), None)
    if sex is None:
        raise ValueError(f"tanınmayan sütun: {header}")
    return " > ".join(parts[2:-2]), kind, sex


def read_all() -> dict[tuple[int, str, str, str, str], float]:
    cells = pl.read_parquet(CELLS).filter(pl.col("year") >= 2014)
    titles = [
        t
        for t in cells["title"].unique().to_list()
        if "toptan" in plain(t) and not re.search(r"yas grup", plain(t))
    ]
    out: dict[tuple[int, str, str, str, str], float] = defaultdict(float)
    for (year, title), table in cells.filter(pl.col("title").is_in(titles)).group_by(
        "year", "title"
    ):
        scheme = scheme_of(title)
        if year in SKIP_YEARS:
            continue
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
            raise ValueError(f"{year} {scheme}: Toplam satırı yok: {title}")
        # The open band ("75+", "80 ve üzeri") is printed three ways: as the only row for
        # the oldest ages, as a subtotal of single ages printed below it, and as the real
        # band followed by single ages the Toplam leaves out. The reading whose
        # columns add up to the printed Toplam rows is the one the table means.
        starts = {int(k[3]) for k in bands}
        whole = dict(singles)
        cut = {
            k: v for k, v in singles.items() if not starts or int(k[3]) < min(starts)
        }
        cut.update({(*k[:3], k[3] + "+"): v for k, v in bands.items()})

        def total_of(ages: dict, key: tuple[str, str, str]) -> float:
            return sum(v for k, v in ages.items() if k[:3] == key)

        # decided per column, since a table may print its columns differently
        ages: dict[tuple[str, str, str, str], float] = {}
        misses = []
        for key, total in printed.items():
            tol = max(1.0, total * 0.001)
            if abs(total_of(whole, key) - total) <= tol:
                chosen = whole
            elif abs(total_of(cut, key) - total) <= tol:
                chosen = cut
            else:
                misses.append(f"{key}: yaşlar {total_of(whole, key)}, Toplam {total}")
                continue
            ages.update({k: v for k, v in chosen.items() if k[:3] == key})
        if misses:
            raise ValueError(f"{year} {scheme} {title[:40]}: " + "; ".join(misses[:3]))
        for (branch, kind, sex, age), total in ages.items():
            if sex != "total":
                continue
            parts = ages.get((branch, kind, "male", age), 0.0) + ages.get(
                (branch, kind, "female", age), 0.0
            )
            # 2014 4/a prints age 86 as 2 + 0 = 0: a slip of a person or two
            if abs(parts - total) > 2:
                raise ValueError(
                    f"{year} {scheme} {kind} yaş {age}: erkek+kadın {parts}, Toplam {total}"
                )
        for (_branch, kind, sex, age), value in ages.items():
            if sex != "total":
                out[(year, scheme, kind, sex, age)] += value
    return out


class SgkLumpSumPayments:
    source_id = "sgk"
    indicator_id = "sgk_lump_sum_payments"

    def fetch(self) -> Path:
        return CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": f"age={age};benefit={kind};scheme={scheme};sex={sex}",
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


SGK_LUMP_SUM_ADAPTERS = {"sgk_lump_sum_payments": SgkLumpSumPayments}
