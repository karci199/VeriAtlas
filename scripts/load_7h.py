"""What each settlement *was* — town, belde or village — from the 2015 election tables.

The 7H workbooks group every settlement into `MAHALLE` (town neighbourhoods) or
`BELDE - KÖY` (the rest, with belde and köy told apart). That grouping is the pre-6360
administrative classification and the YSK kept using it after 2014: Ankara still appears
with 866 villages, İstanbul with 164, in a year when neither had any in law.

That makes this the only reachable source for a question nothing else answers — which of
today's neighbourhoods used to be a village. Kalecik's seven town neighbourhoods here are
exactly the seven a human picked out by hand from the record numbers; Gölköy is a village
here, as it was in the 2000 census.

It is stored as `koken` — origin — and never as the answer to "is this urban". That
question has a tense: Bahçeşehir is a belde in this file and 64.000 people in a dense city
today, and both are true. The density answer lives in `urban_rural` (TÜİK's DEGURBA), the
history lives here, and merging them would destroy the only interesting part.

**Matching is by name**, which everything else in this repo refuses to do — 7H carries no
record number, only İl / İlçe / Mahalle text. The join is therefore made unique-to-unique
inside a district: a name that occurs twice on either side is dropped rather than guessed.
About one settlement in five ends up unmatched and is left `null`. Null, not "koy": a
missing origin is a missing answer, and filling it would put 17 million people into a
category no source put them in.

Run:  uv run python scripts/load_7h.py "<...>/AATOPLU 7H.xlsx"
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import openpyxl
import polars as pl

sys.path.insert(0, "src")

from veriatlas.config import RAW

DATA = Path("src/veriatlas/data")
SOURCE_ID = "ysk_7h_2015"

TOWN_SHEET = "MAHALLE"
RURAL_SHEET = "BELDE - KÖY"

#: Trailing words that name the *kind* of place rather than the place. Stripped before
#: punctuation is dropped — otherwise "Araplı Bel." folds to ARAPLIBEL and never meets
#: the ARAPLI that 7H wrote, which is exactly how the first belde pass found nothing.
#: The dot is required, so a settlement genuinely ending in "-bel" is left alone.
SUFFIX = re.compile(r"\s*(MAH\.|MAHALLESI|MAH|KOY\.|KOYU|BEL\.|BELEDIYESI)\s*$")

#: 7H writes a belde as "Haydarlı (B)" when the same district also holds a village of that
#: name — the marker is the disambiguator, so it is *not* stripped in the general key.
#: Dropping it there would fold the belde and the village into one name and the
#: unique-to-unique join would then discard both. It is stripped only when a belde is
#: being matched against a belediye, where the village cannot be confused with it.
BELDE_MARK = re.compile(r"B$")
FOLD = str.maketrans("İIŞĞÜÖÇ", "IISGUOC")


#: Province names 7H writes differently from the registry. Checked exhaustively, not
#: guessed: after folding, exactly one of the 81 disagrees. Left as a table rather than a
#: fuzzy match, because a fuzzy match that silently pairs Kırşehir with Kırıkkale would
#: be far worse than a name we can see is missing.
ALIAS = {"AFYON": "AFYONKARAHISAR"}


def key(text: object) -> str:
    """A name reduced to what two sources can agree on: letters and digits, folded."""
    folded = str(text or "").upper().translate(FOLD)
    cleaned = re.sub(r"[^A-Z0-9]", "", SUFFIX.sub("", folded))
    return ALIAS.get(cleaned, cleaned)


def read_7h(path: Path) -> pl.DataFrame:
    """Every settlement in the workbook, as (province, district, name, origin)."""
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for sheet in (TOWN_SHEET, RURAL_SHEET):
        if sheet not in book.sheetnames:
            raise ValueError(f"{path.name} icinde '{sheet}' sayfasi yok")

    rows = []
    # Town sheet: il | ilce | mahalle | ...
    for row in book[TOWN_SHEET].iter_rows(values_only=True):
        if isinstance(row[0], str) and key(row[0]) not in ("IL", "") and row[2]:
            rows.append((key(row[0]), key(row[1]), key(row[2]), "kent"))
    # Rural sheet: il | Belde/Köy | ilce | mahalle | ...
    for row in book[RURAL_SHEET].iter_rows(values_only=True):
        if isinstance(row[0], str) and key(row[0]) not in ("IL", "") and row[3]:
            kind = "belde" if str(row[1] or "").strip() == "Belde" else "koy"
            rows.append((key(row[0]), key(row[2]), key(row[3]), kind))
    if not rows:
        raise ValueError("7H satiri okunamadi — sayfa duzeni degismis olabilir")
    return pl.DataFrame(rows, schema=["il", "ilce", "ad", "koken"], orient="row")


def ours() -> pl.DataFrame:
    """Our settlements with the same three name parts, for both levels."""
    provinces = pl.read_csv(DATA / "areas_tr.csv").select(
        pl.col("area_id").alias("il_id"), pl.col("name_tr").alias("il_adi")
    )
    districts = pl.read_csv(DATA / "areas_tr_districts.csv").select(
        pl.col("area_id").alias("ilce_id"), pl.col("name_tr").alias("ilce_adi")
    )

    def side(name: str, level: str) -> pl.DataFrame:
        return (
            pl.read_csv(DATA / name)
            .with_columns(pl.col("area_id").str.slice(0, 5).alias("il_id"))
            .join(provinces, on="il_id", how="left")
            .join(districts, left_on="parent_id", right_on="ilce_id", how="left")
            .with_columns(
                pl.col("municipality").alias("bel_adi")
                if "municipality" in pl.read_csv(DATA / name).columns
                else pl.lit(None, dtype=pl.Utf8).alias("bel_adi")
            )
            .select("area_id", "name_tr", "il_adi", "ilce_adi", "bel_adi")
            .with_columns(pl.lit(level).alias("duzey"))
        )

    both = pl.concat(
        [
            side("areas_tr_neighbourhoods.csv", "neighbourhood"),
            side("areas_tr_villages.csv", "village"),
        ]
    )
    return both.with_columns(
        pl.col("il_adi").map_elements(key, return_dtype=pl.Utf8).alias("il"),
        pl.col("ilce_adi").map_elements(key, return_dtype=pl.Utf8).alias("ilce"),
        pl.col("name_tr").map_elements(key, return_dtype=pl.Utf8).alias("ad"),
        pl.col("bel_adi").map_elements(key, return_dtype=pl.Utf8).alias("bel"),
    )


def matched(theirs: pl.DataFrame, mine: pl.DataFrame) -> pl.DataFrame:
    """Unique-to-unique join on the three name parts.

    `keep="none"` on both sides is the whole safety argument: a district holding two
    "Merkez" keeps neither. Half of a duplicate pair matched at random would be worse than
    no match, because it would look like an answer.
    """
    on = ["il", "ilce", "ad"]
    return mine.unique(subset=on, keep="none").join(
        theirs.unique(subset=on, keep="none"), on=on, how="inner"
    )


def by_municipality(theirs: pl.DataFrame, mine: pl.DataFrame) -> pl.DataFrame:
    """Belde rows matched to the belediye they are, not to a neighbourhood inside it.

    The two sources count beldes at different grains. 7H writes one row per belde —
    "Araplı", 851 voters — while our registry holds every neighbourhood inside it, and
    those neighbourhoods are called things like "Merkez" and "Yeni". Matching name to
    name therefore misses almost every belde in the country, which is why the first pass
    found 1.646 of them and the country had roughly 1.400 belde belediyeleri worth of
    neighbourhoods left over.

    So the belde is matched where it actually lives: in `municipality`. Every
    neighbourhood under that belediye inherits the origin, because that is what the
    source is saying about them collectively.
    """
    beldes = (
        theirs.filter(pl.col("koken") == "belde")
        .with_columns(pl.col("ad").str.replace(BELDE_MARK.pattern, "").alias("ad"))
        .unique(subset=["il", "ilce", "ad"], keep="none")
    )
    towns = (
        mine.filter(pl.col("bel").is_not_null())
        .select("area_id", "duzey", "il", "ilce", pl.col("bel").alias("ad"))
        .unique(subset=["area_id"])
    )
    return towns.join(beldes, on=["il", "ilce", "ad"], how="inner").select(
        "area_id", "duzey", "koken"
    )


def derived(frame: pl.DataFrame, level: str) -> pl.Expr:
    """Origin worked out from our own registry, for provinces 7H never covered.

    Only defensible outside the 30 metropolitan provinces, and there it is close to a
    definition rather than a guess. Law 6360 left those provinces alone: a village is
    still a village, and a belediye that is not the district's own is a belde belediyesi,
    because those are the only three kinds there are.

    It has one known bias, measured against 7H across the 50 provinces where both exist:
    147 of 2.536 neighbourhoods (5,8%) are villages that were absorbed into the district
    belediye, so they now sit under its name and this rule calls them "kent" when 7H
    calls them "koy". Agreement is 93,7%. That is good enough to publish and not good
    enough to hide, which is what `koken_kaynak` is for.
    """
    if level == "village":
        return pl.lit("koy")
    fold = {"İ": "I", "Ş": "S", "Ğ": "G", "Ü": "U", "Ö": "O", "Ç": "C"}

    def clean(column: str) -> pl.Expr:
        expr = pl.col(column).str.to_uppercase()
        for a, b in fold.items():
            expr = expr.str.replace_all(a, b, literal=True)
        return expr.str.replace_all(" BEL.", "", literal=True).str.strip_chars()

    return (
        pl.when(clean("municipality") == clean("ilce_adi"))
        .then(pl.lit("kent"))
        .otherwise(pl.lit("belde"))
    )


def attach(
    registry: Path, pairs: pl.DataFrame, level: str, uncovered: list[str]
) -> tuple[int, int, int]:
    """Write `koken` and, beside it, where each value came from.

    Two sources in one column would be indistinguishable once written, and one of them is
    a derivation with a known 6% lean. `koken_kaynak` keeps them separable for good, so a
    reader can drop the derived rows and still have a clean answer.
    """
    wanted = pairs.filter(pl.col("duzey") == level).select("area_id", "koken")
    frame = pl.read_csv(registry)
    frame = frame.drop([c for c in ("koken", "koken_kaynak") if c in frame.columns])

    districts = pl.read_csv(DATA / "areas_tr_districts.csv").select(
        pl.col("area_id").alias("ilce_id"), pl.col("name_tr").alias("ilce_adi")
    )
    joined = (
        frame.join(wanted, on="area_id", how="left")
        .with_columns(pl.col("area_id").str.slice(0, 5).alias("il_id"))
        .join(districts, left_on="parent_id", right_on="ilce_id", how="left")
    )
    fill = pl.col("koken").is_null() & pl.col("il_id").is_in(uncovered)
    joined = joined.with_columns(
        pl.when(pl.col("koken").is_not_null())
        .then(pl.lit("7h"))
        .when(fill)
        .then(pl.lit("turetildi"))
        .otherwise(None)
        .alias("koken_kaynak"),
        pl.when(fill)
        .then(derived(joined, level))
        .otherwise(pl.col("koken"))
        .alias("koken"),
    ).drop("il_id", "ilce_adi")
    joined.write_csv(registry)
    return (
        int(joined["koken"].is_not_null().sum()),
        len(joined),
        int((joined["koken_kaynak"] == "turetildi").sum()),
    )


def uncovered_provinces(theirs: pl.DataFrame, mine: pl.DataFrame) -> list[str]:
    """Provinces 7H has no row for at all, and where a village is still a village.

    A province only qualifies if it still has villages in our registry: in the 30
    metropolitan provinces the derivation has nothing to stand on, since every village
    there became a neighbourhood in 2014 and the registry can no longer tell which.
    """
    villages = pl.read_csv(DATA / "areas_tr_villages.csv").with_columns(
        pl.col("area_id").str.slice(0, 5).alias("il_id")
    )
    keeps_villages = set(villages["il_id"].unique().to_list())
    seen = set(theirs["il"].unique().to_list())
    missing = mine.filter(~pl.col("il").is_in(list(seen)))
    return sorted(
        {
            area[:5]
            for area in missing["area_id"].to_list()
            if area[:5] in keeps_villages
        }
    )


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('kullanim: load_7h.py "<...>/AATOPLU 7H.xlsx"')
    source = Path(sys.argv[1])
    if not source.exists():
        raise SystemExit(f"dosya yok: {source}")

    RAW.mkdir(parents=True, exist_ok=True)
    kept = RAW / f"ysk-7h-2015-{datetime.now(UTC):%Y-%m-%d}.xlsx"
    if kept.resolve() != source.resolve():
        shutil.copy2(source, kept)
    digest = hashlib.sha256(kept.read_bytes()).hexdigest()[:16]

    theirs = read_7h(kept)
    mine = ours()
    direct = matched(theirs, mine).select("area_id", "duzey", "koken")
    extra = by_municipality(theirs, mine).join(direct, on="area_id", how="anti")
    pairs = pl.concat([direct, extra])
    print(
        f"7H: {len(theirs)} yerlesim | bizim: {len(mine)} | "
        f"ad eslesmesi: {len(direct)} + belediye eslesmesi: {len(extra)}"
    )
    print(pairs.group_by("koken").len().sort("koken"))

    uncovered = uncovered_provinces(theirs, mine)
    print("7H'de hic gecmeyen, koyu duran il:", uncovered or "yok")

    report = {}
    for level, registry in (
        ("neighbourhood", DATA / "areas_tr_neighbourhoods.csv"),
        ("village", DATA / "areas_tr_villages.csv"),
    ):
        hit, total, made = attach(registry, pairs, level, uncovered)
        report[level] = (hit, total, made)
        print(f"{level}: {hit}/{total} ({100 * hit / total:.1f}%), {made} turetildi")

    manifest = {
        "source_id": SOURCE_ID,
        "dataset": "settlement_origin_7h",
        "file": kept.name,
        "sha256_16": digest,
        "rows": len(theirs),
        "matched": {k: v[0] for k, v in report.items()},
        "of": {k: v[1] for k, v in report.items()},
        "derived": {k: v[2] for k, v in report.items()},
        "derived_for": uncovered,
        "join": "name within district, unique-to-unique",
        "as_of": "2015-06-07",
        "retrieved_at": datetime.now(UTC).strftime("%Y-%m-%d"),
    }
    with (RAW / "manifests.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False) + "\n")
    print("manifest yazildi:", digest)


if __name__ == "__main__":
    main()
