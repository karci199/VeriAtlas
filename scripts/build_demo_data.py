"""Small per-district series for the map demo, straight out of the fact table.

Three readings per district and year: population, the 0-14 share and the 65+ share. The
shares are computed from the age dimension rather than stored, because the fact table
keeps counts and the map wants a rate.

Writes public/tiles/ilce-veri.json — one object keyed by area id, small enough to sit in
the page without a database behind it.

Run:  uv run python scripts/build_demo_data.py
"""

import json
import pathlib

import polars as pl

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "tiles" / "ilce-veri.json"


def main() -> None:
    df = pl.read_parquet(ROOT / "public" / "fact.parquet")
    pop = df.filter(
        (pl.col("area_level") == "district") & (pl.col("indicator_id") == "population")
    ).with_columns(
        pl.col("period_start").dt.year().alias("yil"),
        pl.col("dims").str.extract(r"age=([^;]+)").alias("yas"),
    )

    def band_low(band: str) -> int:
        return int(band.split("-")[0].replace("+", ""))

    bands = sorted({b for b in pop["yas"].unique().to_list() if b}, key=band_low)
    young = [b for b in bands if band_low(b) < 15]
    old = [b for b in bands if band_low(b) >= 65]

    total = pop.group_by(["area_id", "yil"]).agg(pl.col("value").sum().alias("nufus"))
    y = (
        pop.filter(pl.col("yas").is_in(young))
        .group_by(["area_id", "yil"])
        .agg(pl.col("value").sum().alias("genc"))
    )
    o = (
        pop.filter(pl.col("yas").is_in(old))
        .group_by(["area_id", "yil"])
        .agg(pl.col("value").sum().alias("yasli"))
    )
    joined = total.join(y, on=["area_id", "yil"], how="left").join(
        o, on=["area_id", "yil"], how="left"
    )

    out: dict[str, dict[str, list]] = {}
    for row in joined.iter_rows(named=True):
        rec = out.setdefault(row["area_id"], {})
        rec[str(row["yil"])] = [
            int(row["nufus"]),
            round(100 * (row["genc"] or 0) / row["nufus"], 1),
            round(100 * (row["yasli"] or 0) / row["nufus"], 1),
        ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    years = sorted({y for rec in out.values() for y in rec})
    print(f"{len(out)} ilce · {years[0]}-{years[-1]} · {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
