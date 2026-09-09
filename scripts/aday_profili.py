"""Age and education of the candidates who stood, from the TÜİK candidate profile.

Two things make these reports hard to read, and both fail silently:

* An empty cell is **omitted**, not printed as a dash, so a row carries anywhere from six
  to eleven numbers. Reading them in order moves doctorates into master's degrees.
* A row can be shifted a few columns against the header. The gender cell says by how much,
  so the offset is measured per row rather than assumed.

Every row is therefore read by column, and then checked against its own Toplam: the parts
must add up to the total the report prints. Rows that fail are counted and reported, not
quietly dropped.

The education scheme changed: 2011 has three grades, 2015 onwards has nine. Only the three
coarse buckets are comparable across the whole series.

The mean age is an estimate from group midpoints -- the report has no exact ages. "45-49"
is read as 47 and the open top group as 78. Good to about half a year; not evidence for a
change smaller than that.

Run:  uv run python scripts/aday_profili.py           # adaylar
      uv run python scripts/aday_profili.py kazanan   # secilenler
"""

from __future__ import annotations

import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from parse_secim import cells_of, fold

HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
PROFIL = HAM / "secim" / "profil"

AGE = re.compile(r"^(\d{2})-(\d{2})$|^(\d{2})\+$")
NUMBER = re.compile(r"-|\d+")
GENDER = ("Erkek", "Kadın")
TOP_MIDPOINT = 78.0

#: Which coarse bucket each printed education heading belongs to. The 2011 report grades
#: candidates in three steps and the later ones in nine; only these three carry across.
BUCKET = {
    "okumayazmabilmeyen": "ilkokul ve altı",
    "okumayazmabilenfakatbirokul": "ilkokul ve altı",
    "ilkokul": "ilkokul ve altı",
    "ilkogretim": "ortaokul-lise",
    "ortaokulveyadengiokul": "ortaokul-lise",
    "liseveyadengiokul": "ortaokul-lise",
    "ortaokullise": "ortaokul-lise",
    "yuksekokulveyafakulte": "yükseköğretim",
    "yukseklisans": "yükseköğretim",
    "doktora": "yükseköğretim",
    "universiteyuksekokul": "yükseköğretim",
    # Counted so the row's parts can reach its printed total, but kept out of the
    # comparison: an unknown grade is not a grade.
    "bilinmeyen": "bilinmeyen",
}
BUCKETS = ["ilkokul ve altı", "ortaokul-lise", "yükseköğretim"]

YEAR_LABEL = {
    "2011": "2011",
    "2015_7_haziran": "2015 Haz",
    "2015_1_kasim": "2015 Kas",
    "2018": "2018",
    "2023": "2023",
}


def midpoint(label: str) -> float:
    match = AGE.match(label)
    if match.group(3):
        return TOP_MIDPOINT
    return (int(match.group(1)) + int(match.group(2))) / 2


def header_of(rows: list[list[str]]) -> tuple[dict[int, str], int] | None:
    """({column: education heading}, total column), read from the header row."""
    for index, row in enumerate(rows):
        filled = [(i, c) for i, c in enumerate(row) if c]
        if not any(fold(c) == "toplam" for _, c in filled):
            continue
        total = next(i for i, c in filled if fold(c) == "toplam")
        # A heading can be broken over several lines -- "Okuma yazma bilen fakat bir
        # okul" sits one row above "bitirmeyen", and the first grades of the scale can be
        # a row further up still. Taking only the line that carries "Toplam" loses those
        # columns, their counts never reach the printed total, and every row of the report
        # is then thrown away as unreadable.
        columns: dict[int, str] = {}
        for near in rows[max(0, index - 4) : index + 2]:
            for i, c in enumerate(near):
                if c and i != total and fold(c) in BUCKET:
                    columns[i] = c
        if columns:
            return columns, total
    return None


def read(path: pathlib.Path) -> tuple[list[tuple[str, str, dict[str, int]]], int]:
    """([(age group, gender, {bucket: count})], rows whose parts did not add up)."""
    raw = re.sub(
        r"(?is)<script.*?</script>",
        " ",
        path.read_text(encoding="windows-1254", errors="replace"),
    )
    rows = [cells_of(r) for r in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw)]
    found = header_of(rows)
    if not found:
        return [], 0
    columns, total_column = found

    def gender_column(row: list[str]) -> int | None:
        return next((i for i, c in enumerate(row) if c in GENDER), None)

    out: list[tuple[str, str, dict[str, int]]] = []
    bad = 0
    age = None
    for row in rows:
        for cell in row:
            if cell and AGE.match(cell):
                age = cell
        here = gender_column(row)
        if here is None or age is None:
            continue
        # A "Toplam" line repeats the province's people under the last age group it saw;
        # counted, every province would be added twice.
        if any(fold(c) == "toplam" for c in row if c):
            continue

        def read_at(shift: int, row: list[str] = row) -> dict[str, int] | None:
            """The row's counts at this offset, or None if the parts miss the total."""

            def value(column: int) -> int:
                index = column + shift
                cell = row[index] if 0 <= index < len(row) else ""
                return int(cell) if cell.isdigit() else 0

            counts: dict[str, int] = dict.fromkeys([*BUCKETS, "bilinmeyen"], 0)
            for column, heading in columns.items():
                counts[BUCKET[fold(heading)]] += value(column)
            # The report prints the row's own total, so the offset can be *found* rather
            # than assumed: the one where the parts reach the printed total is the right
            # one. A row that no offset satisfies is not counted at all.
            return counts if sum(counts.values()) == value(total_column) else None

        # An age group with no candidate at all prints as dashes and totals zero. It is
        # a real, readable row -- counting it as unreadable made whole years look broken.
        widest = max(len(r) for r in rows)
        fits = [
            found
            for shift in sorted(range(-widest, widest + 1), key=abs)
            if (found := read_at(shift)) is not None
        ]
        # An all-zero read satisfies the check trivially -- parts and total both read as
        # nothing -- so a row aligned at the wrong offset can look empty instead of
        # unreadable, and its people vanish without a warning. A reading that finds
        # somebody is therefore preferred over one that finds nobody.
        counts = next(
            (found for found in fits if sum(found.values())),
            fits[0] if fits else None,
        )
        if counts is None:
            bad += 1
            continue
        # The row printed digits but every offset that satisfied the total read it as
        # empty. That is not an empty row, it is a row this reader cannot align -- the
        # report omits blank cells entirely, so the columns are not a uniform shift of the
        # header. Counted and reported; the alternative is losing people in silence.
        if not sum(counts.values()) and any(c.isdigit() for c in row if c):
            bad += 1
            continue
        out.append((age, row[here], counts))
    return out, bad


def summarise(page: str) -> None:
    files = sorted((PROFIL / page).glob("*__yas_grubu__egitim_durumu__*.html"))
    if not files:
        raise SystemExit(f"{PROFIL / page}: yas x egitim raporu yok")
    order = list(YEAR_LABEL)
    files.sort(key=lambda p: order.index(p.name.split("__")[0]))
    baslik = f"{'Yıl':<9}{'Kişi':>7}{'Ort. yaş':>9}{'Kadın %':>9}"
    print(baslik + "".join(f"{b:>17}" for b in BUCKETS) + "   okunamayan")
    for path in files:
        records, bad = read(path)
        total = weighted = women = 0
        buckets = dict.fromkeys([*BUCKETS, "bilinmeyen"], 0)
        for age, gender, counts in records:
            count = sum(counts.values())
            total += count
            weighted += midpoint(age) * count
            if gender == "Kadın":
                women += count
            for name, value in counts.items():
                buckets[name] += value
        if not total:
            continue
        year = YEAR_LABEL[path.name.split("__")[0]]
        line = (
            f"{year:<9}{total:>7,}{weighted / total:>9.1f}{100 * women / total:>9.1f}"
        )
        line += "".join(f"{100 * buckets[b] / total:>16.1f}%" for b in BUCKETS)
        print(line + f"{bad:>13}")


if __name__ == "__main__":
    summarise(sys.argv[1] if len(sys.argv) > 1 else "aday")
