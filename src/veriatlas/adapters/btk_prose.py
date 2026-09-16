r"""BTK quarterly market reports: figures that only the prose carries.

Some series are drawn as charts whose labels are part of the image (every report from about
2017), so they cannot be read from the text layer — but the sentence introducing the chart
states the same quarter's figures. This adapter reads those sentences from
`C:\veri-ham\btk\pdf\text\<report>.json` (see `scripts/fetch_btk_pdfs.py`).

* mobile operators' share of subscriptions (Şekil "Abone Sayısına Göre Pazar Payları"),
  2013-2 … 2026-1: the three shares must add up to 100 ± 0.5, which is what makes a
  misread sentence visible;
* the operators' postpaid share of subscriptions, from the sentence above the prepaid /
  postpaid chart (2011-4 … 2026-1; 2021-1, whose sentence the magazine layout breaks, was
  read off the chart image instead, see `scripts/btk_churn_dataset.py`);
* mobile number portability: the quarter's successful ports and the cumulative total since
  the service started, and the cumulative total for fixed lines (a separate sentence, the
  service started in September 2009).

A report states its own quarter only, so each quarter comes from one report and there is no
cross-check between reports; the ones whose sentence does not parse are simply missing.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..config import RAW

TEXT = RAW / "btk" / "pdf" / "text"
OPERATORS = {
    "turkcell": r"Turkcell",
    "vodafone": r"Vodafone",
    "tt_mobil": r"(?:TT\s*Mobil|Avea)",
}
SUFFIX = r"[’'](?:in|ın|un|ün|nin|nın|n)?\s*(?:ise\s*)?"
PORTS = re.compile(r"numara taşıma sayısı[^.]{0,220}?([\d.]{7,})\s*olarak gerçekleşmiş")
# the cumulative sentence is printed twice: once for mobile, once for fixed lines
PORTS_TOTAL = re.compile(r"toplam\s+([\d.]{7,})\s+adet numara taşıma işlemi")
PORTS_TOTAL_FIXED = re.compile(
    r"Sabit hatlarda numara taşınabilirliği[^.]{0,220}?toplam\s+([\d.]{7,})\s+adet numara taşıma"
)
UNITS = {
    "btk_mobile_subscriber_share": "percent",
    "btk_mobile_postpaid_share": "percent",
    "btk_number_portability": "item",
    "btk_number_portability_total": "item",
    "btk_number_portability_fixed_total": "item",
}


def report_text(report: str) -> str:
    pages = json.loads((TEXT / f"{report}.json").read_text(encoding="utf-8"))
    return " ".join(pages[6:]).replace("\n", " ")


def reports() -> list[str]:
    names = sorted(p.stem for p in TEXT.glob("20??-Q?.json"))
    if len(names) < 65:
        raise FileNotFoundError(f"{TEXT}: {len(names)} rapor metni")
    return names


def quarter(report: str) -> dt.date:
    year, q = report.split("-Q")
    return dt.date(int(year), (int(q) - 1) * 3 + 1, 1)


def number(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def subscriber_shares(text: str) -> dict[str, float] | None:
    """The three shares of the sentence before the market-share chart, if they add to 100."""
    for anchor in ("abone sayısına göre", "abone sayılarına göre"):
        start = text.find(anchor)
        while start >= 0:
            segment = text[start : start + 520]
            found: dict[str, list[float]] = {}
            for name, pattern in OPERATORS.items():
                found[name] = [
                    number(m.group(1))
                    for m in re.finditer(
                        pattern + SUFFIX + r"%\s?(\d{1,2}(?:,\d+)?)", segment
                    )
                ]
            if all(found.values()):
                # a sentence may name an operator twice: take the reading that adds up
                for turkcell in found["turkcell"]:
                    for vodafone in found["vodafone"]:
                        for tt_mobil in found["tt_mobil"]:
                            if abs(turkcell + vodafone + tt_mobil - 100) <= 0.5:
                                return {
                                    "turkcell": turkcell,
                                    "vodafone": vodafone,
                                    "tt_mobil": tt_mobil,
                                }
            start = text.find(anchor, start + 1)
    return None


POSTPAID = re.compile(
    r"en fazla faturalı aboneye\s+(Turkcell|Vodafone|TT\s*Mobil|Avea)[’'][^%]{0,80}?"
    r"%\s?(\d{1,2}(?:,\d+)?)[’']?[^.]{0,40}?faturalı"
)
FOLLOWER = re.compile(
    r"%\s?(\d{1,2}(?:,\d+)?)\s*ile\s+(Turkcell|Vodafone|TT\s*Mobil|Avea)"
)


def operator_code(name: str) -> str:
    name = name.replace(" ", "")
    return "tt_mobil" if name in ("TTMobil", "Avea") else name.lower()


def postpaid_shares(text: str) -> dict[str, float] | None:
    """ "…en fazla faturalı aboneye Vodafone'un sahip olduğu ve Vodafone abonelerinin
    %88,4'ünün faturalı abonelerden oluştuğu … Vodafone'u %81 ile Turkcell ve %80,4 ile
    TT Mobil takip etmektedir." — the three operators' postpaid share."""
    leader = POSTPAID.search(text)
    if not leader:
        return None
    found = {operator_code(leader.group(1)): number(leader.group(2))}
    for share, name in FOLLOWER.findall(text[leader.end() : leader.end() + 320]):
        found[operator_code(name)] = number(share)
    return found if len(found) == 3 else None


def image_postpaid() -> dict[str, dict[str, float]]:
    """The quarters whose sentence does not parse, read off the chart image instead."""
    import importlib.util

    from ..config import ROOT

    spec = importlib.util.spec_from_file_location(
        "btk_churn", ROOT / "scripts" / "btk_churn_dataset.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.POSTPAID_SHARE


def load_all() -> dict[tuple[str, str, dt.date], float]:
    out: dict[tuple[str, str, dt.date], float] = {}
    for report in reports():
        text = report_text(report)
        start = quarter(report)
        shares = subscriber_shares(text)
        if shares:
            for name, share in shares.items():
                out[
                    ("btk_mobile_subscriber_share", f"telecom_operator={name}", start)
                ] = share
        postpaid = postpaid_shares(text) or image_postpaid().get(report)
        if postpaid:
            for name, share in postpaid.items():
                out[
                    ("btk_mobile_postpaid_share", f"telecom_operator={name}", start)
                ] = share
        ports = PORTS.search(text)
        if ports:
            out[("btk_number_portability", "", start)] = number(ports.group(1))
        if ports:  # the mobile total follows the quarter's figure
            total = PORTS_TOTAL.search(text, ports.end(), ports.end() + 260)
            if total:
                out[("btk_number_portability_total", "", start)] = number(
                    total.group(1)
                )
        fixed = PORTS_TOTAL_FIXED.search(text)
        if fixed:
            out[("btk_number_portability_fixed_total", "", start)] = number(
                fixed.group(1)
            )
    quarters = {start for _i, _d, start in out}
    if len(quarters) < 40:
        raise ValueError(f"BTK metin: {len(quarters)} çeyrek okundu")
    return out


_CACHE: dict[tuple[str, str, dt.date], float] = {}


class BtkProse:
    source_id = "btk"
    indicator_id = ""

    def fetch(self) -> Path:
        return TEXT

    def parse(self, raw: Path) -> pl.DataFrame:
        if not _CACHE:
            _CACHE.update(load_all())
        records = [
            {"period_start": start, "dims": dims, "value": v}
            for (indicator, dims, start), v in _CACHE.items()
            if indicator == self.indicator_id
        ]
        return pl.DataFrame(
            records, schema_overrides={"value": pl.Float64}
        ).with_columns(
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("quarterly").alias("frequency"),
            pl.lit(UNITS[self.indicator_id]).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit("2026-06").alias("vintage"),
            pl.lit("btk").alias("source_id"),
            pl.lit(dt.date(2026, 9, 16)).alias("retrieved_at"),
        )


BTK_PROSE_ADAPTERS = {
    indicator: type(f"BtkProse_{indicator}", (BtkProse,), {"indicator_id": indicator})
    for indicator in UNITS
}
