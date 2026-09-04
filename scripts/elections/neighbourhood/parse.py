"""Parse downloaded TUIK election reports into one long-format CSV.

Each report covers one (year, secim cevresi, ilce) and lists neighbourhood-level
rows: sandik sayisi, kayitli secmen, oy kullanan, gecerli oy and per-party votes.

Two layout quirks drive the design:
  * Cells carry colspan, so rows are expanded into positional slots.
  * On some total rows the sandik count is pushed onto a separate stray row,
    leaving that row one value short. Such rows are detected by their first
    value starting far to the right of a normal row, and the orphan sandik on
    the following row is folded back in.

Each report is also checked against the year in its filename; a mismatch would
mean the parallel browser sessions that generated the reports crossed over.
"""

import collections
import csv
import pathlib
import re
import sys

BASE = pathlib.Path(__file__).parent
HTML = BASE / "html"
YEAR_RE = re.compile(r"\d{4}")
NUM_RE = re.compile(r"-?\d+")
AGG = ["sandik", "kayitli_secmen", "oy_kullanan", "gecerli_oy"]


def slots(row_html):
    """Cells of one <tr>, expanded by colspan; empty cells kept as ''."""
    out = []
    for attrs, inner in re.findall(r"(?is)<t[dh]([^>]*)>(.*?)</t[dh]>", row_html):
        text = re.sub("<[^>]+>", "", inner).replace("&nbsp;", " ").replace("\xa0", " ")
        out.append(re.sub(r"\s+", " ", text).strip())
        span = re.search(r'colspan\s*=\s*"?(\d+)', attrs, re.IGNORECASE)
        out.extend([""] * (int(span.group(1)) - 1 if span else 0))
    return out


SKIP = re.compile(
    r"Sandık|Kayıtlı seçmen|Oy kullanan|Geçerli oy|Seçim çevresi|Seçime katılan|Milletvekili",
    re.IGNORECASE,
)


def columns(rows):
    """Column names: the four aggregates plus party/alliance labels.

    The header spans one or two rows; they are the pre-data rows that mention
    the aggregate captions. Everything left after dropping those captions is a
    party or alliance, in report order.
    """
    parties = []
    started = False
    for r in rows:
        labels = [c for c in r if c]
        if not labels:
            continue
        if any(NUM_RE.fullmatch(c) for c in labels):
            break  # data starts
        if not started and not any(
            re.search(r"Sandık|Geçerli oy", c, re.IGNORECASE) for c in labels
        ):
            continue
        started = True
        parties += [c for c in labels if not SKIP.search(c)]
    return AGG + parties


def parse(path):
    raw = path.read_text(encoding="windows-1254", errors="replace")
    raw = re.sub(r"(?is)<script.*?</script>", " ", raw)
    rows = [slots(r) for r in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw)]
    title = next(
        (
            " ".join(c for c in r if c)
            for r in rows
            if "Milletvekili Genel Seçimi" in " ".join(r)
        ),
        "",
    )

    numbered = []
    for r in rows:
        nums = [(i, c) for i, c in enumerate(r) if NUM_RE.fullmatch(c)]
        labels = [c for c in r if c and not NUM_RE.fullmatch(c)]
        numbered.append((r, nums, labels))

    width = collections.Counter(len(n) for _, n, _ in numbered if len(n) > 4)
    if not width:
        raise ValueError("veri satiri yok")
    ncol = width.most_common(1)[0][0]
    first = collections.Counter(n[0][0] for _, n, _ in numbered if len(n) == ncol)
    normal_start = first.most_common(1)[0][0]

    data = []
    for idx, (row, nums, labels) in enumerate(numbered):
        if len(nums) == ncol:
            values = [c for _, c in nums]
        elif len(nums) == ncol - 1 and nums and nums[0][0] > normal_start + 3:
            # sandik pushed onto the next stray row
            nxt = numbered[idx + 1][1] if idx + 1 < len(numbered) else []
            orphan = nxt[0][1] if len(nxt) == 1 and not numbered[idx + 1][2] else ""
            values = [orphan] + [c for _, c in nums]
        else:
            continue
        name = " ".join(labels).strip()
        data.append((name or "(toplam)", values))
    return title, ncol, data


def main():
    files = sorted(f for f in HTML.glob("*.html") if f.stem.count("__") == 2)
    out = BASE / "secim_mahalle.csv"
    problems, n = [], 0
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["yil", "cevre", "ilce", "birim", "olcut", "deger"])
        for f in files:
            yil, cevre, ilce = f.stem.split("__")
            try:
                title, ncol, data = parse(f)
                raw = f.read_text(encoding="windows-1254", errors="replace")
                cols = columns(
                    [
                        slots(r)
                        for r in re.findall(
                            r"(?is)<tr[^>]*>(.*?)</tr>",
                            re.sub(r"(?is)<script.*?</script>", " ", raw),
                        )
                    ]
                )
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{f.stem}: {exc}")
                continue
            got = YEAR_RE.search(title)
            if not got or got.group() != YEAR_RE.search(yil).group():
                problems.append(f"{f.stem}: yil uyusmuyor -> {title[:50]}")
                continue
            if len(cols) != ncol:
                problems.append(f"{f.stem}: sutun sayisi {len(cols)} != {ncol}")
                continue
            for birim, values in data:
                for col, val in zip(cols, values):
                    if val != "":
                        w.writerow([yil, cevre, ilce, birim, col, val])
                        n += 1
    print(f"dosya={len(files)} satir={n} -> {out}")
    for p in problems[:12]:
        print("SORUN", p)
    print("sorun sayisi:", len(problems))


if __name__ == "__main__":
    sys.exit(main())
