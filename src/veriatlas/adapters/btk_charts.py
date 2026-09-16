r"""BTK quarterly market reports: charts whose labels are still in the text layer (2009-2016).

Up to about 2016 the report charts are vector drawings, so their bar labels are words in the
PDF. This adapter reads the one whose series was lost: "Mobil İşletmeci Bazında Toplam Abone
Sayıları, Milyon" — mobile subscriptions by operator, quarter by quarter.

The chart is read from the word positions, like the postal charts: the row of "2011-1 …"
labels gives a column per quarter, the numbers above it are grouped into lines, and a line of
one number per column is a series. Four such lines are printed — the total and the three
operators — told apart by size: the line the other three add up to is the total, and the rest
in descending order are Turkcell, Vodafone and Avea (that order held well past 2016). The sum
check is what makes a misread line visible.

From 2017 the charts are images and the labels are gone: the operators' shares then come from
the prose (`btk_prose.py`) and the total from the summary tables.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import PUBLIC, RAW
from .kgm import fold

FOLDER = RAW / "btk" / "pdf" / "elektronik-haberlesme-pazar-verileri"
CHART = r"(mobil)?isletmecibazindatoplamabonesayilari"  # older reports drop "Mobil"
NUMBER = re.compile(r"\d{1,3}(?:,\d+)?")
QUARTER = re.compile(r"^20\d\d-[1-4]$")
ORDER = ("turkcell", "vodafone", "tt_mobil")
SKIPPED: list[tuple] = []  # columns whose four labels do not add up


def reports() -> list[Path]:
    paths = sorted(FOLDER.glob("20??-Q?.pdf"))
    if len(paths) < 65:
        raise FileNotFoundError(f"{FOLDER}: {len(paths)} rapor")
    return paths


def lines_of(words: list[dict]) -> dict[float, list[dict]]:
    rows: dict[float, list[dict]] = {}
    for word in words:
        row = next((t for t in rows if abs(t - word["top"]) < 3), round(word["top"], 1))
        rows.setdefault(row, []).append(word)
    return {top: sorted(line, key=lambda w: w["x0"]) for top, line in rows.items()}


def read_page(words: list[dict]) -> dict[tuple[str, dt.date], float] | None:
    """The chart on this page, if it is the one we are after."""
    rows = lines_of(words)
    caption = next(
        (
            top
            for top, line in rows.items()
            if line[0]["text"].startswith("Şekil")
            and re.search(CHART, fold(" ".join(w["text"] for w in line)))
        ),
        None,
    )
    if caption is None:
        return None
    # in the market reports the caption stands above its chart, so the quarter labels and
    # the bar labels are below it
    axis = next(
        (
            top
            for top, line in sorted(rows.items())
            if top > caption
            and len(line) >= 4
            and all(QUARTER.match(w["text"]) for w in line)
        ),
        None,
    )
    if axis is None:
        return None
    columns = [((w["x0"] + w["x1"]) / 2, w["text"]) for w in rows[axis]]
    spacing = (columns[-1][0] - columns[0][0]) / (len(columns) - 1)
    # The bar labels are not printed at one height, so they are collected by column: four
    # numbers per quarter, the largest being the total of the other three.
    found: dict[str, list[float]] = {token: [] for _x, token in columns}
    for word in words:
        if not (caption < word["top"] < axis) or not NUMBER.fullmatch(word["text"]):
            continue
        centre = (word["x0"] + word["x1"]) / 2
        column = next(
            (token for x, token in columns if abs(centre - x) <= spacing / 2), None
        )
        if column:
            found[column].append(float(word["text"].replace(",", ".")))
    out: dict[tuple[str, dt.date], float] = {}
    for token, values in found.items():
        values.sort(reverse=True)
        if len(values) < 4:
            continue  # an axis tick fell in the column, or a label is missing
        # the labels are rounded to one or two decimals, so the total is allowed to miss
        # its parts by 0.12 million
        reading = next(
            (
                (v[0], v[1:4])
                for v in (values[k : k + 4] for k in range(len(values) - 3))
                if abs(sum(v[1:4]) - v[0]) <= 0.12
            ),
            None,
        )
        if reading is None:
            # a y-axis tick fell in the column, or the chart is laid out some other way
            SKIPPED.append((token, values))
            continue
        _total, parts = reading
        year, quarter = token.split("-")
        period = dt.date(int(year), (int(quarter) - 1) * 3 + 1, 1)
        for operator, number in zip(ORDER, parts, strict=True):
            out[(f"telecom_operator={operator}", period)] = number * 1e6
    return out or None


def load_all() -> dict[tuple[str, dt.date], float]:
    import pdfplumber

    out: dict[tuple[str, dt.date], float] = {}
    for path in reports():  # oldest first: a newer report wins
        with pdfplumber.open(path) as document:
            for page in document.pages:
                found = read_page(page.extract_words())
                if found:
                    out.update(found)
                    break
    if len(out) < 90:
        raise ValueError(f"BTK mobil abone grafiği: {len(out)} değer")
    return out


class BtkMobileSubscribersByOperator:
    source_id = "btk"
    indicator_id = "btk_mobile_subscribers_by_operator"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {"period_start": start, "dims": dims, "value": v}
            for (dims, start), v in load_all().items()
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("quarterly").alias("frequency"),
            pl.lit("subscriber").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-06").alias("vintage"),
            pl.lit("btk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


BTK_CHART_ADAPTERS = {
    BtkMobileSubscribersByOperator.indicator_id: BtkMobileSubscribersByOperator
}


def totals_and_shares():
    """Total mobile subscriptions, the operators' shares and the quarters already read off
    the charts — all three from the warehouse, so the PDFs are not opened again."""
    import duckdb

    fact = str(PUBLIC / "fact.parquet")
    con = duckdb.connect()
    totals = dict(
        con.execute(
            "select period_start, value from read_parquet(?) where indicator_id = ? "
            "and dims = ? and frequency = 'quarterly'",
            [fact, "btk_subscribers_summary_quarterly", "subscriber_type=mobile_total"],
        ).fetchall()
    )
    shares = {
        (dims, start): value
        for dims, start, value in con.execute(
            "select dims, period_start, value from read_parquet(?) "
            "where indicator_id = ?",
            [fact, "btk_mobile_subscriber_share"],
        ).fetchall()
    }
    measured = {
        start
        for (start,) in con.execute(
            "select distinct period_start from read_parquet(?) where indicator_id = ?",
            [fact, "btk_mobile_subscribers_by_operator"],
        ).fetchall()
    }
    return totals, shares, measured


class BtkMobileSubscribersEstimated:
    """Share × total, for the quarters the chart no longer prints (2017-2 on).

    The reports stopped printing the operators' subscription numbers when the charts became
    images; the prose keeps the shares, and the summary page keeps the total, so the product
    continues the series. Only quarters with both, and only where the read series stops:
    the figures are marked ``estimated`` because BTK rounds the shares to one decimal, which
    leaves about ±50 thousand subscriptions of slack.
    """

    source_id = "btk"
    indicator_id = "btk_mobile_subscribers_by_operator_estimated"

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        totals, shares, measured = totals_and_shares()
        records = []
        for (dims, start), share in shares.items():
            if start in measured or start not in totals:
                continue
            records.append(
                {
                    "period_start": start,
                    "dims": dims,
                    "value": totals[start] * share / 100,
                }
            )
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("quarterly").alias("frequency"),
            pl.lit("subscriber").alias("unit"),
            pl.lit("estimated").alias("quality_flag"),
            pl.lit("2026-06").alias("vintage"),
            pl.lit("btk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


BTK_CHART_ADAPTERS[BtkMobileSubscribersEstimated.indicator_id] = (
    BtkMobileSubscribersEstimated
)
