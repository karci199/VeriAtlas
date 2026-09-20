r"""The list the map's picker is built from: every indicator it can actually paint.

Without this the page would have to guess. An indicator exists at some levels and not
others, covers some years, and carries breakdowns the reader has to choose between — and
none of that is knowable from the dictionary alone, because a cube is only written where
an export exists. So the catalogue is assembled from what is on disk:

    public/harita/katalog.json

    {"konular": [{"id": "nufus", "ad": "Nüfus", "gostergeler": [
        {"id": "population", "ad": "Nüfus", "birim": "kişi",
         "duzeyler": {"province": {"yillar": [...]}, "district": {...}},
         "tanim": "..."}]}]}

**Only indicators with a cube are listed.** A picker that offers a thousand entries and
then says "bu gösterge haritada yok" a thousand times is worse than a shorter list that
keeps its promise. What is missing is missing for a stated reason — an index with a
breakdown cannot be summed into one number per area — and `build_map_cube.py` prints the
count each run.

Run:  uv run python scripts/build_map_catalog.py
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

from veriatlas.config import PUBLIC
from veriatlas.indicators import load

CUBES = PUBLIC / "harita"
OUT = CUBES / "katalog.json"
#: `yerlesim` is the map's finest layer — neighbourhoods and villages in one cube, built
#: because the map draws them in one layer. It is a level here like any other.
LEVELS = ("province", "district", "yerlesim", "neighbourhood", "village")


def main() -> None:
    dictionary = load()
    by_topic: dict[str, list] = {}

    for name, spec in dictionary.indicators.items():
        stem = name.replace("_", "-")
        levels = {}
        for level in LEVELS:
            path = CUBES / f"{stem}-{level}.json"
            if not path.exists():
                continue
            cube = json.loads(path.read_text(encoding="utf-8"))
            # The slice cubes sit beside the total one, named `<gösterge>-<düzey>--<boyut>-<değer>`.
            # They are listed rather than opened: the picker only needs to know what it
            # may offer, and reading forty files to build a menu is forty files too many.
            slices = []
            for part in sorted(CUBES.glob(f"{stem}-{level}--*.json")):
                key = part.stem.split("--", 1)[1]
                dim, _, value = key.partition("-")
                slices.append({"boyut": dim, "deger": value})
            levels[level] = {
                "yillar": cube["yillar"],
                "alan": len(cube["deger"]),
                "kirilimlar": slices,
            }
        if not levels:
            continue

        by_topic.setdefault(spec.topic.topic_id, []).append(
            {
                "id": name,
                "ad": spec.label_tr,
                "birim": spec.unit.label_tr,
                "siklik": spec.frequency,
                "duzeyler": levels,
                # The definition is the one thing that keeps a choropleth honest: what the
                # number counts, and what it does not. It travels with the indicator.
                "tanim": spec.definition_tr or "",
            }
        )

    # `spec.topic` is the Topic itself; its id keys the grouping so the label and the
    # order can be read back from any one of its indicators.
    labels = {spec.topic.topic_id: spec.topic for spec in dictionary.indicators.values()}
    topics = []
    for topic_id, indicators in sorted(by_topic.items()):
        topic = labels.get(topic_id)
        topics.append(
            {
                "id": topic_id,
                "ad": topic.label_tr if topic else topic_id,
                "sira": topic.order if topic else 999,
                "gostergeler": sorted(indicators, key=lambda item: item["ad"]),
            }
        )
    topics.sort(key=lambda t: (t["sira"], t["ad"]))

    OUT.write_text(
        json.dumps({"konular": topics}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    total = sum(len(t["gostergeler"]) for t in topics)
    print(f"{OUT} · {len(topics)} konu, {total} gösterge, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
