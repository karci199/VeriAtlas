"""Bellwether, volatility and shift indices for provinces, districts and neighbourhoods.

Four general elections, 2015-06 to 2023. 2007 and 2011 are left out: the Kurdish movement
ran as independents and the tables give only the independents' total, which also holds
other independents (scripts/elections/README.md: they produce false swings). 2002 holds
only 77 % of its valid vote at neighbourhood level. Parties are pooled into five blocs so
that renamed parties stay comparable:

- AKP;
- CHP;
- nationalist: MHP, İYİ, BBP, Zafer;
- Kurdish movement: HDP, YSP;
- other: everything else, alliance-only ballots included.

Distance between two vote splits is the dissimilarity index, half the sum of absolute
differences in bloc shares (0 = identical, 100 = no overlap).

- Bellwether, 2023: distance of the full party split (nine parties + other) from Türkiye.
- Bellwether, all six: mean bloc distance from Türkiye over the four elections.
- Volatility: mean bloc distance between consecutive elections (Pedersen index).
  Türkiye's own figure is printed for scale.
- Shift: bloc distance 2015-06 -> 2023, with the bloc that gained and lost most, and the
  distance from Türkiye's own change (how far the place moved against the national tide).

Neighbourhoods: at least MIN_VALID valid votes in every election and never an
institutional box (more voted than registered by over 2 %). Districts are keyed by the
current plate-district code in the tiles; provinces by plate.

Run from the main checkout root. Writes C:/veri-ham/analiz/siyasi_endeks/tables.json.
"""

import glob
import itertools
import json
from pathlib import Path

import polars as pl

ELECTIONS = ["mv2015h", "mv2015k", "mv2018", "mv2023"]
FIRST = ELECTIONS[0]
LABEL = {
    FIRST: "2007",
    "mv2011": "2011",
    "mv2015h": "2015-H",
    "mv2015k": "2015-K",
    "mv2018": "2018",
    "mv2023": "2023",
}
BLOCS = {
    "akp": ["AK PARTİ"],
    "chp": ["CHP"],
    "nat": ["MHP", "İYİ PARTİ", "BBP", "BÜYÜK BİRLİK", "ZAFER PARTİSİ"],
    "kurd": ["HDP", "YEŞİL SOL PARTİ"],
}
PARTIES_2023 = {
    "akp": "AK PARTİ",
    "chp": "CHP",
    "mhp": "MHP",
    "iyi": "İYİ PARTİ",
    "ysp": "YEŞİL SOL PARTİ",
    "yrp": "YENİDEN REFAH",
    "zafer": "ZAFER PARTİSİ",
    "tip": "TİP",
    "bbp": "BÜYÜK BİRLİK",
}
B = ["akp", "chp", "nat", "kurd", "oth"]
MIN_VALID = 1000
MIN_VALID_DISTRICT = 10000
NAMES = "C:/veri-ham/analiz/mahalle/mahalle.parquet"
OUT = Path("C:/veri-ham/analiz/siyasi_endeks")
TOP = 15


def load(election: str) -> pl.DataFrame:
    rows = []
    for path in sorted(glob.glob(f"public/tiles/secim-{election}-mahalle-TR-*.json")):
        for key, v in json.load(open(path, encoding="utf-8")).items():
            parts = key.split("-")
            if len(parts) != 4:
                continue
            votes = v["v"]
            r = {
                "key": key,
                "plate": parts[1],
                "county": parts[2],
                "id": parts[3],
                "name": v.get("ad"),
                "reg": v["k"],
                "voted": v["o"],
                "valid": v["g"],
            }
            for bloc, names in BLOCS.items():
                r[bloc] = sum(votes.get(n, 0) for n in names)
            if election == "mv2023":
                for p, n in PARTIES_2023.items():
                    r["p_" + p] = votes.get(n, 0)
            rows.append(r)
    df = pl.DataFrame(rows).with_columns(
        (pl.col("valid") - pl.sum_horizontal(B[:-1])).clip(0).alias("oth"),
        pl.lit(election).alias("election"),
    )
    return df


def shares(df: pl.DataFrame, by: list[str], cols: list[str]) -> pl.DataFrame:
    g = df.group_by(by).agg(pl.col(["valid", *cols]).sum())
    return g.with_columns([(pl.col(c) / pl.col("valid") * 100).alias(c) for c in cols])


def dissim(a: list[str], b: list[str]) -> pl.Expr:
    return (
        pl.sum_horizontal(
            [(pl.col(x) - pl.col(y)).abs() for x, y in zip(a, b, strict=True)]
        )
        / 2
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = [load(e) for e in ELECTIONS]
    allv = pl.concat(frames, how="diagonal_relaxed")

    names = pl.read_parquet(NAMES).select(
        pl.col("id").cast(pl.Utf8), "province", "district"
    )
    geo = (
        allv.select("plate", "county", "id")
        .unique()
        .join(names, on="id", how="left")
        .with_columns(
            pl.col("province").drop_nulls().first().over("plate").alias("province"),
            pl.col("district")
            .drop_nulls()
            .mode()
            .first()
            .over("plate", "county")
            .alias("district"),
        )
    )
    prov_name = geo.select("plate", "province").unique("plate")
    dist_name = geo.select("plate", "county", "province", "district").unique(
        ["plate", "county"]
    )

    # Provinces present in every election (all 81 since 2015).
    plates = set.intersection(*[set(f["plate"]) for f in frames])
    allv = allv.filter(pl.col("plate").is_in(plates))
    print("provinces in all elections:", len(plates))

    tr = shares(allv, ["election"], B).rename({b: "tr_" + b for b in B}).drop("valid")
    tables: dict[str, list[dict]] = {}

    def level(by: list[str], units: pl.DataFrame, min_valid: int) -> pl.DataFrame:
        s = shares(units, [*by, "election"], B)
        ok = (
            s.group_by(by)
            .agg((pl.col("valid") >= min_valid).all().alias("ok"), pl.len().alias("n"))
            .filter(pl.col("ok") & (pl.col("n") == len(ELECTIONS)))
            .select(by)
        )
        return s.join(ok, on=by).join(tr, on="election")

    # Neighbourhoods: never an institutional box.
    inst = allv.filter(pl.col("voted") > pl.col("reg") * 1.02).select("key").unique()
    mah_units = allv.join(inst, on="key", how="anti")
    levels = {
        "il": (["plate"], allv, 0),
        "ilce": (["plate", "county"], allv, MIN_VALID_DISTRICT),
        "mahalle": (["key"], mah_units, MIN_VALID),
    }
    meta = {}
    for lv, (by, units, mv) in levels.items():
        s = level(by, units, mv).sort("election")
        s = s.with_columns(dissim(B, ["tr_" + b for b in B]).alias("d_tr"))
        wide = s.pivot(on="election", index=by, values=[*B, "d_tr", "valid"])

        def col(metric: str, e: str) -> str:
            return f"{metric}_{e}"

        # Volatility: consecutive pairs.
        pairs = list(itertools.pairwise(ELECTIONS))
        wide = wide.with_columns(
            [
                dissim([col(b, a) for b in B], [col(b, c) for b in B]).alias(
                    f"v_{a}_{c}"
                )
                for a, c in pairs
            ]
        ).with_columns(
            pl.mean_horizontal([f"v_{a}_{c}" for a, c in pairs]).alias("volatility"),
            pl.mean_horizontal([col("d_tr", e) for e in ELECTIONS]).alias(
                "bellwether_all"
            ),
            dissim([col(b, FIRST) for b in B], [col(b, "mv2023") for b in B]).alias(
                "shift"
            ),
        )
        trc = {
            b: {e: tr.filter(pl.col("election") == e)["tr_" + b][0] for e in ELECTIONS}
            for b in B
        }
        wide = wide.with_columns(
            [
                (pl.col(col(b, "mv2023")) - pl.col(col(b, FIRST))).alias("chg_" + b)
                for b in B
            ]
        ).with_columns(
            (
                pl.sum_horizontal(
                    [
                        (pl.col("chg_" + b) - (trc[b]["mv2023"] - trc[b][FIRST])).abs()
                        for b in B
                    ]
                )
                / 2
            ).alias("shift_vs_tr")
        )
        if lv == "il":
            wide = wide.join(prov_name, on="plate", how="left").with_columns(
                pl.col("province").alias("place")
            )
        elif lv == "ilce":
            wide = wide.join(
                dist_name, on=["plate", "county"], how="left"
            ).with_columns(pl.format("{} / {}", "province", "district").alias("place"))
        else:
            last = mah_units.filter(pl.col("election") == "mv2023").select(
                "key", "plate", "county", "name"
            )
            wide = (
                wide.join(last, on="key", how="left")
                .join(dist_name, on=["plate", "county"], how="left")
                .with_columns(
                    pl.format("{} / {} / {}", "province", "district", "name").alias(
                        "place"
                    )
                )
            )
        wide = wide.with_columns(pl.col(col("valid", "mv2023")).alias("valid23"))
        meta[lv] = wide.height
        print(f"{lv}: {wide.height} units")

        def pack(df: pl.DataFrame, cols: list[str]) -> list[dict]:
            return (
                df.select(["place", *cols])
                .with_columns(
                    [pl.col(c).round(1) for c in cols if df.schema[c].is_float()]
                )
                .to_dicts()
            )

        bloc23 = [col(b, "mv2023") for b in B]
        tables[f"{lv}_consistent"] = pack(
            wide.sort("volatility").head(TOP), ["valid23", "volatility", *bloc23]
        )
        tables[f"{lv}_volatile"] = pack(
            wide.sort("volatility", descending=True).head(TOP),
            ["valid23", "volatility", *[f"v_{a}_{c}" for a, c in pairs]],
        )
        tables[f"{lv}_shift"] = pack(
            wide.sort("shift", descending=True).head(TOP),
            ["valid23", "shift", "shift_vs_tr", *["chg_" + b for b in B]],
        )
        tables[f"{lv}_shift_vs_tr"] = pack(
            wide.sort("shift_vs_tr", descending=True).head(TOP),
            ["valid23", "shift_vs_tr", "shift", *["chg_" + b for b in B]],
        )
        tables[f"{lv}_bellwether_all"] = pack(
            wide.sort("bellwether_all").head(TOP),
            ["valid23", "bellwether_all", *[col("d_tr", e) for e in ELECTIONS]],
        )
        wide.write_parquet(OUT / f"{lv}.parquet")

    # Bellwether 2023 on the full party split, all units with enough votes that year.
    last = allv.filter(pl.col("election") == "mv2023")
    pcols = ["p_" + p for p in PARTIES_2023]
    last = last.with_columns(
        (pl.col("valid") - pl.sum_horizontal(pcols)).alias("p_oth")
    )
    pcols = [*pcols, "p_oth"]
    trp = {c: last[c].sum() / last["valid"].sum() * 100 for c in pcols}
    for lv, by, mv in (
        ("il", ["plate"], 0),
        ("ilce", ["plate", "county"], MIN_VALID_DISTRICT),
        ("mahalle", ["key"], MIN_VALID),
    ):
        src = last if lv != "mahalle" else last.join(inst, on="key", how="anti")
        s = shares(src, by, pcols).filter(pl.col("valid") >= mv)
        s = s.with_columns(
            (pl.sum_horizontal([(pl.col(c) - trp[c]).abs() for c in pcols]) / 2).alias(
                "d23"
            )
        )
        if lv == "il":
            s = s.join(prov_name, on="plate", how="left").with_columns(
                pl.col("province").alias("place")
            )
        elif lv == "ilce":
            s = s.join(dist_name, on=["plate", "county"], how="left").with_columns(
                pl.format("{} / {}", "province", "district").alias("place")
            )
        else:
            s = (
                s.join(src.select("key", "plate", "county", "name"), on="key")
                .join(dist_name, on=["plate", "county"], how="left")
                .with_columns(
                    pl.format("{} / {} / {}", "province", "district", "name").alias(
                        "place"
                    )
                )
            )
        cols = [
            "valid",
            "d23",
            "p_akp",
            "p_chp",
            "p_mhp",
            "p_iyi",
            "p_ysp",
            "p_yrp",
            "p_zafer",
        ]
        tables[f"{lv}_bellwether23"] = (
            s.sort("d23").head(TOP).select(["place", *cols])
            .with_columns([pl.col(c).round(1) for c in cols[1:]]).to_dicts()
        )  # fmt: skip

    trv = tr.sort("election")
    trvol = [
        sum(abs(trv["tr_" + b][i] - trv["tr_" + b][i + 1]) for b in B) / 2
        for i in range(len(ELECTIONS) - 1)
    ]
    national = {
        "tr_2023": {c: round(v, 1) for c, v in trp.items()},
        "tr_blocs": {e: {b: round(trc[b][e], 1) for b in B} for e in ELECTIONS},
        "tr_volatility": round(sum(trvol) / len(trvol), 1),
        "tr_shift": round(sum(abs(trc[b]["mv2023"] - trc[b][FIRST]) for b in B) / 2, 1),
        "units": meta,
    }
    json.dump(
        {"national": national, "tables": tables, "labels": LABEL},
        open(OUT / "tables.json", "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    print(json.dumps(national, ensure_ascii=False))


if __name__ == "__main__":
    main()
