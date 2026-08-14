"""Export a browser-sized slice of the fact table for the web screen.

The page is static, so it reads a plain CSV rather than querying the warehouse. Turkish
names are joined in here, not in the page: the fact table stores ids, the registry owns
labels (decision K1).

Run:  uv run python scripts/export_web.py
"""

import gzip
import json
import sys

import polars as pl

sys.path.insert(0, "src")

from veriatlas.aggregate import to_level
from veriatlas.areas import (
    load_areas,
    load_districts,
    load_neighbourhoods,
    load_parents,
    load_weights,
)
from veriatlas.config import PUBLIC
from veriatlas.indicators import get, load
from veriatlas.schema import parse_dims


def served(name: str | None) -> str | None:
    """The name the page asks for — every dataset goes out gzipped."""
    return name + ".gz" if name else name


def report(path, frame: pl.DataFrame) -> None:
    size = write_dataset(frame, path)
    print(
        "yazildi:", path.name + ".gz", frame.height, "satir", round(size / 1e6, 2), "MB"
    )


def write_dataset(frame: pl.DataFrame, path) -> int:
    """Write a dataset the page will fetch, gzipped.

    The district slice is 53 MB of CSV and 3.9 MB gzipped — the same numbers, a
    fourteenth of the wire. Compression happens here rather than being left to the
    server because the page has to work off `python -m http.server`, which negotiates
    nothing; the page unpacks it itself with `DecompressionStream`.

    Dropping the four columns that are constant within a file (level, quality flag,
    vintage, source) saves half the *plain* bytes and almost nothing after gzip — 3.6 MB
    against 3.9 — so they stay. Provenance keeps travelling with the rows it describes,
    which is the point of having it there at all.
    """
    target = path.with_suffix(path.suffix + ".gz")
    with gzip.open(target, "wb", compresslevel=6) as handle:
        frame.write_csv(handle)
    return target.stat().st_size


#: Which exported file carries which indicator. The page looks the file up here rather
#: than knowing it, so adding an indicator is an export change, not a page change.
DATASETS = {
    "tfr": "tfr.csv",
    "population": "population.csv",
    "median_age": "median_age.csv",
    "marital_status": "marital.csv",
    "household_by_type": "household-type.csv",
    "foreign_population": "foreign.csv",
    "deaths": "deaths.csv",
    "mean_marriage_age": "marriage-age.csv",
    "mean_first_marriage_age": "first-marriage-age.csv",
    **{
        name: name.replace("_", "-") + ".csv"
        for name in (
            "population_density",
            "household_size",
            "household_count",
            "migration_in",
            "migration_out",
            "migration_net",
            "migration_net_rate",
            "migration_from_abroad",
            "migration_to_abroad",
            "marriages",
            "divorces",
            "registry_population",
            "births",
            "natural_increase",
            "infant_mortality",
            "under5_mortality",
        )
    },
}

#: Indicators that carry breakdowns and so go out through `export_broken_down` rather
#: than the plain line-chart slice. Named once: the same list drives the level map and the
#: files, and having it written out twice is how marital status came to be loaded into the
#: warehouse and then quietly not exported to the page.
BROKEN_DOWN = (
    "population",
    "median_age",
    "marital_status",
    "household_by_type",
    "foreign_population",
    "deaths",
    "mean_marriage_age",
    "mean_first_marriage_age",
)

#: Indicators with no breakdown at all: one value per area and year.
#:
#: Exported at exactly the levels the source published, with no roll-up. Half of these
#: are rates — density, household size, the net migration rate — and a rate does not add
#: up, so rolling one to İBBS means choosing a weighting. That is a decision with a right
#: answer per indicator, not a default, and it is not made here on the way past.
PLAIN = tuple(name for name in DATASETS if name not in BROKEN_DOWN and name != "tfr")


def export_dictionary(
    loaded: set[str],
    levels: dict[str, list[str]],
    fine: dict[str, dict[str, dict]],
) -> None:
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
                    # The page fetches exactly what is named here, extension included,
                    # so the gzip is a fact about the file rather than a rule the page
                    # has to know.
                    "dataset": served(DATASETS.get(ind.indicator_id)),
                    # Which levels exist, and which of them the page has to go and fetch
                    # before it can draw them. The level menu is built from this rather
                    # than from the rows in hand, or a lazily-held level would be missing
                    # from the menu that is supposed to load it.
                    "levels": levels.get(ind.indicator_id, []),
                    "parts": {
                        level: served(
                            DATASETS[ind.indicator_id].replace(
                                ".csv", "-" + level + ".csv"
                            )
                        )
                        for level in levels.get(ind.indicator_id, [])
                        if level in LAZY_LEVELS and ind.indicator_id in DATASETS
                    },
                    # The finest published resolution of a breakdown: the file, and the
                    # levels it covers. The levels matter — single years exist for
                    # provinces and the country but not for districts or neighbourhoods,
                    # and offering the choice where it does not apply is offering a
                    # setting that silently does nothing.
                    "fine": fine.get(ind.indicator_id, {}),
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

    # Coarser readings of a breakdown, for the page to offer next to the raw values.
    groupings = {
        g.grouping_id: {
            "label": g.label_tr,
            "dim": g.dim,
            "covers": {name: list(values) for name, values in g.covers.items()},
            "note": g.note_tr,
        }
        for g in load().groupings.values()
    }

    # One breakdown value against another: a gap, a ratio.
    comparisons = {
        c.comparison_id: {
            "label": c.label_tr,
            "dim": c.dim,
            "plus": c.plus,
            "minus": c.minus,
            "how": c.how,
            "unit": c.unit.label_tr if c.unit else None,
            "decimals": c.unit.decimals if c.unit else None,
            "note": c.note_tr,
        }
        for c in load().comparisons.values()
    }

    # One set of a breakdown's values over another. The page resolves the group names to
    # bands through the grouping, so the level's own band list decides what "65+" covers.
    ratios = {
        r.ratio_id: {
            "label": r.label_tr,
            "dim": r.dim,
            "grouping": r.grouping,
            "over": list(r.over),
            "under": list(r.under),
            "unit": r.unit.label_tr,
            "decimals": r.unit.decimals,
            "note": r.note_tr,
        }
        for r in load().ratios.values()
    }

    derivations = {
        d.derivation_id: {
            "label": d.label_tr,
            # Null where the derivation keeps the indicator's own unit and precision.
            "unit": d.unit.label_tr if d.unit else None,
            "decimals": d.unit.decimals if d.unit else None,
            "quality": d.quality,
            "needs_span": d.needs_span,
            "note": d.note_tr,
        }
        for d in load().derivations.values()
    }

    # Which bigger area each province belongs to, in both hierarchies. Two hundred-odd
    # short strings, and they let the map draw levels that have no boundary file of their
    # own: an İBBS region is exactly a set of provinces, so it can be painted as those
    # provinces sharing one colour. Without this the map tab is dead at four of the five
    # levels the fertility rate is published at.
    # A province sits in two hierarchies at once, so it has a parent in each; walking up
    # both and keeping every ancestor is what lets the page ask "is this province inside
    # TR51" without knowing which hierarchy TR51 belongs to.
    memberships: dict[tuple[str, str], str] = {}
    for row in load_parents().to_dicts():
        memberships[(row["hierarchy"], row["area_id"])] = row["parent_id"]

    provinces = set(load_areas().filter(pl.col("area_level") == "province")["area_id"])
    ancestors: dict[str, list[str]] = {}
    for province in sorted(provinces):
        chain: set[str] = set()
        for hierarchy, area in list(memberships):
            if area != province:
                continue
            node = memberships[(hierarchy, area)]
            while node and node != "TR":
                chain.add(node)
                node = memberships.get((hierarchy, node))
        ancestors[province] = sorted(chain)

    # The names of those ancestors. `belongs` alone carries ids, and an id is not a thing
    # to put in front of a reader: a box offering "TR-R-akdeniz" and "TR62" is a box
    # nobody can use. Only the areas actually named in `belongs`, so this stays a few
    # dozen strings rather than the whole registry.
    named = {area for chain in ancestors.values() for area in chain}
    labels = {
        row["area_id"]: row["name_tr"]
        for row in load_areas().to_dicts()
        if row["area_id"] in named
    }
    missing = named - set(labels)
    if missing:
        # A parent with no name would print as its own id and the reader would meet a
        # code. Louder than letting it through, because it is the registry that is wrong.
        raise KeyError("kayitta adi olmayan ust alan: " + ", ".join(sorted(missing)))

    target = PUBLIC / "meta.json"
    target.write_text(
        json.dumps(
            {
                "tree": tree,
                "dimensions": dimensions,
                "groupings": groupings,
                "comparisons": comparisons,
                "ratios": ratios,
                "derivations": derivations,
                "belongs": ancestors,
                "area_labels": labels,
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


def to_five_year_bands(frame: pl.DataFrame) -> pl.DataFrame:
    """Fold single years of age into five-year bands for the browser.

    The fact table keeps single years because that is what TÜİK publishes and coarser
    groupings are exact sums of it. The page does not need that much: seventy-six bands
    per area-year is 236.816 rows and 1,6 MB against 0,3 MB, on the file every visitor
    downloads before anything is drawn.

    So the export is the boundary between the two. Bands that are not plain numbers pass
    through untouched — the district export already arrives banded, the neighbourhood one
    is split at 18 — and only the single years are folded. When a grouping the screen
    wants does not fall on a five-year boundary, the single years are still in the
    warehouse to build it from.
    """
    if "age" not in frame.columns:
        return frame

    single = pl.col("age").str.contains(r"^\d+$")
    banded = (
        pl.when(single)
        .then(
            ((pl.col("age").cast(pl.Int32, strict=False) // 5) * 5).cast(pl.String)
            + "-"
            + ((pl.col("age").cast(pl.Int32, strict=False) // 5) * 5 + 4).cast(
                pl.String
            )
        )
        .otherwise(pl.col("age"))
    )

    keys = [c for c in frame.columns if c not in ("age", "value")]
    return (
        frame.with_columns(banded.alias("age"))
        .group_by([*keys, "age"])
        .agg(pl.col("value").sum())
        .select(frame.columns)
    )


def export_plain(
    fact: pl.DataFrame, areas: pl.DataFrame, indicator_id: str
) -> list[str]:
    """An indicator with no breakdown: one row per area and year. Returns its levels."""
    rows = fact.filter(pl.col("indicator_id") == indicator_id)
    if rows.height == 0:
        return []

    slim = (
        rows.join(areas, on="area_id", how="left")
        .select(
            "area_id",
            pl.col("name_tr").alias("area"),
            pl.col("area_level").alias("level"),
            pl.col("period_start").dt.year().alias("year"),
            pl.col("value").cast(
                pl.Int64 if get(indicator_id).unit.decimals == 0 else pl.Float64
            ),
            "quality_flag",
            "vintage",
            "source_id",
        )
        .sort("level", "area", "year")
    )
    report(PUBLIC / DATASETS[indicator_id], slim)
    return sorted(slim["level"].unique())


def export_broken_down(
    fact: pl.DataFrame, areas: pl.DataFrame, indicator_id: str, whole: bool = True
) -> dict[str, dict]:
    """One row per area, year and breakdown value, for an indicator that has dims.

    `whole` says the values are whole numbers — population is counted people, a median
    age is not. Rounding the median to an integer would quietly throw away the only
    interesting digit it has.
    """
    rows = fact.filter(pl.col("indicator_id") == indicator_id)
    if rows.height == 0:
        return

    # Which breakdowns to unpack comes from the dictionary, not from a pair written out
    # here. Hard-coded to age and sex, this dropped marital status on the floor — and not
    # loudly: without the column the rows folded together, so 184.827 rows left as 47.232
    # with the married, the divorced and the widowed silently added into one number. The
    # file looked fine and said something false.
    dims = list(get(indicator_id).dims or [])

    slim = (
        rows.join(areas, on="area_id", how="left")
        .with_columns(
            *[pl.col("dims").str.extract(dim + r"=([^;]+)").alias(dim) for dim in dims]
        )
        .select(
            "area_id",
            pl.col("name_tr").alias("area"),
            # Same column name as the fertility slice: the explorer reads both through
            # one loader and should not have to learn a per-file spelling.
            pl.col("area_level").alias("level"),
            pl.col("period_start").dt.year().alias("year"),
            *dims,
            pl.col("value").cast(pl.Int64 if whole else pl.Float64),
            # Provenance travels with the numbers: the screen prints source, vintage and
            # quality straight off the rows it is drawing, so it cannot claim a source
            # the data did not come from.
            "quality_flag",
            "vintage",
            "source_id",
        )
        # Sorted on whatever breakdowns this indicator has, for the same reason the fold
        # is sorted: gzip lives on neighbouring rows looking alike.
        .sort("area", "year", *dims)
    )

    # Single years, where the fact table has them, go out in a file of their own for the
    # reader who asks for that resolution. It is a *replacement* for the banded rows at
    # those levels, never an addition: holding both would mean summing across `age`
    # counted everyone twice, the same trap K14 sets out for levels.
    #
    # Selected by *level*, not by whether a row's own age is a single year. Filtering on
    # the age itself dropped the closing band — the file's tail is "75+", which is not a
    # number — and the resolution came up 496.393 people short of itself at İstanbul.
    # A resolution has to carry the whole distribution or it is not one.
    #
    # Only asked of an indicator that has an age breakdown at all. The extraction used to
    # be hard-coded, so every indicator carried an `age` column even when it meant
    # nothing; driven by the dictionary, the median age has no such column and asking
    # about single years there is asking about a column that does not exist.
    stem = DATASETS[indicator_id].removesuffix(".csv")
    declared: dict[str, dict] = {}
    fine_levels = (
        slim.filter(pl.col("age").str.contains(r"^\d+$"))["level"].unique().to_list()
        if "age" in dims
        else []
    )
    if fine_levels:
        report(
            PUBLIC / (stem + "-age1.csv"),
            slim.filter(pl.col("level").is_in(fine_levels)),
        )
        declared["age"] = {
            "file": served(stem + "-age1.csv"),
            "levels": sorted(fine_levels),
        }

    # After the slim select, so the fold groups on what the page will actually read.
    # Done any earlier, the untouched `dims` column still carries the single year and
    # every row stays distinct — the aggregation runs and changes nothing.
    #
    # Sorted *again* afterwards: group_by returns rows in whatever order it finished in,
    # and gzip lives on neighbouring rows looking alike. Folding after the sort and
    # writing the result straight out took the district file from 3,9 MB to 8,9.
    slim = to_five_year_bands(slim).sort("area", "year", *dims)

    base = slim.filter(~pl.col("level").is_in(LAZY_LEVELS))
    report(PUBLIC / (stem + ".csv"), base)

    for level in LAZY_LEVELS:
        part = slim.filter(pl.col("level") == level)
        if part.height:
            report(PUBLIC / (stem + "-" + level + ".csv"), part)

    return declared


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
        for indicator_id in BROKEN_DOWN
    }

    # `whole=False` where the unit does not add up: a median has no total to be a share
    # of. Marital status is a count, so it does.
    fine = {
        "population": export_broken_down(fact, areas, "population"),
        "median_age": export_broken_down(fact, areas, "median_age", whole=False),
        "marital_status": export_broken_down(fact, areas, "marital_status"),
        "household_by_type": export_broken_down(fact, areas, "household_by_type"),
        "foreign_population": export_broken_down(fact, areas, "foreign_population"),
        "deaths": export_broken_down(fact, areas, "deaths"),
        # `whole=False` for the same reason the median age has it: an age is a position,
        # not a quantity, so "men plus women" is not a total anyone can use.
        "mean_marriage_age": export_broken_down(
            fact, areas, "mean_marriage_age", whole=False
        ),
        "mean_first_marriage_age": export_broken_down(
            fact, areas, "mean_first_marriage_age", whole=False
        ),
    }

    for indicator_id in PLAIN:
        levels[indicator_id] = export_plain(fact, areas, indicator_id)

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

    report(PUBLIC / "tfr.csv", slim)

    levels["tfr"] = sorted(slim["level"].unique())
    export_dictionary(loaded, levels, fine)


if __name__ == "__main__":
    main()
