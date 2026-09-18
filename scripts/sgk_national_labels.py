"""Write the Turkish labels of the SGK national classification codes into indicators.toml.

The yearbook tables print each row as "code? Türkçe ad English name". The adapter stores the
code (K1: Turkish is a label, not an id); this script reads the same cells, keeps the latest
year's label for each code, strips the code and the English half, and prints
`[dim.<key>.values]` blocks to paste (or `--write` to append) into the dictionary.

The English half is found as the first capitalised word after which the rest of the label
has no Turkish letters: "Yaralar ve yüzeysel yaralanmalar Wounds and superficial injuries".
A label with no such split is kept whole.
"""

import re
import sys

import polars as pl

sys.path.insert(0, "src")

from veriatlas.adapters.sgk_national import (
    CELLS,
    Unreadable,
    category,
    fold,
    scheme_of,
    topic_of,
)

TURKISH = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
MONTHS = [
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
]
SKIP = {"age", "hour", "workplace_employees", "job_tenure", "occupation", "month"}


def turkish_part(label: str) -> str:
    text = label.split(" | ")[-1].strip()
    text = re.sub(r"^[A-Z]?\d[\d.]*\s*-\s*", "", text)  # "01-", "A15 -", "00.00"
    text = re.sub(r"^\d{2}\.\d{2}\s*", "", text)
    words = text.split()
    for i in range(1, len(words)):
        if words[i].lstrip("-–(")[:1].isupper() and not TURKISH.search(
            " ".join(words[i:])
        ):
            return " ".join(words[:i]).rstrip(" -–,")
    return text


def main() -> None:
    cells = pl.read_parquet(CELLS)
    labels: dict[str, dict[str, str]] = {}
    for (year, title), group in sorted(
        cells.group_by(["year", "title"]), key=lambda x: x[0][0]
    ):
        folded = fold(title)
        found = topic_of(folded)
        if not found or not scheme_of(folded):
            continue
        suffix, key = found
        state: dict = {}
        rows = (
            group.select("block", "row", "code", "label").unique().sort("block", "row")
        )
        for code, label in rows.select("code", "label").iter_rows():
            try:
                cat = category(code, label, suffix, state)
            except Unreadable:
                continue
            if cat in (None, "TOTAL") or key in SKIP:
                continue
            labels.setdefault(key, {})[cat] = turkish_part(label or "")
    labels["month"] = {f"{i:02d}": name for i, name in enumerate(MONTHS, 1)}
    out = []
    for key in sorted(labels):
        out.append(f"\n[dim.{key}.values]")
        for code in sorted(labels[key]):
            value = labels[key][code].replace('"', "'")
            out.append(f'"{code}" = "{value}"')
        out.append('unknown = "Bilinmeyen"' if "unknown" not in labels[key] else "")
        out.append(
            'unallocated = "Dağıtılmamış"' if "unallocated" not in labels[key] else ""
        )
    text = (
        "\n# SGK national classification labels (scripts/sgk_national_labels.py).\n"
        + "\n".join(line for line in out if line != "")
        + "\n"
    )
    if "--write" in sys.argv:
        with open(
            "src/veriatlas/data/indicators.toml", "a", encoding="utf-8"
        ) as handle:
            handle.write(text)
    print(text[:3000])


if __name__ == "__main__":
    main()
