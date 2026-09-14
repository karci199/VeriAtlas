"""Banks Association of Türkiye: deposits, loans and banking infrastructure by province.

Downloaded by `scripts/fetch_tbb_provinces.py` into `raw/tbb/`. Annual, 1988 onwards for
money, later for counts (employees 2007, ATM/POS/accounts 2010). Amounts are in today's
lira throughout: the 2005 redenomination is already applied at source — the national
savings total runs 62.5 bn (2004) → 88.0 bn (2005) with no thousand-fold step.

Provinces only. The source's regions are its own grouping of provinces and are summed on
the way to the screen like every other region (K15); "Kıbrıs", "Yabancı Ülkeler" and
"İller Bankası" belong to no province and are left out, which is why the province sum of
interbank deposits is 81% of the source's grand total.

Areas are matched by plate number, and the name is checked against ours so that a
renumbered or misspelt row fails rather than lands on a neighbour.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "tbb"

#: TBB measure key → (indicator id, dimension, dimension value)
MEASURES = {
    1178: ("bank_deposits", "deposit_type", "savings"),
    1180: ("bank_deposits", "deposit_type", "certificate"),
    1181: ("bank_deposits", "deposit_type", "public"),
    1182: ("bank_deposits", "deposit_type", "commercial"),
    1183: ("bank_deposits", "deposit_type", "interbank"),
    1184: ("bank_deposits", "deposit_type", "foreign_currency"),
    1356: ("bank_deposits", "deposit_type", "other"),
    4152: ("bank_deposits", "deposit_type", "gold"),
    15178: ("bank_deposit_accounts", "deposit_type", "savings"),
    15180: ("bank_deposit_accounts", "deposit_type", "certificate"),
    15181: ("bank_deposit_accounts", "deposit_type", "public"),
    15182: ("bank_deposit_accounts", "deposit_type", "commercial"),
    15183: ("bank_deposit_accounts", "deposit_type", "interbank"),
    15184: ("bank_deposit_accounts", "deposit_type", "foreign_currency"),
    15356: ("bank_deposit_accounts", "deposit_type", "other"),
    18152: ("bank_deposit_accounts", "deposit_type", "gold"),
    1260: ("bank_loans", "loan_type", "general"),
    1273: ("bank_loans", "loan_type", "agriculture"),
    1275: ("bank_loans", "loan_type", "real_estate"),
    1276: ("bank_loans", "loan_type", "professional"),
    1277: ("bank_loans", "loan_type", "maritime"),
    1278: ("bank_loans", "loan_type", "tourism"),
    1279: ("bank_loans", "loan_type", "other_specialised"),
    4978: ("bank_employees", None, None),
    11978: ("bank_atms", None, None),
    12978: ("bank_pos_terminals", None, None),
    13978: ("bank_merchants", None, None),
}

#: A key the values carry but the measure list does not name: a handful of rows scattered
#: over the years, small counts. Unnamed, so it cannot be stored as anything.
UNNAMED = {1}

#: TBB spelling → ours, where they differ.
NAMES = {"Nevsehir": "Nevşehir", "İçel": "Mersin"}


class TbbProvinces:
    source_id = "tbb"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 14)
    indicator_id = ""

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        areas = json.loads((raw / "areas.json").read_text(encoding="utf-8"))
        measures = json.loads((raw / "measures.json").read_text(encoding="utf-8"))
        values = json.loads((raw / "values.json").read_text(encoding="utf-8"))

        named = {m["PARAMETRE_UK"] for m in measures}
        if named != set(MEASURES):
            raise KeyError(
                "TBB olcu listesi degisti: " + str(sorted(named ^ set(MEASURES)))
            )
        ours = {
            row["area_id"]: row["name_tr"]
            for row in load_areas()
            .filter(pl.col("area_level") == "province")
            .to_dicts()
        }
        province: dict[int, str] = {}
        for area in areas:
            if area["ISBOLGE"]:
                continue
            area_id = f"TR-{area['PLAKA'][0]:02d}"
            name = NAMES.get(area["TR_ADI"], area["TR_ADI"])
            if ours.get(area_id) != name:
                raise KeyError(f"TBB ili eslesmiyor: {area['TR_ADI']} -> {area_id}")
            province[area["KEY"]] = area_id
        if len(province) != 81:
            raise ValueError(f"TBB il sayisi {len(province)}")

        records: list[dict] = []
        unknown = set()
        for row in values:
            key = row["PARAMETRE_UK"]
            if key in UNNAMED:
                continue
            if key not in MEASURES:
                unknown.add(key)
                continue
            indicator_id, dim, value = MEASURES[key]
            if indicator_id != self.indicator_id or row["IL_BOLGE_KEY"] not in province:
                continue
            records.append(
                {
                    "area_id": province[row["IL_BOLGE_KEY"]],
                    "period_start": dt.date(row["YIL"], 1, 1),
                    "dims": format_dims({dim: value}) if dim else "",
                    "value": float(row["TOPLAM"]),
                }
            )
        if unknown:
            raise KeyError("tanimsiz TBB olcu anahtari: " + str(sorted(unknown)))
        frame = pl.DataFrame(records)
        if frame.select("area_id", "period_start", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni il-yil-kirilim iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
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


TBB_ADAPTERS = {
    "tbb_" + ident: type(
        "Tbb" + "".join(p.title() for p in ident.split("_")),
        (TbbProvinces,),
        {"indicator_id": ident},
    )
    for ident in dict.fromkeys(spec[0] for spec in MEASURES.values())
}
