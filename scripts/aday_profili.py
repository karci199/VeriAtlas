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
#: Counts are printed with a thousands separator once they get large -- the candidate
#: tables never do, the voter tables always do. Read as a bare digit string, "1.234" is
#: not a number at all, so every voter row failed its own total and the year came out a
#: few hundred thousand people instead of sixty million.
COUNT = re.compile(r"^\d{1,3}(?:\.\d{3})*$|^\d+$")
NUMBER = re.compile(r"-|\d+")
GENDER = ("Erkek", "Kadın")
TOP_MIDPOINT = 78.0

#: Which coarse bucket each printed education heading belongs to. The 2011 report grades
#: candidates in three steps and the later ones in nine; only these three carry across.
BUCKET = {
    # Kept apart from the rest of "ilkokul ve altı": being unable to read at all is a
    # different thing from having left school early, and it is the one that shows what
    # happened to the oldest women. Merged back for the summary table.
    "okumayazmabilmeyen": "okuma yazma bilmeyen",
    "okumayazmabilenfakatbirokul": "ilkokul ve altı",
    # The voter report prints this heading on one line, the candidate report breaks it
    # over two. Unrecognised, the column drops out of the sum, the row misses its own
    # total, and every row of the file is thrown away.
    "okumayazmabilenfakatbirokulbitirmeyen": "ilkokul ve altı",
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
BUCKETS = [
    "okuma yazma bilmeyen",
    "ilkokul ve altı",
    "ortaokul-lise",
    "yükseköğretim",
]
#: How the summary table groups them: the first two are one line.
SUMMARY = {
    "ilkokul ve altı": ("okuma yazma bilmeyen", "ilkokul ve altı"),
    "ortaokul-lise": ("ortaokul-lise",),
    "yükseköğretim": ("yükseköğretim",),
}

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


def read(path: pathlib.Path) -> tuple[list[tuple[str, str, str, dict[str, int]]], int]:
    """([(area, age group, gender, {bucket: count})], rows that could not be read).

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

    out: list[tuple[str, str, str, dict[str, int]]] = []
    bad = 0
    age = None
    # Headers are collected rather than followed. A block's header can be printed over two
    # lines and come out a column adrift, while the rows below it stay in the columns the
    # first block used -- so the newest header is not always the right one. Each row is
    # tried against the headers seen so far, newest first, and the report's own Toplam
    # decides: the reading whose parts reach the printed total is the reading that is kept.
    headers: list[tuple[dict[int, str], int]] = []
    area = None
    for index, row in enumerate(rows):
        found = header_at(rows, index)
        if found:
            if found not in headers:
                headers.append(found)
            # The block's area is written on the header line itself, to the left of the
            # first grade: "Aladağ" beside "Okuma yazma bilmeyen". Looking for it on the
            # lines above instead picks up the province caption and every district of a
            # province comes out under one name.
            edge = min(found[0])
            here = [
                c
                for i, c in enumerate(row)
                if c and i < edge and fold(c) not in BUCKET and fold(c) != "toplam"
            ]
            if here:
                area = here[0]
            continue
        for cell in row:
            if cell and AGE.match(cell):
                age = cell
        gender = next((c for c in row if c in GENDER), None)
        if gender is None or age is None or not headers:
            continue
        # A "Toplam" line repeats the block's people under the last age group it saw;
        # counted, every district would be added twice.
        if any(fold(c) == "toplam" for c in row if c):
            continue

        def value(column: int, row: list[str] = row) -> int:
            cell = row[column] if 0 <= column < len(row) else ""
            return int(cell.replace(".", "")) if COUNT.match(cell) else 0

        counts = zero = None
        # A reading that does not depend on columns at all: the grades in the order the
        # header prints them, the row's numbers in the order it prints them, and the last
        # number as the total. This rescues the blocks whose "Toplam" heading lands on top
        # of another heading -- there the column map loses a grade and the row is then
        # read against some other block's header, which quietly reported no illiterates
        # in places where most of the oldest women cannot read.
        numbers = [
            int(c.replace(".", "")) if c != "-" else 0
            for c in row
            if c and (COUNT.match(c) or c == "-")
        ]
        for columns, _total in reversed(headers):
            labels = [h for _, h in sorted(columns.items())]
            if len(numbers) != len(labels) + 1:
                continue
            if sum(numbers[:-1]) != numbers[-1]:
                continue
            trial = dict.fromkeys([*BUCKETS, "bilinmeyen"], 0)
            for heading, number in zip(labels, numbers, strict=False):
                trial[BUCKET[fold(heading)]] += number
            if sum(trial.values()):
                counts = trial
                break
        # A block's rows can sit a column or two off its own header. The offset is not
        # guessed: every header seen so far is tried at a few offsets and the report's own
        # Toplam decides. A reading that finds nobody satisfies the check trivially, so it
        # is held back and used only if nothing better is found.
        for columns, total_column in reversed(headers):
            for shift in (0, -1, 1, -2, 2):
                trial: dict[str, int] = dict.fromkeys([*BUCKETS, "bilinmeyen"], 0)
                for column, heading in columns.items():
                    trial[BUCKET[fold(heading)]] += value(column + shift)
                if sum(trial.values()) != value(total_column + shift):
                    continue
                if sum(trial.values()):
                    counts = trial
                    break
                zero = zero or trial
            if counts:
                break
        counts = counts or zero
        if counts is None:
            bad += 1
            continue
        # An age group nobody falls into prints as dashes and totals zero; that is a real
        # row. But a row that printed numbers and read as empty was aligned wrongly, and
        # counting it would lose people without a trace.
        if not sum(counts.values()) and any(COUNT.match(c) for c in row if c):
            bad += 1
            continue
        out.append((area or "", age, gender, counts))
    return out, bad


def summarise(page: str) -> None:
    """One line per election year, summed over every report file of that year.

    The candidate pages answer for the whole country in one file; the voter page answers
    per province, eighty-one files a year. Both are added up the same way.
    """
    files = sorted((PROFIL / page).glob("*__yas_grubu__egitim_durumu__*.html"))
    if not files:
        raise SystemExit(f"{PROFIL / page}: yas x egitim raporu yok")
    years: dict[str, list[pathlib.Path]] = {}
    for path in files:
        years.setdefault(path.name.split("__")[0], []).append(path)
    print(
        f"{'Yıl':<9}{'Kişi':>12}{'Ort. yaş':>9}{'Kadın %':>9}"
        + "".join(f"{b:>17}" for b in SUMMARY)
        + "   okunamayan"
    )
    for key in sorted(years, key=lambda k: list(YEAR_LABEL).index(k)):
        total = weighted = women = bad = 0
        buckets = dict.fromkeys([*BUCKETS, "bilinmeyen"], 0)
        for path in years[key]:
            records, missed = read(path)
            bad += missed
            for _, age, gender, counts in records:
                count = sum(counts.values())
                total += count
                weighted += midpoint(age) * count
                if gender == "Kadın":
                    women += count
                for name, value in counts.items():
                    buckets[name] += value
        if not total:
            continue
        line = (
            f"{YEAR_LABEL[key]:<9}{total:>12,}{weighted / total:>9.1f}"
            f"{100 * women / total:>9.1f}"
        )
        line += "".join(
            f"{100 * sum(buckets[p] for p in parts) / total:>16.1f}%"
            for parts in SUMMARY.values()
        )
        print(line + f"{bad:>13}")


if __name__ == "__main__":
    summarise(sys.argv[1] if len(sys.argv) > 1 else "aday")
