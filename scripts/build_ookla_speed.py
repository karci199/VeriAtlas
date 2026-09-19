r"""Measured mobile internet speed per district, from Ookla's open tile data.

Ookla publishes every quarter's Speedtest results as ~600 m tiles: the average download,
upload and latency of the tests taken inside each tile, with the test and device counts
behind them. The files are open parquet on S3, no key, already in the raw store:

    C:\veri-ham\ookla\<quarter>_mobile.parquet

This is the other half of a question the store could only answer from one side. BTK
reports the speed subscribers are *sold*; this is the speed their phones *measured*.

What the script does, and the two places it could silently lie:

* **The tile's point is placed in a district polygon** (`public/geo/districts/*.geojson`,
  the same boundaries the atlas draws), never matched by name. A tile carries no place
  name at all, so there is nothing to mis-spell — but tiles outside every polygon are
  dropped, and they must be, because the file is global: a bounding box around Türkiye
  still catches Tbilisi, Yerevan and Batumi, which is most of what falls outside.
* **The average is weighted by tests, not by tiles.** A tile with one test and a tile with
  four hundred are one row each; averaging the rows lets an empty hillside outvote a city
  centre. Both the weighted mean and the test count are written out, so a reader can see
  how thin a district's number is.

A district with no tile gets no row rather than a zero — 43 of 973 in 2024Q4, all of them
sparsely populated. That is a real absence of measurement, not a measurement of zero.

**These are the people who ran a speed test**, not a sample of the country: they skew to
people who suspect their connection is bad, and to places with more phones. The level of
a district's number carries that bias; the comparison between districts, and between the
same district in two quarters, is what it is good for.

Run:  uv run python scripts/build_ookla_speed.py
Out:  C:\veri-ham\ookla\hiz_ilce.csv
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, "src")

from veriatlas.config import RAW

#: Quarter → the raw file holding it. Mobile only: Ookla publishes a fixed-broadband set
#: in the same shape, and it is not in the raw store yet.
QUARTERS = {
    "2022-Q4": "2022q4_mobile.parquet",
    "2024-Q4": "2024q4_mobile.parquet",
}
#: A box around Türkiye, to keep the global file out of memory. It is a cheap first cut,
#: not the test: the polygons below decide what counts as inside.
BOX = (25.5, 45.1, 35.6, 42.6)
DISTRICTS = Path("public/geo/districts")
OUT = RAW / "ookla" / "hiz_ilce.csv"


def main() -> None:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(
        "CREATE TABLE district (area_id VARCHAR, parent_id VARCHAR, g GEOMETRY)"
    )
    for path in sorted(glob.glob(str(DISTRICTS / "*.geojson"))):
        con.execute(
            "INSERT INTO district SELECT area_id, parent_id, geom FROM ST_Read(?)",
            [path.replace("\\", "/")],
        )
    total = con.execute("SELECT count(*) FROM district").fetchone()[0]
    if total != 973:
        raise SystemExit(f"ilce poligonu 973 olmali, {total} bulundu")

    rows = []
    for period, name in QUARTERS.items():
        source = (RAW / "ookla" / name).as_posix()
        con.execute(
            """CREATE OR REPLACE TABLE tile AS
               SELECT tile_x AS lon, tile_y AS lat, avg_d_kbps, avg_u_kbps, avg_lat_ms,
                      tests, devices
               FROM read_parquet(?)
               WHERE tile_x BETWEEN ? AND ? AND tile_y BETWEEN ? AND ?""",
            [source, *BOX],
        )
        placed = con.execute(
            """CREATE OR REPLACE TABLE placed AS
               SELECT d.area_id, d.parent_id, t.*
               FROM tile t JOIN district d ON ST_Contains(d.g, ST_Point(t.lon, t.lat))"""
        )
        del placed
        for level, key in (("district", "area_id"), ("province", "parent_id")):
            # Provinces are summed from the tiles, not from the districts: a tile on a
            # coastline can sit inside the province and outside every district polygon,
            # and dropping it twice would make the province quietly smaller than its
            # own districts.
            for row in con.execute(
                f"""SELECT {key} AS area_id,
                       round(sum(avg_d_kbps * tests) / sum(tests) / 1000, 2) AS download,
                       round(sum(avg_u_kbps * tests) / sum(tests) / 1000, 2) AS upload,
                       round(sum(avg_lat_ms * tests) / sum(tests), 1) AS latency,
                       sum(tests) AS tests, sum(devices) AS devices, count(*) AS tiles
                    FROM placed GROUP BY 1"""
            ).fetchall():
                rows.append((period, level, *row))
        print(period, con.execute("SELECT count(*), sum(tests) FROM placed").fetchone())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        handle.write(
            "period,area_level,area_id,download,upload,latency,tests,devices,tiles\n"
        )
        for row in rows:
            handle.write(",".join(str(value) for value in row) + "\n")
    print(OUT, len(rows), "satır")


if __name__ == "__main__":
    main()
