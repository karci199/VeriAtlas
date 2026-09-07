"""Turn the fetched election reports into map-ready tables keyed by our area ids.

The report is a hierarchy — country, province, district, urban/rural caption, settlement —
and the level of a row is given by which column its label sits in, not by its text. A
district called "Merkez" would otherwise be read as the urban/rural caption.

Names are matched to area ids once, here, so the browser never has to: the map carries
`TR-16-006` and this writes `TR-16-006`. Names change between years, ids do not.

Writes, per vote:

    public/tiles/secim-<oy>-ilce.json          {area_id: {k, o, g, v: {aday: oy}}}
    public/tiles/secim-<oy>-mahalle-TR-XX.json  the same per province, loaded on demand

Run:  uv run python scripts/parse_secim.py cb2023t1
      uv run python scripts/parse_secim.py --hepsi
"""

from __future__ import annotations

import csv
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
SECIM = HAM / "secim"
OUT = ROOT / "public" / "tiles"
DATA = ROOT / "src" / "veriatlas" / "data"

NUM = re.compile(r"-?\d+")
AGG = ["sandik", "kayitli", "oy_kullanan", "gecerli"]
SUFFIX = re.compile(r"\s+(mah\.?|mahallesi|köy\.?|köyü|belde|bel\.)\s*$", re.IGNORECASE)
CAPTION = re.compile(
    r"^(İl/İlçe merkezi|Belde/Köy|Yurt içi toplam|Türkiye)$", re.IGNORECASE
)


def fold(name: str) -> str:
    text = SUFFIX.sub("", (name or "").strip()).lower()
    for a, b in zip("İIÇĞÖŞÜçğıöşü", "iicgosucgiosu", strict=False):
        text = text.replace(a, b)
    return "".join(ch for ch in text if ch.isalnum())


def cells_of(row_html: str) -> list[str]:
    """Cells of one <tr>, expanded by colspan so a label's column index means something."""
    out: list[str] = []
    for attrs, inner in re.findall(r"(?is)<t[dh]([^>]*)>(.*?)</t[dh]>", row_html):
        text = re.sub("<[^>]+>", "", inner).replace("&nbsp;", " ").replace("\xa0", " ")
        out.append(re.sub(r"\s+", " ", text).strip())
        span = re.search(r'colspan\s*=\s*"?(\d+)', attrs, re.IGNORECASE)
        out.extend([""] * (int(span.group(1)) - 1 if span else 0))
    return out


def columns_of(rows: list[list[str]]) -> list[str]:
    """The candidate/party columns, in report order, from the header rows."""
    names: list[str] = []
    started = False
    # Header captions are recognised on their folded form, not by a case-insensitive
    # substring: "İl" matched inside "KILIÇDAROĞLU" and quietly dropped a candidate,
    # which shifted every value one column to the left.
    caption_words = (
        "sandik",
        "kayitli",
        "oykullanan",
        "gecerli",
        "gecersiz",
        "katilim",
        "sayisi",
        "orani",
        "bolge",
        "muhtarlik",
        "bucak",
        "dagilimi",
        "ililcebolge",
    )
    # Whole-label captions: "İl" and "İlçe" are also column headers, and they are too
    # short to be matched as substrings without hitting a candidate's name.
    caption_exact = {"il", "ilce", "bolge", "muhtarlikmahalleadi", "yerlesimyeri"}
    for row in rows:
        labels = [c for c in row if c]
        if not labels:
            continue
        if any(NUM.fullmatch(c) for c in labels):
            break
        if not started and not any(
            fold(c).startswith(("sandik", "gecerli")) for c in labels
        ):
            continue
        started = True
        names += [
            c
            for c in labels
            if fold(c) not in caption_exact
            and not any(w in fold(c) for w in caption_words)
        ]
    return names


def read_report(path: pathlib.Path) -> list[dict]:
    """[{level, name, parent_name, values}] for one report file."""
    raw = path.read_text(encoding="windows-1254", errors="replace")
    raw = re.sub(r"(?is)<script.*?</script>", " ", raw)
    rows = [cells_of(r) for r in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw)]
    names = columns_of(rows)
    if not names:
        return []
    width = len(AGG) + len(names)

    out: list[dict] = []
    province = district = None
    for row in rows:
        numbers = [c for c in row if NUM.fullmatch(c)]
        # A round percentage stays an integer and makes the row one value too long; it is
        # always the fourth number (katılım) in the referendum layout.
        if len(numbers) == width + 1:
            numbers = numbers[:3] + numbers[4:]
        if len(numbers) != width:
            continue
        labels = [(i, c) for i, c in enumerate(row) if c and not NUM.fullmatch(c)]
        if not labels:
            continue
        index, label = labels[0]
        if CAPTION.match(label):
            continue
        values = dict(zip(AGG + names, [int(v) for v in numbers], strict=False))
        if index <= 1:
            province, district = label, None
            out.append({"level": "il", "name": label, "parent": None, "values": values})
        elif index <= 3:
            district = label
            out.append(
                {"level": "ilce", "name": label, "parent": province, "values": values}
            )
        elif district:
            out.append(
                {
                    "level": "mahalle",
                    "name": label,
                    "parent": district,
                    "values": values,
                }
            )
    return out


def area_index() -> tuple[dict, dict, dict]:
    """(province by folded name, district by (province, name), neighbourhood by (district, name))."""
    provinces: dict[str, str] = {}
    for row in csv.DictReader((DATA / "areas_tr.csv").open(encoding="utf-8")):
        if row.get("area_level") == "province":
            provinces[fold(row["name_tr"])] = row["area_id"]

    districts: dict[tuple[str, str], str] = {}
    district_name: dict[str, str] = {}
    for row in csv.DictReader((DATA / "areas_tr_districts.csv").open(encoding="utf-8")):
        districts[(row["parent_id"], fold(row["name_tr"]))] = row["area_id"]
        district_name[row["area_id"]] = row["name_tr"]

    hoods: dict[tuple[str, str], str] = {}
    path = DATA / "areas_tr_neighbourhoods.csv"
    if path.exists():
        for row in csv.DictReader(path.open(encoding="utf-8")):
            hoods[(row["parent_id"], fold(row["name_tr"]))] = row["area_id"]
    return provinces, districts, hoods


def main(argv: list[str]) -> None:
    votes = [a for a in argv if not a.startswith("--")]
    if "--hepsi" in argv or not votes:
        votes = sorted(p.name for p in SECIM.iterdir() if p.is_dir())
    provinces, districts, hoods = area_index()
    OUT.mkdir(parents=True, exist_ok=True)

    for vote in votes:
        folder = SECIM / vote
        files = sorted(folder.glob("*.html"))
        if not files:
            continue
        district_out: dict[str, dict] = {}
        hood_out: dict[str, dict[str, dict]] = {}
        unmatched = 0

        for path in files:
            province_id = None
            for record in read_report(path):
                values = record["values"]
                base = {
                    "k": values.get("kayitli", 0),
                    "o": values.get("oy_kullanan", 0),
                    "g": values.get("gecerli", 0),
                    "v": {k: v for k, v in values.items() if k not in AGG and v},
                }
                if record["level"] == "il":
                    province_id = provinces.get(fold(record["name"]))
                elif record["level"] == "ilce" and province_id:
                    area = districts.get((province_id, fold(record["name"])))
                    if area:
                        district_out[area] = base
                        district_out[area]["ad"] = record["name"]
                    else:
                        unmatched += 1
                elif record["level"] == "mahalle" and province_id:
                    parent = districts.get((province_id, fold(record["parent"] or "")))
                    if not parent:
                        continue
                    area = hoods.get((parent, fold(record["name"])))
                    key = area or f"{parent}~{fold(record['name'])}"
                    base["ad"] = record["name"]
                    hood_out.setdefault(province_id, {})[key] = base

        (OUT / f"secim-{vote}-ilce.json").write_text(
            json.dumps(district_out, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        for province_id, rows in hood_out.items():
            (OUT / f"secim-{vote}-mahalle-{province_id}.json").write_text(
                json.dumps(rows, separators=(",", ":"), ensure_ascii=False),
                encoding="utf-8",
            )
        total_hoods = sum(len(v) for v in hood_out.values())
        print(
            f"{vote}: {len(district_out)} ilçe, {total_hoods} yerleşim"
            + (f", {unmatched} eşleşmedi" if unmatched else "")
        )


if __name__ == "__main__":
    main(sys.argv[1:])
