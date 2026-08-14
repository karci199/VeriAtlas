"""Export a browser-sized slice of the fact table for the web screen.

The page is static, so it reads a plain CSV rather than querying the warehouse. Turkish
names are joined in here, not in the page: the fact table stores ids, the registry owns
labels (decision K1).

Run:  uv run python scripts/export_web.py
"""

import json
import sys

import polars as pl

sys.path.insert(0, "src")

from veriatlas.aggregate import to_level
from veriatlas.areas import (
    load_areas,
    load_districts,
    load_neighbourhoods,
    load_weights,
)
from veriatlas.config import PUBLIC
from veriatlas.indicators import load
from veriatlas.schema import parse_dims

#: Which exported file carries which indicator. The page looks the file up here rather
#: than knowing it, so adding an indicator is an export change, not a page change.
DATASETS = {
    "tfr": "tfr.csv",
    "population": "population.csv",
    "median_age": "median_age.csv",
}


def export_dictionary(loaded: set[str], levels: dict[str, list[str]]) -> None:
    """Emit the tree and labels the page renders, so nothing is spelled out in HTML.

    Indicators without data yet still appear, marked unavailable: the tree is the plan
    as much as the inventory, and a greyed-out entry says "not yet" where an absent one
    would say "never".
    """
    tree = [
        {
            "topic": topic.label_tr,
            "indicators": [
                {
                    "id": ind.indicator_id,
                    "label": ind.label_tr,
                    "unit": ind.unit.label_tr,
                    "decimals": ind.unit.decimals,
                    "additive": ind.unit.additive,
                    "frequency": ind.frequency,
                    "definition": ind.definition_tr,
                    "dims": list(ind.dims),
                    "views": list(ind.views),
                    "dataset": DATASETS.get(ind.indicator_id),
                    # Which levels exist, and which of them the page has to go and fetch
                    # before it can draw them. The level menu is built from this rather
                    # than from the rows in hand, or a lazily-held level would be missing
                    # from the menu that is supposed to load it.
                    "levels": levels.get(ind.indicator_id, []),
                    "parts": {
                        level: DATASETS[ind.indicator_id].replace(
                            ".csv", "-" + level + ".csv"
                        )
                        for level in levels.get(ind.indicator_id, [])
                        if level in LAZY_LEVELS and ind.indicator_id in DATASETS
                    },
                    "available": ind.indicator_id in loaded,
                }
                for ind in indicators
            ],
        }
        for topic, indicators in load().tree()
    ]

    # Dimension labels travel with the tree: the page shows "Kadın", the fact table
    # stores `female`, and neither spelling is written into the page (K1).
    dimensions = {
        dim.dim_id: {"label": dim.label_tr, "values": dim.values_tr}
        for dim in load().dimensions.values()
    }

    derivations = {
        d.derivation_id: {
            "label": d.label_tr,
            "unit": d.unit.label_tr,
            "decimals": d.unit.decimals,
            "quality": d.quality,
            "needs_span": d.needs_span,
            "note": d.note_tr,
        }
        for d in load().derivations.values()
    }

    target = PUBLIC / "meta.json"
    target.write_text(
        json.dumps(
            {
                "tree": tree,
                "dimensions": dimensions,
                "derivations": derivations,
                "sources": sources(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("yazildi:", target)


#: Levels whose rows go out in a file of their own, fetched by the page only when the
#: reader asks for that level.
#:
#: District population broken down by sex and age is 973 × 38 × 19 years — around 700.000
#: rows and 50 MB. Shipping that inside the main file would make every visitor download
#: it to look at a province line chart. The page already fetches district *boundaries*
#: per province on demand for the same reason, so this follows the pattern it has.
#:
#: The split has to be by level and complete: a level's rows all live in one file or the
#: other. District totals in one file and district breakdowns in the other would let
#: anything that sums across the breakdown count those districts twice.
#: Neighbourhoods are here for the same reason and more so: Bursa alone is 1061 of them,
#: and the whole country would be around fifty thousand. When the other provinces arrive
#: this will have to split again, per province, the way the district *boundaries* already
#: do — one file per level stops being small enough somewhere around the second province.
LAZY_LEVELS = ("district", "neighbourhood")


def export_broken_down(
    fact: pl.DataFrame, areas: pl.DataFrame, indicator_id: str, whole: bool = True
) -> None:
    """One row per area, year and breakdown value, for an indicator that has dims.

    `whole` says the values are whole numbers — population is counted people, a median
    age is not. Rounding the median to an integer would quietly throw away the only
    interesting digit it has.
    """
    rows = fact.filter(pl.col("indicator_id") == indicator_id)
    if rows.height == 0:
        return

    slim = (
        rows.join(areas, on="area_id", how="left")
        .with_columns(
            pl.col("dims").str.extract(r"age=([^;]+)").alias("age"),
            pl.col("dims").str.extract(r"sex=([^;]+)").alias("sex"),
        )
        .select(
            "area_id",
            pl.col("name_tr").alias("area"),
            # Same column name as the fertility slice: the explorer reads both through
            # one loader and should not have to learn a per-file spelling.
            pl.col("area_level").alias("level"),
            pl.col("period_start").dt.year().alias("year"),
            "age",
            "sex",
            pl.col("value").cast(pl.Int64 if whole else pl.Float64),
            # Provenance travels with the numbers: the screen prints source, vintage and
            # quality straight off the rows it is drawing, so it cannot claim a source
            # the data did not come from.
            "quality_flag",
            "vintage",
            "source_id",
        )
        .sort("area", "year", "sex")
    )

    stem = DATASETS[indicator_id].removesuffix(".csv")
    base = slim.filter(~pl.col("level").is_in(LAZY_LEVELS))
    target = PUBLIC / (stem + ".csv")
    base.write_csv(target)
    print("yazildi:", target, base.height, "satir")

    for level in LAZY_LEVELS:
        part = slim.filter(pl.col("level") == level)
        if part.height == 0:
            continue
        target = PUBLIC / (stem + "-" + level + ".csv")
        part.write_csv(target)
        print("yazildi:", target, part.height, "satir")


def sources() -> list[dict[str, str]]:
    """Where each part of the screen comes from, for the Kaynaklar tab.

    Assembled from the files themselves rather than typed out, so it cannot drift away
    from what was actually loaded.
    """
    fact = pl.read_parquet(PUBLIC / "fact.parquet").filter(
        pl.col("indicator_id") == "tfr"
    )
    weights = load_weights()

    return [
        {
            "kapsam": "Toplam doğurganlık hızı, 81 il × 2009-2025",
            "kaynak": fact["source_id"][0],
            "surum": fact["vintage"][0],
            "cekim": str(fact["retrieved_at"][0]),
            "not": "Dosyada yayım tarihi yok; sürüm çekim ayıyla dolduruldu.",
        },
        {
            "kapsam": "İl listesi, nüfuslar, coğrafi bölgeler",
            "kaynak": weights["source_id"][0],
            "surum": str(weights["vintage"][0]),
            "cekim": str(weights["retrieved_at"][0]),
            "not": "Nüfus, bölge değerlerini ağırlıklandırmak için kullanılıyor.",
        },
        {
            "kapsam": "İBBS-1 / İBBS-2 eşleşmesi",
            "kaynak": "elle tutulan kayıt",
            "surum": "—",
            "cekim": str(weights["retrieved_at"][0]),
            "not": "Kaynak: Wikipedia İBBS tablosu; 81 ilin tamamı doğrulandı.",
        },
        {
            "kapsam": "Bölge ve İBBS değerleri",
            "kaynak": "hesaplandı",
            "surum": "—",
            "cekim": "—",
            "not": "Nüfusla ağırlıklı ortalama. Doğru ağırlık doğurgan çağdaki kadın "
            "nüfusu olduğu için satırlar 'tahmin' işaretli.",
        },
    ]


def main() -> None:
    fact = pl.read_parquet(PUBLIC / "fact.parquet")
    # Districts live in their own registry (they carry validity columns the others do
    # not), so the name lookup is the two files stacked.
    areas = pl.concat(
        [
            load_areas().select("area_id", "name_tr"),
            load_districts().select("area_id", "name_tr"),
            # A neighbourhood's own name is not enough to identify it: a hundred of them
            # repeat inside Bursa alone, seven of them called "Yeni Mah.". The district
            # is part of the label the reader needs, so it is joined on here rather than
            # left to the page.
            load_neighbourhoods()
            .join(
                load_districts().select(
                    pl.col("area_id").alias("parent_id"),
                    pl.col("name_tr").alias("district"),
                ),
                on="parent_id",
                how="left",
            )
            .select(
                "area_id",
                (pl.col("district") + " / " + pl.col("name_tr")).alias("name_tr"),
            ),
        ]
    )

    loaded = set(fact["indicator_id"].unique())

    # What the page is allowed to offer, taken from what was actually exported — the
    # fertility slice gains levels here through the roll-up, and population loses none.
    levels: dict[str, list[str]] = {
        indicator_id: sorted(
            fact.filter(pl.col("indicator_id") == indicator_id)["area_level"].unique()
        )
        for indicator_id in ("population", "median_age")
    }

    export_broken_down(fact, areas, "population")
    export_broken_down(fact, areas, "median_age", whole=False)

    # The line-chart slice below is fertility only; population carries breakdowns and
    # goes out through export_population instead.
    fact = fact.filter(pl.col("indicator_id") == "tfr")
    assert all(parse_dims(d) == {} for d in fact["dims"].unique()), (
        "this slice assumes no breakdowns"
    )
    provinces = fact.join(areas, on="area_id", how="left").select(
        "area_id",
        pl.col("name_tr").alias("area"),
        pl.lit("province").alias("level"),
        pl.col("period_start").dt.year().alias("year"),
        "value",
        "unit",
        "quality_flag",
        "vintage",
        "source_id",
    )

    rolled = [
        to_level(provinces, lvl) for lvl in ("country", "region", "nuts1", "nuts2")
    ]
    slim = pl.concat([provinces, *rolled]).sort("level", "area", "year")

    target = PUBLIC / "tfr.csv"
    slim.write_csv(target)
    print("yazildi:", target, slim.height, "satir")

    levels["tfr"] = sorted(slim["level"].unique())
    export_dictionary(loaded, levels)


if __name__ == "__main__":
    main()
