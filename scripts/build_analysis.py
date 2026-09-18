"""Make the warehouse answer questions directly: elections, labels, areas and ready views.

`load.py` writes one table, `fact`. That is enough to store data and too little to ask it
anything quickly: indicator names live in the TOML dictionary, area names and parents in
CSV registries, and elections are not in the warehouse at all (they are JSON files built
for the map). Every analysis started by re-joining those by hand.

This adds, next to `fact` and without touching it:

- `indicator`  id, Turkish label, topic, unit, decimals, frequency, dims
- `area`       every area with name, level, province and district above it
- `election`   one row per area x election x choice (candidate, party, yes/no), district
               and neighbourhood level, with registered / voted / valid and the share
- views        `v_fact` (fact with names), `v_province_year`, `v_district_year`,
               `v_latest`, `v_election_turnout`, `v_election_winner`

Election rows copied onto a district that did not exist yet (the old "Merkez" drawn on its
successors) are kept out: analysis must count each vote once.

Run after load.py:  uv run python scripts/build_analysis.py
"""

import csv
import json
import re
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC, WAREHOUSE
from veriatlas.indicators import load

DATA = Path("src/veriatlas/data")
TILES = PUBLIC / "tiles"


def indicator_rows() -> list[tuple]:
    return [
        (
            i.indicator_id,
            i.label_tr,
            i.topic.topic_id,
            i.topic.label_tr,
            i.unit.unit_id,
            i.unit.label_tr,
            i.unit.decimals,
            i.frequency,
            ",".join(i.dims),
        )
        for i in load().indicators.values()
    ]


def area_rows() -> list[tuple]:
    rows: dict[str, tuple] = {}
    for name in (
        "areas_tr.csv",
        "areas_tr_districts.csv",
        "areas_tr_neighbourhoods.csv",
        "areas_tr_villages.csv",
    ):
        path = DATA / name
        if not path.exists():
            continue
        for r in csv.DictReader(path.open(encoding="utf-8")):
            area = r["area_id"]
            parts = area.split("-")
            province = "-".join(parts[:2]) if len(parts) >= 2 else None
            district = "-".join(parts[:3]) if len(parts) >= 3 else None
            rows[area] = (area, r["area_level"], r["name_tr"], province, district)
    return list(rows.values())


def election_kind(key: str) -> tuple[str, int]:
    year = int(re.search(r"(\d{4})", key).group(1))
    if key.startswith("yerel_"):
        return key.rsplit("_", 1)[0], year
    return re.match(r"[a-z]+", key).group(0), year


def election_parquet(con: duckdb.DuckDBPyConnection) -> int:
    """Stream every election file into one parquet, then into the table."""
    votes = [
        v["anahtar"] for v in json.loads((TILES / "secimler.json").read_text("utf-8"))
    ]
    # Cached next to the warehouse: writing it takes minutes, loading it seconds, and a
    # failed SQL step should not cost the whole pass again.
    out = WAREHOUSE.parent / "election-cache.csv"
    newest = max(p.stat().st_mtime for p in TILES.glob("secim-*.json"))
    count = 0
    if out.exists() and out.stat().st_mtime > newest:
        print("secim onbellegi kullaniliyor:", out)
        votes = []
    with (
        open(out.with_suffix(".tmp"), "w", encoding="utf-8", newline="")
        if votes
        else open(__import__("os").devnull, "w")
    ) as handle:
        writer = csv.writer(handle)
        for vote in votes:
            kind, year = election_kind(vote)
            files = [(TILES / f"secim-{vote}-ilce.json", "district")]
            files += [
                (p, "neighbourhood")
                for p in sorted(TILES.glob(f"secim-{vote}-mahalle-TR-*.json"))
            ]
            for path, level in files:
                for key, row in json.loads(path.read_text("utf-8")).items():
                    if row.get("eski"):
                        continue
                    # An unmatched settlement is keyed `district~name`: kept, no area id.
                    area = None if "~" in key else key
                    for choice, n in (row.get("v") or {}).items():
                        writer.writerow(
                            [
                                vote,
                                kind,
                                year,
                                level,
                                area,
                                key.split("~")[0][:9],
                                row.get("ad", ""),
                                row.get("k", 0),
                                row.get("o", 0),
                                row.get("g", 0),
                                choice,
                                n,
                            ]
                        )
                        count += 1
    if votes:
        out.with_suffix(".tmp").replace(out)
    con.execute("drop table if exists election")
    con.execute(
        """
        create table election as
        select column00 as election, column01 as kind, column02::int as year,
               column03 as area_level, column04 as area_id, column05 as province_or_district,
               column06 as name, column07::bigint as registered, column08::bigint as voted,
               column09::bigint as valid, column10 as choice, column11::bigint as votes,
               case when column09::bigint > 0 then column11::double / column09::double end as share
        from read_csv(?, header = false, all_varchar = true)
        """,
        [str(out)],
    )
    return count


VIEWS = """
create or replace view v_fact as
select f.indicator_id, i.label_tr as indicator, i.topic_label as topic, f.area_id,
       a.name_tr as area, f.area_level, a.province_id, p.name_tr as province,
       year(f.period_start) as year, f.period_start, f.dims, f.value, i.unit_label as unit,
       f.source_id
from fact f
left join indicator i using (indicator_id)
left join area a using (area_id)
left join area p on p.area_id = a.province_id;

-- One number per province and year: no breakdown.
create or replace view v_province_year as
select * from v_fact where area_level = 'province' and dims = '';

create or replace view v_district_year as
select * from v_fact where area_level = 'district' and dims = '';

-- The newest year of each indicator at each level, no breakdown.
create or replace view v_latest as
select * from v_fact f
where dims = '' and year = (select max(year(period_start)) from fact g
                            where g.indicator_id = f.indicator_id
                              and g.area_level = f.area_level);

create or replace view v_election_turnout as
select distinct election, kind, year, area_level, area_id, name, registered, voted, valid,
       case when registered > 0 then voted::double / registered end as turnout
from election;

create or replace view v_election_winner as
select election, kind, year, area_level, area_id, name, choice as winner, votes, share
from election
qualify row_number() over (partition by election, area_level, area_id, name
                           order by votes desc) = 1;
"""


def main() -> None:
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("drop table if exists indicator")
    con.execute(
        "create table indicator (indicator_id varchar, label_tr varchar, topic varchar,"
        " topic_label varchar, unit varchar, unit_label varchar, decimals int,"
        " frequency varchar, dims varchar)"
    )
    con.executemany(
        "insert into indicator values (?,?,?,?,?,?,?,?,?)", indicator_rows()
    )
    con.execute("drop table if exists area")
    con.execute(
        "create table area (area_id varchar, area_level varchar, name_tr varchar,"
        " province_id varchar, district_id varchar)"
    )
    con.executemany("insert into area values (?,?,?,?,?)", area_rows())
    n = election_parquet(con)
    con.execute(VIEWS)
    for table in ("fact", "indicator", "area", "election"):
        print(
            f"{table:10} {con.execute(f'select count(*) from {table}').fetchone()[0]:>12,}"
        )
    print("secim satiri yazildi:", f"{n:,}")
    con.close()


if __name__ == "__main__":
    main()
