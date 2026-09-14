"""Consumer prices and the dollar rate, from EVDS3 — the deflators for every lira series.

Downloaded by `scripts/fetch_evds_housing.py <group>` into `raw/evds/`:

    bie_tukfiy2003  CPI 2003=100, Türkiye, monthly 2003-
    bie_tuksehir2   CPI 2003=100 by İBBS-2 region, monthly 2003-2022 (archive)
    bie_tuksehir    CPI 1994=100 for 20 provinces, monthly 1995-2004 (archive); its seven
                    geographic regions are TÜİK's old grouping, not ours, and are left out
    bie_dkdovytl    CBRT USD buying rate, business days 1970-

The region series are named "1.Bölge İstanbul", "2.Bölge Tekirdağ, Edirne, Kırklareli":
the provinces listed are matched against our İBBS-2 membership, so the region code is
derived and checked, never assumed from the order.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import DATA, RAW
from ..indicators import get

DOWNLOADS = RAW / "evds"
REGION = re.compile(r"^\d+\.Bölge (.+?) \(Arşiv\)$")

#: Archive province codes that are not the capitalised province name.
PROVINCE_CODES = {"DBAKIR": "Diyarbakır", "GANTEP": "Gaziantep", "ICEL": "Mersin"}
#: The seven old geographic regions in the 1994-based table — not provinces.
OLD_REGIONS = {
    "AKDENIZ",
    "DANADOLU",
    "EGE",
    "GDANADOLU",
    "IANADOLU",
    "KARADENIZ",
    "MARMARA",
}

ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def skeleton(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.translate(ASCII).lower())


def nuts2_by_members() -> dict[frozenset[str], str]:
    """Set of member province names (ASCII skeleton) → İBBS-2 code."""
    table = pl.read_csv(DATA / "nuts_tr.csv")
    groups: dict[str, set[str]] = {}
    for row in table.to_dicts():
        groups.setdefault(row["nuts2_id"], set()).add(skeleton(row["province_name"]))
    return {frozenset(members): code for code, members in groups.items()}


def monthly(label: str) -> dt.date:
    year, month = label.split("-")
    return dt.date(int(year), int(month), 1)


def daily(label: str) -> dt.date:
    day, month, year = label.split("-")
    return dt.date(int(year), int(month), int(day))


class EvdsPrices:
    source_id = "cbrt_evds"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 14)
    indicator_id = ""
    group = ""

    def fetch(self) -> Path:
        return DOWNLOADS / (self.group + ".json")

    def areas(self, series: list[dict]) -> dict[str, tuple[str, str]]:
        """Series code → (area id, level) for the series this indicator keeps."""
        if self.group in ("bie_tukfiy2003", "bie_dkdovytl"):
            code = (
                "TP.GENENDEKS.T1"
                if self.group == "bie_tukfiy2003"
                else "TP.DK.USD.A.YTL"
            )
            return {code: ("TR", "country")}
        if self.group == "bie_tuksehir2":
            members = nuts2_by_members()
            out = {}
            for s in series:
                if s["SERIE_CODE"] == "TP.FG.TS01":
                    out[s["SERIE_CODE"]] = ("TR", "country")
                    continue
                found = REGION.match(s["SERIE_NAME"])
                names = (
                    frozenset(
                        skeleton(n.replace("Afyon", "Afyonkarahisar"))
                        for n in found.group(1).split(",")
                    )
                    if found
                    else None
                )
                if names not in members:
                    raise KeyError("bolge eslesmedi: " + s["SERIE_NAME"])
                out[s["SERIE_CODE"]] = (members[names], "nuts2")
            if len(set(out.values())) != 27:
                raise ValueError("26 bolge + Turkiye beklenirdi")
            return out
        # bie_tuksehir: provinces by name
        ids = {
            skeleton(row["name_tr"]): row["area_id"]
            for row in load_areas()
            .filter(pl.col("area_level") == "province")
            .to_dicts()
        }
        out = {}
        for s in series:
            suffix = s["SERIE_CODE"].rsplit(".", 1)[1]
            if suffix in OLD_REGIONS:
                continue
            if suffix == "TURKIYE":
                out[s["SERIE_CODE"]] = ("TR", "country")
                continue
            key = skeleton(PROVINCE_CODES.get(suffix, suffix))
            if key not in ids:
                raise KeyError("il eslesmedi: " + s["SERIE_CODE"])
            out[s["SERIE_CODE"]] = (ids[key], "province")
        return out

    def parse(self, raw: Path) -> pl.DataFrame:
        payload = json.loads(raw.read_text(encoding="utf-8"))
        indicator = get(self.indicator_id)
        to_date = daily if indicator.frequency == "daily" else monthly
        records = []
        for code, (area, level) in self.areas(payload["series"]).items():
            column = code.replace(".", "_")
            for item in payload["items"]:
                if item.get(column) in (None, ""):
                    continue
                records.append(
                    {
                        "area_id": area,
                        "area_level": level,
                        "period_start": to_date(item["Tarih"]),
                        "value": float(item[column]),
                    }
                )
        frame = pl.DataFrame(records)
        if frame.select("area_id", "period_start").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni alan-donem iki kez")
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit("").alias("dims"),
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


GROUPS = {
    "cpi_2003": "bie_tukfiy2003",
    "cpi_region_2003": "bie_tuksehir2",
    "cpi_province_1994": "bie_tuksehir",
    "usd_try_buying": "bie_dkdovytl",
}

EVDS_PRICE_ADAPTERS = {
    "evds_" + ident: type(
        "Evds" + "".join(p.title() for p in ident.split("_")),
        (EvdsPrices,),
        {"indicator_id": ident, "group": group},
    )
    for ident, group in GROUPS.items()
}
