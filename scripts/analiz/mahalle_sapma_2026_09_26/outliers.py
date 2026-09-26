"""Neighbourhoods that stand out: demography (ADNKS 2024) and the 2023 general election.

Reads C:/veri-ham/analiz/mahalle_sapma/table.parquet (build_table.py) and names from
C:/veri-ham/analiz/mahalle/mahalle.parquet. Only places of at least MIN_POP residents:
the question is a large neighbourhood that looks unlike a large neighbourhood, not a
hamlet of forty.

- Each measure: the most extreme places, both ends.
- Combined: robust z (median/MAD) over all measures, summed in squares — the places that
  are odd in several ways at once.
- Election: highest party shares, and the largest gap between a place and its own
  district (the district total with the place itself taken out). Places with an
  institutional ballot box (more voted than registered, by over 2 %) are left out of the
  vote lists and flagged in the demographic ones.
"""

import polars as pl

T = "C:/veri-ham/analiz/mahalle_sapma/table.parquet"
NAMES = "C:/veri-ham/analiz/mahalle/mahalle.parquet"
OUT = "C:/veri-ham/analiz/mahalle_sapma/"
MIN_POP = 5000
MIN_VALID = 2000
TOP = 10
MEASURES = [
    "male_pct",
    "child_pct",
    "elder_pct",
    "young_adult_pct",
    "never_married_pct",
    "divorced_pct",
    "widowed_pct",
    "uni_pct",
    "no_school_pct",
]
PARTIES = ["akp", "chp", "mhp", "iyi", "ysp", "yrp", "zafer", "tip", "bbp"]


def main() -> None:
    names = pl.read_parquet(NAMES).select(
        pl.col("id").cast(pl.Utf8), "province", "district", "neighbourhood"
    )
    t = (
        pl.read_parquet(T)
        .join(names, on="id", how="left")
        .with_columns(
            (pl.col("voted") > pl.col("reg") * 1.02).fill_null(False).alias("inst"),
            pl.format("{} / {} / {}", "province", "district", "neighbourhood").alias(
                "place"
            ),
        )
    )
    big = t.filter(pl.col("pop") >= MIN_POP)
    print(f"neighbourhoods >= {MIN_POP}: {big.height}")

    cfg = pl.Config(
        tbl_rows=40, tbl_width_chars=200, fmt_str_lengths=60, float_precision=1
    )
    with cfg:
        for m in MEASURES:
            s = big.drop_nulls(m).sort(m)
            cols = ["place", "pop", m, "inst"]
            print(f"\n## {m}  median {s[m].median():.1f}")
            print("lowest");  print(s.head(TOP).select(cols))  # fmt: skip
            print("highest"); print(s.tail(TOP).reverse().select(cols))  # fmt: skip

        z = (
            big.drop_nulls(MEASURES)
            .with_columns(
                [
                    (
                        (pl.col(m) - pl.col(m).median())
                        / (pl.col(m) - pl.col(m).median()).abs().median()
                        / 1.4826
                    ).alias("z_" + m)
                    for m in MEASURES
                ]  # fmt: skip
            )
            .with_columns(
                pl.sum_horizontal([pl.col("z_" + m) ** 2 for m in MEASURES])
                .sqrt()
                .alias("odd")
            )
        )
        z.write_parquet(OUT + "big_z.parquet")
        print("\n## most unusual overall")
        print(
            z.sort("odd", descending=True)
            .head(25)
            .select("place", "pop", "odd", *MEASURES, "inst")
        )

        # Election.
        v = t.filter(pl.col("valid").is_not_null())
        v = v.with_columns(
            pl.concat_str(["plate", "county"], separator="-").alias("dkey")
        )
        sums = v.group_by("dkey").agg(
            pl.col("valid").sum().alias("d_valid"),
            *[pl.col("v_" + p).sum().alias("d_" + p) for p in PARTIES],
        )
        v = v.join(sums, on="dkey").with_columns(
            [
                (
                    pl.col(p)
                    - (pl.col("d_" + p) - pl.col("v_" + p))
                    / (pl.col("d_valid") - pl.col("valid"))
                    * 100
                ).alias("gap_" + p)
                for p in PARTIES
            ]
        )
        ve = v.filter((pl.col("valid") >= MIN_VALID) & ~pl.col("inst"))
        ve.write_parquet(OUT + "votes.parquet")
        print(
            f"\nplaces with >= {MIN_VALID} valid votes, no institutional box: {ve.height}"
        )
        for p in PARTIES:
            print(f"\n## {p}: highest share")
            print(
                ve.sort(p, descending=True)
                .head(TOP)
                .select("place", "valid", p, "gap_" + p)
            )
        for p in ["akp", "chp", "mhp", "iyi", "ysp", "yrp"]:
            print(f"\n## {p}: furthest from own district")
            s = ve.sort(pl.col("gap_" + p).abs(), descending=True).head(TOP)
            print(s.select("place", "valid", p, "gap_" + p))
        print("\n## turnout")
        s = ve.sort("turnout")
        print(s.head(TOP).select("place", "reg", "turnout"))
        print(s.tail(TOP).reverse().select("place", "reg", "turnout"))
        print("\n## institutional boxes in large places (more voted than registered)")
        print(
            t.filter(pl.col("inst") & (pl.col("reg") >= 1000))
            .with_columns((pl.col("voted") - pl.col("reg")).alias("extra"))
            .sort("extra", descending=True)
            .head(15)
            .select("place", "pop", "reg", "voted", "extra", "male_pct", "ysp", "akp")
        )


if __name__ == "__main__":
    main()
