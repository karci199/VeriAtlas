"""2023 general election: where AKP took the smallest share of the People's Alliance vote,
and CHP the smallest share of the Nation Alliance vote.

People's Alliance = AKP + MHP + Yeniden Refah + BBP + alliance-only ballots (DSP ran on AKP
lists). Nation Alliance = CHP + İYİ + alliance-only ballots (DEVA, Gelecek, Saadet, DP ran
on CHP lists, so their votes are inside CHP's).

Provinces where a member party did not stand are left out of that alliance: there the
share is 0 or 100 by construction. Found from the data (under 0.2 % of the valid vote):
CHP 13 18 29 49 66 68 69, İYİ 02 19 24 30 53 65 72 74 81, BBP 47 73.

Thresholds: at least MIN_VALID valid votes and MIN_ALLIANCE votes for the alliance, and no
institutional ballot box (more voted than registered by over 2 %).
Run from the main checkout root.
"""

import glob
import json

import polars as pl

MIN_VALID = 300
MIN_ALLIANCE = 100
TOP = 25
CUMHUR = ["AK PARTİ", "MHP", "YENİDEN REFAH", "BÜYÜK BİRLİK", "CUMHUR İTTİFAKI"]
MILLET = ["CHP", "İYİ PARTİ", "MİLLET İTTİFAKI"]
NO_CUMHUR = {"47", "73"}
NO_MILLET = {"13", "18", "29", "49", "66", "68", "69", "02", "19", "24", "30", "53", "65", "72", "74", "81"}  # fmt: skip
NAMES = "C:/veri-ham/analiz/mahalle/mahalle.parquet"


def main() -> None:
    rows = []
    for path in sorted(glob.glob("public/tiles/secim-mv2023-mahalle-TR-*.json")):
        for key, v in json.load(open(path, encoding="utf-8")).items():
            parts = key.split("-")
            if len(parts) != 4:
                continue
            g = v["v"].get
            rows.append(
                {
                    "plate": parts[1],
                    "county": parts[2],
                    "id": parts[3],
                    "tile_name": v.get("ad"),
                    "reg": v["k"],
                    "voted": v["o"],
                    "valid": v["g"],
                    "akp": g("AK PARTİ", 0),
                    "mhp": g("MHP", 0),
                    "yrp": g("YENİDEN REFAH", 0),
                    "bbp": g("BÜYÜK BİRLİK", 0),
                    "chp": g("CHP", 0),
                    "iyi": g("İYİ PARTİ", 0),
                    "ysp": g("YEŞİL SOL PARTİ", 0),
                    "cumhur": sum(g(n, 0) for n in CUMHUR),
                    "millet": sum(g(n, 0) for n in MILLET),
                }
            )
    names = pl.read_parquet(NAMES).select(
        pl.col("id").cast(pl.Utf8), "province", "district", "neighbourhood", "pop"
    )
    raw = pl.DataFrame(rows).join(names, on="id", how="left")
    # Villages missing from the Endeksa dump have no names; take them from their district.
    raw = raw.with_columns(
        pl.col("province").fill_null(
            pl.col("province").drop_nulls().first().over("plate")
        ),
        pl.col("district").fill_null(
            pl.col("district").drop_nulls().first().over("plate", "county")
        ),
    ).with_columns(
        pl.format(
            "{} / {} / {}",
            "province",
            "district",
            pl.coalesce("neighbourhood", "tile_name"),
        ).alias("place"),
        (pl.col("voted") > pl.col("reg") * 1.02).alias("inst"),
    )
    t = raw.filter((pl.col("valid") >= MIN_VALID) & ~pl.col("inst"))
    pct = lambda a, b: (pl.col(a) / pl.col(b) * 100).round(1)

    c = t.filter(
        ~pl.col("plate").is_in(NO_CUMHUR) & (pl.col("cumhur") >= MIN_ALLIANCE)
    ).with_columns(
        pct("akp", "cumhur").alias("akp_in_cumhur"),
        pct("mhp", "cumhur").alias("mhp_in_cumhur"),
        pct("yrp", "cumhur").alias("yrp_in_cumhur"),
        pct("bbp", "cumhur").alias("bbp_in_cumhur"),
        pct("cumhur", "valid").alias("cumhur_pct"),
    )
    m = t.filter(
        ~pl.col("plate").is_in(NO_MILLET) & (pl.col("millet") >= MIN_ALLIANCE)
    ).with_columns(
        pct("chp", "millet").alias("chp_in_millet"),
        pct("iyi", "millet").alias("iyi_in_millet"),
        pct("millet", "valid").alias("millet_pct"),
    )
    with pl.Config(tbl_rows=60, tbl_width_chars=220, fmt_str_lengths=55):
        tc = c["akp"].sum() / c["cumhur"].sum() * 100
        print(f"Cumhur: {c.height} places; AKP share of alliance overall {tc:.1f}")
        print(
            c.sort("akp_in_cumhur")
            .head(TOP)
            .select(
                "place",
                "valid",
                "cumhur",
                "akp_in_cumhur",
                "mhp_in_cumhur",
                "yrp_in_cumhur",
                "bbp_in_cumhur",
                "cumhur_pct",
            )  # fmt: skip
        )
        tm = m["chp"].sum() / m["millet"].sum() * 100
        print(f"\nMillet: {m.height} places; CHP share of alliance overall {tm:.1f}")
        print(
            m.sort("chp_in_millet")
            .head(TOP)
            .select(
                "place",
                "valid",
                "millet",
                "chp_in_millet",
                "iyi_in_millet",
                "millet_pct",
            )
        )
        print("\nBy province, places where AKP < 50 % of Cumhur")
        print(
            c.filter(pl.col("akp_in_cumhur") < 50)
            .group_by("province").len().sort("len", descending=True).head(15)
        )  # fmt: skip
        print("\nBy province, places where CHP < 50 % of Millet")
        print(
            m.filter(pl.col("chp_in_millet") < 50)
            .group_by("province").len().sort("len", descending=True).head(15)
        )  # fmt: skip

        big = pl.col("valid") >= 2000
        print("\nLarge places (>= 2000 valid): AKP share of Cumhur, lowest")
        print(
            c.filter(big)
            .sort("akp_in_cumhur")
            .head(15)
            .select("place", "valid", "akp_in_cumhur", "mhp_in_cumhur", "cumhur_pct")
        )
        print("\nLarge places (>= 2000 valid): CHP share of Millet, lowest")
        print(
            m.filter(big)
            .sort("chp_in_millet")
            .head(15)
            .select("place", "valid", "chp_in_millet", "iyi_in_millet", "millet_pct")
        )
        # Province and district: every ballot box, no size threshold, so small villages
        # count; only provinces where a member party did not stand are left out.
        for level in (["province"], ["province", "district"]):
            name = (
                "Provinces" if len(level) == 1 else "Districts (>= 3000 alliance votes)"
            )
            cu = (
                raw.filter(~pl.col("plate").is_in(NO_CUMHUR))
                .group_by(level)
                .agg(pl.col("akp", "mhp", "yrp", "bbp", "cumhur").sum())
                .filter(pl.col("cumhur") >= 3000)
                .with_columns(
                    pct("akp", "cumhur").alias("akp_in"),
                    pct("mhp", "cumhur").alias("mhp_in"),
                    pct("yrp", "cumhur").alias("yrp_in"),
                    pct("bbp", "cumhur").alias("bbp_in"),
                )
                .sort("akp_in")
            )
            mi = (
                raw.filter(~pl.col("plate").is_in(NO_MILLET))
                .group_by(level)
                .agg(pl.col("chp", "iyi", "millet").sum())
                .filter(pl.col("millet") >= 3000)
                .with_columns(
                    pct("chp", "millet").alias("chp_in"),
                    pct("iyi", "millet").alias("iyi_in"),
                )
                .sort("chp_in")
            )
            print(f"\n{name}: AKP share of Cumhur, lowest")
            print(cu.head(15).drop("akp", "mhp", "yrp", "bbp"))
            print(f"\n{name}: CHP share of Millet, lowest")
            print(mi.head(15).drop("chp", "iyi"))


if __name__ == "__main__":
    main()
