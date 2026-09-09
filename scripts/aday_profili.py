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


def header_at(rows: list[list[str]], index: int) -> tuple[dict[int, str], int] | None:
    """({column: education heading}, total column) if this row is a header, else None."""
    filled = [(i, c) for i, c in enumerate(rows[index]) if c]
    if not any(fold(c) == "toplam" for _, c in filled):
        return None
    total = next(i for i, c in filled if fold(c) == "toplam")
    # A heading can be broken over several lines -- "Okuma yazma bilen fakat bir okul"
    # sits one row above "bitirmeyen" -- so the lines around this one are read too.
    columns: dict[int, str] = {}
    for near in rows[max(0, index - 4) : index + 2]:
        for i, c in enumerate(near):
            if c and i != total and fold(c) in BUCKET:
                columns[i] = c
    return (columns, total) if columns else None


def read(path: pathlib.Path) -> tuple[list[tuple[str, str, dict[str, int]]], int]:
    """([(age group, gender, {bucket: count})], rows that could not be read).

    The report is one block per province and it **reprints the header for every block**,
    in different columns each time: İstanbul's total sits in column 29, a small province's
    in column 19. Carrying one header across the file puts every other province's values
    in the wrong grade, or misses them entirely. So the header is picked up again wherever
    it reappears, and each row is read against the one above it.
    """
    raw = re.sub(
        r"(?is)<script.*?</script>",
        " ",
        path.read_text(encoding="windows-1254", errors="replace"),
    )
    rows = [cells_of(r) for r in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw)]

    out: list[tuple[str, str, dict[str, int]]] = []
    bad = 0
    age = None
    header: tuple[dict[int, str], int] | None = None
    for index, row in enumerate(rows):
        found = header_at(rows, index)
        if found:
            header = found
            continue
        for cell in row:
            if cell and AGE.match(cell):
                age = cell
        gender = next((c for c in row if c in GENDER), None)
        if gender is None or age is None or header is None:
            continue
        # A "Toplam" line repeats the block's people under the last age group it saw;
        # counted, every province would be added twice.
        if any(fold(c) == "toplam" for c in row if c):
            continue
        columns, total_column = header

        def value(column: int, row: list[str] = row) -> int:
            cell = row[column] if 0 <= column < len(row) else ""
            return int(cell) if cell.isdigit() else 0

        counts: dict[str, int] = dict.fromkeys([*BUCKETS, "bilinmeyen"], 0)
        for column, heading in columns.items():
            counts[BUCKET[fold(heading)]] += value(column)
        # The report prints the row's own total, so the reading can be checked against it
        # rather than trusted: the parts have to reach the total. A row that fails is
        # counted and reported -- silently dropping it would lose people without a trace.
        if sum(counts.values()) != value(total_column):
            bad += 1
            continue
        out.append((age, gender, counts))
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
