"""Voter education by district, from the TÜİK voter profile.

The profile crosses age with education for every district of every province, so the share
of the electorate that finished higher education can be put side by side across the nine
hundred and seventy-odd districts. Reading is done by `aday_profili`, which checks each
row against its own printed total.

Two cautions the numbers themselves do not carry:

* This is the **registered electorate**, not the population: no one under eighteen, and
  the citizens registered abroad are a separate scope that is not in these files.
* Rows the reader cannot align are counted, not hidden. A district whose report was badly
  read would show a small electorate; the count is printed so it can be seen.

Run:  uv run python scripts/secmen_egitim_ilce.py 2023
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from aday_profili import BUCKETS, PROFIL, read


def collect(year: str) -> tuple[dict[tuple[str, str], dict[str, int]], int]:
    files = sorted(PROFIL.glob(f"secmen/{year}__yas_grubu__egitim_durumu__*.html"))
    if not files:
        raise SystemExit(f"{year}: secmen yas x egitim raporu yok")
    table: dict[tuple[str, str], dict[str, int]] = {}
    unread = 0
    for path in files:
        province = path.stem.split("__")[-1]
        records, bad = read(path)
        unread += bad
        for area, _age, _gender, counts in records:
            key = (province, area)
            row = table.setdefault(key, dict.fromkeys([*BUCKETS, "bilinmeyen"], 0))
            for name, value in counts.items():
                row[name] += value
    return table, unread


def main(year: str) -> None:
    table, unread = collect(year)
    rows = []
    for (province, district), counts in table.items():
        total = sum(counts.values())
        if total < 1000:  # a block this small is a reading failure, not a district
            continue
        rows.append((100 * counts["yükseköğretim"] / total, total, province, district))
    rows.sort(reverse=True)
    print(f"{year}: {len(rows)} ilçe · okunamayan satır {unread:,}")
    print(f"\n{'':4}{'İlçe':<22}{'İl':<16}{'Seçmen':>12}{'Yükseköğretim %':>17}")
    for title, part in (("EN YÜKSEK", rows[:15]), ("EN DÜŞÜK", rows[-15:])):
        print(f"\n{title}")
        for rank, (share, total, province, district) in enumerate(part, 1):
            print(f"{rank:>3} {district:<22}{province:<16}{total:>12,}{share:>16.1f}%")
    weighted = sum(r[0] * r[1] for r in rows) / sum(r[1] for r in rows)
    print(f"\nTürkiye (bu ilçelerin ağırlıklı ortalaması): {weighted:.1f}%")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2023")
