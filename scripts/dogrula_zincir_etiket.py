r"""Where a chain's own district label and its coordinate disagree — and how far apart.

`chain_stores` places every branch by coordinate, for good reasons written down in that
module: a chain's published district is its marketing geography, it folds Turkish letters
away in slugs, and two of the sources leave it blank. But a coordinate can be wrong too,
and when it is, the store does not disappear — it moves to a neighbouring district and is
counted there. Nothing downstream can see that.

This script makes it visible. For every brand whose dump carries both a coordinate and the
chain's own province/district, it compares the two and measures the distance from the
point to the labelled district's bounding box:

* **under 10 km** — a boundary case. The districts touch, the shop sits near the line, and
  the coordinate is the better answer. Ordinary.
* **over 10 km** — one of the two is broken. `BURSA İZNİK KALE MAĞAZASI` carries İznik in
  its name and an address in İznik's Selçuklu neighbourhood, with a coordinate 35 km away
  in Gemlik; `ÇEKMEKÖY LARA SOK. MAĞAZASI` is 975 km from Çekmeköy, in Çamlıhemşin.

Nothing is corrected *here*: this script measures, and `chain_stores.agreed_area` acts.
The two are kept apart because the measurement is the thing that justifies the rule and
has to stay readable on its own.

The rule cannot simply prefer the label, because both fields fail, in opposite directions
and in different brands: ŞOK's labels are sound and some of its coordinates are typos,
while Koçtaş files Ankamall — which stands in Yenimahalle — under `HAMAMÖZÜ`, an Amasya
district. So the adapter asks a third source, the store's own name and address, and moves
a store to its label only when that text names the labelled district too. Run this script
after any refetch: a brand whose `UZAK` column jumps has changed how it writes one of the
two fields.

Run:  uv run python scripts/dogrula_zincir_etiket.py [--uzak-km 10]
"""

from __future__ import annotations

import argparse
import csv
import math
import sys

sys.path.insert(0, "src")

from veriatlas.adapters.chain_stores import _districts, dump, locate
from veriatlas.areas import (
    CENTRE,
    DISTRICT_ALIASES,
    PROVINCE_ALIASES,
    load_areas,
    load_districts,
)

#: Brand -> (province column, district column). Only the dumps that carry both.
LABELLED = {
    "sok": ("province", "district"),
    "dominos": ("province", "district"),
    "vestel": ("il", "ilce"),
    "koctas": ("il", "kaynak_ilce"),
    "burger_king": ("il", "ilce"),
}


def upper_tr(text: str) -> str:
    """`i` -> `İ` before upper(), which otherwise turns `İznik` into `IZNIK`."""
    return text.replace("i", "İ").replace("ı", "I").upper()


def registry() -> tuple[dict, dict, dict]:
    areas = load_areas()
    provinces = {
        upper_tr(row["name_tr"]): row["area_id"]
        for row in areas.filter(areas["area_level"] == "province").iter_rows(named=True)
    }
    districts, names = {}, {}
    for row in load_districts().iter_rows(named=True):
        districts[(row["parent_id"], upper_tr(row["name_tr"]))] = row["area_id"]
        names[row["area_id"]] = row["name_tr"]
    return provinces, districts, names


def labelled_area(
    row: dict, columns: tuple[str, str], provinces, districts
) -> str | None:
    province = upper_tr(row[columns[0]].strip())
    province = upper_tr(PROVINCE_ALIASES.get(province.title(), province))
    parent = provinces.get(province)
    if parent is None:
        return None
    district = upper_tr(row[columns[1]].strip())
    if district == upper_tr(CENTRE):
        district = province
    for (alias_parent, alias), real in DISTRICT_ALIASES.items():
        if alias_parent == parent and upper_tr(alias) == district:
            district = upper_tr(real)
            break
    return districts.get((parent, district))


def kilometres(lng: float, lat: float, area: str, boxes: dict) -> float | None:
    box = boxes.get(area)
    if box is None:  # an abolished district has no polygon
        return None
    x0, y0, x1, y1 = box
    dx = max(x0 - lng, 0, lng - x1) * 111_320 * math.cos(math.radians(lat))
    dy = max(y0 - lat, 0, lat - y1) * 111_320
    return math.hypot(dx, dy) / 1000


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zincir etiketi ile koordinat karşılaştırması"
    )
    parser.add_argument("--uzak-km", type=float, default=10.0)
    parser.add_argument("--ornek", type=int, default=5)
    args = parser.parse_args()

    provinces, districts, names = registry()
    boxes = {area: box for area, _rings, box in _districts()}

    for brand, columns in LABELLED.items():
        try:
            path = dump(brand)
        except FileNotFoundError:
            print(f"{brand:<12} dökümü yok, atlandı")
            continue
        same = near = far = skipped = 0
        worst = []
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    lng, lat = float(row["lng"]), float(row["lat"])
                except (KeyError, ValueError):
                    skipped += 1
                    continue
                by_point = locate(lng, lat)
                by_label = labelled_area(row, columns, provinces, districts)
                if by_point is None or by_label is None:
                    skipped += 1
                    continue
                if by_point == by_label:
                    same += 1
                    continue
                distance = kilometres(lng, lat, by_label, boxes)
                if distance is None:
                    skipped += 1
                    continue
                if distance > args.uzak_km:
                    far += 1
                    worst.append(
                        (
                            distance,
                            (row.get("name") or row.get("ad") or "")[:34],
                            names.get(by_label),
                            names.get(by_point),
                        )
                    )
                else:
                    near += 1
        compared = same + near + far
        if not compared:
            print(f"{brand:<12} karşılaştırılabilir satır yok")
            continue
        print(
            f"{brand:<12} {compared:>6,} karşılaştırıldı | aynı %{same / compared * 100:5.2f}"
            f" | sınır (<{args.uzak_km:.0f} km) {near:>4} | UZAK {far:>4}"
            f" (%{far / compared * 100:.2f}) | atlanan {skipped}"
        )
        worst.sort(reverse=True)
        for distance, name, label, point in worst[: args.ornek]:
            print(f"    {distance:6.0f} km  {name:<36} {label} -> {point}")


if __name__ == "__main__":
    main()
