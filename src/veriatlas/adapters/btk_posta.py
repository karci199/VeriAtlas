r"""BTK "Türkiye Posta Sektörü Pazar Verileri Raporu": half-year national series, 2021-2025.

The reports (btk.gov.tr/posta-sektoru-pazar-verileri-raporu, kept in
`C:\veri-ham\btk\pdf\posta-sektoru-pazar-verileri-raporu`) print their series as bar charts,
not tables — but the bar labels and the period labels are in the text layer. A chart is read
from the word positions: the row of "2021-1 2021-2 …" labels gives a column centre per
period, and every number above that row whose centre falls in a column is that period's
value. The y-axis ticks sit left of the first column and are dropped.

Only charts with one number per period are read (a stacked percentage chart has three, and
its shares are not loaded). The chart is named by the "Şekil N: …" caption under it.

Each report repeats the earlier half-years, so a period is printed by several reports: the
newest wins, and a disagreement beyond rounding (2%) between two reports is an error.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold

FOLDER = RAW / "btk" / "pdf" / "posta-sektoru-pazar-verileri-raporu"
PERIOD = re.compile(r"^(20\d\d)-([12])$")
# a number, and not the "5." of a heading
NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:,\d+)?")

# caption pattern (folded, anchored at the start) -> (indicator, unit, scale)
# The sector's total revenue and the parcel revenue are drawn as stacked charts with three
# numbers per column, so they cannot be read this way and are not loaded.
CHARTS = {
    r"donemleregoreposta(subeacente|acentesube)sayilari": (
        "btk_post_branches",
        "item",
        1,
    ),
    r"haberlesmegonderilerinindonemleregoredagilimi": ("btk_post_letters", "item", 1e6),
    r"postakolisikargosugonderiadetlerinindonemleregoredagilimi": (
        "btk_post_parcels",
        "item",
        1e6,
    ),
    r"donemleregorehaberlesmegelirleri": ("btk_post_letter_revenue", "try", 1e6),
    r"postasektorundetoplamistihdamsayilari": ("btk_post_employment", "person", 1),
    r"postasektorundegerceklestirilentoplamyatirimmiktari": (
        "btk_post_investment",
        "try",
        1e6,
    ),
    r"btktarafindantoplanansikayetlerinsayisi": ("btk_post_complaints", "item", 1e3),
}
UNITS = {indicator: unit for indicator, unit, _ in CHARTS.values()}


def value(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def reports() -> list[Path]:
    paths = sorted(FOLDER.glob("Posta*.pdf"))
    if len(paths) < 7:
        raise FileNotFoundError(f"{FOLDER}: {len(paths)} rapor")
    return paths


def read_page(words: list[dict]) -> dict[str, dict[dt.date, float]]:
    """{caption: {period start: value}} for the charts on one page."""
    rows: dict[float, list[dict]] = {}
    for word in words:
        if not PERIOD.match(word["text"]):
            continue
        # the labels of one axis are not printed at exactly the same height
        row = next((t for t in rows if abs(t - word["top"]) < 3), round(word["top"], 1))
        rows.setdefault(row, []).append(word)
    out: dict[str, dict[dt.date, float]] = {}
    for top, labels in rows.items():
        if len(labels) < 6:
            continue
        labels.sort(key=lambda w: w["x0"])
        centres = [((w["x0"] + w["x1"]) / 2, w["text"]) for w in labels]
        spacing = (centres[-1][0] - centres[0][0]) / (len(centres) - 1)
        caption = next(
            (
                w["text"]
                for w in words
                if w["top"] > top and re.match(r"^(Şekil|Tablo)", w["text"])
            ),
            None,
        )
        if caption is None:
            continue
        # the caption is a line: collect the words on its row
        caption_top = next(
            w["top"] for w in words if w["text"] == caption and w["top"] > top
        )
        title = " ".join(
            w["text"]
            for w in sorted(
                (w for w in words if abs(w["top"] - caption_top) < 3),
                key=lambda w: w["x0"],
            )
        )
        # A chart label shares its line only with other numbers; a number inside the
        # paragraph above the chart sits on a line of words, and is not a label.
        lines: dict[float, list[dict]] = {}
        for word in words:
            if word["top"] >= top:
                continue
            row = next(
                (t for t in lines if abs(t - word["top"]) < 3), round(word["top"], 1)
            )
            lines.setdefault(row, []).append(word)
        found: dict[dt.date, list[float]] = {}
        for row, line in lines.items():
            if not all(NUMBER.fullmatch(word["text"]) for word in line):
                continue
            for word in line:
                centre = (word["x0"] + word["x1"]) / 2
                if centre < centres[0][0] - spacing / 2:
                    continue  # a y-axis tick
                for column, label in centres:
                    if abs(centre - column) <= spacing / 2:
                        year, half = PERIOD.match(label).groups()
                        start = dt.date(int(year), 1 if half == "1" else 7, 1)
                        found.setdefault(start, []).append(value(word["text"]))
                        break
        if found:
            out[title] = {
                start: values[0] for start, values in found.items() if len(values) == 1
            }
    return out


CONFLICTS: list[tuple] = []  # periods two reports print differently, kept for the notes


def readings() -> dict[tuple[str, dt.date], list[tuple[str, float]]]:
    """Every reading of every period, report by report (oldest first)."""
    import pdfplumber

    out: dict[tuple[str, dt.date], list[tuple[str, float]]] = {}
    for path in reports():
        with pdfplumber.open(path) as document:
            pages = [page.extract_words() for page in document.pages]
        for words in pages:
            for title, series in read_page(words).items():
                key = fold(re.sub(r"^(Şekil|Tablo)\s*\d+\s*:?", "", title))
                match = next(
                    (
                        (indicator, scale)
                        for pattern, (indicator, _unit, scale) in CHARTS.items()
                        if re.match(pattern, key)
                    ),
                    None,
                )
                if match is None:
                    continue
                indicator, scale = match
                for start, number in series.items():
                    out.setdefault((indicator, start), []).append(
                        (path.stem[-6:], number * scale)
                    )
    return out


def load_all() -> dict[tuple[str, dt.date], float]:
    """The reading most reports agree on; ties go to the newest report.

    The reports round differently ("7,9" for "7,86"), so readings within 2% count as the
    same. Where they genuinely differ, the odd one out is a misprint: the 2025-2 report
    prints 232,81 million letter items for 2024-1 where four earlier reports print 132,81.
    """
    out: dict[tuple[str, dt.date], float] = {}
    for slot, found in readings().items():
        groups: list[list[tuple[str, float]]] = []
        for report, number in found:
            scale = next(s for pattern, (i, _u, s) in CHARTS.items() if i == slot[0])
            tolerance = max(abs(number) * 0.02, scale * 0.06)
            group = next(
                (g for g in groups if abs(g[-1][1] - number) <= tolerance), None
            )
            (group if group is not None else groups.append([]) or groups[-1]).append(
                (report, number)
            )
        groups.sort(key=lambda g: (len(g), g[-1][0]))
        if len(groups) > 1:
            CONFLICTS.append(
                (slot[0], slot[1], [(g[-1][0], g[-1][1], len(g)) for g in groups])
            )
        out[slot] = groups[-1][-1][1]
    if len(out) < 60:
        raise ValueError(f"posta: {len(out)} değer, beklenen daha çok")
    return out


_CACHE: dict[tuple[str, dt.date], float] = {}


class BtkPosta:
    source_id = "btk"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        if not _CACHE:
            _CACHE.update(load_all())
        records = [
            {"period_start": start, "value": v}
            for (indicator, start), v in _CACHE.items()
            if indicator == self.indicator_id
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("semiannual").alias("frequency"),
            pl.lit("").alias("dims"),
            pl.lit(UNITS[self.indicator_id]).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-03").alias("vintage"),
            pl.lit("btk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


BTK_POSTA_ADAPTERS = {
    indicator: type(f"BtkPosta_{indicator}", (BtkPosta,), {"indicator_id": indicator})
    for indicator in UNITS
}
