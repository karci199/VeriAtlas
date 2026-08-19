"""Education-level indicators from MEB workbooks: rates as published, ratios as computed.

Six workbooks, one province-level pivot each, all in the shape every other MEDAS-style
export uses — plate-code labels in the header (`Adana-1`), a category in one column, a
year in the next. `area_of` and `LABEL` are reused unchanged from `tuik_median_age`: this
source needed no name matching (K15 already solved it) and no district-level renames to
chase, because these files never went below province.

Two things this module reads but does not store, because storing them would double an
existing category:

* `Genel Ortaöğretim` and `Mesleki Ve Teknik Ortaöğretim` are not separate education
  levels, they are `Ortaöğretim`'s own two components — verified against the source
  (Adana 2024: 97160 + 57642 = 154802, the published `Ortaöğretim` total exactly). Kept
  out of `EGITIM_DUZEYLERI` so a straight sum over the dimension never double-counts.
* `İlköğretim`, published only in the net-enrollment workbook, is the pre-4+4+4-reform
  merge of `İlkokul` and `Ortaokul`. It has no counterpart in the other five workbooks
  (they already split it), so it is read only where `net_enrollment_rate` needs it and
  dropped everywhere else rather than becoming a fifth dimension value nothing else uses.

**Four of the six indicators are computed, not published.** `class_size`, `section_size`,
`section_room_ratio` and `school_size` are ratios of two raw counts (students, rooms,
sections, schools) that this source publishes separately. The project's usual answer to
"a number nobody publishes" is a `[ratio]` or `[base]` entry in the dictionary, computed
by the page from two indicators already in the fact table (K12) — but both mechanisms
assume the denominator is a *slice of one indicator* (a sex, an age band), not a second
indicator matched key-for-key on a shared dimension. There is a real precedent for the
other route: `natural_increase` (births − deaths) is computed once, at load time, and
stored as its own indicator, exactly because sex_ratio (Ratio 1'in dimension is the sex a
single indicator) doesn't fit that shape either. These four follow it — computed here from
counts that never themselves become indicators, because nothing else needs "kaç derslik
var" on its own, only the ratio.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import polars as pl

from ..adapters.base import cached_copy
from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .tuik_median_age import area_of, single_province_regions

DESKTOP = Path(r"C:\Users\katan\OneDrive\Desktop\demografi")
DOWNLOADS = RAW / "meb"

FILES = {
    "okullasma": "İllere Göre Net Okullaşma Oranları.xls",
    "ogrenci_cinsiyet": "İllere ve Yıllara Göre Eğitim Düzeyi Öğrenci Sayıları Cinsiyet.xls",
    "derslik": "İllere ve Yıllara Göre Eğitim Düzeyi Derslik Sayıları.xls",
    "sube": "İllere ve Yıllara Göre Eğitim Düzeyi Şube Sayıları.xls",
    "ogrenci": "İllere ve Yıllara Göre Eğitim Düzeyi Öğrenci Sayıları.xls",
    "okul": "İllere ve Yıllara Göre Eğitim Düzeyi Okul Sayıları.xls",
}

#: The four levels that partition the whole, matched against the dictionary's
#: `dim.egitim_duzeyi.values` — see the module docstring for what is deliberately left out.
EGITIM_DUZEYLERI = {
    "Okul Öncesi": "okul_oncesi",
    "İlkokul": "ilkokul",
    "Ortaokul": "ortaokul",
    "Ortaöğretim": "ortaogretim",
}

SEXES = {"Kadın": "female", "Erkek": "male"}


def fetch(key: str) -> Path:
    return cached_copy(DESKTOP / FILES[key], DOWNLOADS / (key + ".xls"))


def read_pivot(path: Path) -> pl.DataFrame:
    """One MEB pivot to long rows: `(area_id, area_level, kategori, yil, deger)`.

    The header row carries plate-code labels (`Adana-1`); the category repeats down
    column B only when it changes, so it is forward-filled by hand rather than assumed
    present on every row.
    """
    df = pl.read_excel(path, engine="calamine", has_header=False)
    header = df.row(1)
    single = single_province_regions()

    columns: dict[int, tuple[str, str]] = {}
    for index in range(3, df.width):
        cell = header[index]
        if cell is None:
            continue
        match = re.match(r"^(?P<name>.+)-(?P<code>[A-Z0-9]+)$", cell)
        if not match:
            continue
        area = area_of(match.group("code"), single)
        if area is None:
            continue
        columns[index] = area

    if not columns:
        raise ValueError("başlık satırında alan bulunamadı: " + str(path))

    rows: list[dict] = []
    kategori = None
    for r in range(df.height):
        row = df.row(r)
        if row[1] is not None:
            kategori = str(row[1]).strip()
        year_cell = row[2]
        if year_cell is None or not str(year_cell).strip().isdigit():
            continue
        year = int(str(year_cell).strip())
        for index, (area_id, area_level) in columns.items():
            value = row[index]
            if value is None:
                continue
            try:
                fvalue = float(value)
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "area_id": area_id,
                    "area_level": area_level,
                    "kategori": kategori,
                    "yil": year,
                    "deger": fvalue,
                }
            )
    return pl.DataFrame(rows)


def _to_rows(
    frame: pl.DataFrame,
    indicator_id: str,
    source_id: str,
    vintage: str,
    retrieved_at: dt.date,
) -> pl.DataFrame:
    indicator = get(indicator_id)
    return frame.with_columns(
        pl.lit(indicator_id).alias("indicator_id"),
        pl.col("yil").cast(pl.Int32),
        pl.date(pl.col("yil"), 1, 1).alias("period_start"),
        pl.lit(indicator.frequency).alias("frequency"),
        pl.lit(indicator.unit.unit_id).alias("unit"),
        pl.lit("measured").alias("quality_flag"),
        pl.lit(vintage).alias("vintage"),
        pl.lit(source_id).alias("source_id"),
        pl.lit(retrieved_at).alias("retrieved_at"),
    ).select(
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


class _MebAdapter:
    source_id = "meb_egitim"
    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 19)

    def fetch(self) -> Path:
        raise NotImplementedError

    def parse(self, raw: Path) -> pl.DataFrame:
        raise NotImplementedError


class NetEnrollmentRate(_MebAdapter):
    """Net okullaşma oranı, cinsiyet × düzey.

    Ortaöğretim is read as published. İlkokul/Ortaokul/İlköğretim collapse into one
    `ilkogretim` value — see the dictionary note (`dim.egitim_duzeyi`) and the module
    docstring for why: before the 2012 reform they were one institution, and keeping
    the reformed split as its own dimension value would mean the pre-reform years
    simply have no data for it, and the post-reform years no data for the combined one.

    Where the source already gives `İlköğretim` directly, that value is used unchanged.
    Where it only gives `İlkokul` and `Ortaokul` separately (post-reform), the two rates
    are combined weighted by each level's own gendered student count from
    `ogrenci_cinsiyet` — an unweighted average would let a small level's rate move the
    combined number as much as a large one's.
    """

    indicator_id = "net_enrollment_rate"

    def fetch(self) -> Path:
        fetch("okullasma")
        fetch("ogrenci_cinsiyet")
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        long = read_pivot(fetch("okullasma"))
        rows = []
        ilkogretim_direct: set[tuple[str, int, str]] = set()
        split_rows: dict[tuple[str, int, str, str], float] = {}

        for row in long.to_dicts():
            match = re.match(
                r"^(?P<sex>Kadın|Erkek) ve (?P<duzey>.+)$", row["kategori"]
            )
            if not match:
                continue
            sex = SEXES[match.group("sex")]
            duzey = match.group("duzey")
            key = (row["area_id"], row["yil"], sex)

            if duzey == "Ortaöğretim":
                rows.append(
                    {
                        **row,
                        "dims": format_dims(
                            {"sex": sex, "egitim_duzeyi": "ortaogretim"}
                        ),
                        "value": row["deger"],
                    }
                )
            elif duzey == "İlköğretim":
                rows.append(
                    {
                        **row,
                        "dims": format_dims(
                            {"sex": sex, "egitim_duzeyi": "ilkogretim"}
                        ),
                        "value": row["deger"],
                    }
                )
                ilkogretim_direct.add(key)
            elif duzey in ("İlkokul", "Ortaokul"):
                split_rows[(*key, duzey)] = row["deger"]

        # Agirliklandirilmis birlestirme: ayni (il, yil, cinsiyet) icin Ilkokul+Ortaokul
        # ogrenci sayisi, dogrudan Ilkogretim verisi olmayan yillar icin.
        counts = read_pivot(fetch("ogrenci_cinsiyet"))
        weight: dict[tuple[str, int, str, str], float] = {}
        for row in counts.to_dicts():
            match = re.match(
                r"^(?P<sex>Kadın|Erkek) ve (?P<duzey>İlkokul|Ortaokul)$",
                row["kategori"],
            )
            if not match:
                continue
            sex = SEXES[match.group("sex")]
            weight[(row["area_id"], row["yil"], sex, match.group("duzey"))] = row[
                "deger"
            ]

        seen_keys = {k[:3] for k in split_rows}
        for area_id, yil, sex in seen_keys:
            if (area_id, yil, sex) in ilkogretim_direct:
                continue
            ilkokul = split_rows.get((area_id, yil, sex, "İlkokul"))
            ortaokul = split_rows.get((area_id, yil, sex, "Ortaokul"))
            if ilkokul is None or ortaokul is None:
                continue
            w_ilkokul = weight.get((area_id, yil, sex, "İlkokul"))
            w_ortaokul = weight.get((area_id, yil, sex, "Ortaokul"))
            if w_ilkokul and w_ortaokul:
                combined = (ilkokul * w_ilkokul + ortaokul * w_ortaokul) / (
                    w_ilkokul + w_ortaokul
                )
            else:
                combined = (ilkokul + ortaokul) / 2  # agirlik yoksa esit agirlik
            rows.append(
                {
                    "area_id": area_id,
                    "area_level": "province",
                    "yil": yil,
                    "dims": format_dims({"sex": sex, "egitim_duzeyi": "ilkogretim"}),
                    "value": combined,
                }
            )

        frame = pl.DataFrame(rows)
        return _to_rows(
            frame, self.indicator_id, self.source_id, self.vintage, self.retrieved_at
        )


def _duzey_only(row: dict) -> str | None:
    return EGITIM_DUZEYLERI.get(row["kategori"])


def _load_counts(key: str) -> pl.DataFrame:
    """A raw-count workbook (öğrenci/derslik/şube/okul), filtered to the four levels."""
    raw = fetch(key)
    long = read_pivot(raw)
    long = long.filter(pl.col("kategori").is_in(EGITIM_DUZEYLERI))
    return long.with_columns(
        pl.col("kategori").replace(EGITIM_DUZEYLERI).alias("egitim_duzeyi")
    )


def _ratio_indicator(indicator_id: str, numerator_key: str, denominator_key: str):
    class _Ratio(_MebAdapter):
        pass

    _Ratio.indicator_id = indicator_id

    def _fetch(self) -> Path:
        # Both files are fetched so the manifest's checksum covers both; `_parse` re-reads
        # them by key rather than by the single `raw` path `ingest` hands back.
        fetch(numerator_key)
        fetch(denominator_key)
        return DOWNLOADS

    def _parse(self, raw: Path) -> pl.DataFrame:
        num = _load_counts(numerator_key).rename({"deger": "num"})
        den = _load_counts(denominator_key).rename({"deger": "den"})
        joined = num.join(
            den, on=["area_id", "area_level", "egitim_duzeyi", "yil"], how="inner"
        )
        joined = joined.filter(pl.col("den") > 0).with_columns(
            (pl.col("num") / pl.col("den")).alias("value"),
            pl.struct("egitim_duzeyi")
            .map_elements(
                lambda s: format_dims({"egitim_duzeyi": s["egitim_duzeyi"]}),
                return_dtype=pl.String,
            )
            .alias("dims"),
        )
        return _to_rows(
            joined, indicator_id, self.source_id, self.vintage, self.retrieved_at
        )

    _Ratio.fetch = _fetch
    _Ratio.parse = _parse
    return _Ratio


ClassSize = _ratio_indicator("class_size", "ogrenci", "derslik")
SectionSize = _ratio_indicator("section_size", "ogrenci", "sube")
SectionRoomRatio = _ratio_indicator("section_room_ratio", "sube", "derslik")
SchoolSize = _ratio_indicator("school_size", "ogrenci", "okul")


class GenderStudentRatio(_MebAdapter):
    """Kadın/Erkek öğrenci sayısı oranı — computed from the gendered student counts."""

    indicator_id = "gender_student_ratio"

    def fetch(self) -> Path:
        return fetch("ogrenci_cinsiyet")

    def parse(self, raw: Path) -> pl.DataFrame:
        long = read_pivot(raw)
        rows = []
        for row in long.to_dicts():
            match = re.match(
                r"^(?P<sex>Kadın|Erkek) ve (?P<duzey>.+)$", row["kategori"]
            )
            if not match or match.group("duzey") not in EGITIM_DUZEYLERI:
                continue
            rows.append(
                {
                    "area_id": row["area_id"],
                    "area_level": row["area_level"],
                    "yil": row["yil"],
                    "egitim_duzeyi": EGITIM_DUZEYLERI[match.group("duzey")],
                    "sex": SEXES[match.group("sex")],
                    "deger": row["deger"],
                }
            )
        long2 = pl.DataFrame(rows)
        wide = long2.pivot(
            on="sex",
            index=["area_id", "area_level", "yil", "egitim_duzeyi"],
            values="deger",
        )
        wide = wide.filter(pl.col("male") > 0).with_columns(
            (pl.col("female") / pl.col("male") * 100).alias("value"),
            pl.struct("egitim_duzeyi")
            .map_elements(
                lambda s: format_dims({"egitim_duzeyi": s["egitim_duzeyi"]}),
                return_dtype=pl.String,
            )
            .alias("dims"),
        )
        return _to_rows(
            wide, self.indicator_id, self.source_id, self.vintage, self.retrieved_at
        )


MEB_ADAPTERS = {
    "net_enrollment_rate": NetEnrollmentRate,
    "gender_student_ratio": GenderStudentRatio,
    "class_size": ClassSize,
    "section_size": SectionSize,
    "section_room_ratio": SectionRoomRatio,
    "school_size": SchoolSize,
}
