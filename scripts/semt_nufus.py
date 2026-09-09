"""The named settlements inside a province's districts — semts — with their population.

Most of these are former beldeler: municipalities of their own until the 2008 and 2012
metropolitan laws closed them, after which their neighbourhoods went under the district
directly and the name survived only in daily use and in the postal table. They are the
places people actually name when they say where they live, and no official table carries
them any more.

The only country-wide list is the PTT postal code file's `semt_bucak_belde` column, from
2022. Rows where the semt is just the district's own name are dropped: PTT uses the
district name as a single bucket where it has not divided the district, so "Sincan /
Sincan" is a box holding a whole town and names nothing.

Population is TÜİK's neighbourhood series, summed over the neighbourhoods the postal file
assigns to each semt. A semt whose neighbourhoods cannot be matched shows no population
rather than a wrong one; the count of unmatched neighbourhoods is printed.

Run:  uv run python scripts/semt_nufus.py            # Ankara, 2025
      uv run python scripts/semt_nufus.py --il=TR-16 --iladi=BURSA --yil=2025
"""

from __future__ import annotations

import collections
import csv
import gzip
import os
import pathlib
import re
import sys

import openpyxl

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
PTT = HAM / "ptt" / "pk_20220810.xlsx"
TUIK = ROOT / "public" / "population-neighbourhood.csv.gz"


def fold(text: str | None) -> str:
    """An ascii skeleton, so the postal file and TÜİK meet on the same name."""
    if not text:
        return ""
    text = text.strip().upper()
    for a, b in (
        ("İ", "I"),
        ("Ş", "S"),
        ("Ğ", "G"),
        ("Ü", "U"),
        ("Ö", "O"),
        ("Ç", "C"),
    ):
        text = text.replace(a, b)
    text = re.sub(r"\b(MAH|MAHALLESI|MH|KOYU|KOY|BLD|BELDESI)\b\.?", "", text)
    return re.sub(r"[^A-Z0-9]", "", text)


def semt_table(province: str) -> dict[tuple[str, str], str]:
    """{(district, neighbourhood): semt} for one province."""
    book = openpyxl.load_workbook(PTT, read_only=True)
    rows = book[book.sheetnames[0]].iter_rows(values_only=True)
    next(rows)
    out: dict[tuple[str, str], str] = {}
    for il, ilce, semt, mahalle, _code in rows:
        if fold(il) != province:
            continue
        name = (semt or "").strip()
        if not name or fold(name) == fold(ilce):
            continue  # the district's own name is not a semt
        out[(fold(ilce), fold(mahalle))] = name
    return out


def main(argv: list[str]) -> None:
    code = next((a.split("=")[1] for a in argv if a.startswith("--il=")), "TR-06")
    label = next((a.split("=")[1] for a in argv if a.startswith("--iladi=")), "ANKARA")
    year = next((a.split("=")[1] for a in argv if a.startswith("--yil=")), "2025")
    floor = int(next((a.split("=")[1] for a in argv if a.startswith("--min=")), 0))

    table = semt_table(fold(label))
    people: dict[str, list] = collections.defaultdict(lambda: [0, 0, 0, set()])
    missed = 0
    with gzip.open(TUIK, "rt", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not row["area_id"].startswith(code + "-") or row["year"] != year:
                continue
            district, _, neighbourhood = row["area"].partition(" / ")
            semt = table.get((fold(district), fold(neighbourhood)))
            if not semt:
                missed += 1
                continue
            value = int(float(row["value"]))
            bag = people[f"{semt} ({district.strip()})"]
            bag[0] += value
            if row["age"] == "0-17":
                bag[1] += value
            bag[3].add(row["area_id"])

    rows = sorted(
        ((v[0], k, v[1], len(v[3])) for k, v in people.items() if v[0] >= floor),
        reverse=True,
    )
    print(f"{label} · {year} · {len(rows)} semt · eşleşmeyen mahalle satırı {missed:,}")
    print(f"\n{'Semt (ilçe)':<40}{'mahalle':>8}{'nüfus':>10}{'çocuk%':>9}")
    for total, name, child, count in rows:
        print(f"{name:<40}{count:>8}{total:>10,}{100 * child / total:>8.1f}%")
    print(f"\nToplam: {sum(r[0] for r in rows):,} kişi")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
