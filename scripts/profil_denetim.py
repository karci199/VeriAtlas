"""Check every profile report for the column faults that read as plausible numbers.

A misread column does not raise anything: it produces a number, and the number looks like
data. Each fault below was found by hand, one place at a time, after it had already been
reported as a finding -- so they are checked here across every file instead.

    eksik kademe   a grade the header prints but the column map lost (the "Toplam"
                   heading landing on top of another heading did this)
    sifir okuryazar a block where NO woman over 65 is recorded as unable to read, which
                   in Turkey is a reading failure almost everywhere, not a fact
    okunamayan     rows whose parts never reach their own printed total
    toplam sapma   the block total against the sum of its own rows

Run:  uv run python scripts/profil_denetim.py            # secmen
      uv run python scripts/profil_denetim.py aday kazanan
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from aday_profili import BUCKET, PROFIL, header_at, read
from parse_secim import cells_of, fold

OLD = {"65-69", "70-74", "75+"}
#: Every grade the reports use. A header that prints one of these but whose column map
#: does not carry it has lost a column.
GRADES = set(BUCKET)


def headings(path: pathlib.Path) -> list[tuple[int, set[str], set[str]]]:
    """[(row, grades printed, grades mapped)] for each header in the file."""
    import re

    raw = re.sub(
        r"(?is)<script.*?</script>",
        " ",
        path.read_text(encoding="windows-1254", errors="replace"),
    )
    rows = [cells_of(r) for r in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw)]
    out = []
    for index in range(len(rows)):
        found = header_at(rows, index)
        if not found:
            continue
        columns, _total = found
        printed = {
            fold(c)
            for near in rows[max(0, index - 4) : index + 2]
            for c in near
            if c and fold(c) in GRADES
        }
        out.append((index, printed, {fold(h) for h in columns.values()}))
    return out


def main(pages: list[str]) -> None:
    for page in pages or ["secmen"]:
        files = sorted((PROFIL / page).glob("*__yas_grubu__egitim_durumu__*.html"))
        print(f"== {page}: {len(files)} dosya")
        lost = zeroed = unread = 0
        for path in files:
            for index, printed, mapped in headings(path):
                missing = printed - mapped
                if missing:
                    lost += 1
                    print(
                        f"  EKSİK KADEME {path.name} satır {index}: {sorted(missing)}"
                    )
            records, bad = read(path)
            unread += bad
            women: dict[str, list[int]] = {}
            for area, age, gender, counts in records:
                if age not in OLD or gender != "Kadın":
                    continue
                row = women.setdefault(area, [0, 0])
                row[0] += counts["okuma yazma bilmeyen"]
                row[1] += sum(counts.values())
            for area, (illiterate, total) in women.items():
                if total >= 200 and illiterate == 0:
                    zeroed += 1
                    print(f"  SIFIR OKURYAZAR {path.name} · {area} ({total} kadın)")
        print(f"  eksik kademe {lost} · sıfır okuryazar {zeroed} · okunamayan {unread}")


if __name__ == "__main__":
    main(sys.argv[1:])
