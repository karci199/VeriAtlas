"""Flatten the YÖK Atlas JSON into programme-level parquet tables.

`public/yokatlas_programs.parquet`: one row per programme in the guide (kilavuzKodu unique),
with `area_id` (TR-xx) where the programme is in Türkiye. `public/yokatlas_nets.parquet`: one
row per programme and year. The two join on `kilavuzKodu`.
"""

import json
import sys

import polars as pl

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC, RAW


def main() -> None:
    folder = RAW / "yokatlas"
    guide_file = max(folder.glob("kilavuz_*.json"))
    programs = pl.DataFrame(
        json.loads(guide_file.read_text(encoding="utf-8"))["content"],
        infer_schema_length=None,
    ).with_columns(
        pl.when(
            pl.col("universiteTuru").is_in(["DEVLET", "VAKIF"])
            & (pl.col("ilKodu") <= 81)
        )
        .then(pl.format("TR-{}", pl.col("ilKodu").cast(pl.Utf8).str.zfill(2)))
        .alias("area_id"),
        pl.col("sinav").str.strip_chars(),
        pl.col("donem").str.strip_chars(),
    )
    if programs["kilavuzKodu"].n_unique() != programs.height:
        raise ValueError("kılavuz kodu tekrar ediyor")
    nets = pl.DataFrame(
        json.loads((folder / "netler.json").read_text(encoding="utf-8"))["content"],
        infer_schema_length=None,
    )
    # The API returns 176 rows twice, byte for byte: those are dropped; two different rows
    # for one programme and year would still stop here.
    nets = nets.unique(maintain_order=True)
    # A programme admitting on two score types (EA and SAY) has a row for each.
    if nets.select("kilavuzKodu", "yil", "puanTuru").is_duplicated().any():
        raise ValueError("netler: program × yıl × puan türü tekrar ediyor")
    programs.write_parquet(PUBLIC / "yokatlas_programs.parquet")
    nets.write_parquet(PUBLIC / "yokatlas_nets.parquet")
    print("programlar", programs.height, "netler", nets.height)


if __name__ == "__main__":
    main()
