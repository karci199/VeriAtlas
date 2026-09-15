r"""BTK "Elektronik Kimlik Bilgisini Haiz Cihazlara Dair İstatistikler": IMEI registrations.

btk.gov.tr/elektronik-kimlik-bilgisini-haiz-cihazlara-dair-istatistikler publishes one PDF a
year, 2007-2015 (kept in `C:\veri-ham\btk\pdf\elektronik-kimlik-bilgisini-haiz-cihazlara-dair-istatistikler`).
Each prints its yearly tables back to an earlier year. A PDF can be printed mid-year (the 2010
one is dated 29.09.2010), so a year is taken from the first PDF published after it:
2010-2015 from the 2015 PDF, 2007-2009 from the 2010 PDF. The 2015 PDF has no print date;
its 2015 row is assumed whole.

Tables, in print order (2015 PDF / 2010 PDF):
imported IMEIs by SIM count; imported devices (2015 only); manufactured IMEIs (from July
2009, when import and manufacture were first told apart); manufactured devices (2015 only);
devices brought by travellers; blocking/unblocking by court or prosecutor order; lost/stolen
reports; call centre traffic. Every row is checked against its printed total, except two BTK
typos kept as parts (TOTAL_GAPS). A lone "---" cell is the total less the other cells.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..config import RAW

FOLDER = (
    RAW
    / "btk"
    / "pdf"
    / "elektronik-kimlik-bilgisini-haiz-cihazlara-dair-istatistikler"
)

# (indicator, dims per value column before the total, total column checked)
LAYOUT_2015 = [
    ("btk_imei_import", ["sim=single", "sim=dual"]),
    ("_import_devices", ["sim=single", "sim=dual"]),
    ("btk_imei_manufacture", ["sim=single", "sim=dual"]),
    ("_manufacture_devices", ["sim=single", "sim=dual"]),
    (
        "btk_imei_traveller",
        [
            "registration_channel=abone_kayit",
            "registration_channel=bim",
            "registration_channel=e_devlet",
        ],
    ),
    (
        "btk_imei_court_orders",
        [
            "order_channel=bim;order_action=block",
            "order_channel=bim;order_action=unblock",
            "order_channel=uyap;order_action=block",
            "order_channel=uyap;order_action=unblock",
        ],
    ),
    ("btk_imei_theft_reports", ["report_status=verified", "report_status=unverified"]),
    (
        "btk_imei_call_centre",
        ["call_outcome=answered", "call_outcome=failed", "call_outcome=outbound"],
    ),
]
LAYOUT_2010 = [
    ("btk_imei_import", ["sim=single", "sim=dual"]),
    ("btk_imei_manufacture", ["sim=single", "sim=dual"]),
    ("btk_imei_traveller", ["registration_channel=tk", "registration_channel=akm"]),
    (
        "btk_imei_court_orders",
        [
            "order_channel=bim;order_action=block",
            "order_channel=bim;order_action=unblock",
            "order_channel=uyap;order_action=block",
            "order_channel=uyap;order_action=unblock",
        ],
    ),
    ("btk_imei_theft_reports", ["report_status=verified", "report_status=unverified"]),
    (
        "btk_imei_call_centre",
        ["call_outcome=answered", "call_outcome=failed", "call_outcome=outbound"],
    ),
]
ROW = re.compile(r"^(20\d\d)\*?\s+(.+)$")
# BTK printed totals that miss their parts; the parts are kept.
TOTAL_GAPS = {
    ("btk_imei_theft_reports", 2007),  # +625
    ("btk_imei_theft_reports", 2008),  # +156
    ("btk_imei_theft_reports", 2009),  # +1
    ("btk_imei_court_orders", 2009),  # block +100
    ("btk_imei_court_orders", 2010),  # block +80
    ("btk_imei_import", 2010),  # +4,000
}


def number(token: str) -> float:
    if token == "---":  # not printed; filled from the total when it is the only gap
        return float("nan")
    return 0.0 if token in ("_", "-") else float(token.replace(".", ""))


def groups(path: Path) -> list[list[tuple[int, list[float]]]]:
    import pdfplumber

    with pdfplumber.open(path) as document:
        lines = [
            ln.strip()
            for page in document.pages
            for ln in (page.extract_text() or "").splitlines()
        ]
    out: list[list[tuple[int, list[float]]]] = []
    for line in lines:
        match = ROW.match(line)
        if not match:
            continue
        tokens = match.group(2).split()
        if (
            len(tokens) < 3
            or not any("." in t for t in tokens)
            or not all(re.fullmatch(r"[\d.]+|---|_|-", t) for t in tokens)
        ):
            continue
        year = int(match.group(1))
        if not out or year <= out[-1][-1][0]:
            out.append([])
        out[-1].append((year, [number(t) for t in tokens]))
    return out


def read(path: Path, layout, years: range) -> dict[tuple[str, str, int], float]:
    found = groups(path)
    if len(found) != len(layout):
        raise ValueError(f"{path.name}: {len(found)} tablo, beklenen {len(layout)}")
    out = {}
    for (indicator, dims), rows in zip(layout, found, strict=True):
        for year, values in rows:
            if year not in years:
                continue
            if (
                indicator == "btk_imei_court_orders"
            ):  # BİM, UYAP (block, unblock), then totals
                if len(values) != 6:
                    raise ValueError(
                        f"{path.name} {indicator} {year}: {len(values)} sütun"
                    )
                parts = values[:4]
                gap = abs(parts[0] + parts[2] - values[4]) + abs(
                    parts[1] + parts[3] - values[5]
                )
            else:
                if len(values) != len(dims) + 1:
                    raise ValueError(
                        f"{path.name} {indicator} {year}: {len(values)} sütun"
                    )
                parts = values[:-1]
                blanks = [k for k, v in enumerate(parts) if v != v]
                if len(blanks) == 1:  # 2011 manufactured single-SIM IMEIs print "---"
                    parts[blanks[0]] = 0.0
                    parts[blanks[0]] = values[-1] - sum(parts)
                gap = abs(sum(parts) - values[-1])
            if gap and (indicator, year) not in TOTAL_GAPS:
                raise ValueError(
                    f"{path.name} {indicator} {year}: toplam {gap:,.0f} farklı {values}"
                )
            for dim, value in zip(dims, parts, strict=True):
                out[(indicator, dim, year)] = value
    return out


def load_all() -> dict[tuple[str, str, int], float]:
    out = read(FOLDER / "2010.pdf", LAYOUT_2010, range(2007, 2010))
    out.update(read(FOLDER / "2015.pdf", LAYOUT_2015, range(2010, 2016)))
    return out


INDICATORS = sorted({i for i, _ in LAYOUT_2015 if not i.startswith("_")})


class BtkImei:
    source_id = "btk"
    indicator_id = ""

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        records = [
            {"period_start": dt.date(year, 1, 1), "dims": dims, "value": value}
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
            pl.lit("item").alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2016-01").alias("vintage"),
            pl.lit("btk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


BTK_IMEI_ADAPTERS = {
    indicator: type(f"BtkImei_{indicator}", (BtkImei,), {"indicator_id": indicator})
    for indicator in INDICATORS
}
