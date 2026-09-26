"""Car and light commercial vehicle market structure — ODMD monthly reports, Türkiye, yearly.

ODMD's "Otomobil ve Hafif Ticari Araç Pazar Değerlendirme" (`neuralnetwork.aspx?type=35`)
comes as one PDF a month; from 2020 on each carries annex tables ("Ek 4-10") for the month
and for the year to date. The December report's year-to-date section is the full year, and
every table also has last year's column, so year Y is read from the December Y report and,
table by table, from the December Y+1 report where the first is missing. Pulled
2026-09-26 into `odmd/pazar/<primary_id>.pdf` with the list titles in `liste.json`.

Tables kept (cars unless noted): segment × body type (Ek 4), powertrain (Ek 5), CO2 band
(Ek 7), automatic-gearbox sales by segment (Ek 8), light commercial body type (Ek 9) and
powertrain (Ek 10, from 2023). Engine size (Ek 6) is left out: its bands follow the
special consumption tax brackets and change between years. Ek 1-3 and the brand pages
repeat the retail workbooks (`odmd_retail.py`).

The text layer is read, not the table finder: several reports draw tables without rules.
Some reports embed a table as an image; that table is simply absent for that year. Every
table must add up to its own "Toplam" row, and the car tables of one year must agree on
the car total; either failing stops the load. Only complete years are kept.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import ClassVar

import polars as pl

from ..config import RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "odmd" / "pazar"

NUM = r"\d{1,3}(?:\.\d{3})*"
PCT = r"-?\d+(?:,\d+)?\s?%"
PAIR = re.compile(rf"^(.*?)\s*({NUM})\s+({PCT})\s+({NUM})\s+({PCT})")
SEG = re.compile(rf"^([A-F]) \([^)]*\)((?:\s+{NUM}){{8}})")
EK = re.compile(r"^Ek ?(\d+)\s*:")

BODIES = ["sedan", "hatchback", "station_wagon", "mpv", "cdv", "sport", "suv"]
SEGMENTS = {"A": "a", "B": "b", "C": "c", "D": "d", "E": "e", "F": "f"}
CO2 = {
    "< 100": "lt100",
    "≥ 100 - < 120": "100_120",
    "≥ 120 - < 140": "120_140",
    "≥ 140 - < 160": "140_160",
    "≥ 160": "ge160",
}
LCV_BODIES = {
    "Van": "van",
    "Kamyonet": "light_truck",
    "Minibüs": "minibus",
    "Pickup": "pickup",
    "Karavan": "camper",
}
PARENTS = {"Benzin": "petrol", "Dizel": "diesel", "Otogaz": "lpg"}
SUBS = {
    "Hibrit": ("hybrid", "full_hybrid"),
    "Plug-In Hibrit": ("hybrid", "plug_in_hybrid"),
    "Mild Hibrit": ("hybrid", "mild_hybrid"),
    "Saf Elektrik": ("electric", "battery_electric"),
    "Uzatılmış Menzil": ("electric", "range_extender"),
}

INDICATORS = {
    4: "odmd_car_sales_by_segment_body",
    5: "odmd_car_sales_by_powertrain",
    7: "odmd_car_sales_by_co2",
    8: "odmd_car_sales_automatic",
    9: "odmd_lcv_sales_by_body",
    10: "odmd_lcv_sales_by_powertrain",
}


def number(s: str) -> float:
    return float(s.replace(".", ""))


def year_section(text: str, year: int) -> list[str]:
    lines = [line.strip() for line in text.splitlines()]
    heads = (f"Ocak-Aralık {year} Verileri", f"{year} Verileri")
    start = next((i for i, line in enumerate(lines) if line in heads), None)
    if start is None:
        return []
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if (
            re.match(r"^\S+ \d{4} Verileri$", lines[i])
            or "PERAKENDE SATIŞLAR" in lines[i]
        ):
            end = i
            break
    return lines[start:end]


def read_tables(lines: list[str], year: int, previous: bool) -> dict[int, list]:
    """Annex number → rows, for `year`'s column (or the year before, when `previous`)."""
    want, other = (year - 1, year) if previous else (year, year - 1)
    blocks: dict[int, list] = {}
    ek, seg_on = None, False
    for line in lines:
        m = EK.match(line)
        if m:
            ek = int(m.group(1))
            continue
        if ek == 4:
            if re.match(rf"^(Ocak-Aralık )?{want}\b", line):
                seg_on = True
            elif re.match(rf"^(Ocak-Aralık )?{other}\b", line) or line.startswith(
                "Değişim"
            ):
                seg_on = False
            elif seg_on and (sm := SEG.match(line)):
                values = [number(x) for x in sm.group(2).split()]
                blocks.setdefault(4, []).append((sm.group(1), values))
            continue
        if ek in INDICATORS and (pm := PAIR.match(line)):
            value = number(pm.group(2 if previous else 4))
            blocks.setdefault(ek, []).append((pm.group(1).strip(), value))
    return blocks


def rows_for(ek: int, rows: list, label: str) -> tuple[list[tuple[dict, float]], float]:
    """Dims-value rows and the table's own total, checked against each other."""
    out: list[tuple[dict, float]] = []
    if ek == 4:
        for seg, values in rows:
            if sum(values[:7]) != values[7]:
                raise ValueError(f"odmd pazar {label}: {seg} segmenti satiri tutmuyor")
            for body, value in zip(BODIES, values[:7], strict=True):
                out.append(({"body_type": body, "car_segment": SEGMENTS[seg]}, value))
        return out, sum(v[7] for _, v in rows)
    total = next((v for name, v in rows if name.startswith("Toplam")), None)
    body = [(name, v) for name, v in rows if not name.startswith("Toplam")]
    if total is None:
        raise ValueError(f"odmd pazar {label}: Ek {ek} Toplam satiri yok")
    if ek in (5, 10):
        parents, subs = {}, {}
        seen = set()
        for name, v in body:
            if name in PARENTS:
                out.append(({"powertrain": PARENTS[name]}, v))
            elif name in ("Hibrit", "Elektrik") and name not in seen:
                parents["hybrid" if name == "Hibrit" else "electric"] = v
                seen.add(name)
            elif name in SUBS:
                group, code = SUBS[name]
                subs.setdefault(group, {})[code] = v
            else:
                raise KeyError(f"odmd pazar {label}: taninmayan motor tipi: {name}")
        for group, value in parents.items():
            parts = subs.get(group)
            if parts:
                if abs(sum(parts.values()) - value) > 0.5:
                    raise ValueError(
                        f"odmd pazar {label}: {group} alt turleri tutmuyor"
                    )
                out += [({"powertrain": code}, v) for code, v in parts.items()]
            else:
                out.append(({"powertrain": group}, value))
    else:
        mapping = {7: CO2, 9: LCV_BODIES}.get(ek, {})
        for name, v in body:
            if ek == 8:
                code = SEGMENTS.get(name[:1]) if re.match(r"^[A-F] \(", name) else None
                dims = {"car_segment": code}
            else:
                code = mapping.get(name)
                dims = {"co2_band" if ek == 7 else "lcv_body_type": code}
            if code is None:
                raise KeyError(f"odmd pazar {label}: Ek {ek} taninmayan satir: {name}")
            out.append((dims, v))
    if abs(sum(v for _, v in out) - total) > 0.5:
        raise ValueError(f"odmd pazar {label}: Ek {ek} satirlar toplami tutmuyor")
    return out, total


def december_reports(raw: Path) -> dict[int, Path]:
    titles = json.loads((raw / "liste.json").read_text(encoding="utf-8"))
    out = {}
    for pid, title in titles.items():
        m = re.match(r"^(20\d\d) Aralık ", title)
        if m and int(m.group(1)) >= 2020 and (raw / (pid + ".pdf")).exists():
            out[int(m.group(1))] = raw / (pid + ".pdf")
    return out


def text_of(path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


class OdmdMarketBase:
    source_id = "odmd"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 26)
    indicator_id = ""
    annex = 0
    _cache: ClassVar[dict[Path, dict]] = {}

    def fetch(self) -> Path:
        if not (DOWNLOADS / "liste.json").exists():
            raise FileNotFoundError("ODMD pazar dokumu yok: " + str(DOWNLOADS))
        return DOWNLOADS

    @classmethod
    def all_years(cls, raw: Path) -> dict[int, dict[int, list]]:
        if raw not in cls._cache:
            years: dict[int, dict[int, list]] = {}
            fallback: dict[int, dict[int, list]] = {}
            for year, path in december_reports(raw).items():
                lines = year_section(text_of(path), year)
                years[year] = read_tables(lines, year, previous=False)
                fallback[year - 1] = read_tables(lines, year, previous=True)
            merged = {}
            for year in sorted(set(years) | set(fallback)):
                tables = dict(fallback.get(year, {}))
                tables.update(years.get(year, {}))
                merged[year] = tables
            cls._cache[raw] = merged
        return cls._cache[raw]

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        for year, tables in self.all_years(raw).items():
            car_totals = set()
            for ek in (4, 5, 7):
                if ek in tables:
                    car_totals.add(rows_for(ek, tables[ek], str(year))[1])
            if len(car_totals) > 1:
                raise ValueError(
                    f"odmd pazar {year}: otomobil toplamlari tutmuyor {car_totals}"
                )
            if self.annex not in tables:
                continue
            rows, _ = rows_for(self.annex, tables[self.annex], str(year))
            for dims, value in rows:
                records.append((dt.date(year, 1, 1), format_dims(dims), value))
        frame = pl.DataFrame(
            records, schema=["period_start", "dims", "value"], orient="row"
        )
        if frame.is_empty():
            raise ValueError(self.indicator_id + ": satir yok")
        if frame.select("period_start", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni yil-kirilim iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        ).select(
            "indicator_id",
            "area_id",
            "area_level",
            "period_start",
            "frequency",
            "dims",
            "value",
            "unit",
            "quality_flag",
            "vintage",
            "source_id",
            "retrieved_at",
        )


ODMD_MARKET_ADAPTERS = {
    ident: type(
        "".join(p.title() for p in ident.split("_")),
        (OdmdMarketBase,),
        {"indicator_id": ident, "annex": ek},
    )
    for ek, ident in INDICATORS.items()
}
