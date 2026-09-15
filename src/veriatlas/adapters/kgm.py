"""KGM (General Directorate of Highways): distances, road lengths, motorways, bridges.

`scripts/fetch_kgm_documents.py` downloads the files under `raw/kgm/pdf/`;
`scripts/extract_kgm_distances.py` turns the million-row district distance workbook into
`raw/kgm/district_distance_cells.parquet`. Everything else is read from the PDFs here —
they are one or two pages of plain text tables.

What the checks guarantee:

* distances: the district sheet is a full square (every district to every district), the
  province sheet has all 81 × 80 pairs; an unmatched name stops the load;
* road lengths by province: the printed row total equals the sum of the surface types,
  and state + provincial roads equal the printed combined table, province by province;
* motorways: the provinces sum to the printed national total in every year;
* bridges: state + provincial equal the printed combined table, and the material columns
  sum to the printed total.

Where the source breaks its own arithmetic the load reports it and keeps the parts, not
the printed total (K16). Details and the source's quirks: `docs/kgm.md`.
"""

from __future__ import annotations

import datetime as dt
import re
from functools import cache
from pathlib import Path

import openpyxl
import pdfplumber
import polars as pl

from ..areas import load_areas, load_districts
from ..config import RAW

PDF = RAW / "kgm" / "pdf"
DISTRICT_CELLS = RAW / "kgm" / "district_distance_cells.parquet"
PROVINCE_SHEET = PDF / "Root_Uzakliklar" / "ilmesafe.xlsx"
INVENTORY = PDF / "Istatistikler_DevletveIlYolEnvanteri"

#: Printed district names that are not the register's spelling of the same district.
DISTRICT_ALIASES = {
    ("TR-34", "eyup"): "eyupsultan",
    ("TR-55", "ondokuzmayis"): "mayis",
    # İlçe SEGE-2017: Kazan before its 2016 renaming, and Kale written with its province.
    ("TR-06", "kazan"): "kahramankazan",
    ("TR-20", "denizlikale"): "kale",
}

#: Printed province names in the motorway table that are abbreviated.
PROVINCE_ALIASES = {
    "kmaras": "kahramanmaras",
    "surfa": "sanliurfa",
    # The 2010 and 2012 inventories name some provinces by their centre town.
    "izmit": "kocaeli",
    "adapazari": "sakarya",
    "icel": "mersin",
    "afyon": "afyonkarahisar",
    # EPDK monthly report, December 2021.
    "kuthahya": "kutahya",
    # EPDK LPG report 2007.
    "malataya": "malatya",
}

SURFACES = (
    "asphalt_concrete",
    "surface_treatment",
    "stone_block",
    "stabilized",
    "earth",
    "primitive",
)


def fold(text: str) -> str:
    """Lower-case ASCII letters only: `AFYONKARAHİSAR` and `Afyonkarahisar` meet."""
    text = text.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu", strict=True):
        text = text.replace(a, b)
    return re.sub(r"[^a-z]", "", text)


def number(text: str) -> float:
    """`1.674`, `210.968,00`, `193,3` — dot groups thousands, comma is the decimal."""
    return float(text.replace(".", "").replace(",", "."))


@cache
def provinces() -> dict[str, str]:
    registry = load_areas().filter(pl.col("area_level") == "province")
    return {
        fold(n): i
        for n, i in zip(registry["name_tr"], registry["area_id"], strict=True)
    }


def province_id(name: str) -> str:
    # `KOCAELİ (İZMİT)`: the centre town in brackets is not part of the province name.
    key = fold(re.sub(r"\(.*?\)", "", name))
    key = PROVINCE_ALIASES.get(key, key)
    abbreviated = re.fullmatch(r"\s*([A-ZÇĞİÖŞÜ])\s*\.\s*(\S+)\s*", name)
    if key not in provinces() and abbreviated:
        # `D.BAKIR`, `K.MARAŞ`: first letter, dot, the end of the name. Accepted only when
        # exactly one province fits.
        head, tail = fold(abbreviated.group(1)), fold(abbreviated.group(2))
        fits = [k for k in provinces() if k.startswith(head) and k.endswith(tail)]
        if len(fits) == 1:
            key = fits[0]
    if key not in provinces():
        raise KeyError("tanınmayan il adı: " + name)
    return provinces()[key]


def pdf_lines(path: Path) -> list[str]:
    with pdfplumber.open(path) as document:
        return [
            line.strip()
            for page in document.pages
            for line in (page.extract_text() or "").splitlines()
        ]


def fact(
    rows: list[dict],
    indicator_id: str,
    unit: str,
    vintage: str,
    retrieved: dt.date,
) -> pl.DataFrame:
    frame = pl.DataFrame(
        rows, schema_overrides={"value": pl.Float64}, infer_schema_length=None
    )
    return frame.with_columns(
        pl.lit(indicator_id).alias("indicator_id"),
        pl.lit("annual").alias("frequency"),
        pl.lit(unit).alias("unit"),
        pl.lit("measured").alias("quality_flag"),
        pl.lit(vintage).alias("vintage"),
        pl.lit("kgm").alias("source_id"),
        pl.lit(retrieved).alias("retrieved_at"),
    )


class Kgm:
    source_id = "kgm"
    indicator_id = ""
    retrieved_at = dt.date(2026, 9, 14)


# region Distances


def district_key() -> dict[tuple[str, str], tuple[str, str]]:
    """(province id, folded district name) -> (area id, area level)."""
    current = load_districts().filter(pl.col("valid_to").is_null())
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for row in current.iter_rows(named=True):
        key = (row["parent_id"], fold(row["name_tr"]))
        if key in out:
            raise ValueError("kayıt defterinde aynı adlı iki ilçe: " + repr(key))
        out[key] = (row["area_id"], "district")
    return out


def resolve_district(
    key: dict[tuple[str, str], tuple[str, str]], province: str, district: str
) -> tuple[str, str]:
    """A KGM district to an area.

    `MERKEZ` is two different things. In the 51 provinces without a metropolitan
    municipality it is the central district, which the register names after the province.
    In the 30 metropolitan provinces there is no central district any more and KGM's
    `MERKEZ` is the province centre itself — stored at province level, so "how far is this
    district from its province centre" stays answerable.
    """
    pid = province_id(province)
    name = fold(district)
    name = DISTRICT_ALIASES.get((pid, name), name)
    if name == "merkez":
        own = (pid, fold(load_areas().filter(pl.col("area_id") == pid)["name_tr"][0]))
        return key.get(own, (pid, "province"))
    if (pid, name) not in key:
        raise KeyError(f"tanınmayan ilçe adı: {province} / {district}")
    return key[(pid, name)]


class KgmDistrictDistance(Kgm):
    indicator_id = "road_distance_between_districts"
    vintage = "2026-03"

    def fetch(self) -> Path:
        return DISTRICT_CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        cells = pl.read_parquet(raw)
        # The diagonal is printed twice (both zero); nothing else repeats.
        cells = cells.filter(
            ~(
                (cells["from_province"] == cells["to_province"])
                & (cells["from_district"] == cells["to_district"])
            )
        )
        pairs = cells.unique(
            ["from_province", "from_district", "to_province", "to_district"]
        )
        if pairs.height != cells.height:
            raise ValueError("ilçe mesafesinde köşegen dışı çift anahtar")

        key = district_key()
        places = cells.select(
            pl.col("from_province").alias("p"), pl.col("from_district").alias("d")
        )
        places = pl.concat(
            [
                places,
                cells.select(
                    pl.col("to_province").alias("p"), pl.col("to_district").alias("d")
                ),
            ]
        ).unique()
        n = places.height
        if cells.height != n * (n - 1):
            raise ValueError(
                f"ilçe mesafesi tam kare değil: {cells.height} satır, {n} yer"
            )

        lookup = {}
        for p, d in places.iter_rows():
            lookup[(p, d)] = resolve_district(key, p, d)
        ids = [a for a, _ in lookup.values()]
        if len(set(ids)) != len(ids):
            raise ValueError("iki KGM ilçesi aynı alana eşlendi")

        table = pl.DataFrame(
            [(p, d, a, lvl) for (p, d), (a, lvl) in lookup.items()],
            schema=["p", "d", "area_id", "area_level"],
            orient="row",
        )
        frame = (
            cells.join(
                table, left_on=["from_province", "from_district"], right_on=["p", "d"]
            )
            .join(
                table.select("p", "d", pl.col("area_id").alias("to_area")),
                left_on=["to_province", "to_district"],
                right_on=["p", "d"],
            )
            .select(
                "area_id",
                "area_level",
                pl.lit(dt.date(2026, 1, 1)).alias("period_start"),
                ("to_area=" + pl.col("to_area")).alias("dims"),
                pl.col("km").cast(pl.Float64).alias("value"),
            )
        )
        return fact(
            frame.to_dicts(), self.indicator_id, "km", self.vintage, self.retrieved_at
        )


def distance_sheet(rows: list[tuple], origin: str) -> list[dict]:
    """81 × 80 province distances from one cetvel, header row found by `İL ADI`."""
    header_at = next(
        i
        for i, row in enumerate(rows)
        if any(str(c).strip() == "İL ADI" for c in row if c)
    )
    header = rows[header_at]
    name_col = [str(c).strip() for c in header].index("İL ADI")
    # The 2010-2016 sheets repeat the plate and name columns at the right edge.
    columns = {
        j: province_id(str(c))
        for j, c in enumerate(header)
        if j > name_col
        and c
        and str(c).strip()
        and str(c).strip() not in ("İL ADI", "İL NO")
    }
    records = []
    seen = set()
    for row in rows[header_at + 1 :]:
        if len(row) <= name_col or not row[name_col] or not str(row[name_col]).strip():
            continue
        source = province_id(str(row[name_col]))
        plate = str(row[name_col - 1]).strip().split(".")[0].zfill(2)
        if source != "TR-" + plate:
            raise ValueError(
                f"{origin}: plaka ile ad uyuşmuyor: {plate} {row[name_col]}"
            )
        seen.add(source)
        for j, target in columns.items():
            if target == source:
                continue
            value = row[j] if j < len(row) else None
            if value in (None, ""):
                raise ValueError(f"{origin}: il mesafesi boş: {source} -> {target}")
            records.append({"area_id": source, "to": target, "value": float(value)})
    if len(seen) != 81 or len(set(columns.values())) != 81 or len(records) != 81 * 80:
        raise ValueError(
            f"{origin}: il mesafesi eksik: {len(seen)} satır, {len(columns)} sütun"
        )
    return records


class KgmProvinceDistance(Kgm):
    """Road distance between provinces, from the current cetvel and archived copies.

    The current `ilmesafe.xlsx` is dated March 2026; the Wayback Machine kept seventeen
    versions of the older `ilmesafe.xls` (2010-2018). Each copy is stored under the year
    it was fetched in, the newest copy of a year winning. New roads shorten routes, so the
    same pair changes over time (Adana-Adıyaman 329 km in 2010, 337 km in 2026).
    """

    indicator_id = "road_distance_between_provinces"
    vintage = "2026-03"

    def fetch(self) -> Path:
        return PROVINCE_SHEET

    def parse(self, raw: Path) -> pl.DataFrame:
        import xlrd

        sheets: dict[int, tuple[str, list[tuple]]] = {}
        for path in sorted(ARCHIVE.glob("ilmesafe_*.xls")):
            book = xlrd.open_workbook(path).sheet_by_index(0)
            rows = [tuple(book.row_values(i)) for i in range(book.nrows)]
            sheets[int(path.name.split("_")[1][:4])] = (path.name, rows)
        current = openpyxl.load_workbook(raw, read_only=True).worksheets[0]
        sheets[2026] = (raw.name, list(current.iter_rows(values_only=True)))

        records = []
        for year, (name, rows) in sorted(sheets.items()):
            for item in distance_sheet(rows, name):
                records.append(
                    {
                        "area_id": item["area_id"],
                        "area_level": "province",
                        "period_start": dt.date(year, 1, 1),
                        "dims": "to_area=" + item["to"],
                        "value": item["value"],
                    }
                )
        return fact(records, self.indicator_id, "km", self.vintage, self.retrieved_at)


# endregion

# region Road lengths

#: `01 ADANA 193,3 216,1 409,4 3,2 0 0 28,5 441,1 249,2` — plate, name, asphalt concrete,
#: surface treatment, asphalt total, stone block, stabilized, earth, primitive, total,
#: divided road. Names may carry a space (none do today) so the name is non-greedy.
PROVINCE_ROW = re.compile(
    r"^(?P<plate>\d{2}) (?P<name>\D+?) (?P<nums>[\d,]+(?: [\d,]+){8})$"
)


def province_lengths(path: Path) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for line in pdf_lines(path):
        # The 2010 inventories lose Ş: one prints the digit 6 (`ESKİ6EHİR`), the other an
        # unmapped glyph (`ESKİ(cid:3)EHİR`).
        line = line.replace("(cid:3)", "Ş")
        line = re.sub(r"(?<=[A-ZÇĞİÖÜ])6|6(?=[A-ZÇĞİÖÜ])", "Ş", line)
        match = PROVINCE_ROW.match(line)
        if not match:
            continue
        pid = province_id(match["name"])
        if pid != "TR-" + match["plate"]:
            raise ValueError("plaka ile ad uyuşmuyor: " + line)
        values = [number(v) for v in match["nums"].split()]
        asphalt_c, surface_t, asphalt, stone, stab, earth, prim, total, _divided = (
            values
        )
        if (
            abs(asphalt_c + surface_t - asphalt) > 0.15
            or abs(asphalt + stone + stab + earth + prim - total) > 0.15
        ):
            raise ValueError(f"satır toplamı tutmuyor: {path.name} {line}")
        out[pid] = values
    if len(out) != 81:
        raise ValueError(f"{path.name}: {len(out)} il okundu")
    return out


class KgmRoadLength(Kgm):
    """State and provincial road length by surface type, per province, at 1 January 2026."""

    indicator_id = "road_length_by_surface"
    vintage = "2026-01"

    def fetch(self) -> Path:
        return INVENTORY

    def parse(self, raw: Path) -> pl.DataFrame:
        state = province_lengths(raw / "IllereGoreDevletYollari.pdf")
        provincial = province_lengths(raw / "IllereGoreIlYollari.pdf")
        combined = province_lengths(raw / "IllereGoreDevletVeIlYollari.pdf")
        records = []
        for pid in combined:
            for i in (0, 1, 3, 4, 5, 6, 7, 8):
                if abs(state[pid][i] + provincial[pid][i] - combined[pid][i]) > 0.15:
                    raise ValueError(
                        f"devlet + il yolu birleşik tabloyu tutmuyor: {pid} sütun {i}"
                    )
            for road_class, values in (
                ("state", state[pid]),
                ("provincial", provincial[pid]),
            ):
                parts = (
                    values[0],
                    values[1],
                    values[3],
                    values[4],
                    values[5],
                    values[6],
                )
                for surface, value in zip(SURFACES, parts, strict=True):
                    records.append(
                        {
                            "area_id": pid,
                            "area_level": "province",
                            # Lengths at 01.01.2026 are the end-of-2025 network.
                            "period_start": dt.date(2025, 1, 1),
                            "dims": f"road_class={road_class};surface={surface}",
                            "value": value,
                        }
                    )
        return fact(
            records, self.indicator_id, "road_km", self.vintage, self.retrieved_at
        )


class KgmDividedRoad(Kgm):
    indicator_id = "divided_road_length"
    vintage = "2026-01"

    def fetch(self) -> Path:
        return INVENTORY

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        for road_class, name in (
            ("state", "IllereGoreDevletYollari.pdf"),
            ("provincial", "IllereGoreIlYollari.pdf"),
        ):
            for pid, values in province_lengths(raw / name).items():
                records.append(
                    {
                        "area_id": pid,
                        "area_level": "province",
                        "period_start": dt.date(2025, 1, 1),
                        "dims": "road_class=" + road_class,
                        "value": values[8],
                    }
                )
        return fact(
            records, self.indicator_id, "road_km", self.vintage, self.retrieved_at
        )


#: `1967 1 289 12 712 207 31 190 9 319 4 540 59 257` — thousands are grouped with a space,
#: so the numbers cannot be split on spaces. Each of the seven fields is 1-3 digits
#: followed by space-separated groups of exactly three.
HISTORY_ROW = re.compile(r"^(?P<year>(19|20)\d{2}) (?P<rest>[\d ]+)$")
GROUPED = re.compile(r"\d{1,3}(?: \d{3})*")


def split_grouped(text: str, count: int, total_last: bool = True) -> list[float]:
    """Split `1 289 12 712 207 ...` into `count` numbers whose last is the sum of the rest.

    Space both groups thousands and separates fields, so the reading is ambiguous in
    general. The row total resolves it: try every way of cutting the digit groups into
    `count` numbers and keep the one whose parts add up to the last.
    """
    tokens = text.split()
    found = []

    def walk(i: int, acc: list[int]) -> None:
        if len(acc) == count:
            if i == len(tokens) and (not total_last or sum(acc[:-1]) == acc[-1]):
                found.append(list(acc))
            return
        for j in range(i + 1, len(tokens) + 1):
            head, tail = tokens[i], tokens[i + 1 : j]
            if not 1 <= len(head) <= 3 or any(len(t) != 3 for t in tail):
                break
            walk(j, [*acc, int("".join([head, *tail]))])

    walk(0, [])
    if len(found) != 1:
        raise ValueError(f"satır tek türlü bölünemedi ({len(found)} okuma): {text}")
    return [float(v) for v in found[0]]


ARCHIVE = RAW / "kgm" / "wayback"


class KgmRoadLengthArchive(Kgm):
    """State and provincial roads together, by province and surface, from archived copies.

    KGM overwrites the province inventory every year. The Wayback Machine kept nine
    versions of `IllereGoreDevletVeIlYollari.pdf` (2010-2026), fetched into `raw/kgm/wayback/`
    by `scripts/fetch_kgm_wayback.sh`. Each is dated inside (`(01.01.2018)`): the network at the end of
    the year before. The split into state and provincial roads was not archived, so this
    series is the two together — which the current year's file also gives.
    """

    indicator_id = "road_length_by_surface_province"
    vintage = "2026-02"
    column = None  # surface columns

    def fetch(self) -> Path:
        return ARCHIVE

    def files(self, raw: Path) -> dict[int, Path]:
        by_year: dict[int, Path] = {}
        for path in sorted(raw.glob("IllereGoreDevletVeIlYollari_*.pdf")):
            dates = [
                re.search(r"\(01\.01\.(\d{4})\)", line) for line in pdf_lines(path)
            ]
            years = {int(m.group(1)) - 1 for m in dates if m}
            if len(years) != 1:
                raise ValueError(f"{path.name}: tarih okunamadı {years}")
            year = years.pop()
            if year in by_year:
                raise ValueError(f"{path.name}: {year} iki dosyada")
            by_year[year] = path
        return by_year

    def parse(self, raw: Path) -> pl.DataFrame:
        history = {}
        for line in pdf_lines(INVENTORY / "YillaraGoreDevletVeIlYollari.pdf"):
            match = HISTORY_ROW.match(line)
            if match:
                history[int(match["year"])] = split_grouped(match["rest"], 7)[6]
        records = []
        for year, path in self.files(raw).items():
            table = province_lengths(path)
            total = sum(values[7] for values in table.values())
            # Checked against the national series printed in the current yearbook.
            if year in history and abs(total - history[year]) > 81:
                raise ValueError(
                    f"{year}: il toplamı {total:.0f}, Türkiye serisi {history[year]:.0f}"
                )
            for pid, values in table.items():
                if self.column is None:
                    parts = (
                        values[0],
                        values[1],
                        values[3],
                        values[4],
                        values[5],
                        values[6],
                    )
                    for surface, value in zip(SURFACES, parts, strict=True):
                        records.append(
                            {
                                "area_id": pid,
                                "area_level": "province",
                                "period_start": dt.date(year, 1, 1),
                                "dims": "surface=" + surface,
                                "value": value,
                            }
                        )
                else:
                    records.append(
                        {
                            "area_id": pid,
                            "area_level": "province",
                            "period_start": dt.date(year, 1, 1),
                            "dims": "",
                            "value": values[self.column],
                        }
                    )
        return fact(
            records, self.indicator_id, "road_km", self.vintage, self.retrieved_at
        )


class KgmRoadClassArchive(Kgm):
    """State and provincial roads apart, by province and surface, from archived copies.

    `IllereGoreDevletYollari.pdf` and `IllereGoreIlYollari.pdf` were archived more often than
    the combined table. A year is kept only when both are there; where one year has two
    copies, the newest that passes the row checks is used (the first 2015 provincial copy
    does not add up, its replacement does). The current year comes from the live files.
    """

    indicator_id = "road_length_by_surface"
    vintage = "2026-02"
    divided = False

    def fetch(self) -> Path:
        return ARCHIVE

    def tables(self, raw: Path, stem: str) -> dict[int, dict[str, list[float]]]:
        found: dict[int, dict[str, list[float]]] = {}
        for path in sorted(raw.glob(stem + "_*.pdf"), reverse=True):
            dates = {
                int(m.group(1)) - 1
                for m in (
                    re.search(r"\(01\.01\.(\d{4})\)", line) for line in pdf_lines(path)
                )
                if m
            }
            if len(dates) != 1:
                raise ValueError(f"{path.name}: tarih okunamadı")
            year = dates.pop()
            if year in found:
                continue
            try:
                found[year] = province_lengths(path)
            except ValueError:
                continue
        return found

    def parse(self, raw: Path) -> pl.DataFrame:
        state = self.tables(raw, "IllereGoreDevletYollari")
        provincial = self.tables(raw, "IllereGoreIlYollari")
        state[2025] = province_lengths(INVENTORY / "IllereGoreDevletYollari.pdf")
        provincial[2025] = province_lengths(INVENTORY / "IllereGoreIlYollari.pdf")
        combined = KgmRoadLengthArchive().files(ARCHIVE)
        records = []
        for year in sorted(set(state) & set(provincial)):
            if year in combined:
                whole = province_lengths(combined[year])
                for pid in whole:
                    if (
                        abs(
                            state[year][pid][7]
                            + provincial[year][pid][7]
                            - whole[pid][7]
                        )
                        > 1
                    ):
                        raise ValueError(
                            f"{year} {pid}: devlet + il birleşik tabloyu tutmuyor"
                        )
            for road_class, table in (
                ("state", state[year]),
                ("provincial", provincial[year]),
            ):
                for pid, values in table.items():
                    if self.divided:
                        items = [("road_class=" + road_class, values[8])]
                    else:
                        parts = (
                            values[0],
                            values[1],
                            values[3],
                            values[4],
                            values[5],
                            values[6],
                        )
                        items = [
                            (f"road_class={road_class};surface={surface}", value)
                            for surface, value in zip(SURFACES, parts, strict=True)
                        ]
                    for dims, value in items:
                        records.append(
                            {
                                "area_id": pid,
                                "area_level": "province",
                                "period_start": dt.date(year, 1, 1),
                                "dims": dims,
                                "value": value,
                            }
                        )
        return fact(
            records, self.indicator_id, "road_km", self.vintage, self.retrieved_at
        )


class KgmDividedRoadClassArchive(KgmRoadClassArchive):
    indicator_id = "divided_road_length"
    divided = True


class KgmDividedRoadArchive(KgmRoadLengthArchive):
    indicator_id = "divided_road_length_province"
    column = 8


class KgmRoadLengthHistory(Kgm):
    """State and provincial roads together, by surface, Türkiye, 1967-2025 (year end)."""

    indicator_id = "road_length_history"
    vintage = "2026-01"

    def fetch(self) -> Path:
        return INVENTORY / "YillaraGoreDevletVeIlYollari.pdf"

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        # Printed column order: asphalt concrete, surface treatment, stone block,
        # stabilized, earth, primitive, total.
        for line in pdf_lines(raw):
            match = HISTORY_ROW.match(line)
            if not match:
                continue
            values = split_grouped(match["rest"], 7)
            for surface, value in zip(SURFACES, values[:6], strict=True):
                records.append(
                    {
                        "area_id": "TR",
                        "area_level": "country",
                        "period_start": dt.date(int(match["year"]), 1, 1),
                        "dims": "surface=" + surface,
                        "value": value,
                    }
                )
        years = {r["period_start"].year for r in records}
        if years != set(range(1967, 2026)):
            raise ValueError(
                "yol uzunluğu yılları eksik: "
                + str(sorted(set(range(1967, 2026)) - years))
            )
        return fact(
            records, self.indicator_id, "road_km", self.vintage, self.retrieved_at
        )


class KgmMotorway(Kgm):
    """Completed motorway length by province, 2000-2025 (year end)."""

    indicator_id = "motorway_length"
    vintage = "2026-01"

    def fetch(self) -> Path:
        return (
            PDF
            / "Istatistikler_OtoyolEnvanterBilgisi"
            / "YillarİtibariyleYapimiTamamlanmisOtoyollar.pdf"
        )

    def parse(self, raw: Path) -> pl.DataFrame:
        lines = pdf_lines(raw)
        years = [int(y) for y in lines[2].split()]
        if years != list(range(2000, 2026)):
            raise ValueError("otoyol yılları beklenmedik: " + lines[2])
        totals = [number(v) for v in lines[5].split()]
        records = []
        sums = [0.0] * len(years)
        repeat = len(years) - 1
        row = re.compile(
            rf"^TR[A-Z0-9]{{3}} (?P<name>\D+?) (?P<nums>\d+(?: \d+){{{repeat}}})$"
        )
        for line in lines[6:]:
            match = row.match(line)
            if not match:
                continue
            pid = province_id(match["name"])
            for i, (year, value) in enumerate(
                zip(years, match["nums"].split(), strict=True)
            ):
                sums[i] += float(value)
                records.append(
                    {
                        "area_id": pid,
                        "area_level": "province",
                        "period_start": dt.date(year, 1, 1),
                        "dims": "",
                        "value": float(value),
                    }
                )
        off = [(y, s, t) for y, s, t in zip(years, sums, totals, strict=True) if s != t]
        if off:
            raise ValueError(
                "otoyol il toplamı Türkiye toplamını tutmuyor: " + repr(off)
            )
        return fact(
            records, self.indicator_id, "road_km", self.vintage, self.retrieved_at
        )


TRAFFIC = PDF / "Trafik_TrafikveUlasimBilgileri"

#: `01 ADANA 1.902.633 1.349.978 ...` — plate, name, then either six numbers (vehicle-,
#: passenger-, tonne-km on motorway and state road) or twelve (motorway, state, provincial,
#: total for each), with `-` or `‐` where the province has no motorway.
TRAFFIC_ROW = re.compile(
    r"^(?P<plate>\d{2}) (?P<name>\D+?) (?P<nums>(?:[\d.]+|[-‐])(?: (?:[\d.]+|[-‐]))+)$"
)
MEASURES = ("vehicle_km", "passenger_km", "tonne_km")


@cache
def traffic_pages(path: Path) -> dict[str, list[float]]:
    """Province -> the numbers of its row in the `İLLERE GÖRE ... TAŞIT-KM` table."""
    out: dict[str, list[float]] = {}
    with pdfplumber.open(path) as document:
        for page in document.pages[-45:]:
            text = page.extract_text() or ""
            head = fold(" ".join(text.splitlines()[:3]))
            if not ("illeregore" in head and "tasitkm" in head):
                continue
            for line in text.splitlines():
                match = TRAFFIC_ROW.match(line.strip())
                if not match:
                    continue
                pid = province_id(match["name"])
                if pid != "TR-" + match["plate"]:
                    raise ValueError(f"{path.name}: plaka ile ad uyuşmuyor: {line}")
                out[pid] = [
                    0.0 if v in "-‐" else number(v) for v in match["nums"].split()
                ]
    return out


class KgmVehicleKm(Kgm):
    """Vehicle-, passenger- and tonne-km on KGM roads by province, 2012-2025 (thousands).

    From the yearly `Trafik ve Ulaşım Bilgileri`. The main volume prints motorway and state
    road; the provincial road volumes (2012, 2016, 2019, 2023) add provincial roads, and the
    2012 main volume carries all three. Where two volumes print the same cell they must agree.
    """

    indicator_id = "kgm_vehicle_km"
    vintage = "2026-05"
    measure = 0

    def fetch(self) -> Path:
        return TRAFFIC

    def parse(self, raw: Path) -> pl.DataFrame:
        cells: dict[tuple[int, str, str], float] = {}
        for path in sorted(raw.glob("*.pdf")):
            year = 2000 + int(path.name[:2])
            if year < 2012:
                continue
            rows = traffic_pages(path)
            if not rows:
                raise ValueError(f"{path.name}: il taşıt-km tablosu bulunamadı")
            if len(rows) != 81:
                raise ValueError(f"{path.name}: {len(rows)} il okundu")
            for pid, values in rows.items():
                # The 2016 provincial volume leaves the motorway cell empty instead of `-`
                # for provinces without one: three numbers short, one per measure.
                if len(values) in (3, 9):
                    step = len(values) // 3
                    values = [
                        v
                        for m in range(3)
                        for v in [0.0, *values[m * step : (m + 1) * step]]
                    ]
                if len(values) == 6:
                    classes = {"motorway": values[0::2], "state": values[1::2]}
                elif len(values) == 12:
                    classes = {
                        "motorway": values[0::4],
                        "state": values[1::4],
                        "provincial": values[2::4],
                    }
                    for m in range(3):
                        if abs(sum(values[4 * m : 4 * m + 3]) - values[4 * m + 3]) > 2:
                            raise ValueError(f"{path.name} {pid}: toplam tutmuyor")
                else:
                    raise ValueError(f"{path.name} {pid}: {len(values)} sayı")
                for road_class, triple in classes.items():
                    key = (year, pid, road_class)
                    value = triple[self.measure]
                    if key in cells and abs(cells[key] - value) > 1:
                        raise ValueError(
                            f"{path.name} {key}: iki ciltte farklı {cells[key]} / {value}"
                        )
                    cells[key] = value
        records = [
            {
                "area_id": pid,
                "area_level": "province",
                "period_start": dt.date(year, 1, 1),
                "dims": "road_class=" + road_class,
                "value": value,
            }
            for (year, pid, road_class), value in cells.items()
        ]
        unit = ("thousand_vehicle_km", "thousand_passenger_km", "thousand_tonne_km")[
            self.measure
        ]
        return fact(records, self.indicator_id, unit, self.vintage, self.retrieved_at)


class KgmPassengerKm(KgmVehicleKm):
    indicator_id = "kgm_passenger_km"
    measure = 1


class KgmTonneKm(KgmVehicleKm):
    indicator_id = "kgm_tonne_km"
    measure = 2


# endregion

# region Traffic accident summaries

#: `2015 1.313.359 183.011 1.130.348 7.530 3.831 3.699 304.421` — year, all accidents,
#: fatal or injury, damage only, deaths total, at the scene, within 30 days (`-` before
#: 2015: not collected), injured.
ACCIDENT_ROW = re.compile(r"^(?P<year>20\d{2}) (?P<nums>[\d.]+(?: (?:[\d.]+|-)){6})$")


@cache
def accident_series() -> dict[int, list[float | None]]:
    """Table 1 of the archived summaries (2015 and 2016 editions), newest edition winning.

    The current edition prints the table as drawing, not text, and the 2009-2011 editions
    use police and gendarmerie counts that drop agreed damage-only accidents from 2008 —
    a different series. Only the TÜİK-based Table 1 is read.
    """
    series: dict[int, list[float | None]] = {}
    for path in sorted(ARCHIVE.glob("TrafikKazalariOzeti2017_*.pdf")):
        try:
            lines = pdf_lines(path)
        except Exception:  # noqa: BLE001, S112 — two archived copies are truncated
            continue
        for line in lines:
            match = ACCIDENT_ROW.match(line)
            if not match:
                continue
            values = [None if v == "-" else number(v) for v in match["nums"].split()]
            total, injury, damage, deaths, scene, later, _ = values
            if total != injury + damage or deaths != scene + (later or 0):
                raise ValueError(f"{path.name}: kaza satırı toplamı tutmuyor: {line}")
            series[int(match["year"])] = values
    return series


class KgmTrafficAccidents(Kgm):
    """Traffic accidents, Türkiye, 2006-2016, by kind (KGM summaries, TÜİK figures)."""

    indicator_id = "traffic_accidents_total"
    vintage = "2017-07"

    def fetch(self) -> Path:
        return ARCHIVE

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        for year, values in accident_series().items():
            for kind, value in (
                ("fatal_or_injury", values[1]),
                ("damage_only", values[2]),
            ):
                records.append(
                    {
                        "area_id": "TR",
                        "area_level": "country",
                        "period_start": dt.date(year, 1, 1),
                        "dims": "accident_kind=" + kind,
                        "value": value,
                    }
                )
        return fact(
            records, self.indicator_id, "accident", self.vintage, self.retrieved_at
        )


class KgmTrafficCasualties(KgmTrafficAccidents):
    """Killed (at the scene, within 30 days) and injured, Türkiye, 2006-2016."""

    indicator_id = "traffic_casualties"

    def parse(self, raw: Path) -> pl.DataFrame:
        records = []
        for year, values in accident_series().items():
            items = [("killed_at_scene", values[4]), ("injured", values[6])]
            if values[5] is not None:
                items.append(("killed_within_30_days", values[5]))
            for kind, value in items:
                records.append(
                    {
                        "area_id": "TR",
                        "area_level": "country",
                        "period_start": dt.date(year, 1, 1),
                        "dims": "casualty=" + kind,
                        "value": value,
                    }
                )
        return fact(
            records, self.indicator_id, "person", self.vintage, self.retrieved_at
        )


# endregion

# region Bridges

BRIDGE_TITLES = (
    ("state", "DEVLET YOLLARI ÜZERİNDEKİ BÜYÜKSANAT YAPILARI"),
    ("provincial", "İL YOLLARI ÜZERİNDEKİ BÜYÜK SANAT YAPILARI"),
    ("combined", "DEVLET VE İL YOLLARI ÜZERİNDEKİ BÜYÜK SANAT YAPILARI"),
)
MATERIALS = ("reinforced_concrete", "steel", "stone")
BRIDGE_ROW = re.compile(r"^(?P<year>20\d{2}) (?P<nums>\S+(?: \S+){7})$")


@cache
def bridge_tables() -> dict[str, dict[int, list[float]]]:
    """Road class -> year -> [count, length] × (concrete, steel, stone, total)."""
    raw = (
        PDF
        / "Istatistikler_SanatYapilariBakimOnarimIsletmeBilgileri"
        / "kopruenvanterbilgileri.pdf"
    )
    tables: dict[str, dict[int, list[float]]] = {}
    current = None
    for line in pdf_lines(raw):
        for road_class, title in BRIDGE_TITLES:
            if line == title:
                current = road_class
                tables[current] = {}
        match = BRIDGE_ROW.match(line)
        if current and match:
            tables[current][int(match["year"])] = [
                number(v) for v in match["nums"].split()
            ]
    if set(tables) != {"state", "provincial", "combined"}:
        raise ValueError("köprü tabloları eksik: " + repr(set(tables)))
    return tables


def bridge_checks() -> list[str]:
    """Where the printed tables disagree with themselves. Reported, not fatal."""
    notes = []
    tables = bridge_tables()
    for road_class, rows in tables.items():
        for year, v in rows.items():
            if v[0] + v[2] + v[4] != v[6] or abs(v[1] + v[3] + v[5] - v[7]) > 1:
                notes.append(f"{road_class} {year}: malzeme toplamı tutmuyor")
    for year, v in tables["combined"].items():
        s, p = tables["state"][year], tables["provincial"][year]
        if s[6] + p[6] != v[6]:
            notes.append(
                f"{year}: devlet {s[6]:.0f} + il {p[6]:.0f} != birleşik {v[6]:.0f}"
            )
    return notes


class KgmBridges(Kgm):
    """Large bridges on state and provincial roads by material, Türkiye, 2002-2024."""

    indicator_id = "bridges"
    vintage = "2025-01"
    position = 0  # count; length is position 1

    def fetch(self) -> Path:
        return (
            PDF
            / "Istatistikler_SanatYapilariBakimOnarimIsletmeBilgileri"
            / "kopruenvanterbilgileri.pdf"
        )

    def parse(self, raw: Path) -> pl.DataFrame:
        tables = bridge_tables()
        records = []
        for road_class in ("state", "provincial"):
            for year, values in tables[road_class].items():
                for m, material in enumerate(MATERIALS):
                    records.append(
                        {
                            "area_id": "TR",
                            "area_level": "country",
                            "period_start": dt.date(year, 1, 1),
                            "dims": f"bridge_material={material};road_class={road_class}",
                            "value": values[2 * m + self.position],
                        }
                    )
        unit = "bridge" if self.position == 0 else "metre"
        return fact(records, self.indicator_id, unit, self.vintage, self.retrieved_at)


class KgmBridgeLength(KgmBridges):
    indicator_id = "bridge_length"
    position = 1


# endregion

KGM_ADAPTERS = {
    "kgm_province_distance": KgmProvinceDistance,
    "kgm_district_distance": KgmDistrictDistance,
    "kgm_road_length": KgmRoadClassArchive,
    "kgm_divided_road": KgmDividedRoadClassArchive,
    "kgm_road_length_history": KgmRoadLengthHistory,
    "kgm_road_length_archive": KgmRoadLengthArchive,
    "kgm_divided_road_archive": KgmDividedRoadArchive,
    "kgm_motorway": KgmMotorway,
    "kgm_bridges": KgmBridges,
    "kgm_traffic_accidents": KgmTrafficAccidents,
    "kgm_traffic_casualties": KgmTrafficCasualties,
    "kgm_vehicle_km": KgmVehicleKm,
    "kgm_passenger_km": KgmPassengerKm,
    "kgm_tonne_km": KgmTonneKm,
    "kgm_bridge_length": KgmBridgeLength,
}
