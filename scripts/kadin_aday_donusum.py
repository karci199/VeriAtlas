"""Whether a party's women candidates turn into women deputies, party by party.

Every party publishes a share of women among its candidates. That number is easy to raise
and costs nothing: a candidate placed fourth on a list in a province the party wins one
seat in has been nominated, not run. The number that costs something is the share of women
among the people the party actually sent to parliament.

The ratio between the two is what this measures. A party that nominates 30 per cent women
and elects 30 per cent has put them where its seats are; one that nominates 30 and elects
10 has used them to fill the places it does not win. The same arithmetic run on men gives
the mirror image, so the gap is not an artefact of how many candidates each party ran.

Source: the TÜİK candidate and elected-candidate profiles, crossed by party and sex, read
with the reader in `aday_profili`. 2011 and 2023 only -- for 2015 and 2018 TÜİK serves the
elected table in place of the candidate one, which would make every party look perfect.

Run:  uv run python scripts/kadin_aday_donusum.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from aday_profili import COUNT, GENDER, PROFIL, YEAR_LABEL
from parse_secim import cells_of, fold

#: The candidate pages cross sex with party in their own pair of files.
PAIR = "yas_grubu__siyasi_parti_bagimsiz"
#: Years whose candidate report is the candidate report. See the module docstring.
YEARS = ("2011", "2023")


def party_header(
    rows: list[list[str]], index: int
) -> tuple[dict[int, str], int] | None:
    """({column: party}, total column) if this row heads a party table.

    The education reader cannot be reused here: it recognises a heading by matching it
    against the list of school grades, and a party name is in no such list. A party column
    is therefore anything on the heading line that is not the total and not the label of
    the rows -- read positionally, since these reports shift columns from block to block.
    """
    filled = [(i, c) for i, c in enumerate(rows[index]) if c]
    if not any(fold(c) == "toplam" for _, c in filled):
        return None
    totals = [i for i, c in filled if fold(c) == "toplam"]
    columns: dict[int, str] = {}
    for near in rows[max(0, index - 3) : index + 2]:
        for i, c in enumerate(near):
            key = fold(c)
            if not c or key == "toplam" or len(c) < 2:
                continue
            if key in ("yasgrubu", "cinsiyet", "il", "ilce", "bolge") or c in GENDER:
                continue
            if AGE_LIKE(c):
                continue
            columns[i] = c
    total = next((i for i in totals if i not in columns), None)
    return (columns, total) if columns and total is not None else None


def AGE_LIKE(text: str) -> bool:
    import re

    return bool(re.match(r"^\d{2}(-\d{2}|\+)$", text.strip()))


def by_party(page: str, year: str) -> dict[str, dict[str, int]]:
    """{party: {gender: people}} from the sex-by-party report of one year."""
    import re

    found = sorted((PROFIL / page).glob(f"{year}__{PAIR}__*.html"))
    if not found:
        return {}
    out: dict[str, dict[str, int]] = {}
    for path in found:
        raw = re.sub(
            r"(?is)<script.*?</script>",
            " ",
            path.read_text(encoding="windows-1254", errors="replace"),
        )
        rows = [cells_of(r) for r in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw)]
        header = None
        for index, row in enumerate(rows):
            head = party_header(rows, index)
            if head:
                header = head
                continue
            gender = next((c for c in row if c in GENDER), None)
            if gender is None or header is None:
                continue
            if any(fold(c) == "toplam" for c in row if c):
                continue
            columns, total_column = header

            # The row's own total is the check: the parties have to add up to it, or the
            # row was read against the wrong block's columns and is not counted.
            def value(column: int, row: list[str] = row) -> int:
                cell = row[column] if 0 <= column < len(row) else ""
                return int(cell.replace(".", "")) if COUNT.match(cell) else 0

            parts = {p: value(c) for c, p in columns.items()}
            if sum(parts.values()) != value(total_column) or not sum(parts.values()):
                continue
            for party, count in parts.items():
                out.setdefault(party, {}).setdefault(gender, 0)
                out[party][gender] += count
    return out


def main() -> None:
    print("KADIN ADAYIN MİLLETVEKİLİNE DÖNÜŞÜMÜ")
    for year in YEARS:
        aday = by_party("aday", year)
        kazanan = by_party("kazanan", year)
        if not aday or not kazanan:
            print(f"\n{YEAR_LABEL.get(year, year)}: parti kırılımlı rapor yok")
            continue
        print(f"\n{YEAR_LABEL.get(year, year)}")
        print(
            f"{'Parti':<22}{'aday':>7}{'kadın%':>8}"
            f"{'seçilen':>9}{'kadın%':>8}{'dönüşüm':>9}"
        )
        rows = []
        for party, counts in aday.items():
            won = kazanan.get(party)
            if not won:
                continue
            a_total = sum(counts.values())
            w_total = sum(won.values())
            if a_total < 50 or w_total < 5:
                continue
            a_share = 100 * counts.get("Kadın", 0) / a_total
            w_share = 100 * won.get("Kadın", 0) / w_total
            rows.append((w_total, party, a_total, a_share, w_total, w_share))
        rows.sort(reverse=True)
        for _, party, a_total, a_share, w_total, w_share in rows:
            ratio = w_share / a_share if a_share else 0
            print(
                f"{party[:21]:<22}{a_total:>7,}{a_share:>7.1f}%"
                f"{w_total:>9,}{w_share:>7.1f}%{ratio:>8.2f}x"
            )


if __name__ == "__main__":
    sys.exit(main())
