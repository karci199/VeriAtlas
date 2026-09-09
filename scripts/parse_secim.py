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
    r"^(İl/İlçe merkezi|Belde/Köy|Yurt içi toplam|Türkiye|Şehir)$",
    re.IGNORECASE,
)


def fold(name: str) -> str:
    text = SUFFIX.sub("", (name or "").strip()).lower()
    for a, b in zip("İIÇĞÖŞÜçğıöşüâîûÂÎÛ", "iicgosucgiosuaiuaiu", strict=False):
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
        # The milletvekili reports head their label column "Seçim çevresi ve ilçe" and
        # the local ones "İlçe / Belediye adı / Muhtarlık". Without these the label column
        # is counted as a party, every row comes out one value too short, and the file
        # parses to nothing at all — which is what "mv2023: 0 yerlesim" was.
        "secimcevresi",
        "belediyeadi",
        "mahalleadi",
    )
    # Whole-label captions: "İl" and "İlçe" are also column headers, and they are too
    # short to be matched as substrings without hitting a candidate's name.
    caption_exact = {
        "il",
        "ilce",
        "bolge",
        "muhtarlikmahalleadi",
        "yerlesimyeri",
        # The council reports head their label column "Belediye"; as a whole label it is
        # a caption, as a substring it would swallow "BÜYÜK BİRLİK" and the rest.
        "belediye",
        "koy",
        "mahalle",
    }
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


VALUE_HEAD = {
    "sandikkurulusayisi": "sandik",
    "sandiksayisi": "sandik",
    "kayitlisecmensayisi": "kayitli",
    "oykullanansecmensayisi": "oy_kullanan",
    "gecerlioysayisi": "gecerli",
    # 1989 heads the column "Geçerli oy", without the "sayısı" the later years add.
    "gecerlioy": "gecerli",
    "oykullanansecmensayisiveorani": "oy_kullanan",
}
#: Columns that carry a number but are not a vote: seats won, and the percentage columns
#: the report interleaves. Counted as a party they would be added to the vote total.
NOT_A_PARTY = ("uyeliksayisi", "baskanliksayisi", "orani", "yuzde")
#: Whole headings of the column the area name is written in. Exact, because "İl" as a
#: substring matches inside a party name.
LABEL_EXACT = {"il", "ilce", "bolge", "belediye", "koy", "mahalle", "yerlesimyeri"}
#: The same heading written at length.
LABEL_HEAD = (
    "secimcevresi",
    "ililce",
    "ililcebolge",
    "belediye",
    "mahalle",
    "yerlesim",
    "muhtarlik",
)


def header_columns(rows: list[list[str]]) -> tuple[list[int], dict[int, str]] | None:
    """(label column indices, {column index: value name}) read from the header row.

    Older reports leave a party's cell **empty** where it took no votes, so a row does not
    carry a fixed count of numbers — counting them and comparing against a width drops
    every row and the file parses to nothing. The header says which column each value
    lives in, so the value is read from its column and a blank one is a zero.
    """
    for row in rows:
        filled = [(i, c) for i, c in enumerate(row) if c]
        if not any(fold(c) in VALUE_HEAD for _, c in filled):
            continue
        # Not "everything left of the first number is a label": the 2007 milletvekili
        # report heads column 1 with "Sandık kurulu sayısı" and column 7 with "Seçim
        # çevresi ve bölgesi", so the label column sits to the RIGHT of a value column.
        # Each header cell is classified on its own text instead.
        labels: list[int] = []
        values: dict[int, str] = {}
        for i, c in filled:
            key = fold(c)
            if key in VALUE_HEAD:
                values[i] = VALUE_HEAD[key]
            elif key in LABEL_EXACT or any(w in key for w in LABEL_HEAD):
                labels.append(i)
            elif not any(w in key for w in NOT_A_PARTY):
                values[i] = c
        return (labels, values) if labels and values else None
    return None


def read_by_column(
    rows: list[list[str]], label_cols: list[int], value_cols: dict[int, str]
) -> list[dict]:
    """Rows read by column position: level from which label column is filled."""

    # The header is not always a reliable map of the label columns: the provincial-council
    # report heads them with a single merged "İl İlçe" cell while its rows still indent
    # province, district and settlement into three different columns. So the depths come
    # from the rows, and the header only says where the labels end and the values begin.
    def label_cells(row: list[str]) -> list[tuple[int, str]]:
        return [
            (i, c)
            for i, c in enumerate(row)
            if c and i not in value_cols and not NUM.fullmatch(c)
        ]

    seen = {
        next((i for i, c in label_cells(row) if not CAPTION.match(c)), None)
        for row in rows
        if any(NUM.fullmatch(row[c]) for c in value_cols if c < len(row))
    } - {None}
    depths = sorted(seen) or sorted(label_cols)
    out: list[dict] = []
    province = district = None
    for row in rows:
        labels = label_cells(row)
        if not labels:
            continue
        index, label = labels[0]
        if CAPTION.match(label):
            continue
        values: dict[str, int] = {}
        for col, name in value_cols.items():
            cell = row[col] if col < len(row) else ""
            values[name] = int(cell) if NUM.fullmatch(cell) else 0
        if not any(values.values()):
            continue
        # The label column a name sits in is its level. Depths come from the header, so a
        # report that indents differently is read on its own terms.
        rank = depths.index(index) if index in depths else len(depths) - 1
        if rank == 0:
            province, district = label, None
            out.append({"level": "il", "name": label, "parent": None, "values": values})
        elif rank == 1 or len(depths) == 2:
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


#: The settlement type the report prints in its own cell beside the name.
TYPE_CELL = re.compile(r"^(mah\.?|mahallesi|köy\.?|köyü|bucağı|belde)$", re.IGNORECASE)
#: "Ceyhan İlçe toplamı" and "Adana(1) nolu seçim çevresi toplamı" -- the older reports
#: indent province, district and settlement into the SAME column and say the level in
#: words instead. Read by column alone, every one of their rows comes out a province.
DISTRICT_TOTAL = re.compile(r"\s*ilçe\s*toplamı\s*$", re.IGNORECASE)
AREA_TOTAL = re.compile(r"seçim\s*çevresi\s*toplamı", re.IGNORECASE)
#: A sub-total inside a district. Matched only with the word "toplamı" -- on "bucağı"
#: alone it would delete real villages whose name ends that way.
BUCAK_TOTAL = re.compile(r"bucağı\s*toplamı\s*$", re.IGNORECASE)


def level_from_text(labels: list[tuple[int, str]]) -> tuple[str, str] | None:
    """(level, name) where the report names the level instead of indenting it."""
    _, label = labels[0]
    if BUCAK_TOTAL.search(label):
        return "atla", label
    if any(TYPE_CELL.match(c) for _, c in labels[1:]):
        return "mahalle", label
    if DISTRICT_TOTAL.search(label):
        return "ilce", DISTRICT_TOTAL.sub("", label).strip()
    if any(AREA_TOTAL.search(c) for _, c in labels):
        return "il", AREA_TOTAL.sub("", label).strip().rstrip(" nolu").strip()
    return None


def read_report(path: pathlib.Path) -> list[dict]:
    """[{level, name, parent_name, values}] for one report file."""
    raw = path.read_text(encoding="windows-1254", errors="replace")
    raw = re.sub(r"(?is)<script.*?</script>", " ", raw)
    rows = [cells_of(r) for r in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", raw)]
    names = columns_of(rows)
    if not names:
        return []
    width = len(AGG) + len(names)

    # Which column a label sits in gives its level, but the columns are not the same
    # from report to report: the referendum layout puts province/district/settlement at
    # 0-1 / 2-3 / deeper, the milletvekili one at 2 / 4 / 6. Fixed thresholds read an
    # electoral district as a district and a district as a settlement — silently, since
    # every row still parses. So the three depths are taken from the file itself.
    depths = sorted(
        {
            next((i for i, c in enumerate(row) if c and not NUM.fullmatch(c)), None)
            for row in rows
            if len([c for c in row if NUM.fullmatch(c)]) in (width, width + 1)
        }
        - {None}
    )
    il_depth = depths[0] if depths else 0
    ilce_depth = depths[1] if len(depths) > 1 else il_depth + 2

    out: list[dict] = []
    province = district = None
    # The "Ceyhan İlçe toplamı" line sits after its settlements in some years, so the
    # district is read up front; otherwise every settlement above it is parentless and
    # silently dropped.
    for row in rows:
        for cell in row:
            if cell and DISTRICT_TOTAL.search(cell):
                district = DISTRICT_TOTAL.sub("", cell).strip()
                break
        if district:
            break
    # A province line resets the district, and in these reports the province total is
    # printed above the settlements that belong to the district the file is about. The
    # district read above is kept as the fallback so they are not orphaned.
    file_district = district
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
        named = level_from_text(labels)
        if named:
            level, name = named
            if level == "atla":
                continue
            if level == "il":
                province, district = name, None
            elif level == "ilce":
                district = name
            elif not district:
                district = file_district
                if not district:
                    continue
            out.append(
                {
                    "level": level,
                    "name": name,
                    "parent": {"il": None, "ilce": province}.get(level, district),
                    "values": values,
                }
            )
            continue
        if index <= il_depth:
            province, district = label, None
            out.append({"level": "il", "name": label, "parent": None, "values": values})
        elif index <= ilce_depth:
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
    # Older reports leave a party's cell empty where it took no votes, so their rows never
    # reach the full width: the read above returns nothing, or just the one province total
    # that happened to be complete. Reading by column position recovers them. Both reads
    # are done and the longer one wins, so a report the width-based read already
    # understands keeps being read the way it always was.
    # A read that reached the settlement is the report understood; it is kept as it is.
    # Where the width-based read came back with nothing, or with only the handful of rows
    # that happened to be complete, the column-position read is tried in its place.
    if any(r["level"] == "mahalle" for r in out):
        return out
    header = header_columns(rows)
    if header:
        by_column = read_by_column(rows, *header)
        if len(by_column) > len(out):
            return by_column
    return out


#: District names the election reports use that the registry does not. Each was checked to
#: land on exactly one district: a wrong entry welds two different places into one series.
#: Only spelling and renaming here -- a district that SPLIT is not in this table, because
#: its votes cannot be attributed to any one successor.
DISTRICT_ALIAS = {
    ("TR-04", "dogubeyazit"): "dogubayazit",
    ("TR-07", "kale"): "demre",
    ("TR-09", "yenihisar"): "didim",
    ("TR-22", "suleoglu"): "suloglu",
    ("TR-25", "ilica"): "aziziye",
    ("TR-27", "kargamis"): "karkamis",
    ("TR-31", "samandagi"): "samandag",
    ("TR-44", "arapkir"): "arapgir",
    ("TR-44", "poturge"): "puturge",
    ("TR-56", "aydinlar"): "tillo",
    # The abbreviation rule cannot reach this one: the registry spells it
    # "Marmaraereğlisi", so the shortened tail "Ereğli" is not its ending.
    ("TR-59", "meregli"): "marmaraereglisi",
}


def match_district(districts: dict, province_id: str, name: str) -> str | None:
    """The district id for a name as the election report writes it.

    The reports name a central district "Adıyaman Merkez" where the registry calls it
    "Merkez", and spell Kâhta with the circumflex the registry drops. Both were silently
    dropping two hundred districts off the map — they came out black, which looks like a
    place that did not vote.
    """
    key = fold(name)
    hit = districts.get((province_id, key))
    if hit:
        return hit
    alias = DISTRICT_ALIAS.get((province_id, key))
    if alias:
        return districts.get((province_id, alias))
    if key.endswith("merkez"):
        for candidate in ("merkez", key[: -len("merkez")]):
            hit = districts.get((province_id, candidate))
            if hit:
                return hit
    # "Ş.Koçhisar" is Şereflikoçhisar and "M.Kemalpaşa" Mustafakemalpaşa: the report
    # abbreviates the first word to its initial. Expanded only when the province holds
    # exactly one district that fits, so an ambiguous abbreviation stays unmatched.
    short = re.match(r"^(\w)\.\s*(.+)$", name.strip())
    if short:
        head, tail = fold(short.group(1)), fold(short.group(2))
        fits = [
            area
            for (prov, folded), area in districts.items()
            if prov == province_id and folded.startswith(head) and folded.endswith(tail)
        ]
        if len(fits) == 1:
            return fits[0]
    # A district can change province: Osmaniye left Adana in 1996, Düzce left Bolu in
    # 1999, and reports from before that name them under the old one. Taken only when the
    # name belongs to exactly one district in the whole country -- "Merkez" never does.
    elsewhere = [area for (_, folded), area in districts.items() if folded == key]
    if len(elsewhere) == 1:
        return elsewhere[0]
    return None


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

    # Neighbourhoods are looked up in the index built from the map's own geometry
    # (build_mahalle_index.py). The MEDAS registry carries different ids, and matching
    # against it left most settlements grey on the map.
    hoods: dict[tuple[str, str], str] = {}
    index = ROOT / "public" / "tiles" / "mahalle-adlari.json"
    if index.exists():
        for district, table in json.loads(index.read_text(encoding="utf-8")).items():
            for name, area_id in table.items():
                hoods[(district, name)] = area_id
    return provinces, districts, hoods


ADLAR = {
    "cb": "Cumhurbaşkanlığı",
    "ho": "Halk oylaması",
    "mv": "Milletvekili",
    "yerel": "Yerel seçim",
}
YEREL_OFIS = {
    "bsb": "büyükşehir belediye başkanlığı",
    "bel": "belediye başkanlığı",
    "belmec": "belediye meclisi",
    "ilgen": "il genel meclisi",
}


def etiket(vote: str) -> str:
    """A human label for a vote key, so the page's picker needs no table of its own."""
    if vote.startswith("yerel_"):
        _, office, year = vote.split("_")
        return f"{ADLAR['yerel']} {year} · {YEREL_OFIS.get(office, office)}"
    tur = ADLAR.get(vote[:2], vote[:2])
    kalan = vote[2:]
    if kalan.endswith("t1"):
        return f"{tur} {kalan[:-2]} · 1. tur"
    if kalan.endswith("t2"):
        return f"{tur} {kalan[:-2]} · 2. tur"
    if kalan.endswith("k"):
        return f"{tur} {kalan[:-1]} · Kasım"
    if kalan.endswith("h"):
        return f"{tur} {kalan[:-1]} · Haziran"
    return f"{tur} {kalan}"


def manifest() -> None:
    """What the page can offer: every vote with a parsed district table, newest first."""
    votes = []
    for path in OUT.glob("secim-*-ilce.json"):
        key = path.name[len("secim-") : -len("-ilce.json")]
        yil = "".join(ch for ch in key if ch.isdigit())[:4]
        votes.append({"anahtar": key, "ad": etiket(key), "yil": yil})
    votes.sort(key=lambda v: (v["yil"], v["anahtar"]), reverse=True)
    (OUT / "secimler.json").write_text(
        json.dumps(votes, ensure_ascii=False), encoding="utf-8"
    )
    print(f"secimler.json: {len(votes)} secim")


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
            # Some years print no province line at all -- the 1995-2007 milletvekili
            # reports open straight at the district. The file is one province's, and its
            # name says which, so the id comes from there and the districts inside it are
            # matched instead of the whole file being dropped.
            stem = path.stem.split("__")[0]
            province_id = provinces.get(fold(re.sub(r"_\d+$", "", stem)))
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
                    area = match_district(districts, province_id, record["name"])
                    if area:
                        district_out[area] = base
                        district_out[area]["ad"] = record["name"]
                    else:
                        unmatched += 1
                elif record["level"] == "mahalle" and province_id:
                    parent = match_district(
                        districts, province_id, record["parent"] or ""
                    )
                    if not parent:
                        continue
                    area = hoods.get((parent, fold(record["name"])))
                    key = area or f"{parent}~{fold(record['name'])}"
                    base["ad"] = record["name"]
                    hood_out.setdefault(province_id, {})[key] = base

        # A country-wide summary for the neighbourhood map: five numbers per settlement
        # instead of the full breakdown. The detail files stay for the panel — 48.000
        # settlements with every candidate would be four megabytes to colour one map.
        adaylar: list[str] = []
        ozet: dict[str, list] = {}
        for rows in hood_out.values():
            for key, row in rows.items():
                win = max(row["v"].items(), key=lambda kv: kv[1], default=None)
                if not win:
                    continue
                if win[0] not in adaylar:
                    adaylar.append(win[0])
                ozet[key] = [
                    row["k"],
                    row["o"],
                    row["g"],
                    adaylar.index(win[0]),
                    win[1],
                ]
        (OUT / f"secim-{vote}-mahalle-ozet.json").write_text(
            json.dumps(
                {"adaylar": adaylar, "y": ozet},
                separators=(",", ":"),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        (OUT / f"secim-{vote}-ilce.json").write_text(
            json.dumps(district_out, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        for province_id, rows in hood_out.items():
            (OUT / f"secim-{vote}-mahalle-{province_id}.json").write_text(
                json.dumps(rows, separators=(",", ":"), ensure_ascii=False),
                encoding="utf-8",
            )
        manifest()
        total_hoods = sum(len(v) for v in hood_out.values())
        print(
            f"{vote}: {len(district_out)} ilçe, {total_hoods} yerleşim"
            + (f", {unmatched} eşleşmedi" if unmatched else "")
        )


if __name__ == "__main__":
    main(sys.argv[1:])
