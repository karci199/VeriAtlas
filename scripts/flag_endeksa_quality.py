"""Mark which Endeksa neighbourhood fields are measured and which are filler.

Endeksa answers for every neighbourhood, but not every answer is data. Three distinct
failures hide behind plausible-looking numbers, and each disables a different group of
fields rather than the whole row:

* `HouseholdCount == 0` — the age bands are all zero too, so population is there but its
  age structure is not. Reading the zeros as "no elderly here" is the trap this guards.
* a `HouseIncome` shared verbatim by many neighbourhoods of one district — the district
  average standing in for a missing local figure. Detected as a value repeated across
  three or more neighbourhoods, not by hard-coding the numbers, which differ per district.
* age bands that do not sum to `PopulationTotal` — a milder inconsistency, reported with
  its size so a threshold can be chosen later rather than assumed here.

Writes raw/endeksa/quality.csv: one row per neighbourhood, one column per field group.

Run:  uv run python scripts/flag_endeksa_quality.py
"""

import collections
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(os.environ.get("VERIATLAS_RAW", ROOT / "raw")) / "endeksa"
SRC = RAW / "demography"
OUT = RAW / "quality.csv"
SHARED_INCOME_MIN = 3


def num(record, key):
    return record.get(key) or 0


def age_total(record):
    return sum(num(record, k) for k in record if k.startswith("Age_") and k.endswith("_Total"))


def main():
    records = []
    for path in sorted(SRC.glob("*.json")):
        for entry in json.loads(path.read_text(encoding="utf-8")).values():
            if entry.get("demography"):
                records.append(entry["demography"])

    shared = collections.defaultdict(collections.Counter)
    for record in records:
        shared[record["CountyId"]][num(record, "HouseIncome")] += 1

    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "district_id", "city", "county", "district", "population",
                "age_ok", "household_ok", "income_ok", "education_ok", "ses_ok",
                "age_gap",
            ]
        )
        counts = collections.Counter()
        for record in records:
            population = num(record, "PopulationTotal")
            household_ok = num(record, "HouseholdCount") > 0
            age_ok = age_total(record) > 0
            income = num(record, "HouseIncome")
            income_ok = bool(income) and shared[record["CountyId"]][income] < SHARED_INCOME_MIN
            education_ok = num(record, "EducationTotal") > 0
            ses_ok = sum(num(record, "SesGroup" + g) for g in ("APlus", "A", "B", "C", "D")) > 0
            gap = age_total(record) - population if age_ok else 0
            writer.writerow(
                [
                    record["DistrictId"], record["CityName"], record["CountyName"],
                    record["DistrictName"], population,
                    int(age_ok), int(household_ok), int(income_ok),
                    int(education_ok), int(ses_ok), gap,
                ]
            )
            counts["toplam"] += 1
            counts["nufus"] += population
            for name, ok in (
                ("yas", age_ok), ("hane", household_ok), ("gelir", income_ok),
                ("egitim", education_ok), ("ses", ses_ok),
            ):
                if not ok:
                    counts[name] += 1
                    counts[name + "_nufus"] += population
            if age_ok and abs(gap) > 2:
                counts["yas_tutmuyor"] += 1

    total, people = counts["toplam"], counts["nufus"]
    print(f"{total} mahalle, {people:,} kisi -> {OUT}")
    for name in ("yas", "hane", "gelir", "egitim", "ses"):
        print(
            f"  {name:8} eksik: {counts[name]:>4} mahalle (%{100 * counts[name] / total:.1f})"
            f"  {counts[name + '_nufus']:>8,} kisi (%{100 * counts[name + '_nufus'] / people:.1f})"
        )
    print(f"  yas bandlari toplami nufusa esit degil: {counts['yas_tutmuyor']} mahalle")


if __name__ == "__main__":
    main()
