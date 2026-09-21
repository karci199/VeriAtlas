"""Parse district-level TUIK election reports into one long-format CSV.

One report covers every district of one electoral district in one election.
Layout differs by era: reports from 1961-1987 carry no "Sandık sayısı" column
and follow each district row with a percentage row, and every report opens with
a Türkiye row. Column names are taken from the report's own header row, so both
eras are handled without hard-coded column lists.

Percentage rows are skipped (their numbers contain a comma) and the Türkiye row
is kept, labelled as such, since it is a useful cross-check.
"""

import csv
import pathlib
import re
import sys

BASE = pathlib.Path(__file__).parent
HTML = BASE / "html"
INT = re.compile(r"-?\d+")
YEAR = re.compile(r"\d{4}")


def slots(row_html):
    """Cells of one <tr>, expanded by colspan; empty cells kept as ''."""
    out = []
    for attrs, inner in re.findall(r"(?is)<t[dh]([^>]*)>(.*?)</t[dh]>", row_html):
        text = re.sub("<[^>]+>", "", inner).replace("&nbsp;", " ").replace("\xa0", " ")
        out.append(re.sub(r"\s+", " ", text).strip())
        span = re.search(r'colspan\s*=\s*"?(\d+)', attrs, re.IGNORECASE)
        out.extend([""] * (int(span.group(1)) - 1 if span else 0))
    return out


IL_ALIAS = {"afyon": "afyonkarahisar", "icel": "mersin", "kmaras": "kahramanmaras"}


def slug(t):
    t = t.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("çğıöşü", "cgiosu"):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", t)


def il_uyuyor(cevre, adlar):
    """Does one of the report's leading rows name the requested province?"""
    bek = slug(re.sub(r"_\d+$", "", cevre))
    bek = IL_ALIAS.get(bek, bek)
    for ad in adlar:
        s = slug(ad)
        s = IL_ALIAS.get(re.sub(r"\d+$", "", s), s)
        if s.startswith(bek) or bek.startswith(s.rstrip("0123456789")) and len(s) > 3:
            return True
    return False


def parse(path):
    raw = re.sub(
        r"(?is)<script.*?</script>",
        " ",
        path.read_text(encoding="windows-1254", errors="replace"),
    )
    rows = [slots(r) for r in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw)]

    title = next(
        (
            " ".join(c for c in r if c)
            for r in rows
            if "Milletvekili Genel Seçimi" in " ".join(r)
        ),
        "",
    )
    # The report title also starts with "Seçim çevresi ve ...", so the header is
    # found by its measure captions. In some years the party names sit on a
    # following row, so label-only rows are consumed until the data begins.
    start = next(
        (i for i, r in enumerate(rows) if any("Kayıtlı seçmen" in c for c in r)), None
    )
    if start is None:
        raise ValueError("baslik satiri yok")
    labels = []
    for r in rows[start:]:
        cells = [c for c in r if c]
        if not cells:
            continue
        if any(INT.fullmatch(c) for c in cells):
            break
        labels += cells

    # Header captions are not always laid out in data order: in 1999 the measure
    # row precedes the row-name/"Sandık sayısı" row. Rebuild the column list in
    # the order the data actually uses.
    def take(pred):
        for i, c in enumerate(labels):
            if pred(c):
                return labels.pop(i)
        return None

    take(lambda c: c.startswith("Seçim çevresi ve"))
    fixed = [
        take(lambda c, k=k: k in c)
        for k in ("Sandık", "Kayıtlı seçmen", "Oy kullanan", "Geçerli oy")
    ]
    cols = [c for c in fixed if c] + labels

    data = []
    for r in rows:
        cells = [c for c in r if c]
        if not cells or cells == labels[: len(cells)]:
            continue
        nums = [c for c in cells if INT.fullmatch(c)]
        if len(nums) != len(cols):
            continue  # percentage rows and layout rows fall out here
        name = " ".join(c for c in cells if not INT.fullmatch(c)).strip()
        if not name:
            continue
        data.append((name, nums))
    return title, cols, data


def main():
    files = sorted(HTML.glob("*.html"))
    out = BASE / "secim_ilce.csv"
    problems, n = [], 0
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["yil", "cevre", "birim", "olcut", "deger"])
        for f in files:
            yil, _, cevre = f.stem.partition("__")
            try:
                title, cols, data = parse(f)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{f.stem}: {exc}")
                continue
            got = YEAR.search(title)
            if not got or got.group() != YEAR.search(yil).group():
                problems.append(f"{f.stem}: yil uyusmuyor -> {title[:50]}")
                continue
            # The report must also be for the province that was requested: a
            # click that fails to register leaves the previous constituency
            # selected, and the alphabetically preceding province is returned
            # instead (Bitlis for Bolu, Malatya for Manisa).
            if data and not il_uyuyor(cevre, [ad for ad, _ in data[:3]]):
                problems.append(f"{f.stem}: il uyusmuyor -> {[a for a, _ in data[:3]]}")
                continue
            if not data:
                problems.append(f"{f.stem}: veri satiri yok")
                continue
            for birim, values in data:
                for col, val in zip(cols, values):
                    w.writerow([yil, cevre, birim, col, val])
                    n += 1
    print(f"dosya={len(files)} satir={n} -> {out}")
    for p in problems[:15]:
        print("SORUN", p)
    print("sorun sayisi:", len(problems))


if __name__ == "__main__":
    sys.exit(main())
