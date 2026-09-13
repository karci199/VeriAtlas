"""Abroad and customs-gate election results → one long table.

The reports fetched by the 2026-09-13 queue (`C:/veri-ham/secim/<vote>_<yurtdisi|gumruk|
genel>/*.html`) are Oracle Reports HTML, one per election, and none of their rows is an
area of ours: abroad is country → mission → ballot box, customs is province → gate →
ballot box. So they are not map tiles; they become `public/secim-disari.csv.gz` in long
form (election, kind, level, parent, name, measure, value).

Reading a row: the header row carrying "Geçerli oy" names the columns. Before it are
single columns (ballot boxes, registered, voted, turnout %); "Geçerli oy" and every
candidate or party after it take two columns, a count and a share. Only counts are kept —
shares are recomputable and rounded. The ballot-box rows have no box-count column, so they
come one number short; that is how they are told apart, and they are skipped (the atlas
stops above the ballot box).

Checked on write: every mission sums to its country, every gate to its province, every
country or province to the report total, for every measure.

Run:  uv run python scripts/parse_secim_disari.py
"""

import gzip
import pathlib
import re
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
sys.path.insert(0, "src")

import parse_secim as ps

from veriatlas.config import PUBLIC, RAW

ROOT = RAW / "secim"
NUMBER = re.compile(r"^-?(\d[\d.]*(,\d+)?|,\d+)$")  # 2017 writes ",8" for 0,8
SINGLE = {
    "Sandık sayısı ve rumuzu": "ballot_boxes",
    "Sandık sayısı ve numarası": "ballot_boxes",
    "Sandık sayısı": "ballot_boxes",
    "Sandık kurulu sayısı ve rumuzu": "ballot_boxes",
    "Kayıtlı seçmen sayısı": "registered",
    "Oy kullanan seçmen sayısı": "voted",
    "Katılım oranı (%)": None,
}


VOTE_KEYS = {
    "Geçerli oy": "valid",
    "Geçerli oy sayısı": "valid",
    "Geçersiz oy": "invalid",
    "Evet oyları": "votes:Evet",
    "Hayır oyları": "votes:Hayır",
}
#: Header cells that name a row level or the table, not a column of numbers.
FURNITURE = {
    "Ülke",
    "Ülkeler",
    "Temsilcilik",
    "İl",
    "Gümrük kapısı",
    "İl, gümrük kapısı",
    "Geçerli oyların dağılımı",
}


def number(text: str) -> float:
    return float(
        ("0" + text if text.startswith(",") else text)
        .replace(".", "")
        .replace(",", ".")
    )


def read(path: pathlib.Path, vote: str, kind: str) -> list[tuple]:
    html = path.read_bytes().decode("windows-1254", errors="replace")
    rows = [
        [c.strip() for c in ps.cells_of(r) if c.strip()]
        for r in re.findall(
            r"<tr[^>]*>(.*?)</tr>", html, flags=re.DOTALL | re.IGNORECASE
        )
    ]
    rows = [r for r in rows if r]
    # The header is spread over the rows above the first number, in an order that
    # changes between reports (2017 puts the vote columns above the ballot-box ones). The
    # data order does not change: single columns first, then the votes. So the names are
    # gathered, the singles put first, and whether each vote column carries a share is
    # read off the "Sayısı" row being there at all (the MV reports have none).
    first = next(
        i
        for i, r in enumerate(rows)
        if len(r) > 2 and all(NUMBER.match(v) for v in r[1:])
    )
    names = list(
        dict.fromkeys(n for r in rows[1:first] for n in r if n not in FURNITURE)
    )
    shares = any(n in ("Sayısı", "(%)", "Oranı (%)") for r in rows[:first] for n in r)
    singles = [n for n in names if n in SINGLE]
    votes = [
        n for n in names if n not in SINGLE and n not in ("Sayısı", "(%)", "Oranı (%)")
    ]
    if not votes:
        raise ValueError(path.name + ": oy sutunu yok")
    order = ["Sandık", "Kayıtlı", "Oy kullanan", "Katılım"]
    singles.sort(key=lambda n: next(i for i, p in enumerate(order) if n.startswith(p)))
    measures: list[str | None] = [SINGLE[n] for n in singles]
    for name in votes:
        key = VOTE_KEYS.get(name, "votes:" + name)
        measures += [key, None] if shares else [key]

    out, parent = [], ""
    parent_voted: float | None = None
    counted = 0.0
    for row in rows:
        label, values = row[0], row[1:]
        if not values or not all(NUMBER.match(v) for v in values):
            continue
        # A ballot box is named by a letter (customs) or a number (abroad).
        if re.fullmatch(r"[A-ZÇĞİÖŞÜ]{1,2}|\d+(-[A-ZÇĞİÖŞÜ]+)?", label):
            continue
        # Walked, not counted: a zero count is printed without its share, and a share
        # that happens to be whole ("100", "92") has no decimal separator, so neither the
        # number of cells nor their format tells a count from a share. The position does:
        # a share follows a non-zero count, and turnout follows a non-zero electorate.
        # Even that is not kept consistently (2014 prints "0,0" after a zero, 2017 "0"),
        # so a share is taken only while there are more cells left than counts still to
        # read, and only if the cell could be a share (a separator, or a whole number up
        # to 100).
        counts_left = sum(m is not None for m in measures)
        taken, rest = [], list(values)
        for measure in measures:
            if measure is None:
                slack = len(rest) - counts_left
                if (
                    slack > 0
                    and rest
                    and ("," in rest[0] or "." in rest[0] or number(rest[0]) <= 100)
                ):
                    rest.pop(0)
                continue
            if not rest:
                raise ValueError(path.name + ": eksik deger: " + " | ".join(row[:4]))
            taken.append((measure, rest.pop(0)))
            counts_left -= 1
        if rest:
            raise ValueError(path.name + ": fazla deger: " + " | ".join(row[:4]))
        if label.lower().startswith(("yurt dışı toplam", "gümrük kapıları toplam")):
            level = "total"
        elif kind == "yurtdisi":
            mission = re.search(
                r"konsolos|elçili|temsilci|ataşe|toplamı$", label, re.IGNORECASE
            )
            # 2023 names some polling points by city alone ("Bremen", "Long Island").
            # Structure decides for those: a row is a mission while the country above it
            # still has votes left that its missions have not accounted for.
            voted = dict(taken).get("voted")
            fits = (
                voted is not None
                and parent_voted is not None
                and counted + number(voted) <= parent_voted + 0.5
                and counted < parent_voted
            )
            level = "mission" if mission or fits else "country"
            if level == "country":
                parent_voted, counted = number(voted) if voted else None, 0.0
            elif voted:
                counted += number(voted)
        elif kind == "gumruk":
            level = "gate" if "Kapı" in label or "Kapi" in label else "province"
        else:
            level = "total"
        if level in ("country", "province"):
            parent = label
        name = label.removesuffix(" Toplamı")
        for measure, value in taken:
            if measure:
                out.append(
                    (
                        vote,
                        kind,
                        level,
                        parent if level in ("mission", "gate") else "",
                        name,
                        measure,
                        number(value),
                    )
                )
    return out


def check(rows: list[tuple]) -> list[str]:
    problems = []
    by = defaultdict(float)
    for vote, kind, level, parent, name, measure, value in rows:
        by[(vote, kind, level, parent, name, measure)] += value
    sums = defaultdict(float)
    for (vote, kind, level, parent, name, measure), value in by.items():
        if level in ("mission", "gate"):
            sums[(vote, kind, "child", parent, measure)] += value
        if level in ("country", "province"):
            sums[(vote, kind, "top", "", measure)] += value
    for (vote, kind, level, parent, name, measure), value in by.items():
        if level in ("country", "province"):
            child = sums.get((vote, kind, "child", name, measure))
            if child is not None and abs(child - value) > 0.5:
                problems.append(
                    f"{vote} {kind} {name} {measure}: alt {child} != {value}"
                )
        if level == "total" and kind != "genel":
            top = sums.get((vote, kind, "top", "", measure))
            if top is not None and abs(top - value) > 0.5:
                problems.append(f"{vote} {kind} toplam {measure}: {top} != {value}")
    return problems


def main() -> None:
    rows = []
    for folder in sorted(ROOT.glob("*_*")):
        found = re.fullmatch(r"(\w+?)_(yurtdisi|gumruk)", folder.name)
        if not found:
            continue
        for path in sorted(folder.glob("*.html")):
            got = read(path, found.group(1), found.group(2))
            print(folder.name, path.name, len(got), "satir")
            rows += got
    problems = check(rows)
    for p in problems[:20]:
        print("DENETIM:", p)
    if problems:
        raise SystemExit(str(len(problems)) + " tutarsizlik")
    target = PUBLIC / "secim-disari.csv.gz"
    with gzip.open(target, "wt", encoding="utf-8", newline="") as handle:
        handle.write("election,kind,level,parent,name,measure,value\n")
        for r in rows:
            handle.write(
                ",".join(
                    '"' + str(x).replace('"', '""') + '"'
                    if isinstance(x, str)
                    else str(int(x))
                    for x in r
                )
                + "\n"
            )
    print("yazildi:", target, len(rows), "satir")


if __name__ == "__main__":
    main()
