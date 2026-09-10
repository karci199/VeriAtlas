"""Voter, candidate and elected ages against the age of the country itself.

Why the electorate barely ages while the country does is the question this answers, and
it needs the two to be measured the same way. Three traps, all of which flatter or
penalise one side:

* The electorate starts at 18. Comparing it to a mean that includes children makes the
  electorate look old by construction, so the population figures are computed twice --
  over everybody, and over the 18-and-over -- and the second is the honest comparison.
* The profile gives age in groups, so its mean is a midpoint estimate. The population is
  therefore binned into the SAME groups and its mean taken the same way; the exact mean is
  printed beside it so the size of the grouping error can be seen rather than assumed.
* The open top group has no upper edge. Both sides use the same assumption for it, so
  whatever it is worth, it is worth the same on both sides.

The population figures are TÜİK's single-year-of-age series (`public/population-age1`),
which reaches province level; there is no district table, so the district cut is voters
only.

Run:  uv run python scripts/yas_karsilastirma.py
      uv run python scripts/yas_karsilastirma.py --il
"""

from __future__ import annotations

import csv
import gzip
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from aday_profili import AGE, PROFIL, TOP_MIDPOINT, midpoint, read

ROOT = pathlib.Path(__file__).resolve().parents[1]
POPULATION = ROOT / "public" / "population-age1.csv.gz"

#: The election years, and the population year each is compared against.
YEARS = {"2011": 2011, "2015 (ort)": 2015, "2018": 2018, "2023": 2023}
#: 2015 went to the polls twice; the two are averaged so the year has one row.
PAIRED = {"2015 (ort)": ("2015_7_haziran", "2015_1_kasim")}
SINGLE = {"2011": ("2011",), "2018": ("2018",), "2023": ("2023",)}

GROUPS = [
    (18, 24),
    (25, 29),
    (30, 34),
    (35, 39),
    (40, 44),
    (45, 49),
    (50, 54),
    (55, 59),
    (60, 64),
    (65, 69),
    (70, 74),
]


def group_midpoint(age: int) -> float:
    """The midpoint the profile would have given this exact age."""
    for low, high in GROUPS:
        if low <= age <= high:
            return (low + high) / 2
    return TOP_MIDPOINT


def population() -> dict[tuple[str, int], dict[int, int]]:
    """{(area, year): {age: people}} for the country and every province."""
    table: dict[tuple[str, int], dict[int, int]] = {}
    with gzip.open(POPULATION, "rt", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            # The single-age file carries the two sexes and no combined line; taking a
            # "total" row that is not there leaves an empty table and every population
            # column reads zero.
            year = int(row["year"])
            if year not in set(YEARS.values()):
                continue
            key = (row["area"], year)
            ages = table.setdefault(key, {})
            # The oldest bucket is written "75+", not a number. Dropping it would take the
            # top of the distribution off and pull every mean down.
            raw = row["age"]
            age = 75 if raw.endswith("+") else int(raw)
            ages[age] = ages.get(age, 0) + int(float(row["value"]))
    return table


def mean_median(ages: dict[int, int], floor: int = 0) -> tuple[float, float, float]:
    """(exact mean, median, mean as the profile's grouping would give it)."""
    items = sorted((a, n) for a, n in ages.items() if a >= floor)
    total = sum(n for _, n in items)
    if not total:
        return 0.0, 0.0, 0.0
    exact = sum(a * n for a, n in items) / total
    binned = sum(group_midpoint(a) * n for a, n in items) / total
    half = total / 2
    running = 0
    median = float(items[-1][0])
    for age, count in items:
        running += count
        if running >= half:
            median = float(age)
            break
    return exact, median, binned


def profile_mean(page: str, keys: tuple[str, ...]) -> tuple[float, int]:
    """(mean age, people) over the reports of these year keys."""
    weighted = total = 0.0
    for key in keys:
        for path in sorted(
            PROFIL.glob(f"{page}/{key}__yas_grubu__egitim_durumu__*.html")
        ):
            records, _ = read(path)
            for _area, age, _gender, counts in records:
                if not AGE.match(age):
                    continue
                count = sum(counts.values())
                total += count
                weighted += midpoint(age) * count
    return (weighted / total if total else 0.0), int(total)


def main(argv: list[str]) -> None:
    ages = population()
    if "--il" in argv or "--ilce" in argv:
        by_district = "--ilce" in argv
        weights: dict[str, list[float]] = {}
        for path in sorted(
            PROFIL.glob("secmen/2023__yas_grubu__egitim_durumu__*.html")
        ):
            province = path.stem.split("__")[-1]
            records, _ = read(path)
            for area, age, _gender, counts in records:
                count = sum(counts.values())
                key = f"{area} ({province})" if by_district else province
                row = weights.setdefault(key, [0.0, 0.0])
                row[0] += midpoint(age) * count
                row[1] += count
        rows = sorted(
            (total_weight / people, name, people)
            for name, (total_weight, people) in weights.items()
            if people >= (1000 if by_district else 0)
        )
        what = "ilçelere" if by_district else "illere"
        print(f"2023 · {what} göre seçmen ortalama yaşı ({len(rows)} birim)")
        for title, part in (("EN GENÇ", rows[:12]), ("EN YAŞLI", rows[-12:])):
            print()
            print(title)
            for mean, name, people in part:
                print(f"  {name:<34}{people:>12,}{mean:>8.1f}")
        return

    print(
        f"{'Yıl':<12}{'Seçmen':>9}{'Aday':>9}{'Seçilen':>9}"
        f"{'TR 18+':>9}{'TR 18+ ortanca':>16}{'TR tüm':>9}{'TR ortanca':>12}"
    )
    for label, year in YEARS.items():
        keys = PAIRED.get(label) or SINGLE[label]
        voter, _ = profile_mean("secmen", keys)
        candidate, _ = profile_mean("aday", keys)
        elected, _ = profile_mean("kazanan", keys)
        country = ages.get(("Türkiye", year)) or {}
        _adult_exact, adult_median, adult_binned = mean_median(country, floor=18)
        whole_exact, whole_median, _ = mean_median(country)
        print(
            f"{label:<12}{voter:>9.1f}{candidate:>9.1f}{elected:>9.1f}"
            f"{adult_binned:>9.1f}{adult_median:>16.1f}{whole_exact:>9.1f}"
            f"{whole_median:>12.1f}"
        )
    print("\nTR 18+ sütunu, seçmen ile aynı yaş gruplarına bölünerek hesaplandı.")


if __name__ == "__main__":
    main(sys.argv[1:])
