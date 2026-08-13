"""Run adapters and put their rows in the warehouse.

    uv run python scripts/load.py            # every adapter
    uv run python scripts/load.py tuik_tfr   # one of them

Replaces the earlier one-off `load_tfr.py`: fetching and parsing now live in the
adapter, and this script only orchestrates.
"""

import sys

import duckdb
import polars as pl

sys.path.insert(0, "src")

from veriatlas.adapters import ADAPTERS, ingest
from veriatlas.config import PUBLIC, WAREHOUSE, ensure_dirs


def main() -> None:
    ensure_dirs()
    wanted = sys.argv[1:] or list(ADAPTERS)

    unknown = [name for name in wanted if name not in ADAPTERS]
    if unknown:
        raise SystemExit("bilinmeyen adaptör: " + ", ".join(unknown))

    frames = []
    for name in wanted:
        frame, manifest = ingest(ADAPTERS[name]())
        frames.append(frame)
        print(
            f"{name:12} {manifest.rows:6} satır  "
            f"{manifest.areas} alan × {manifest.periods} dönem  "
            f"sürüm {manifest.vintage}  sağlama {manifest.checksum}"
        )

    fact = pl.concat(frames)
    target = PUBLIC / "fact.parquet"
    fact.write_parquet(target)

    con = duckdb.connect(WAREHOUSE)
    con.execute(
        "create or replace table fact as select * from read_parquet(?)", [str(target)]
    )
    con.close()

    print("parquet :", target)
    print("depo    :", WAREHOUSE)


if __name__ == "__main__":
    main()
