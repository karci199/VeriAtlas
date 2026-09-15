"""EPDK (Energy Market Regulatory Authority): electricity, natural gas, fuel and LPG by province.

`scripts/fetch_epdk_documents.py` downloads every document linked from EPDK's report pages
into `raw/epdk/files/<market>/`. This adapter reads the Excel annexes of the 2025 market
development reports — the only years published as spreadsheets; earlier years sit inside
Word and PDF reports and are not read here.

Every table is checked against the totals it prints: the kinds of a province against the
province total, and the provinces against the national total. A table that does not add up
stops the load. The province name is carried down: the tables print it on the first row of
a block only, and the national total row has an empty name cell — read naively, that row
joins the last province (it made Bayburt consume all of Türkiye's electricity).
"""

from __future__ import annotations

import datetime as dt
from functools import cache
from pathlib import Path

import openpyxl
import polars as pl

from ..config import RAW
from .kgm import fold, province_id

FILES = RAW / "epdk" / "files"
ELECTRICITY = FILES / "elektrik_yillik" / "CTzWPdgnxCU_.xlsx"
GAS = FILES / "dogalgaz_yillik" / "kcdXT4G_vpI_.xlsx"
PETROL = FILES / "petrol_yillik" / "Wrw13Vh9_zc_.xlsx"
LPG = FILES / "lpg_yillik" / "1EpuUc03tR8_.xlsx"

CONSUMER_TYPES = {
    "aydinlatma": "lighting",
    "kamuveozelhizmetlersektoruilediger": "commercial_public",
    "mesken": "residential",
    "sanayi": "industrial",
    "tarimsalfaaliyetler": "agricultural",
}
GAS_SECTORS = {
    "donusumcevrimsektoru": "conversion",
    "enerjisektoru": "energy",
    "ulasimsektoru": "transport",
    "sanayisektoru": "industry",
    "hizmetsektoru": "services",
    "konutlar": "residential",
    "diger": "other",
}
PETROL_PRODUCTS = {
    "benzinturleri": "gasoline",
    "denizcilikyakitlari": "marine_fuel",
    "digerurunler": "other",
    "fueloilturleri": "fuel_oil",
    "gazyagi": "kerosene",
    "havacilikyakitlari": "aviation_fuel",
    "motorinturleri": "diesel",
}
LPG_PRODUCTS = {"tuplu": "cylinder", "dokme": "bulk", "otogaz": "autogas"}


class TotalMismatch(ValueError):
    pass


def close(a: float, b: float, what: str) -> None:
    if abs(a - b) > max(1.0, abs(b) * 1e-6):
        raise TotalMismatch(f"{what}: parçalar {a:,.1f}, basılı toplam {b:,.1f}")


@cache
def sheet(path: Path, name: str) -> list[tuple]:
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    return list(book[name].iter_rows(values_only=True))


def fact(
    records: list[dict], indicator_id: str, unit: str, vintage: str
) -> pl.DataFrame:
    frame = pl.DataFrame(records, schema_overrides={"value": pl.Float64})
    return frame.with_columns(
        pl.lit(indicator_id).alias("indicator_id"),
        pl.lit("province").alias("area_level"),
        pl.lit("annual").alias("frequency"),
        pl.lit(unit).alias("unit"),
        pl.lit("measured").alias("quality_flag"),
        pl.lit(vintage).alias("vintage"),
        pl.lit("epdk").alias("source_id"),
        pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
    )


def row(area: str, year: int, dims: str, value: float) -> dict:
    return {
        "area_id": area,
        "period_start": dt.date(year, 1, 1),
        "dims": dims,
        "value": float(value),
    }


class Epdk:
    source_id = "epdk"
    indicator_id = ""
    vintage = "2026-06"

    def fetch(self) -> Path:
        return FILES


# region Electricity


def electricity(table: str) -> list[dict]:
    """Tablo 3 (consumption, MWh) or Tablo 4 (consumers): province × type, 2024 and 2025."""
    rows = sheet(ELECTRICITY, table)
    columns = {2: 2024, 4: 2025}
    blocks: dict[str, dict[str, tuple]] = {}
    grand = None
    province = None
    for r in rows[2:]:
        label = fold(str(r[1] or ""))
        if label == "geneltoplam":
            grand = r
            continue
        if r[0]:
            province = province_id(str(r[0]))
        if province and r[1] and isinstance(r[2], (int, float)):
            blocks.setdefault(province, {})[label] = r
    if len(blocks) != 81 or grand is None:
        raise ValueError(
            f"elektrik {table}: {len(blocks)} il, genel toplam {grand is not None}"
        )
    out = []
    for col, year in columns.items():
        national = 0.0
        for province, kinds in blocks.items():
            parts = {
                CONSUMER_TYPES[k]: v[col] for k, v in kinds.items() if k != "iltoplam"
            }
            if set(parts) != set(CONSUMER_TYPES.values()):
                raise ValueError(
                    f"elektrik {table} {province}: türler eksik {sorted(parts)}"
                )
            close(
                sum(parts.values()),
                kinds["iltoplam"][col],
                f"elektrik {table} {province} {year}",
            )
            national += kinds["iltoplam"][col]
            out += [row(province, year, "consumer=" + k, v) for k, v in parts.items()]
        close(national, grand[col], f"elektrik {table} Türkiye {year}")
    return out


class EpdkElectricityConsumption(Epdk):
    indicator_id = "epdk_electricity_consumption"

    def parse(self, raw: Path) -> pl.DataFrame:
        return fact(electricity("Tablo 3"), self.indicator_id, "mwh", self.vintage)


class EpdkElectricityConsumers(Epdk):
    indicator_id = "epdk_electricity_consumers"

    def parse(self, raw: Path) -> pl.DataFrame:
        return fact(
            electricity("Tablo 4"), self.indicator_id, "subscriber", self.vintage
        )


# endregion

# region Natural gas


class EpdkGasSales(Epdk):
    """Tablo-13: sales by province, company and sector (Sm3), summed over companies.

    Each province block ends with a TOPLAM row that the company rows are checked against.
    The closing `DİĞER` block is gas used in the transmission grid and storage, which has no
    province; it is left out, and the provinces then add up to the national sales without it.
    """

    indicator_id = "epdk_natural_gas_sales"

    def parse(self, raw: Path) -> pl.DataFrame:
        rows = sheet(GAS, "Tablo 13")
        header = None
        province = None
        sums: dict[str, float] = {}
        out = []
        for r in rows:
            first = fold(str(r[0] or ""))
            if r[1] and fold(str(r[1])) == "lisanstipi":
                header = [GAS_SECTORS.get(fold(str(c or ""))) for c in r]
                province = None if first == "diger" else province_id(str(r[0]))
                sums = {}
                continue
            if province is None or header is None:
                continue
            if fold(str(r[1] or "")) == "toplam":
                for i, sector in enumerate(header):
                    if sector:
                        close(
                            sums.get(sector, 0.0),
                            float(r[i] or 0),
                            f"doğalgaz {province} {sector}",
                        )
                        out.append(
                            row(
                                province, 2025, "gas_sector=" + sector, float(r[i] or 0)
                            )
                        )
                close(
                    sum(sums.values()),
                    float(r[9] or 0),
                    f"doğalgaz {province} genel toplam",
                )
                province = None
                continue
            for i, sector in enumerate(header):
                if sector and isinstance(r[i], (int, float)):
                    sums[sector] = sums.get(sector, 0.0) + r[i]
        if len({o["area_id"] for o in out}) != 81:
            raise ValueError(f"doğalgaz: {len({o['area_id'] for o in out})} il")
        return fact(out, self.indicator_id, "m3", "2026-05")


class EpdkGasSubscribers(Epdk):
    """Tablo-8: residential subscribers and eligible consumers by province, end of 2025."""

    indicator_id = "epdk_natural_gas_subscribers"

    def parse(self, raw: Path) -> pl.DataFrame:
        rows = sheet(GAS, "Tablo 8")
        provinces: dict[str, list[float]] = {}
        companies: dict[str, list[float]] = {}
        current = None
        grand = None
        for r in rows[3:]:
            if not r[0]:
                continue
            name = str(r[0]).strip()
            if fold(name) == "geneltoplam":
                grand = r
                continue
            try:
                current = province_id(name)
                provinces[current] = [r[1] or 0, r[2] or 0]
                companies[current] = [0.0, 0.0]
            except KeyError:
                if current is None:
                    raise
                companies[current][0] += r[1] or 0
                companies[current][1] += r[2] or 0
        out = []
        for pid, (subs, eligible) in provinces.items():
            close(companies[pid][0], subs, f"doğalgaz abone {pid}")
            close(companies[pid][1], eligible, f"doğalgaz serbest tüketici {pid}")
            out += [
                row(pid, 2025, "gas_customer=subscriber", subs),
                row(pid, 2025, "gas_customer=eligible_consumer", eligible),
            ]
        close(sum(v[0] for v in provinces.values()), grand[1], "doğalgaz abone Türkiye")
        return fact(out, self.indicator_id, "subscriber", "2026-05")


# endregion

# region Fuel and LPG


class EpdkFuelSales(Epdk):
    """Tablo 17: domestic sales of petroleum products by province and product (tonnes), 2025."""

    indicator_id = "epdk_fuel_sales"

    def parse(self, raw: Path) -> pl.DataFrame:
        rows = sheet(PETROL, "Tablo 17")
        header = [PETROL_PRODUCTS.get(fold(str(c or ""))) for c in rows[3]]
        total_col = [fold(str(c or "")) for c in rows[3]].index("toplamton")
        province = None
        out = []
        national = 0.0
        for r in rows[4:]:
            if r[0]:
                province = province_id(str(r[0]))
            label = fold(str(r[1] or ""))
            if label == "iltoplam":
                parts = {p: float(r[i] or 0) for i, p in enumerate(header) if p}
                close(sum(parts.values()), float(r[total_col]), f"akaryakıt {province}")
                national += float(r[total_col])
                out += [
                    row(province, 2025, "fuel_product=" + p, v)
                    for p, v in parts.items()
                ]
            elif label == "toplam":
                close(national, float(r[total_col]), "akaryakıt Türkiye")
        if len({o["area_id"] for o in out}) != 81:
            raise ValueError("akaryakıt: il sayısı 81 değil")
        return fact(out, self.indicator_id, "tonne", "2026-05")


class EpdkLpgSales(Epdk):
    """Tablo 1: LPG sales by province and product (cylinder, bulk, autogas; tonnes), 2025."""

    indicator_id = "epdk_lpg_sales"

    def parse(self, raw: Path) -> pl.DataFrame:
        rows = sheet(LPG, "Tablo 1")
        header = rows[2]
        cols = {
            LPG_PRODUCTS[fold(str(c))]: i
            for i, c in enumerate(header)
            if c and fold(str(c)) in LPG_PRODUCTS
        }
        total_col = [fold(str(c or "")) for c in header].index("toplam")
        out = []
        national = 0.0
        for r in rows[4:]:
            if not r[1]:
                continue
            if fold(str(r[1])) == "toplam":
                close(national, r[total_col], "LPG Türkiye")
                continue
            pid = province_id(str(r[1]))
            close(sum(r[i] for i in cols.values()), r[total_col], f"LPG {pid}")
            national += r[total_col]
            out += [row(pid, 2025, "lpg_product=" + p, r[i]) for p, i in cols.items()]
        if len({o["area_id"] for o in out}) != 81:
            raise ValueError("LPG: il sayısı 81 değil")
        return fact(out, self.indicator_id, "tonne", "2026-05")


# endregion

EPDK_ADAPTERS = {
    "epdk_electricity_consumption": EpdkElectricityConsumption,
    "epdk_electricity_consumers": EpdkElectricityConsumers,
    "epdk_natural_gas_sales": EpdkGasSales,
    "epdk_natural_gas_subscribers": EpdkGasSubscribers,
    "epdk_fuel_sales": EpdkFuelSales,
    "epdk_lpg_sales": EpdkLpgSales,
}
