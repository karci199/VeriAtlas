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
from veriatlas.adapters.tuik_vital import PAIRED
from veriatlas.config import PUBLIC, WAREHOUSE, ensure_dirs
from veriatlas.derived import (
    age_specific_death_rate,
    marriage_age_total,
    median_age_total,
    natural_increase,
)


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

    # After every adapter, because it reads across them: the median age of everyone is
    # computed from the population distribution, which TÜİK publishes, rather than from
    # the two published medians, which cannot be averaged. Only when the run holds both
    # indicators — loading one adapter alone must not write a half-derived answer.
    if {"population", "median_age"} <= set(fact["indicator_id"].unique()):
        totals = median_age_total(fact)
        if not totals.is_empty():
            fact = pl.concat([fact, totals])
            print(f"{'turetme':12} {len(totals):6} satır  ortanca yaş, toplam")

    # Same rule, the other cross-indicator row: only when the run holds both sides.
    if {"births", "deaths"} <= set(fact["indicator_id"].unique()):
        balance = natural_increase(fact)
        if not balance.is_empty():
            fact = pl.concat([fact, balance])
            print(f"{'turetme':12} {len(balance):6} satır  doğal nüfus artışı")

    # Deaths over the population of the same age and sex. Same rule as above and the
    # same reason: half of it — deaths with no denominator — is not a smaller answer, it
    # is no answer.
    if {"population", "deaths_by_age"} <= set(fact["indicator_id"].unique()):
        rates = age_specific_death_rate(fact)
        if not rates.is_empty():
            fact = pl.concat([fact, rates])
            print(f"{'turetme':12} {len(rates):6} satır  yaşa özgü ölüm hızı")

    # An indicator fed by two adapters is only whole when both ran. Loading one alone is a
    # legitimate thing to do while working, so this warns rather than refuses — but it
    # says so, because the result looks like a finished indicator with half its breakdown.
    for indicator_id, names in PAIRED.items():
        ran = [name for name in names if name in wanted]
        if ran and len(ran) < len(names):
            print(
                "UYARI:",
                indicator_id,
                "yarim yuklendi, eksik:",
                ", ".join(name for name in names if name not in ran),
            )

    if "mean_marriage_age" in set(fact["indicator_id"].unique()):
        both = marriage_age_total(fact)
        if not both.is_empty():
            fact = pl.concat([fact, both])
            print(f"{'turetme':12} {len(both):6} satır  ortalama evlenme yaşı, toplam")

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
