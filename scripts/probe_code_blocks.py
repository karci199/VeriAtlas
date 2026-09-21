"""Can a neighbourhood's MEDAS code say whether it used to be a village?

In the metropolitan provinces law 6360 turned every village into a neighbourhood in 2014,
and the converted ones were given record numbers from a different range — Kalecik's own
neighbourhoods run 2135-2161, its ex-villages 178507-178579. The gap between the two is
176.346 wide, and it is the only trace of the conversion left in the data: `first_seen`
cannot help, because MEDAS backfills today's administrative structure over every year.

So the rule under test is: inside one district, sort the codes and cut at the largest
jump. Below the cut, neighbourhoods that were already neighbourhoods; above it, villages
in disguise.

This probe does not trust the rule — it scores it. TÜİK's own urban/rural classification
is already in the registry, and it was produced from population density, which is a
completely different measurement. If a rule read off record numbers agrees with a rule
read off satellite grids, neither is likely to be an artefact of the other.

Nothing is written. This is the check you run before letting a derived column exist.

Run:  uv run python scripts/probe_code_blocks.py
"""

from __future__ import annotations

import sys

import polars as pl

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC

DATA = PUBLIC.parent / "src" / "veriatlas" / "data"

#: A jump has to be big to mean anything. Consecutive numbering inside a town drifts by
#: ones and twos; the conversion blocks sit six digits away. Anything between is noise.
CUT = 1000


def population(level: str, year: int = 2025) -> pl.DataFrame:
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    return (
        fact.filter(
            (pl.col("indicator_id") == "population")
            & (pl.col("area_level") == level)
            & (pl.col("period_start").dt.year() == year)
        )
        .group_by("area_id")
        .agg(pl.col("value").sum().alias("nufus"))
    )


def blocks(frame: pl.DataFrame) -> pl.DataFrame:
    """Label each neighbourhood by which side of its district's largest jump it sits on."""
    ordered = frame.sort("parent_id", "medas_code")
    gapped = ordered.with_columns(
        (pl.col("medas_code") - pl.col("medas_code").shift(1).over("parent_id")).alias(
            "fark"
        )
    )
    biggest = (
        gapped.group_by("parent_id")
        .agg(pl.col("fark").max().alias("en_buyuk"))
        .with_columns(pl.col("en_buyuk").fill_null(0))
    )
    joined = gapped.join(biggest, on="parent_id", how="left")
    # The cut is the first row whose own gap is the district's largest: everything from
    # there on is the upper block. Cumulative max over the ordered rows does that without
    # a second pass.
    return joined.with_columns(
        pl.when(pl.col("en_buyuk") < CUT)
        .then(pl.lit("tek blok"))
        .otherwise(
            pl.when(
                ((pl.col("fark") == pl.col("en_buyuk")) & (pl.col("fark") >= CUT))
                .cast(pl.Int8)
                .cum_max()
                .over("parent_id")
                == 1
            )
            .then(pl.lit("donusen"))
            .otherwise(pl.lit("yerli"))
        )
        .alias("blok")
    )


def main() -> None:
    hoods = pl.read_csv(DATA / "areas_tr_neighbourhoods.csv")
    villages = pl.read_csv(DATA / "areas_tr_villages.csv").with_columns(
        pl.col("area_id").str.slice(0, 5).alias("il_id")
    )
    metro = set(
        hoods.with_columns(pl.col("area_id").str.slice(0, 5).alias("il_id"))["il_id"]
        .unique()
        .to_list()
    ) - set(villages["il_id"].unique().to_list())

    frame = (
        hoods.with_columns(pl.col("area_id").str.slice(0, 5).alias("il_id"))
        .filter(pl.col("il_id").is_in(list(metro)))
        .join(population("neighbourhood"), on="area_id", how="left")
        .drop_nulls("nufus")
    )
    provinces = pl.read_csv(DATA / "areas_tr.csv").select(
        "area_id", pl.col("name_tr").alias("il")
    )
    districts = pl.read_csv(DATA / "areas_tr_districts.csv").select(
        "area_id", pl.col("name_tr").alias("ilce")
    )

    marked = (
        blocks(frame)
        .join(provinces, left_on="il_id", right_on="area_id", how="left")
        .join(districts, left_on="parent_id", right_on="area_id", how="left")
    )
    print(f"{len(metro)} buyuksehir ili, {len(marked)} mahalle\n")

    print("== Blok x TUIK sinifi (mahalle sayisi) ==")
    table = (
        marked.drop_nulls("urban_rural")
        .group_by("blok", "urban_rural")
        .agg(pl.len().alias("n"), pl.col("nufus").sum().alias("kisi"))
        .sort("blok", "urban_rural")
    )
    print(table)

    print("\n== Blok basina kir orani ==")
    per = (
        marked.drop_nulls("urban_rural")
        .group_by("blok")
        .agg(
            pl.len().alias("mahalle"),
            (pl.col("urban_rural") == "kir").sum().alias("kir"),
            pl.col("nufus").sum().alias("kisi"),
            pl.col("nufus")
            .filter(pl.col("urban_rural") == "kir")
            .sum()
            .alias("kir_kisi"),
        )
        .with_columns(
            (100 * pl.col("kir") / pl.col("mahalle")).round(1).alias("kir_%_sayi"),
            (100 * pl.col("kir_kisi") / pl.col("kisi")).round(1).alias("kir_%_nufus"),
        )
    )
    print(per)

    print("\n== Ilcelerin blok yapisi ==")
    shape = (
        marked.group_by("il", "ilce")
        .agg(pl.col("blok").n_unique().alias("blok_sayisi"), pl.col("blok").first())
        .group_by("blok_sayisi", "blok")
        .agg(pl.len().alias("ilce"))
        .sort("blok_sayisi")
    )
    print(shape)

    print("\n== Iki yontemin il duzeyinde kir payi ==")
    il = (
        marked.drop_nulls("urban_rural")
        .group_by("il")
        .agg(
            pl.col("nufus").sum().alias("toplam"),
            pl.col("nufus").filter(pl.col("blok") == "donusen").sum().alias("blok_kir"),
            pl.col("nufus")
            .filter(pl.col("urban_rural") == "kir")
            .sum()
            .alias("tuik_kir"),
        )
        .with_columns(
            (100 * pl.col("blok_kir") / pl.col("toplam")).round(1).alias("blok_%"),
            (100 * pl.col("tuik_kir") / pl.col("toplam")).round(1).alias("tuik_%"),
        )
        .with_columns((pl.col("blok_%") - pl.col("tuik_%")).alias("fark"))
        .sort("tuik_%", descending=True)
    )
    print(il.select("il", "blok_%", "tuik_%", "fark"))
    print("\nortalama mutlak fark:", round(il["fark"].abs().mean(), 1), "puan")

    print("\n== Kalecik ==")
    print(
        marked.filter(pl.col("ilce") == "Kalecik")
        .group_by("blok")
        .agg(pl.len().alias("mahalle"), pl.col("nufus").sum().alias("kisi"))
    )


if __name__ == "__main__":
    main()
