"""Median age per neighbourhood, interpolated from Endeksa's five-year bands.

Endeksa serves fourteen bands (0-4 … 60-64, then 65+). The median is found by walking the
cumulative distribution to the band that crosses half the population and interpolating
inside it. The last band is open-ended, so a neighbourhood whose median falls there cannot
be interpolated and is reported as 65+ rather than given a made-up number.

The estimate is checked against what it implies for the country: summing every
neighbourhood and taking the median of that gives a figure TÜİK also publishes, so the
method can be wrong in a way that is visible rather than silent.

Run:  uv run python scripts/mahalle_ortanca_yas.py [--n=15] [--min=200]
"""

from __future__ import annotations

import json
import pathlib
import sys

HAM = pathlib.Path("C:/veri-ham/endeksa/demography")

BANDS = [(0, 4), (5, 9), (10, 14), (15, 19), (20, 24), (25, 29), (30, 34),
         (35, 39), (40, 44), (45, 49), (50, 54), (55, 59), (60, 64)]
KEYS = [f"Age_{lo}_{hi}_Total" for lo, hi in BANDS] + ["Age_65_Total"]


def median_age(counts: list[float]) -> float | None:
    """Linear interpolation inside the band that crosses the halfway point."""
    total = sum(counts)
    if total <= 0:
        return None
    half, running = total / 2, 0.0
    for index, count in enumerate(counts):
        if running + count >= half:
            if index == len(counts) - 1:
                return None  # 65+ is open-ended; no width to interpolate across
            low = BANDS[index][0]
            return low + 5 * (half - running) / count if count else float(low)
        running += count
    return None


def main(argv: list[str]) -> None:
    n = int(next((a.split("=")[1] for a in argv if a.startswith("--n=")), 15))
    floor = int(next((a.split("=")[1] for a in argv if a.startswith("--min=")), 200))

    rows, country = [], [0.0] * len(KEYS)
    acik_uclu = 0
    for path in sorted(HAM.glob("TR-*.json")):
        for hood in json.loads(path.read_text(encoding="utf-8")).values():
            dem = hood.get("demography") or {}
            counts = [float(dem.get(k) or 0) for k in KEYS]
            for i, c in enumerate(counts):
                country[i] += c
            total = sum(counts)
            if total < floor:
                continue
            age = median_age(counts)
            if age is None:
                acik_uclu += 1
                continue
            rows.append((age, hood.get("name_tr", "?"), dem.get("CountyName", "?"),
                         dem.get("CityName", "?"), int(total)))

    print(f"mahalle: {len(rows):,} (nufus >= {floor}) · 65+ bandinda kalan: {acik_uclu}")
    print(f"ulke geneli ortanca yas (ayni yontemle): {median_age(country):.1f}")

    rows.sort()
    print(f"\n=== EN GENC {n} MAHALLE ===")
    print(f"{'mahalle':22} {'ilce':16} {'il':14} {'yas':>5} {'nufus':>9}")
    for age, ad, ilce, il, pop in rows[:n]:
        print(f"{ad:22} {ilce:16} {il:14} {age:5.1f} {pop:9,}")
    print(f"\n=== EN YASLI {n} MAHALLE ===")
    for age, ad, ilce, il, pop in rows[-n:][::-1]:
        print(f"{ad:22} {ilce:16} {il:14} {age:5.1f} {pop:9,}")


if __name__ == "__main__":
    main(sys.argv[1:])
