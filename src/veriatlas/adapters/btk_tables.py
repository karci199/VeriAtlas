r"""BTK quarterly market reports, the numbered tables ("Çizelge"), 2010 … 2026-Q1.

The report PDFs (btk.gov.tr/elektronik-haberlesme-pazar-verileri) are kept in
`C:\veri-ham\btk\pdf\elektronik-haberlesme-pazar-verileri`, their text layer page by page in
`C:\veri-ham\btk\pdf\text\<report>.json` (pdfplumber). 2018-Q2 and 2018-Q4 are not on the
site; the 2019 reports and 2020-Q2 are laid out as a magazine whose tables do not come out
as rows, and 2021-Q1 sets its tables in a font with no text mapping: those reports give
nothing, and a period only they printed (2018-4) is missing.

A table is found by its title (folded, so renumbering does not matter) and read in one of
two shapes:

* across: a header of periods ("2025-1 2025-2 …" or "2020 2021 …"), rows of label + one
  number per period, and a TOTAL row that must equal the sum of the rows;
* down: rows of "2025-1 n n n", the columns named by their count (layouts changed over the
  years), with column sums checked where the table has them.

Every report repeats the last few periods, so each period is printed by several reports;
reports are read oldest first and the newest wins. A row whose cells wrapped onto the next
line, or lost digits in the text layer ("5.945.413.12"), is skipped in that report — the
same period comes from a neighbouring report — and its table's total is not checked there.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from ..config import RAW
from .kgm import fold

TEXT = RAW / "btk" / "pdf" / "text"
PERIOD = re.compile(r"^(?:19|20)\d\d(?:-[1-4])?\*?$")
NUMBER = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d+)?$|^-?\d+(?:,\d+)?$|^-$")
CUT = re.compile(r"^-?\d{1,3}(?:\.\d{3})*\.\d{1,2}$")  # lost trailing digits
# "Çizelge 1-3’te …" is a sentence about the table, not its title; "Çizelge 13" lost its dash.
TITLE = re.compile(
    r"^\s*(?:Çizelge|ÇİZELGE|Tablo)\s*\d+\s*[-–.\s]?\s*\d+(?![’'\d])\s*:?\s*(.*)$"
)

Slot = tuple[str, str, dt.date, str]  # indicator, dims, period start, frequency
TOTAL_GAPS: list[tuple] = []  # printed totals BTK got wrong, kept for the notes
SKIPPED_ROWS: list[tuple] = []  # unreadable rows of tables without a total


def value(token: str) -> float:
    if CUT.match(token):
        return float("nan")
    if token == "-":
        return 0.0
    return float(token.replace(".", "").replace(",", "."))


def period_start(token: str) -> tuple[dt.date, str]:
    token = token.rstrip("*")
    if "-" in token:
        year, quarter = token.split("-")
        return dt.date(int(year), (int(quarter) - 1) * 3 + 1, 1), "quarterly"
    return dt.date(int(token), 1, 1), "annual"


def report_lines(report: str) -> list[str]:
    pages = json.loads((TEXT / f"{report}.json").read_text(encoding="utf-8"))
    # Pages stamped "GİZLİ — SADECE KURUM İÇİ" (2024-Q2, 2024-Q3, 2025-Q1…Q3, 2026-Q1) are left
    # out until the user decides on them; their periods come from the neighbouring reports.
    lines = [
        line.strip()
        for page in pages[6:]
        if not re.search(r"G\s*İ\s*Z\s*L\s*İ|SADECE KURUM İÇİ", page)
        for line in page.splitlines()
    ]
    return [re.sub(r"\b(20\d\d) - ([1-4])\b", r"\1-\2", line) for line in lines]


def reports() -> list[str]:
    names = sorted(p.stem for p in TEXT.glob("20??-Q?.json"))
    if len(names) < 65:
        raise FileNotFoundError(f"{TEXT}: {len(names)} rapor metni")
    return names


def find_title(lines: list[str], pattern: str) -> int | None:
    for i, line in enumerate(lines):
        match = TITLE.match(line)
        if not match or "...." in line:
            continue
        title = match.group(1)
        if len(fold(title)) < 12 and i + 1 < len(
            lines
        ):  # title broken after the number
            title = title + " " + lines[i + 1]
        if re.search(pattern, fold(title)):
            return i
    return None


def split_row(line: str) -> tuple[str, list[str]]:
    tokens = line.split()
    numbers: list[str] = []
    while tokens and (NUMBER.match(tokens[-1]) or CUT.match(tokens[-1])):
        numbers.insert(0, tokens.pop())
    return " ".join(tokens), numbers


@dataclass
class Table:
    title: str
    indicator: str = ""  # across tables: one indicator
    rows: dict[str, str] = field(default_factory=dict)  # folded label regex -> dims
    total: str | None = r"toplam"
    # down tables: {column count: [(indicator, dims) or None per column]}
    layouts: dict[int, list[tuple[str, str] | None]] = field(default_factory=dict)
    # down tables: [(part column indexes, total column index)] per layout column count
    sums: dict[int, list[tuple[tuple[int, ...], int]]] = field(default_factory=dict)
    scale: float = 1.0
    dash_is_blank: bool = False  # "-" means "not yet offered" (4.5G before 2016), not 0
    stacked: bool = (
        False  # SMS/MMS: "SMS a b c" / period / "MMS a b c", operators across
    )

    def row_dims(self, label: str) -> str | None:
        # fold drops digits: keep 3G and 4.5G apart first
        label = re.sub(r"4[.,]5\s*G", "dortbucukG", label)
        label = re.sub(r"\b3\s*G", "ucG", label)
        key = fold(label)
        for pattern, dims in self.rows.items():
            if re.fullmatch(pattern, key):
                return dims
        return None

    def read(self, report: str) -> dict[Slot, float]:
        lines = report_lines(report)
        start = find_title(lines, self.title)
        if start is None:
            return {}
        if self.stacked:
            return self.read_stacked(report, lines, start)
        if self.layouts:
            return self.read_down(report, lines, start)
        return self.read_across(report, lines, start)

    def read_across(
        self, report: str, lines: list[str], start: int
    ) -> dict[Slot, float]:
        header = None
        for i in range(start + 1, min(start + 8, len(lines))):
            if TITLE.match(lines[i]):
                break  # the next table: this one printed no header here
            tokens = lines[i].split()
            periods = [t for t in tokens if PERIOD.match(t)]
            if periods and len(periods) >= len(tokens) - 3:
                header = (i, periods)
                break
        if header is None:
            return {}  # a magazine-layout report: the title is not above its table
        i, periods = header
        if len(set(periods)) != len(periods) and all("-" in p for p in periods):
            # 2025-Q1 complaints print "2023-3 2024-4 2024-1 …": consecutive quarters
            # ending at the last one are meant.
            year, quarter = (int(x) for x in periods[-1].rstrip("*").split("-"))
            rebuilt = []
            for _ in periods:
                rebuilt.insert(0, f"{year}-{quarter}")
                year, quarter = (year, quarter - 1) if quarter > 1 else (year - 1, 4)
            periods = rebuilt
        out: dict[Slot, float] = {}
        total_row = None
        broken = False
        pending = ""
        misses = 0
        block = lines[i + 1 : i + 40]
        for n, line in enumerate(block):
            if TITLE.match(line) or line.startswith(("Şekil", "•")):
                break
            label, numbers = split_row(line)
            if not numbers:
                pending = (pending + " " + label).strip()
                misses += 1
                if out and misses > 2:
                    break
                continue
            misses = 0
            full = (pending + " " + label).strip()
            pending = ""
            if not label and len(numbers) == 1:
                continue  # a cell wrapped off the row above
            below = (
                block[n + 1]
                if n + 1 < len(block) and not split_row(block[n + 1])[1]
                else ""
            )
            # a label broken around its numbers: "UYDU" / numbers / "HABERLEŞME"
            # longest reading first, so "Mobil Cepten İnternet" + "(4.5G)" is not taken as the total
            names = [t for t in (f"{full} {below}".strip(), full, label) if t]
            dims = next((d for d in map(self.row_dims, names) if d is not None), None)
            is_total = bool(self.total) and any(
                re.fullmatch(self.total, fold(t)) for t in names
            )
            if below and self.row_dims(f"{full} {below}") is not None:
                block[n + 1] = ""  # the tail is used up
            if dims is None and not is_total:
                if "(cid:" in line:
                    return {}
                if self.total is None:
                    # no total to betray a lost row: note it, the period comes from
                    # a neighbouring report (2014-Q4 prints the labels under the numbers)
                    SKIPPED_ROWS.append((report, self.indicator, line))
                    continue
                raise ValueError(
                    f"{report} {self.indicator}: tanınmayan satır {line!r}"
                )
            if dims == "_skip":
                continue
            if len(numbers) != len(periods):
                broken = True
                if is_total:
                    break
                continue
            cells = [
                float("nan") if (self.dash_is_blank and token == "-") else value(token)
                for token in numbers
            ]
            if is_total:
                total_row = cells
                break
            for token, cell in zip(periods, cells, strict=True):
                start_, frequency = period_start(token)
                slot = (self.indicator, dims, start_, frequency)
                if slot in out:
                    raise ValueError(f"{report} {self.indicator}: {slot} iki kez")
                if not math.isnan(cell):
                    out[slot] = cell * self.scale
                else:
                    broken = True
        if not out:
            return {}
        if self.total and not broken:
            if total_row is None:
                raise ValueError(f"{report} {self.indicator}: toplam satırı yok")
            for token, printed in zip(periods, total_row, strict=True):
                start_, _ = period_start(token)
                parts = sum(v for s, v in out.items() if s[2] == start_) / self.scale
                gap = abs(parts - printed)
                if not math.isnan(printed) and gap > max(2.0, abs(printed) * 1e-6):
                    # BTK's own total misses its rows now and then (2012 other operators by
                    # up to 7% - a type left out of the rows - 2024-1 complaints by 90); a
                    # misread row misses by more.
                    if gap > abs(printed) * 0.1:
                        raise ValueError(
                            f"{report} {self.indicator} {token}: parçalar {parts:,.0f}, toplam {printed:,.0f}"
                        )
                    TOTAL_GAPS.append((report, self.indicator, token, parts, printed))
        return out

    def read_stacked(
        self, report: str, lines: list[str], start: int
    ) -> dict[Slot, float]:
        """ "Hizmet Türü Avea Turkcell Vodafone", then per period "SMS a b c", the period
        alone, "MMS a b c" (the period sits between its two rows)."""
        header = lines[start + 1]
        operators = [
            self.row_dims(name)
            for name in re.findall(r"TT Mobil|Avea|Turkcell|Vodafone", header)
        ]
        if not operators:
            return {}  # 2014 reports print SMS and MMS as totals by quarter; 2021-Q1 unreadable
        if len(operators) != 3 or None in operators:
            raise ValueError(f"{report} {self.indicator}: işletmeci başlığı {header!r}")
        out: dict[Slot, float] = {}
        pending: dict[str, list[float]] = {}
        period = None
        for line in lines[start + 2 : start + 60]:
            label, numbers = split_row(line)
            key = fold(label)
            if key in ("sms", "mms") and len(numbers) == 3:
                if (
                    key == "mms"
                ):  # millions with one decimal: "4.5" is 4,5 here, not cut
                    numbers = [
                        t.replace(".", ",") if re.fullmatch(r"\d+\.\d{1,2}", t) else t
                        for t in numbers
                    ]
                pending[key] = [value(t) for t in numbers]
            elif re.fullmatch(r"20\d\d-[1-4]", line):
                period = line
            else:
                if out or pending:
                    break
                continue
            if period and len(pending) == 2:
                start_, frequency = period_start(period)
                for kind, cells in pending.items():
                    for operator, cell in zip(operators, cells, strict=True):
                        if math.isnan(cell):
                            continue
                        out[
                            (
                                self.indicator,
                                f"message_type={kind};{operator}",
                                start_,
                                frequency,
                            )
                        ] = cell * self.scale
                pending, period = {}, None
        return out

    def read_down(self, report: str, lines: list[str], start: int) -> dict[Slot, float]:
        out: dict[Slot, float] = {}
        started = False
        for line in lines[start + 1 : start + 45]:
            tokens = line.split()
            if not (tokens and re.match(r"^20\d\d-[1-4]\*?$", tokens[0])):
                if started and not re.match(r"^[\d.\s]+$", line):
                    break
                continue
            started = True
            cells = tokens[1:]
            layout = self.layouts.get(len(cells))
            if layout is None or not all(NUMBER.match(c) for c in cells):
                continue  # a broken row ("6. 082"); a neighbouring report has the period
            numbers = [value(c) for c in cells]
            if any(
                abs(sum(numbers[k] for k in parts) - numbers[total]) > 2
                for parts, total in self.sums.get(len(cells), [])
            ):
                TOTAL_GAPS.append((report, self.title, tokens[0], line, None))
                continue  # 2021-Q3/Q4 print 2021-1 fibre with backbone + access ≠ total
            start_, frequency = period_start(tokens[0])
            for column, number in zip(layout, numbers, strict=True):
                if column is not None:
                    indicator, dims = column
                    out[(indicator, dims, start_, frequency)] = number * self.scale
        return out


OPERATORS = {
    r"(t|turk)telekom": "telecom_operator=turk_telekom",
    r"turkcell": "telecom_operator=turkcell",
    r"vodafone": "telecom_operator=vodafone",
    r"(avea|ttmobil)": "telecom_operator=tt_mobil",
}
AUTHORISATIONS = {
    r"iss": "authorisation=isp",
    r"sth": "authorisation=fixed_telephony",
    r"altyapi": "authorisation=infrastructure",
    r"uydu(haberlesme|telekom)": "authorisation=satellite_communication",
    r"uyduplatform": "authorisation=satellite_platform",
    r"rehberlik": "authorisation=directory",
    r"kablotv|kablo(lu)?yayin": "authorisation=cable_tv",
    r"gmpcs": "authorisation=gmpcs",
    r"okth": "authorisation=pamr",
    r"sanalmobil|smsi|mvno": "authorisation=mvno",
}
SECTORS = {
    r"mobil": "complaint_sector=mobile",
    r"iss|internetservissaglayiciligi": "complaint_sector=isp",
    r"uyduplatform": "complaint_sector=satellite_platform",
    r"sabittelefon": "complaint_sector=fixed_telephony",
    r"kablotv": "complaint_sector=cable_tv",
}

TABLES = [
    Table(
        r"turktelekom(un)?vemobil(sebeke)?isletmecilerin(in)?ucayliknetsatis",
        "btk_operator_revenue",
        OPERATORS,
    ),
    Table(
        r"turktelekom(un)?vemobil(sebeke)?isletmecilerin(in)?ucaylikyatirim",
        "btk_operator_investment",
        OPERATORS,
    ),
    Table(
        r"digerisletmecilerinucaylikgelir", "btk_other_operator_revenue", AUTHORISATIONS
    ),
    Table(
        r"digerisletmecilerinucaylikyatirim",
        "btk_other_operator_investment",
        {r"digerisletmeciler": ""},
        total=None,
    ),
    Table(
        r"sektorbazindaucayliktuketicisikayet",
        "btk_consumer_complaints",
        SECTORS,
    ),
    Table(
        r"(ucg|ghizmetikullaniciverileri|gvedortbucukghizmeti)",
        "btk_mobile_broadband_tech",
        {
            r"ucgabonesayisi(mmaboneleridahil)?": "mobile_bb_measure=subscribers_3g",
            r"dortbucukgabonesayisi(mmaboneleridahil)?": "mobile_bb_measure=subscribers_45g",
            r"mobilbilgisayardaninternet(toplam)?": "mobile_bb_measure=computer_total",
            r"mobilbilgisayardanintern?e?t?dortbucukg": "mobile_bb_measure=computer_45g",
            r"mobilcepteninternet(toplam)?": "mobile_bb_measure=handset_total",
            r"mobilcepteninternetdortbucukg": "mobile_bb_measure=handset_45g",
            r"mobilinternetkullanimmiktaritbyte(toplam)?": "mobile_bb_measure=data_tb_total",
            r"mobilinternetkullanimmiktaritbytedortbucukg": "mobile_bb_measure=data_tb_45g",
            # 2010-2012 "mobil internet" tables: another definition, and data in GB
            r"mobilinternet(kullanici|abone)sayisi": "_skip",
            r"mobilinternetkullanimmiktarigbyte": "_skip",
        },
        total=None,
        dash_is_blank=True,
    ),
    Table(
        r"sthisletmecilerinintasiyicisecimi",
        "btk_carrier_selection",
        {
            r"tasiyicionsecimi": "carrier_selection=preselection",
            r"aramabazindatasiyicisecimi": "carrier_selection=call_by_call",
        },
        total=None,
    ),
    Table(
        r"^uyduplatformhizmetigelirleri",
        "btk_satellite_platform_revenue",
        {
            r"yurtici(toplam)?gelir": "revenue_scope=domestic",
            r"yurtdisi(toplam)?gelir": "revenue_scope=abroad",
            r"toplamgelir": "revenue_scope=domestic",  # 2022 on: one row, abroad no longer printed
        },
        total=None,
    ),
    Table(
        r"^isletmecibazindasmsvemmsmiktari",
        "btk_messages_by_operator",
        OPERATORS,
        total=None,
        stacked=True,
        scale=1e6,
    ),
    Table(
        r"^okth(hizmetleri|abone)",
        layouts={
            3: [
                ("btk_pamr", "pamr_measure=subscribers"),
                ("btk_pamr", "pamr_measure=users"),
                ("btk_pamr_revenue", ""),
            ]
        },
    ),
    Table(
        r"^rehberlikhizmetleri",
        layouts={
            7: [
                ("btk_directory_services", "directory_measure=calls"),
                ("btk_directory_services", "directory_measure=call_minutes"),
                ("btk_directory_services", "directory_measure=name_queries"),
                ("btk_directory_services", "directory_measure=number_queries"),
                (
                    "btk_directory_services",
                    "directory_measure=individual_number_queries",
                ),
                (
                    "btk_directory_services",
                    "directory_measure=corporate_number_queries",
                ),
                ("btk_directory_revenue", ""),
            ]
        },
    ),
    Table(
        r"^kabloluyayinhizmetleri",
        layouts={
            4: [
                ("btk_cable_services", "cable_service=cable_tv"),
                ("btk_cable_services", "cable_service=cable_internet"),
                ("btk_cable_services", "cable_service=cable_telephony"),
                ("btk_cable_services", "cable_service=iptv"),
            ],
            5: [
                ("btk_cable_services", "cable_service=cable_tv"),
                ("btk_cable_services", "cable_service=cable_internet"),
                ("btk_cable_services", "cable_service=cable_telephony"),
                ("btk_cable_services", "cable_service=iptv"),
                None,  # revenue, 2011-2012 only
            ],
        },
    ),
    Table(
        r"^uyduhaberlesmehizmetlerineiliskinabone",
        layouts={2: [("btk_satellite_subscribers", ""), ("btk_satellite_revenue", "")]},
    ),
    Table(
        r"^gmpcshizmet(ine|lerine)iliskinabone",
        layouts={2: [("btk_gmpcs_subscribers", ""), ("btk_gmpcs_revenue", "")]},
    ),
    Table(
        r"^sthisletmecilerininnetsatisgelirleri$",
        layouts={1: [("btk_fixed_telephony_revenue", "")]},
    ),
    Table(
        r"^(alternatifaltyapiisletmeciligihizmetlerineiliskingelir|altyapiisletmecigrubunailiskingelir|altyapihizmetlerineiliskingelir)",
        layouts={1: [("btk_infrastructure_revenue", "")]},
    ),
    Table(
        r"^alternatifisletmecilerinfiberuzunluklari",
        layouts={
            5: [
                ("btk_fiber_alternative", "fiber_part=own"),
                ("btk_fiber_alternative", "fiber_part=leased"),
                ("btk_fiber_alternative_use", "fiber_use=backbone"),
                ("btk_fiber_alternative_use", "fiber_use=access"),
                None,
            ]
        },
        sums={5: [((0, 1), 4), ((2, 3), 4)]},
    ),
    Table(
        r"^isletmecilerinfiberuzunluklari",
        layouts={
            5: [
                ("btk_fiber_operators", "fiber_part=own"),
                ("btk_fiber_operators", "fiber_part=leased"),
                ("btk_fiber_operators_use", "fiber_use=backbone"),
                ("btk_fiber_operators_use", "fiber_use=access"),
                None,
            ]
        },
        sums={5: [((0, 1), 4), ((2, 3), 4)]},
    ),
]


def load_all() -> dict[Slot, float]:
    out: dict[Slot, float] = {}
    for report in reports():
        for table in TABLES:
            out.update(table.read(report))
    return out


UNITS = {
    "btk_operator_revenue": "try",
    "btk_operator_investment": "try",
    "btk_other_operator_revenue": "try",
    "btk_other_operator_investment": "try",
    "btk_consumer_complaints": "item",
    "btk_mobile_broadband_tech": "subscriber",
    "btk_carrier_selection": "subscriber",
    "btk_satellite_platform_revenue": "try",
    "btk_messages_by_operator": "item",
    "btk_pamr": "subscriber",
    "btk_pamr_revenue": "try",
    "btk_directory_services": "item",
    "btk_directory_revenue": "try",
    "btk_cable_services": "subscriber",
    "btk_satellite_subscribers": "subscriber",
    "btk_satellite_revenue": "try",
    "btk_gmpcs_subscribers": "subscriber",
    "btk_gmpcs_revenue": "try",
    "btk_fixed_telephony_revenue": "try",
    "btk_infrastructure_revenue": "try",
    "btk_fiber_alternative": "km",
    "btk_fiber_alternative_use": "km",
    "btk_fiber_operators": "km",
    "btk_fiber_operators_use": "km",
}
_CACHE: dict[Slot, float] = {}


class BtkTable:
    source_id = "btk"
    indicator_id = ""

    def fetch(self) -> Path:
        return TEXT

    def parse(self, raw: Path) -> pl.DataFrame:
        if not _CACHE:
            _CACHE.update(load_all())
        records = [
            {"period_start": start, "frequency": frequency, "dims": dims, "value": v}
            for (indicator, dims, start, frequency), v in _CACHE.items()
            if indicator == self.indicator_id and not math.isnan(v)  # cut-off cells
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(UNITS[self.indicator_id]).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-06").alias("vintage"),
            pl.lit("btk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


BTK_TABLE_ADAPTERS = {
    indicator: type(f"BtkTable_{indicator}", (BtkTable,), {"indicator_id": indicator})
    for indicator in UNITS
}
