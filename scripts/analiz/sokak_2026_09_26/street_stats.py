"""Street counts and street names from the PTT postal-code table (2026-09-18 snapshot).

C:/veri-ham/ptt/postakodu_2026-09-18.csv holds one row per delivery point: province,
district, district code, neighbourhood, street, postal code. It is not a street census:
in a village PTT lists the village itself, so 39 k of 72 k settlements carry one row
(src/veriatlas/adapters/ptt_postal.py). Two counts are therefore kept side by side at
every level:

- `streets_all`: every distinct street row, villages' single rows included;
- `streets`: streets in neighbourhoods PTT splits into at least MIN_STREETS streets —
  the figure to read as "how many streets".

Also per level: neighbourhoods (all / split), postal codes, numbered streets ("1203.
Sokak", grid planning), streets whose name carries a type word (cadde, bulvar, meydan,
yol — rare: PTT mostly drops the type), a few common names, and the most common names.

Run from the repository root. Output, C:/veri-ham/analiz/sokak/:
tr.csv, province.csv, district.csv, neighbourhood.csv, top_names_{tr,province}.csv.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, "src")
from veriatlas.areas import load_districts

SRC = Path("C:/veri-ham/ptt/postakodu_2026-09-18.csv")
OUT = Path("C:/veri-ham/analiz/sokak")
MIN_STREETS = 5
TYPES = {
    "cadde": r"\bCAD(DE|DESİ|\.)?\b",
    "bulvar": r"\bBULVAR|\bBLV\.?\b|\bBULV\.?\b",
    "meydan": r"\bMEYDAN",
    "yol": r"\bYOLU?\b",
}
NAMES = {
    "ataturk": r"ATATÜRK",
    "cumhuriyet": r"CUMHURİYET",
    "istiklal": r"İSTİKLAL",
    "fatih": r"\bFATİH\b",
    "mevlana": r"MEVLANA",
    "yunus_emre": r"YUNUS\s*EMRE",
}


def normalise(col: pl.Expr) -> pl.Expr:
    """Street name without PTT's `_1` suffix, the type word and trailing punctuation."""
    kinds = "|".join(f"(?:{p})" for p in TYPES.values())
    return (
        col.str.replace_all(r"_\d+$", "")
        .str.replace_all(r"\s+(SOKAĞI|SOKAK|SOK\.?|SK\.?)$", "")
        .str.replace_all(kinds, "")
        .str.replace_all(r"[.\-]+$", "")
        .str.strip_chars()
    )


def summarise(streets: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    split = pl.col("split")
    return (
        streets.group_by(by)
        .agg(
            pl.col("hood").n_unique().alias("neighbourhoods"),
            pl.col("hood").filter(split).n_unique().alias("neighbourhoods_split"),
            pl.len().alias("streets_all"),
            split.sum().alias("streets"),
            pl.col("posta_kodu").n_unique().alias("postal_codes"),
            (pl.col("numbered") & split).sum().alias("numbered"),
            *[(pl.col("t_" + k) & split).sum().alias(k) for k in TYPES],
            *[(pl.col("n_" + k) & split).sum().alias(k) for k in NAMES],
        )
        .with_columns(
            (pl.col("numbered") / pl.col("streets") * 100)
            .round(1)
            .alias("numbered_pct"),
            (pl.col("streets") / pl.col("neighbourhoods_split"))
            .round(1)
            .alias("streets_per_split_hood"),
        )
    )


def top_names(named: pl.DataFrame, by: list[str], n: int) -> pl.DataFrame:
    return (
        named.group_by([*by, "name"])
        .len()
        .sort([*by, "len", "name"], descending=[False] * len(by) + [True, False])
        .group_by(by, maintain_order=True)
        .head(n)
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = pl.read_csv(SRC, infer_schema_length=0).with_columns(
        pl.col("sokak").str.strip_chars().str.to_uppercase(),
        pl.concat_str(["ilce_kodu", "mahalle"], separator="|").alias("hood"),
    )
    streets = raw.unique(["hood", "sokak"])
    size = streets.group_by("hood").len().rename({"len": "hood_rows"})
    streets = streets.join(size, on="hood").with_columns(
        (pl.col("hood_rows") >= MIN_STREETS).alias("split"),
        pl.col("sokak").str.contains(r"^\d+[\s.]*[A-Z]?\.?$").alias("numbered"),
        *[pl.col("sokak").str.contains(p).alias("t_" + k) for k, p in TYPES.items()],
        *[pl.col("sokak").str.contains(p).alias("n_" + k) for k, p in NAMES.items()],
        normalise(pl.col("sokak")).alias("name"),
    )
    registry = load_districts().filter(pl.col("medas_code").is_not_null())
    code_to_area = dict(
        zip(registry["medas_code"].cast(pl.Utf8), registry["area_id"], strict=True)
    )
    streets = streets.with_columns(
        pl.col("ilce_kodu").replace_strict(code_to_area, default=None).alias("area_id")
    )
    if streets["area_id"].is_null().any():
        raise ValueError("PTT district code missing from the registry")
    named = streets.filter(
        pl.col("split") & ~pl.col("numbered") & (pl.col("name") != "")
    )

    tr = summarise(
        streets.with_columns(pl.lit("Türkiye").alias("country")), ["country"]
    )
    province = summarise(streets, ["il"]).sort("streets", descending=True)
    district = (
        summarise(streets, ["il", "ilce", "area_id"])
        .join(
            top_names(named, ["area_id"], 1).rename(
                {"name": "top_name", "len": "top_name_n"}
            ),
            on="area_id",
            how="left",
        )
        .sort("area_id")
    )
    hood = (
        streets.group_by("il", "ilce", "area_id", "mahalle")
        .agg(
            pl.len().alias("streets_all"),
            pl.col("split").first().alias("split"),
            pl.col("posta_kodu").n_unique().alias("postal_codes"),
            pl.col("numbered").sum().alias("numbered"),
            *[pl.col("t_" + k).sum().alias(k) for k in TYPES],
        )
        .sort("area_id", "mahalle")
    )
    tr.write_csv(OUT / "tr.csv")
    province.write_csv(OUT / "province.csv")
    district.write_csv(OUT / "district.csv")
    hood.write_csv(OUT / "neighbourhood.csv")
    top_names(named.with_columns(pl.lit("TR").alias("c")), ["c"], 50).write_csv(
        OUT / "top_names_tr.csv"
    )
    top_names(named, ["il"], 10).write_csv(OUT / "top_names_province.csv")

    cfg = pl.Config(tbl_rows=30, tbl_cols=16, tbl_width_chars=220, fmt_str_lengths=36)
    with cfg:
        print("TÜRKİYE")
        print(tr.transpose(include_header=True, column_names=["value"]))
        cols = ["il", "neighbourhoods", "neighbourhoods_split", "streets_all", "streets",
                "postal_codes", "numbered_pct", "streets_per_split_hood"]  # fmt: skip
        print("\nPROVINCES, most streets")
        print(province.head(15).select(cols))
        print("\nPROVINCES, fewest streets")
        print(province.tail(10).select(cols))
        dcols = [
            "il",
            "ilce",
            "neighbourhoods_split",
            "streets",
            "numbered_pct",
            "top_name",
        ]
        print("\nDISTRICTS, most streets")
        print(district.sort("streets", descending=True).head(15).select(dcols))
        print("\nNEIGHBOURHOODS, most streets")
        print(
            hood.sort("streets_all", descending=True)
            .head(15)
            .select("il", "ilce", "mahalle", "streets_all", "postal_codes", "numbered")
        )
        print("\nsplit neighbourhoods:", hood["split"].sum(), "of", hood.height)


if __name__ == "__main__":
    main()
