"""Registered vehicles by type — TÜİK SDMX data browser, country and province, yearly.

MEDAS never gave this: its "Motorlu Kara Taşıt Sayısı" by type comes back as the year's
registrations and deregistrations (a flow), and only the fuel and age breakdowns are the
stock. The stock by type is the SDMX flow `DF_MOTORLU_KARA_TASIT_ILLER_V3`: 81 provinces
and Türkiye, eight vehicle types, monthly from 2005-01. Pulled 2026-09-26 with

    POST https://databrowser2.tuik.gov.tr/api/core/nodes/1/datasets/TR,<flow>,1.0/data
    body []  → JSON-stat

No session is needed. Only December is kept: the stock at year end, the same moment as
`vehicles_by_fuel` (Türkiye 2025: 33,612,650 in both). The flow also carries a percent
unit (`PT`, each type's share); it is derivable and not stored.

Provinces come as NUTS-3 codes with Turkish names; they are matched by name, and a name
the area registry does not know stops the load.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl

from ..config import DATA, RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "tuik_sdmx"
FLOW = "DF_MOTORLU_KARA_TASIT_ILLER_V3"
URL = "https://databrowser2.tuik.gov.tr/api/core/nodes/1/datasets/TR,{},1.0/data"

TYPES = {
    "1": "car",
    "2": "minibus",
    "3": "bus",
    "4": "pickup",
    "5": "truck",
    "6": "motorcycle",
    "7": "special_purpose",
    "9": "tractor",
}
TOTAL = "_T"


def read_jsonstat(path: Path) -> pl.DataFrame:
    """A JSON-stat dataset to one row per filled cell, every dimension as a code column."""
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = data["id"]
    codes = []
    for dim in ids:
        index = data["dimension"][dim]["category"]["index"]
        codes.append(
            sorted(index, key=index.get) if isinstance(index, dict) else list(index)
        )
    strides = [1] * len(ids)
    for i in range(len(ids) - 2, -1, -1):
        strides[i] = strides[i + 1] * len(codes[i + 1])
    values = data["value"]
    cells = values.items() if isinstance(values, dict) else enumerate(values)
    rows = []
    for pos, value in cells:
        if value is None or value == "":
            continue
        pos = int(pos)
        row = {
            dim: codes[i][(pos // strides[i]) % len(codes[i])]
            for i, dim in enumerate(ids)
        }
        row["value"] = float(value)
        rows.append(row)
    labels = data["dimension"]["REF_AREA"]["category"]["label"]
    return pl.DataFrame(rows).with_columns(
        pl.col("REF_AREA").replace_strict(labels).alias("area_name")
    )


def province_ids() -> dict[str, str]:
    areas = pl.read_csv(DATA / "areas_tr.csv").filter(
        pl.col("area_level") == "province"
    )
    return dict(zip(areas["name_tr"], areas["area_id"], strict=True))


class TuikVehicleStock:
    source_id = "tuik_veri_portali"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 26)
    indicator_id = "vehicles_by_type"

    def fetch(self) -> Path:
        path = DOWNLOADS / (FLOW + ".json")
        if not path.exists():
            import httpx

            response = httpx.post(
                URL.format(FLOW),
                content="[]",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Origin": "https://databrowser2.tuik.gov.tr",
                    "Referer": "https://databrowser2.tuik.gov.tr/",
                    "User-Agent": "Mozilla/5.0",
                },
                timeout=180,
            )
            response.raise_for_status()
            DOWNLOADS.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
        return path

    def parse(self, raw: Path) -> pl.DataFrame:
        cells = read_jsonstat(raw).filter(
            (pl.col("UNIT_MEASURE") == "PN")
            & pl.col("TIME_PERIOD").str.ends_with("-12")
        )
        unknown = set(cells["ARAC_TUR"]) - set(TYPES) - {TOTAL}
        if unknown:
            raise KeyError(
                "tasit stoku: taninmayan tur kodu: " + ", ".join(sorted(unknown))
            )
        ids = province_ids()
        names = set(cells.filter(pl.col("REF_AREA") != "TR")["area_name"])
        if names - set(ids):
            raise KeyError(
                "tasit stoku: taninmayan il: " + ", ".join(sorted(names - set(ids)))
            )
        if len(names) != 81:
            raise ValueError(f"tasit stoku: {len(names)} il geldi, 81 bekleniyordu")

        # The total is kept only to prove the types add up; the stored rows are the types.
        types = cells.filter(pl.col("ARAC_TUR") != TOTAL)
        sums = types.group_by("REF_AREA", "TIME_PERIOD").agg(pl.col("value").sum())
        check = cells.filter(pl.col("ARAC_TUR") == TOTAL).join(
            sums, on=["REF_AREA", "TIME_PERIOD"], suffix="_types"
        )
        off = check.filter((pl.col("value") - pl.col("value_types")).abs() > 0.5)
        if not off.is_empty():
            raise ValueError(
                f"tasit stoku: {off.height} alan-yilda turler toplami tutmuyor"
            )

        frame = types.with_columns(
            pl.when(pl.col("REF_AREA") == "TR")
            .then(pl.lit("TR"))
            .otherwise(pl.col("area_name").replace_strict(ids, default=None))
            .alias("area_id"),
            pl.when(pl.col("REF_AREA") == "TR")
            .then(pl.lit("country"))
            .otherwise(pl.lit("province"))
            .alias("area_level"),
            pl.date(pl.col("TIME_PERIOD").str.slice(0, 4).cast(pl.Int32), 1, 1).alias(
                "period_start"
            ),
            pl.col("ARAC_TUR")
            .replace_strict(
                {k: format_dims({"vehicle_type": v}) for k, v in TYPES.items()}
            )
            .alias("dims"),
        )
        if frame.select("area_id", "period_start", "dims").is_duplicated().any():
            raise ValueError("tasit stoku: ayni alan-yil-tur iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
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
