"""Yearly settlement series for one district's file page.

public/atlas/<district>.json (build_atlas_data.py) holds the 2024 Endeksa snapshot per
settlement, keyed by Endeksa id. TÜİK MEDAS gives every settlement a yearly 0-17 / 18+ ×
sex count from 2013, keyed by MEDAS code — a different id. This joins the two by folded
name within the district and writes public/atlas/<district>.children.json:

    {"years": [2013, ...], "units": [{"id": <atlas unit id>, "name", "urban",
        "series": {"2013": {"child": n, "adult": n, "male": n, "female": n}, ...}}],
     "totals": {"2013": {"urban": {"child", "adult"}, "rural": {...}}, ...},
     "vital": {"2014": {"births": n, "deaths": n}, ...}}   # TÜİK district counts

Settlements in MEDAS with no Endeksa counterpart (renamed, merged) are listed under
"unmatched" rather than dropped silently; their people still count in "totals".

Run:  uv run python scripts/build_district_children.py TR-16-006
"""

import json
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
ATLAS = PUBLIC / "atlas"

TR_LOWER = str.maketrans(
    "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ", "abcçdefgğhıijklmnoöprsştuüvyz"
)


def fold(name: str) -> str:
    name = name.split("/")[-1].translate(TR_LOWER).strip()
    for suffix in (" mah.", " mahallesi", " köyü", " köy"):
        name = name.removesuffix(suffix)
    return "".join(ch for ch in name if ch.isalnum())


def main(district: str) -> None:
    atlas = json.loads((ATLAS / f"{district}.json").read_text(encoding="utf-8"))
    frames = []
    for dataset in ("population-neighbourhood", "population-village"):
        df = pl.read_csv(PUBLIC / f"{dataset}.csv.gz", infer_schema_length=0)
        frames.append(df.filter(pl.col("area_id").str.starts_with(district + "-")))
    rows = pl.concat(frames).with_columns(
        pl.col("value").cast(pl.Int64), pl.col("year").cast(pl.Int32)
    )
    years = sorted(rows["year"].unique().to_list())

    by_name = {fold(u["name"]): u for u in atlas["units"]}
    units: dict[str, dict] = {}
    unmatched: list[str] = []
    for (medas_id, label), part in rows.group_by(
        ["area_id", "area"], maintain_order=True
    ):
        unit = by_name.get(fold(label))
        if unit is None:
            unmatched.append(label)
            continue
        series = {}
        for (year,), cell in part.group_by(["year"], maintain_order=True):
            child = cell.filter(pl.col("age") == "0-17")["value"].sum()
            adult = cell.filter(pl.col("age") == "18+")["value"].sum()
            male = cell.filter(pl.col("sex") == "male")["value"].sum()
            female = cell.filter(pl.col("sex") == "female")["value"].sum()
            series[str(year)] = {
                "child": child,
                "adult": adult,
                "male": male,
                "female": female,
            }
        entry = units.setdefault(
            unit["id"],
            {
                "id": unit["id"],
                "name": unit["name"],
                "urban": unit["urban"],
                "medas": [],
                "series": {},
            },
        )
        entry["medas"].append(medas_id)
        for (
            year,
            cell,
        ) in series.items():  # a settlement split in MEDAS sums into one atlas unit
            acc = entry["series"].setdefault(
                year, {"child": 0, "adult": 0, "male": 0, "female": 0}
            )
            for key, value in cell.items():
                acc[key] += value

    urban_names = {fold(u["name"]) for u in atlas["units"] if u["urban"]}
    totals = {}
    for (year,), part in rows.group_by(["year"], maintain_order=True):
        t = {"urban": {"child": 0, "adult": 0}, "rural": {"child": 0, "adult": 0}}
        for row in part.iter_rows(named=True):
            side = "urban" if fold(row["area"]) in urban_names else "rural"
            t[side]["child" if row["age"] == "0-17" else "adult"] += row["value"]
        totals[str(year)] = t

    vital: dict[str, dict] = {}
    for dataset, key in (("births-district", "births"), ("deaths-district", "deaths")):
        df = pl.read_csv(PUBLIC / f"{dataset}.csv.gz", infer_schema_length=0)
        df = df.filter(pl.col("area_id") == district).with_columns(
            pl.col("value").cast(pl.Int64)
        )
        for (year,), part in df.group_by(["year"]):
            vital.setdefault(str(year), {})[key] = part["value"].sum()

    out = {
        "district": district,
        "vital": vital,
        "years": years,
        "units": list(units.values()),
        "totals": totals,
        "unmatched": unmatched,
    }
    path = ATLAS / f"{district}.children.json"
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{len(units)} units matched, {len(unmatched)} unmatched: {unmatched}")
    print("yazildi:", path.name, round(path.stat().st_size / 1e3), "KB")


if __name__ == "__main__":
    main(sys.argv[1])
