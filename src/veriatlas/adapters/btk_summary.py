r"""BTK quarterly market reports, "Özet Bilgiler" (summary) table: yearly national figures.

Every year-end (Q4) report from 2013 opens with a two-year summary table in the text layer
(PDFs from btk.gov.tr/elektronik-haberlesme-pazar-verileri, kept in
`C:\veri-ham\btk\pdf\elektronik-haberlesme-pazar-verileri`). The 2009-2012 reports have no
such table; 2012 comes from the 2013 report. 2018-Q4 is not on the site, so 2018 comes from
the 2019 report. Each year is taken from the newest report printing it.

The page after the table states Türk Telekom's and the alternative operators' fibre length
in a sentence, read here too (2012-2024; the 2025 report dropped it).

Checks: every item must be found in every report; the broadband parts must add up to the
printed broadband total in both columns. Broadband subscribers and call minutes themselves
are not loaded from here (btk_internet_subscribers, btk_call_minutes already hold them).
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold  # drops digits and brackets: patterns carry neither

FOLDER = RAW / "btk" / "pdf" / "elektronik-haberlesme-pazar-verileri"

ITEMS = [
    (r"yetkilendirmesayisi", "btk_operators", "operator_count=authorisations"),
    (r"isletmecisayisi", "btk_operators", "operator_count=operators"),
    (r"sektorugelirleri", "btk_sector_revenue", ""),
    (r"sektoruyatirimlari", "btk_sector_investment", ""),
    (r"^sabitabonesayisi", "btk_subscribers_summary", "subscriber_type=fixed"),
    (
        r"^toplammobilabonesayisi",
        "btk_subscribers_summary",
        "subscriber_type=mobile_total",
    ),
    (r"^mmabonesayisi", "btk_subscribers_summary", "subscriber_type=m2m"),
    (
        r"^mobilabonekisisayisi",
        "btk_subscribers_summary",
        "subscriber_type=mobile_persons",
    ),
    (r"^kablotvabonesayisi", "btk_subscribers_summary", "subscriber_type=cable_tv"),
    (r"^toplamsmstrafigi", "btk_messages", "message_type=sms"),
    (r"^toplammmstrafigi", "btk_messages", "message_type=mms"),
    (r"^(sabitmou|sabitabonebasinaaylikses)", "btk_minutes_of_use", "network=fixed"),
    (r"^(mobilmou|mobilabonebasinaaylikses)", "btk_minutes_of_use", "network=mobile"),
    (
        r"^turktelekom(arpu|abonebasinaayli)",
        "btk_arpu_summary",
        "arpu_scope=turk_telekom",
    ),
    (r"^mobil(arpu|abonebasinaayli)", "btk_arpu_summary", "arpu_scope=mobile"),
    (r"^mobilbilgisayardaninternetabone", "_skip", ""),
    (r"sestrafigi", "_skip", ""),
    (r"^toplamgenisbantinternetabone", "_bb_total", ""),
    (r"^mobilbilgisayardaninternet$", "_bb", "mobile_computer"),
    (r"^mobilcepteninternet$", "_bb", "mobile_handset"),
    (r"^xdsl$", "_bb", "xdsl"),
    (r"^fiber$", "_bb", "fiber"),
    (r"^kablo$", "_bb", "cable"),
    (r"^diger$", "_bb", "other"),
]
BROADBAND = ("mobile_computer", "mobile_handset", "xdsl", "fiber", "cable", "other")
REQUIRED = {
    ("btk_operators", "operator_count=operators"),
    ("btk_operators", "operator_count=authorisations"),
    ("btk_sector_revenue", ""),
    ("btk_sector_investment", ""),
    ("btk_subscribers_summary", "subscriber_type=fixed"),
    ("btk_subscribers_summary", "subscriber_type=mobile_total"),
    ("btk_subscribers_summary", "subscriber_type=m2m"),
    ("btk_subscribers_summary", "subscriber_type=mobile_persons"),
    ("btk_minutes_of_use", "network=fixed"),
    ("btk_minutes_of_use", "network=mobile"),
    ("btk_arpu_summary", "arpu_scope=turk_telekom"),
    ("btk_arpu_summary", "arpu_scope=mobile"),
    ("btk_data_traffic", "network=fixed"),
    ("btk_data_traffic", "network=mobile"),
    ("btk_data_per_subscriber", "network=fixed"),
    ("btk_data_per_subscriber", "network=mobile"),
    ("_bb_total", ""),
} | {("_bb", c) for c in BROADBAND}
UNITS = {
    "btk_operators": "item",
    "btk_sector_revenue": "try",
    "btk_sector_investment": "try",
    "btk_subscribers_summary": "subscriber",
    "btk_messages": "item",
    "btk_minutes_of_use": "minute_per_month",
    "btk_arpu_summary": "try_per_month",
    "btk_data_traffic": "terabyte",
    "btk_data_per_subscriber": "gigabyte_per_month",
    "btk_fiber_length": "km",
}
SCALES = {"btk_messages": 1e6}  # printed in millions
TOKEN = re.compile(r"-?%?-?\d[\d.,]*")


def to_float(token: str) -> float:
    token = token.replace("%", "")
    dotted = re.fullmatch(
        r"(-?\d{1,3}(?:\.\d{3})+)\d?", token
    )  # a glued footnote digit
    if dotted:
        return float(dotted.group(1).replace(".", ""))
    return float(token.replace(",", "."))


def split(line: str) -> tuple[str, list[str]]:
    """Label text and the trailing numeric tokens of a line."""
    tokens = line.split()
    numbers: list[str] = []
    while tokens and (TOKEN.fullmatch(tokens[-1]) or tokens[-1] in ("-%", "%")):
        token = tokens.pop()
        if token not in ("-%", "%"):  # 2016 prints the change as "-% 22,5"
            numbers.insert(0, token)
    return " ".join(tokens), numbers


def summary_text(path: Path) -> tuple[int, str]:
    import pdfplumber

    with pdfplumber.open(path) as document:
        for i in range(1, 16):
            text = document.pages[i].extract_text() or ""
            head = re.search(
                r"(20\d\d)\s*[-/]\s*(20\d\d)\s*(?:YILI\s*)?ÖZET BİLGİLERİ", text
            )
            if head and re.search(r"\d\.\d{3}\.\d{3}", text):
                following = document.pages[i + 1].extract_text() or ""
                return max(
                    int(head.group(1)), int(head.group(2))
                ), text + "\n" + following
    raise ValueError(f"{path.name}: özet tablosu yok")


def parse_summary(path: Path) -> tuple[int, dict[tuple[str, str], tuple[float, float]]]:
    """{(indicator, dims): (this year, previous year)} from one year-end report."""
    year, text = summary_text(path)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    found: dict[tuple[str, str], tuple[float, float]] = {}

    def put(slot, current, previous):
        if slot in found:
            raise ValueError(f"{path.name}: {slot} iki kez")
        found[slot] = (current, previous)

    section = None
    above = ""
    table_lines = []
    for line in lines:
        if line.startswith(("•", "\uf0b7")):
            break
        table_lines.append(line)
    skip_next = False
    for n, line in enumerate(table_lines):
        if skip_next:  # the tail of a label already used by the line above
            skip_next = False
            continue
        label, numbers = split(line)
        key = fold(label)
        if "datatrafigitbyte" in key:
            section = "btk_data_traffic"
        elif "abonebasinaaylikdata" in fold(above + label):
            section = "btk_data_per_subscriber"
        if key in ("mobil", "sabit") and section:
            slot = (section, "network=" + ("fixed" if key == "sabit" else "mobile"))
            if len(numbers) >= 2:
                put(slot, to_float(numbers[0]), to_float(numbers[1]))
            elif len(numbers) == 1:
                # 2025: "74.319.563 65.153.324" on the line above, "Sabit 14,1" here.
                prev_label, prev_numbers = split(table_lines[n - 1])
                if prev_label or len(prev_numbers) != 2:
                    raise ValueError(f"{path.name}: {line!r} değer satırı yok")
                put(slot, to_float(prev_numbers[0]), to_float(prev_numbers[1]))
            continue
        if len(numbers) < 2:
            above = line if not numbers else ""
            continue
        # A wrapped label: the numbers sit beside a part of it, the rest above or below.
        below = table_lines[n + 1] if n + 1 < len(table_lines) else ""
        below = below if not split(below)[1] else ""
        candidates = [
            key,
            fold(above + label),
            fold(above + label + below),
            fold(label + below),
        ]
        above = ""
        # The line's own label first; a neighbour only when the line alone names nothing.
        match = None
        for candidate in candidates:
            match = candidate and next(
                (item for item in ITEMS if re.search(item[0], candidate)), None
            )
            if match:
                break
        if match and match[1] != "_skip":
            put((match[1], match[2]), to_float(numbers[0]), to_float(numbers[1]))
        if match and match is not None and candidates.index(candidate) >= 2:
            skip_next = True
        continue
    fibre = re.search(
        r"Alternatif işletmecilerin.*?(\d{1,3}(?:\.\d{3})+) km.*?(\d{1,3}(?:\.\d{3})+)\s*km.*?"
        r"Türk Telekom.*?(\d{1,3}(?:\.\d{3})+) km.*?(\d{1,3}(?:\.\d{3})+)\s*km",
        " ".join(lines),
    )
    if fibre:
        before, after, tt_before, tt_after = (to_float(g) for g in fibre.groups())
        put(("btk_fiber_length", "fiber_owner=alternative"), after, before)
        put(("btk_fiber_length", "fiber_owner=turk_telekom"), tt_after, tt_before)
    return year, found


def reports() -> dict[int, dict[tuple[str, str], tuple[float, float]]]:
    out = {}
    for path in sorted(FOLDER.glob("20*-Q4.pdf")):
        if int(path.name[:4]) < 2013:
            continue
        year, found = parse_summary(path)
        if year != int(path.name[:4]):
            raise ValueError(f"{path.name}: tablo yılı {year}")
        missing = REQUIRED - set(found)
        if missing:
            raise ValueError(f"BTK özet {year}: bulunamadı {sorted(missing)}")
        for column in (0, 1):
            parts = sum(found[("_bb", c)][column] for c in BROADBAND)
            total = found[("_bb_total", "")][column]
            if abs(parts - total) > 2:
                raise ValueError(
                    f"BTK özet {year} sütun {column}: genişbant parçaları {parts:,.0f} ≠ {total:,.0f}"
                )
        out[year] = found
    if len(out) < 12:
        raise FileNotFoundError(f"{FOLDER}: {len(out)} yıl sonu raporu")
    return out


def load_all() -> dict[tuple[str, str, int], float]:
    """Oldest report first, so a newer report's previous-year column overwrites."""
    out: dict[tuple[str, str, int], float] = {}
    for year, found in sorted(reports().items()):
        for (indicator, dims), (current, previous) in found.items():
            if not indicator.startswith("_"):
                out[(indicator, dims, year - 1)] = previous
                out[(indicator, dims, year)] = current
    return out


class BtkSummary:
    source_id = "btk"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {
                "period_start": dt.date(year, 1, 1),
                "dims": dims,
                "value": value * SCALES.get(indicator, 1.0),
            }
            for (indicator, dims, year), value in load_all().items()
            if indicator == self.indicator_id
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("annual").alias("frequency"),
            pl.lit(UNITS[self.indicator_id]).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-03").alias("vintage"),
            pl.lit("btk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


BTK_SUMMARY_ADAPTERS = {
    indicator: type(
        f"BtkSummary_{indicator}", (BtkSummary,), {"indicator_id": indicator}
    )
    for indicator in UNITS
}
