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
from veriatlas.areas import load_areas, load_weights
from veriatlas.config import PUBLIC
from veriatlas.indicators import load
from veriatlas.schema import parse_dims


def export_dictionary(loaded: set[str]) -> None:
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
                    "frequency": ind.frequency,
                    "definition": ind.definition_tr,
                    "available": ind.indicator_id in loaded,
                }
                for ind in indicators
            ],
        }
        for topic, indicators in load().tree()
    ]

    target = PUBLIC / "meta.json"
    target.write_text(
        json.dumps({"tree": tree, "sources": sources()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("yazildi:", target)


def sources() -> list[dict[str, str]]:
    """Where each part of the screen comes from, for the Kaynaklar tab.

    Assembled from the files themselves rather than typed out, so it cannot drift away
    from what was actually loaded.
    """
    fact = pl.read_parquet(PUBLIC / "fact_tfr.parquet")
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
    fact = pl.read_parquet(PUBLIC / "fact_tfr.parquet")
    areas = load_areas().select("area_id", "name_tr")

    assert all(parse_dims(d) == {} for d in fact["dims"].unique()), (
        "this slice assumes no breakdowns; add dimension columns before exporting"
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

    rolled = [to_level(provinces, level) for level in ("region", "nuts1", "nuts2")]
    slim = pl.concat([provinces, *rolled]).sort("level", "area", "year")

    target = PUBLIC / "tfr.csv"
    slim.write_csv(target)
    print("yazildi:", target, slim.height, "satir")

    export_dictionary(set(fact["indicator_id"].unique()))


if __name__ == "__main__":
    main()
