"""Illiteracy among the oldest women in the electorate, by year and by place.

The share is taken **within** a group, not across the whole electorate: of the women aged
65 and over who are registered to vote, how many cannot read. Measured that way it is a
record of who was sent to school seventy years ago, and it falls as those cohorts are
replaced -- so the fall is not a literacy campaign, it is a generation being replaced by
one that went to school.

Men of the same ages are printed beside them, because the gap is the point: the same
villages, the same years, and two very different chances of being taught to read.

Run:  uv run python scripts/okuryazarlik_yasli_kadin.py
      uv run python scripts/okuryazarlik_yasli_kadin.py --il
      uv run python scripts/okuryazarlik_yasli_kadin.py --ilce
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from aday_profili import PROFIL, YEAR_LABEL, read

OLD = {"65-69", "70-74", "75+"}
ILLITERATE = "okuma yazma bilmeyen"


def tally(year: str) -> dict[tuple[str, str], list[int]]:
    """{(area, gender): [illiterate, people]} over the 65-and-over of one year."""
    out: dict[tuple[str, str], list[int]] = {}
    for path in sorted(PROFIL.glob(f"secmen/{year}__yas_grubu__egitim_durumu__*.html")):
        province = path.stem.split("__")[-1]
        records, _ = read(path)
        for area, age, gender, counts in records:
            if age not in OLD:
                continue
            for key in ((province, gender), (f"{area} ({province})", gender)):
                row = out.setdefault(key, [0, 0])
                row[0] += counts[ILLITERATE]
                row[1] += sum(counts.values())
    return out


def share(row: list[int]) -> float:
    return 100 * row[0] / row[1] if row[1] else 0.0


def main(argv: list[str]) -> None:
    years = list(YEAR_LABEL)
    if "--il" in argv or "--ilce" in argv:
        by_district = "--ilce" in argv
        table = tally("2023")
        rows = [
            (share(row), name, row[1])
            for (name, gender), row in table.items()
            if gender == "Kadın"
            and ("(" in name) == by_district
            and row[1] >= (500 if by_district else 0)
        ]
        rows.sort(reverse=True)
        what = "ilçe" if by_district else "il"
        print(f"2023 · 65+ kadın seçmende okuma yazma bilmeyen oranı ({what})")
        for title, part in (("EN YÜKSEK", rows[:12]), ("EN DÜŞÜK", rows[-12:])):
            print()
            print(title)
            for value, name, people in part:
                print(f"  {name:<34}{people:>10,}{value:>8.1f}%")
        return

    print(
        f"{'Yıl':<12}{'65+ kadın':>12}{'okuma yazma bilmeyen':>22}{'65+ erkek':>12}{'':>10}"
    )
    for year in years:
        table = tally(year)
        women = [0, 0]
        men = [0, 0]
        for (name, gender), row in table.items():
            if "(" in name:  # districts only, so the country is counted once
                target = women if gender == "Kadın" else men
                target[0] += row[0]
                target[1] += row[1]
        print(
            f"{YEAR_LABEL[year]:<12}{women[1]:>12,}{share(women):>21.1f}%"
            f"{men[1]:>12,}{share(men):>9.1f}%"
        )


if __name__ == "__main__":
    main(sys.argv[1:])
