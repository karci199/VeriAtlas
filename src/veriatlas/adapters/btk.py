"""BTK quarterly electronic-communications market reports, national series.

The figures were transcribed from the BTK "Türkiye Elektronik Haberleşme Sektörü Üç Aylık
Pazar Verileri" reports (PDFs 2009 … 2026-Q1) by the `scripts/btk_*_dataset.py` scripts,
first written on branch `claude/elektronik-haberlesme-datasets-2aee0f`: tables come from the
text layer, chart labels were read off rendered pages, and each quarter is taken from the
newest report that prints it. Those scripts write `raw/btk/*.csv`; the CSVs are kept in
`C:\\veri-ham\\btk`. The mobile ARPU figures live in the script itself and are read from it
here (nominal lira only; the real and currency versions need the macro file, not required
for the warehouse — EVDS has the deflators).

Not here: mobile subscribers by operator (its input CSV was lost with the worktree and has
to be read off the PDFs again).
"""

from __future__ import annotations

import csv
import datetime as dt
import importlib.util
from pathlib import Path
from typing import ClassVar

import polars as pl

from ..config import RAW, ROOT

FOLDER = RAW / "btk"


def period(text: str) -> tuple[dt.date, str]:
    """ "2024-3" -> (2024-07-01, quarterly); "2024" -> (2024-01-01, annual)."""
    if "-" in text:
        year, quarter = text.split("-")
        return dt.date(int(year), (int(quarter) - 1) * 3 + 1, 1), "quarterly"
    return dt.date(int(text), 1, 1), "annual"


def read(name: str) -> list[dict[str, str]]:
    with (FOLDER / name).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def value(text: str) -> float | None:
    return float(text) if text not in ("", None) else None


def frame(records: list[dict], indicator: str, unit: str) -> pl.DataFrame:
    return pl.DataFrame(records, schema_overrides={"value": pl.Float64}).with_columns(
        pl.lit("TR").alias("area_id"),
        pl.lit("country").alias("area_level"),
        pl.lit(indicator).alias("indicator_id"),
        pl.lit(unit).alias("unit"),
        pl.lit("measured").alias("quality_flag"),
        pl.lit("2026-06").alias("vintage"),
        pl.lit("btk").alias("source_id"),
        pl.lit(dt.date(2026, 9, 15)).alias("retrieved_at"),
    )


def rows(file: str, key: str, columns: dict[str, str], dim: str, scale: float = 1.0):
    out = []
    for r in read(file):
        start, frequency = period(r[key])
        for column, code in columns.items():
            v = value(r.get(column, ""))
            if v is None:
                continue
            out.append(
                {
                    "period_start": start,
                    "frequency": frequency,
                    "dims": f"{dim}={code}" if dim else "",
                    "value": v * scale,
                }
            )
    return out


class Btk:
    source_id = "btk"
    indicator_id = ""
    unit = ""

    def fetch(self) -> Path:
        return FOLDER

    def records(self) -> list[dict]:
        raise NotImplementedError

    def parse(self, raw: Path) -> pl.DataFrame:
        return frame(self.records(), self.indicator_id, self.unit)


class FixedBroadband(Btk):
    """Year-end internet subscribers by technology (Çizelge 3-1), 2008-2025 and 2026-1."""

    indicator_id = "btk_internet_subscribers"
    unit = "subscriber"
    COLUMNS: ClassVar[dict[str, str]] = {
        "xdsl": "xdsl",
        "kablo": "cable",
        "ftth": "ftth",
        "fttb": "fttb",
        "fiber": "fiber_combined",
        "kablosuz_sabit": "fixed_wireless",
        "diger": "other",
        "mobil_bilgisayar": "mobile_computer",
        "mobil_cep": "mobile_handset",
    }

    def records(self):
        out = rows("sabit_genisbant.csv", "donem", self.COLUMNS, "internet_technology")
        # From 2014 "fiber" is FTTH + FTTB printed beside its parts: kept only for 2010-2013,
        # when it is the one fibre line. Each row must then add up to the printed TOPLAM.
        split = {r["donem"] for r in read("sabit_genisbant.csv") if r["ftth"]}
        for r in read("sabit_genisbant.csv"):
            if (
                r["donem"] in split
                and abs(float(r["fiber"]) - float(r["ftth"]) - float(r["fttb"])) > 0.5
            ):
                raise ValueError(f"BTK genişbant {r['donem']}: fiber ≠ FTTH + FTTB")
        split_starts = {period(d)[0] for d in split}
        out = [
            o
            for o in out
            if not (
                o["dims"] == "internet_technology=fiber_combined"
                and o["period_start"] in split_starts
            )
        ]
        for r in read("sabit_genisbant.csv"):
            columns = [
                c for c in self.COLUMNS if not (c == "fiber" and r["donem"] in split)
            ]
            parts = sum(value(r[c]) or 0.0 for c in columns)
            if abs(parts - float(r["toplam"])) > 0.5:
                raise ValueError(
                    f"BTK genişbant {r['donem']}: parçalar {parts:,.0f}, toplam {r['toplam']}"
                )
        # Year-end rows are "YYYY-4": stored as the year (annual); 2026-1 stays quarterly.
        for o in out:
            if o["frequency"] == "quarterly" and o["period_start"].month == 10:
                o["period_start"] = dt.date(o["period_start"].year, 1, 1)
                o["frequency"] = "annual"
        return out


class FixedBroadbandRevenue(Btk):
    indicator_id = "btk_fixed_broadband_revenue"
    unit = "try"

    def records(self):
        return [
            {**p, "value": p["value"]}
            for p in rows("sabit_genisbant_gelir.csv", "donem", {"gelir_tl": "x"}, "")
        ]


class FixedVoice(Btk):
    """Fixed telephone lines by operator group and technology (Çizelge 2-1), quarterly."""

    indicator_id = "btk_fixed_voice_lines"
    unit = "subscriber"
    COLUMNS: ClassVar[dict[str, str]] = {
        "tt_pstn": "turk_telekom_pstn",
        "tt_isdn": "turk_telekom_isdn",
        "tt_ankesor": "turk_telekom_payphone",
        "sth_pstn": "alternative_pstn",
        "sth_isdn": "alternative_isdn",
        "sth_voip": "alternative_voip",
    }

    def records(self):
        return rows(
            "sabit_ses_teknoloji.csv", "donem", self.COLUMNS, "fixed_voice_line"
        )


class CallMinutes(Btk):
    indicator_id = "btk_call_minutes"
    unit = "minute"

    def records(self):
        return rows(
            "trafik_yillik.csv",
            "yil",
            {"mobil": "mobile", "sabit": "fixed"},
            "network",
            1e9,
        )


class TurkTelekomTraffic(Btk):
    indicator_id = "btk_turk_telekom_traffic"
    unit = "minute"

    def records(self):
        columns = {
            "sebeke_ici": "on_net",
            "mobil": "to_mobile",
            "sth": "to_alternative_fixed",
            "uluslararasi": "international",
            "rehberlik": "directory",
        }
        return rows("tt_trafik_dagilimi.csv", "donem", columns, "call_destination", 1e6)


class MobileTraffic(Btk):
    indicator_id = "btk_mobile_traffic_by_operator"
    unit = "minute"

    def records(self):
        columns = {
            "turkcell": "turkcell",
            "vodafone": "vodafone",
            "ttmobil": "turk_telekom",
        }
        return rows(
            "mobil_trafik_isletmeci.csv", "donem", columns, "mobile_operator", 1e9
        )


class M2M(Btk):
    indicator_id = "btk_m2m_subscribers"
    unit = "subscriber"

    def records(self):
        annual = rows("m2m_yillik.csv", "yil", {"m2m": "m2m"}, "")
        quarterly = rows("m2m_ceyreklik.csv", "donem", {"m2m_milyon": "m2m"}, "", 1e6)
        return annual + quarterly


class MobileArpu(Btk):
    """Mobile ARPU by operator, prepaid and postpaid, nominal lira per month, 2011-1 … 2026-1."""

    indicator_id = "btk_mobile_arpu"
    unit = "try_per_month"

    def records(self):
        spec = importlib.util.spec_from_file_location(
            "btk_arpu", ROOT / "scripts" / "btk_arpu_dataset.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        out = []
        for kind, table in (("prepaid", module.PREPAID), ("postpaid", module.POSTPAID)):
            for donem, *values in table:
                start, frequency = period(donem)
                for operator, tl in zip(
                    ("turkcell", "vodafone", "turk_telekom"), values[:-1], strict=True
                ):
                    out.append(
                        {
                            "period_start": start,
                            "frequency": frequency,
                            "dims": f"mobile_operator={operator};tariff_type={kind}",
                            "value": tl,
                        }
                    )
        return out


def quarterly_deflators() -> tuple[dict[dt.date, float], dict[dt.date, float]]:
    """Quarter start -> (mean USD/TRY buying rate, mean CPI 2003=100), from the EVDS rows
    already in the warehouse. A quarter needs all three CPI months."""
    import duckdb

    fact = str(ROOT / "public" / "fact.parquet")
    con = duckdb.connect()
    query = """
        select make_date(year(period_start), (quarter(period_start) - 1) * 3 + 1, 1) q,
               avg(value), count(distinct month(period_start))
        from read_parquet(?) where indicator_id = ? and dims = '' group by 1
    """
    usd = {q: v for q, v, _ in con.execute(query, [fact, "usd_try_buying"]).fetchall()}
    cpi = {
        q: v for q, v, n in con.execute(query, [fact, "cpi_2003"]).fetchall() if n == 3
    }
    return usd, cpi


class MobileArpuUsd(MobileArpu):
    """Nominal ARPU / quarterly mean CBRT USD buying rate (EVDS usd_try_buying)."""

    indicator_id = "btk_mobile_arpu_usd"
    unit = "usd_per_month"

    def records(self):
        usd, _ = quarterly_deflators()
        out = super().records()
        missing = {o["period_start"] for o in out} - set(usd)
        if missing:
            raise ValueError(f"BTK ARPU $: kur yok {sorted(missing)}")
        return [{**o, "value": o["value"] / usd[o["period_start"]]} for o in out]


class MobileArpuReal(MobileArpu):
    """Nominal ARPU in lira of the last quarter with full CPI (TÜİK CPI 2003=100 via EVDS)."""

    indicator_id = "btk_mobile_arpu_real"
    unit = "try_per_month"

    def records(self):
        _, cpi = quarterly_deflators()
        out = super().records()
        base = cpi[max(o["period_start"] for o in out)]
        missing = {o["period_start"] for o in out} - set(cpi)
        if missing:
            raise ValueError(f"BTK ARPU reel: TÜFE yok {sorted(missing)}")
        return [{**o, "value": o["value"] * base / cpi[o["period_start"]]} for o in out]


BTK_ADAPTERS = {
    cls.indicator_id: cls
    for cls in (
        FixedBroadband,
        FixedBroadbandRevenue,
        FixedVoice,
        CallMinutes,
        TurkTelekomTraffic,
        MobileTraffic,
        M2M,
        MobileArpu,
        MobileArpuUsd,
        MobileArpuReal,
    )
}
