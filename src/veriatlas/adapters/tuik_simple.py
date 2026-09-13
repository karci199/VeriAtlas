"""The narrow MEDAS measures: density, households, migration, foreign nationals.

`scripts/fetch_medas_simple.py` pulls a file per measure and level, each one small enough
that a single query covered every published year. They share a shape — year down the
rows, area label carrying its code (K15), one or more value columns — so they share an
adapter, and what differs between them is a line in `MEASURES` rather than a module.

Only the measures that bring something new are loaded. TÜİK also publishes the annual
growth rate, the sex ratio and the three dependency ratios, and all five are exact
functions of rows we already hold: they stay in `raw/` as a check on our own derivations
(and that check passed — 0,0025 mean absolute difference over 1.539 province-years)
rather than becoming a second copy on the screen that could drift out of step.

Three shapes, and the third is a trap:

* **No breakdown** — one value column headed `Ölçüm bazında`.
* **Named columns** — the header names each value, as sexes or household types.
* **Two breakdowns in one column** — migration in and out arrive as sex × fourteen age
  bands, 28 columns. Stored with both (2026-09-13; until then summed to a total). The 28
  cells reproduce the old totals in 1.458 of 1.458 province-years.

The trap: the nine household types MEDAS publishes are **not siblings**. "Tek çekirdek
aileden oluşan hanehalkı" contains three of the others, and one of those contains two
more. Summing all nine gives 977.631 households for Adana in 2014 where the published
count is 548.384 — a 78% overcount that looks like a plausible number. Only the four that
partition the whole are stored, and those reproduce the published total in 972 of 972
province-years.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..areas import load_areas
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .tuik_median_age import area_of, single_province_regions

DOWNLOADS = RAW / "medas" / "basit"

#: `Adana-1`, `Türkiye-TR`
LABEL = re.compile(r"^(?P<name>.+)-(?P<code>[A-Z0-9]+)$")

#: The four household types that partition the whole, to the ids the fact table stores.
#: The other five are sub-types of these and are deliberately not loaded — see the note
#: above. Kept as a mapping rather than a list so the Turkish stays out of the ids (K1).
HOUSEHOLD_TYPES = {
    "Tek Kişilik Hanehalkı": "single_person",
    "Tek Çekirdek Aileden Oluşan Hanehalkı": "one_nuclear_family",
    "En Az Bir Çekirdek Aile Ve Diğer Kişilerden Oluşan Hanehalkı": "nuclear_and_others",
    "Çekirdek Aile Bulunmayan Birden Fazla Kişiden Oluşan Hanehalkı": "no_nuclear_family",
}

SEXES = {"Erkek": "male", "Kadın": "female"}

#: Migration in and out arrive as sex × fourteen age bands, 28 columns headed
#: `Erkek ve 15-19`. Stored with both breakdowns (K29: the broken-down file replaces the
#: total rather than sitting beside it); the bands are the source's own, closing at 65+.
MIGRATION_BANDS = [
    "0-4",
    "5-9",
    "10-14",
    "15-19",
    "20-24",
    "25-29",
    "30-34",
    "35-39",
    "40-44",
    "45-49",
    "50-54",
    "55-59",
    "60-64",
    "65+",
]
MIGRATION_COLUMNS = {
    f"{sex_tr} ve {band}": {"sex": sex, "age": band}
    for sex_tr, sex in SEXES.items()
    for band in MIGRATION_BANDS
}

#: file stem → (indicator id, dim name or None, column map or None).
#:
#: A column map means "keep only these columns, under these ids"; `None` with a dim means
#: there is no dim and the columns are summed; `None` with no dim means the single value
#: column is the value.
MEASURES = {
    "yogunluk": ("population_density", None, None),
    "hane-buyuklugu": ("household_size", None, None),
    "hane-sayisi": ("household_count", None, None),
    "hane-tipleri": ("household_by_type", "household_type", HOUSEHOLD_TYPES),
    "goc-aldigi": ("migration_in", None, MIGRATION_COLUMNS),
    "goc-verdigi": ("migration_out", None, MIGRATION_COLUMNS),
    "goc-net": ("migration_net", None, None),
    # `goc-net-hizi` is downloaded and not loaded: it is net migration divided by the
    # population, and the screen's "İl nüfusunun %'si" already divides by exactly that.
    # See the note above `[indicator.migration_from_abroad]` in the dictionary.
    "goc-disaridan": ("migration_from_abroad", None, None),
    "goc-disariya": ("migration_to_abroad", None, None),
    "yabanci-uyruklu": ("foreign_population", "sex", SEXES),
    # Yaşam süresi looks like it belongs here — a sex breakdown, one number per
    # area-year — and it does not: MEDAS ships it transposed, areas across the header.
    # It is read by `tuik_vital`, which is where the transposed exports live.
    # Kütük nüfusu is *not* here, though its file has this shape. Summing its columns the
    # way this adapter sums migration's would answer the wrong question — the row is where
    # people live and the column is where they are registered, so a row's total is the
    # resident population we already hold. It needs the other axis, and that is a
    # different adapter: `tuik_registry`.
}


def read_text(path: Path) -> str:
    """The file's text. MEDAS uses either encoding depending on the measure — the district
    exports are ISO-8859-9 and these are UTF-8 with a BOM (docs/medas.md)."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "iso-8859-9"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("dosyanin kodlamasi cozulemedi: " + str(path))


#: MEDAS's own scaffolding words, which sit in the first two lines and are not columns.
FURNITURE = {"Sütunlar", "Satırlar", "Ölçüm bazında"}


def header_of(lines: list[str]) -> dict[int, str]:
    """Column index to column name.

    Found rather than counted to: a blank line at the top would shift a fixed index and
    every value would land under its neighbour's name. But "the first line that names
    something" is not it either — the file opens with `||Sütunlar|` and then a title line
    `Satırlar||Hanehalkı Tiplerine Göre…`, and taking either of those as the header left
    the real nine columns unmatched.

    What separates the header from the two lines above it: the header has nothing in its
    first two cells, and once MEDAS's own scaffolding words are dropped it is the line
    that names the most. Ties do not arise — the header is the only line naming more than
    one thing, and for a measure with no breakdown the scaffolding rule alone settles it.
    """
    best: dict[int, str] = {}
    for line in lines:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3 or cells[0] or cells[1]:
            # A row with a year or an area label in it: past the header, stop looking.
            if cells and cells[0].isdigit():
                break
            continue
        named = {
            index: cell
            for index, cell in enumerate(cells)
            if index >= 2
            and cell
            and cell not in FURNITURE
            and not cell.replace(".", "").isdigit()
        }
        if len(named) > len(best):
            best = named
    return best


def read_export(
    path: Path,
    spec: tuple,
    single: dict[str, str],
    district_codes: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """One export as fact-table rows.

    `district_codes` switches the label rule. A district file labels its rows
    `Adana(Aladağ)-1757`, and that number is a MEDAS district code, not a plate: read with
    the province rule it becomes TR-17. With the codes given, each row is resolved by code
    *and year* (a renamed district keeps its code, see `tuik_vital_district.area_at`), and
    a row that resolves to nothing while carrying a value stops the load rather than
    quietly dropping that district's households.
    """
    indicator_id, dim, columns = spec
    if district_codes is not None:
        from .tuik_vital_district import area_at
    unresolved: set[str] = set()
    lines = read_text(path).splitlines()
    header = header_of(lines)

    if columns:
        wanted = {
            index: columns[name] for index, name in header.items() if name in columns
        }
        missing = set(columns) - set(header.values())
        if missing:
            # A column that moved or was renamed would silently contribute nothing, and
            # the total would come up short in a way nobody could see on the chart.
            raise KeyError(
                indicator_id + ": dosyada olmayan sutun: " + ", ".join(sorted(missing))
            )
    else:
        wanted = None

    rows: list[dict] = []
    year = None
    for line in lines:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3:
            continue
        if cells[0].isdigit() and len(cells[0]) == 4:
            year = int(cells[0])

        label = LABEL.match(cells[1])
        if not label or year is None:
            continue
        if district_codes is None:
            area = area_of(label.group("code"), single)
        else:
            found = area_at(district_codes.get(label.group("code"), []), year)
            area = (found, "district") if found else None
            if not area and any(cells[2:]):
                unresolved.add(cells[1])
        if not area:
            continue

        def number(cell: str) -> float | None:
            try:
                return float(cell)
            except ValueError:
                return None

        if wanted:
            for index, value_id in wanted.items():
                if index >= len(cells) or not cells[index]:
                    continue
                value = number(cells[index])
                if value is None:
                    continue
                rows.append(
                    {
                        "area_id": area[0],
                        "area_level": area[1],
                        "year": year,
                        # A column can carry two breakdowns at once (`Erkek ve 15-19`),
                        # in which case the map gives the dims whole.
                        "dims": format_dims(
                            value_id if isinstance(value_id, dict) else {dim: value_id}
                        ),
                        "value": value,
                    }
                )
            continue

        # No breakdown kept: one column stays as it is, several are summed. Migration in
        # and out arrive as sex × age and are wanted as a total.
        values = [number(cell) for cell in cells[2:] if cell]
        values = [v for v in values if v is not None]
        if not values:
            # Empty is withheld, not zero.
            continue
        rows.append(
            {
                "area_id": area[0],
                "area_level": area[1],
                "year": year,
                "dims": "",
                "value": sum(values),
            }
        )
    if unresolved:
        raise KeyError(
            indicator_id
            + ": kayitta karsiligi olmayan ilce ("
            + str(len(unresolved))
            + ") "
            + path.name
            + ": "
            + ", ".join(sorted(unresolved)[:10])
        )
    return rows


def check_districts_add_up(
    frame: pl.DataFrame, indicator_id: str, additive: bool
) -> None:
    """District rows against the province rows of the same file set.

    A count must sum to its province exactly, year by year and breakdown by breakdown; a
    district missing from one year's file, or a code resolved to the wrong province, shows
    up here as a difference and nowhere else. A mean (household size) does not sum, so it
    is only checked for coverage: every province with district rows in a year.
    """
    districts = frame.filter(pl.col("area_level") == "district").with_columns(
        pl.col("area_id").str.slice(0, 5).alias("province")
    )
    provinces = frame.filter(pl.col("area_level") == "province")
    keys = ["province", "year", "dims"]

    if not additive:
        covered = districts.select("province", "year").unique()
        wanted = provinces.filter(pl.col("year") >= districts["year"].min()).select(
            pl.col("area_id").alias("province"), "year"
        )
        gaps = wanted.join(covered, on=["province", "year"], how="anti")
        if gaps.height:
            raise KeyError(
                indicator_id
                + ": ilce satiri olmayan il-yil: "
                + str(gaps.head(5).rows())
            )
        return

    summed = districts.group_by(keys).agg(pl.col("value").sum().alias("districts"))
    compared = summed.join(
        provinces.select(pl.col("area_id").alias("province"), "year", "dims", "value"),
        on=keys,
        how="full",
        coalesce=True,
    ).filter(pl.col("year") >= districts["year"].min())
    off = compared.filter(
        pl.col("districts").is_null()
        | pl.col("value").is_null()
        | ((pl.col("districts") - pl.col("value")).abs() > 0.5)
    )
    if off.height:
        raise ValueError(
            indicator_id
            + ": ilce toplami ile il tutmuyor ("
            + str(off.height)
            + " il-yil): "
            + str(off.sort("year").head(5).rows())
        )


class NarrowMeasure:
    """One measure, one indicator — the contract every other adapter keeps.

    Eleven measures share this code, so at first they shared one adapter too, and that
    was wrong in a way `ingest` caught immediately: it validates a frame against *the*
    indicator the adapter declares, and a frame carrying eleven of them fails the first
    dimension check. The contract is not in the way here, it is the thing that keeps a
    new source from quietly widening what the fact table accepts. So the class is
    generated per measure instead, and each one gets its own row count in the load log.
    """

    source_id = "tuik_medas"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 14)

    #: Filled in by the subclasses below.
    stem = ""
    spec: tuple = ()

    @property
    def indicator_id(self) -> str:
        return self.spec[0]

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        single = single_province_regions()

        # The level is named rather than globbed: `nufus-goc-net-*` also matches
        # `nufus-goc-net-hizi-province.csv`, so net migration came out with the rate rows
        # mixed in and twice as many rows as it should have. One stem is a prefix of
        # another here, which a wildcard cannot tell apart.
        records: list[dict] = []
        for level in ("country", "province"):
            path = raw / ("nufus-" + self.stem + "-" + level + ".csv")
            if path.exists():
                records.extend(read_export(path, self.spec, single))
        if not records:
            raise ValueError("dosya bulunamadi ya da bos: " + self.stem)

        # District files, where the measure was also pulled at İlçe Düzeyi: one file for
        # every year when it fitted one query, one per year when it did not. Named exactly
        # for the same reason as above — no wildcard that another stem could fall into.
        district_files = [raw / ("nufus-" + self.stem + "-ilce-district.csv")] + sorted(
            raw.glob("nufus-" + self.stem + "-ilce-district-[0-9][0-9][0-9][0-9].csv")
        )
        district_files = [path for path in district_files if path.exists()]
        if district_files:
            from .tuik_vital_district import districts_by_code

            codes = districts_by_code()
            for path in district_files:
                records.extend(read_export(path, self.spec, single, codes))

        indicator = get(self.indicator_id)
        frame = pl.DataFrame(records).with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        )

        # Every province or none, the guard the other adapters keep. A province quietly
        # absent draws as "veri yok" in the middle of the map, indistinguishable from a
        # real gap.
        expected = set(
            load_areas().filter(pl.col("area_level") == "province")["area_id"]
        )
        found = set(frame.filter(pl.col("area_level") == "province")["area_id"])
        if expected - found:
            raise KeyError(
                self.indicator_id
                + ": dosyada karsiligi olmayan il ("
                + str(len(expected - found))
                + "): "
                + ", ".join(sorted(expected - found))
            )

        if district_files:
            check_districts_add_up(frame, self.indicator_id, indicator.unit.additive)

        return frame.select(
            "indicator_id",
            "area_id",
            "area_level",
            "period_start",
            "frequency",
            "dims",
            "value",
            "unit",
            "quality_flag",
            "vintage",
            "source_id",
            "retrieved_at",
        )


#: One adapter class per measure, built from the table above. Written out by hand these
#: would be eleven copies of the same six lines, and the copy that drifted would be the
#: one nobody re-read.
NARROW_ADAPTERS = {
    "tuik_" + spec[0]: type(
        "Tuik" + "".join(part.title() for part in spec[0].split("_")),
        (NarrowMeasure,),
        {"stem": stem, "spec": spec, "__doc__": "Narrow MEDAS measure: " + spec[0]},
    )
    for stem, spec in MEASURES.items()
}
