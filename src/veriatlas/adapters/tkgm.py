r"""TKGM MEGSİS: how much of the cadastre is on the map, province by province.

`scripts/fetch_tkgm_megsis.py` saves the province table of
cbs.tkgm.gov.tr/istatistik/MegsisGenel.aspx as a CSV in `C:\veri-ham\tkgm\`. It is a
snapshot of the day it was taken, not a series — the page prints one "Güncelleme Tarihi"
and no history — so it is stored under the year of that date and will be replaced, not
appended to, when it is taken again.

Three readings of the same parcels, which is why they are three indicators and not one
breakdown: what the registers hold (the title deed's parcels, the cadastre's parcels, and
the parcels the cadastre has but the title deed does not), whether the parcel's geometry
has been approved, and how good its coordinates are. Adding across those three would count
the same parcel three times.

`onayli_oran` is not written: it is the approved share, which follows from the counts.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from functools import cache
from pathlib import Path

import polars as pl

from ..areas import load_neighbourhoods, load_villages
from ..config import RAW
from .kgm import district_key, fold, province_id, provinces, resolve_district

FOLDER = RAW / "tkgm" if (RAW / "tkgm").exists() else Path("C:/veri-ham/tkgm")
SOURCE = "tkgm_megsis"

#: Indicator -> {CSV column: dimension value}. The dim key is the indicator's own.
REGISTERS = {
    "tapu_parsel": "title_deed",
    "kadastro_parsel": "cadastre",
    "tapuda_olmayan_parsel": "not_in_title_deed",
}
APPROVALS = {"onayli_parsel": "approved", "onaysiz_parsel": "unapproved"}
COORDINATES = {
    "kesin_koordinatli": "final",
    "gecici_koordinatli": "provisional",
    "iyilestirilmis_koordinatli": "improved",
}


def snapshot() -> Path:
    """The newest saved snapshot; the file name carries the page's update date."""
    files = sorted(FOLDER.glob("megsis_il_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"TKGM anlık görüntüsü yok: {FOLDER} (scripts/fetch_tkgm_megsis.py)"
        )
    return files[-1]


@cache
def table() -> tuple[dt.date, dict[str, dict[str, float]]]:
    """(snapshot date, {area_id: {column: count}}), with all 81 provinces or it raises."""
    path = snapshot()
    taken = dt.date.fromisoformat(path.stem.rsplit("_", 1)[1])
    rows: dict[str, dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            area = province_id(row["il"])
            if area in rows:
                raise ValueError(f"TKGM: {row['il']} iki kez")
            rows[area] = {
                column: float(row[column])
                for column in (*REGISTERS, *APPROVALS, *COORDINATES)
            }
    missing = sorted(set(provinces().values()) - set(rows))
    if missing:
        raise ValueError(f"TKGM: eksik il {missing}")
    return taken, rows


class Megsis:
    """One reading of the parcel table, as of the snapshot date."""

    source_id = SOURCE
    unit = "parcel"
    indicator_id: str
    dim: str
    columns: dict[str, str]

    def fetch(self) -> Path:
        return FOLDER

    def parse(self, raw: Path) -> pl.DataFrame:
        taken, district_rows = district_table()
        province_rows = province_totals(district_rows)
        _, settlement_rows, matched, total = settlement_table()
        print(
            f"  TKGM yerleşim: {matched}/{total} birim eşleşti ({matched / total:.1%});"
            " eşleşmeyenler kadastro birimi, mahalle değil",
            flush=True,
        )
        levelled: list[tuple[str, str, dict[str, float]]] = [
            *((a, "province", c) for a, c in sorted(province_rows.items())),
            *((a, "district", c) for a, c in sorted(district_rows.items())),
            *((a, level, c) for (a, level), c in sorted(settlement_rows.items())),
        ]
        records = [
            {
                "area_id": area,
                "area_level": level,
                "dims": f"{self.dim}={value}",
                "value": counts[column],
            }
            for area, level, counts in levelled
            for column, value in self.columns.items()
        ]
        return (
            pl.DataFrame(records)
            .with_columns(
                pl.lit(self.indicator_id).alias("indicator_id"),
                pl.lit(dt.date(taken.year, 1, 1)).alias("period_start"),
                pl.lit("annual").alias("frequency"),
                pl.lit(self.unit).alias("unit"),
                pl.lit("measured").alias("quality_flag"),
                pl.lit(taken.strftime("%Y-%m")).alias("vintage"),
                pl.lit(self.source_id).alias("source_id"),
                pl.lit(taken).alias("retrieved_at"),
            )
            .select(
                "indicator_id",
                "area_id",
                "area_level",
                "period_start",
                "frequency",
                "value",
                "unit",
                "dims",
                "quality_flag",
                "vintage",
                "source_id",
                "retrieved_at",
            )
        )


class Parcels(Megsis):
    indicator_id = "cadastral_parcels"
    dim = "parcel_register"
    columns = REGISTERS


class ParcelApproval(Megsis):
    indicator_id = "cadastral_parcels_by_approval"
    dim = "parcel_approval"
    columns = APPROVALS


class ParcelCoordinates(Megsis):
    indicator_id = "cadastral_parcels_by_coordinate"
    dim = "coordinate_quality"
    columns = COORDINATES


TKGM_ADAPTERS = {
    "cadastral_parcels": Parcels,
    "cadastral_parcels_by_approval": ParcelApproval,
    "cadastral_parcels_by_coordinate": ParcelCoordinates,
}


# region District and neighbourhood


#: `Kemalpaşa (artvin)`: TKGM disambiguates the two Kemalpaşa districts in the name
#: itself. The province is already known from the row, so the bracket is dropped.
BRACKET = re.compile(r"\(.*?\)")

#: `İskele/karşıyaka`: a cadastral unit written as a sub-unit of another one. The part
#: before the slash is the settlement the register knows.
SUBUNIT = re.compile(r"/.*$")

#: `Akören Mah.`, `Boztahta Köy.` — the registry's names carry the settlement kind.
KIND = re.compile(r"\s+(Mah|Köy)\.?\s*$")

#: A village record that stops in 2012 is a village law 6360 abolished: the settlement
#: is a neighbourhood today, so a 2026 snapshot must not be filed against it.
VILLAGES_ALIVE_FROM = 2013


def unit_key(name: str) -> str:
    return fold(KIND.sub("", name.strip()))


@cache
def settlement_key() -> dict[tuple[str, str], tuple[str, str]]:
    """(district id, folded settlement name) -> (area id, area level).

    Neighbourhoods win over villages: in a metropolitan province the village record is
    the abolished one, and elsewhere the two names rarely collide.
    """
    key: dict[tuple[str, str], tuple[str, str]] = {}
    villages = load_villages().filter(pl.col("last_seen") >= VILLAGES_ALIVE_FROM)
    for row in villages.iter_rows(named=True):
        key.setdefault(
            (row["parent_id"], unit_key(row["name_tr"])), (row["area_id"], "village")
        )
    for row in load_neighbourhoods().iter_rows(named=True):
        key[(row["parent_id"], unit_key(row["name_tr"]))] = (
            row["area_id"],
            "neighbourhood",
        )
    return key


def province_totals(
    districts: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Provinces summed from their districts, cross-checked against the source's own
    province table.

    The two files are not from the same day — the province table was taken on 14.09 and
    the drill-down on 18.09 — and the cadastre grew by a few thousand parcels in between.
    So the province row is rebuilt from the districts, which keeps one snapshot date for
    every level, and the older table is used only to catch a drill that went wrong: a
    misdirected postback would move a whole district, not a few hundred parcels.
    """
    totals: dict[str, dict[str, float]] = {}
    for area, counts in districts.items():
        province = totals.setdefault(area[:5], dict.fromkeys(counts, 0.0))
        for column, value in counts.items():
            province[column] += value
    _, published = table()
    for area, counts in totals.items():
        drift = abs(counts["kadastro_parsel"] - published[area]["kadastro_parsel"])
        if drift > published[area]["kadastro_parsel"] * 0.01:
            raise ValueError(
                f"TKGM: {area} ilçe toplamı il tablosundan %1'den fazla sapıyor"
            )
    return totals


@cache
def district_table() -> tuple[dt.date, dict[str, dict[str, float]]]:
    """(snapshot date, {district area id: counts}), checked against the province totals."""
    files = sorted(FOLDER.glob("megsis_ilce_*.csv"))
    if not files:
        raise FileNotFoundError(f"TKGM ilçe görüntüsü yok: {FOLDER}")
    taken = dt.date.fromisoformat(files[-1].stem.rsplit("_", 1)[1])
    key = district_key()
    rows: dict[str, dict[str, float]] = {}
    with files[-1].open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            area, level = resolve_district(key, row["il"], BRACKET.sub("", row["ilce"]))
            if level != "district":
                raise ValueError(f"TKGM: ilçe değil {row['il']}/{row['ilce']}")
            if area in rows:
                raise ValueError(f"TKGM: {row['il']}/{row['ilce']} iki kez")
            rows[area] = {
                column: float(row[column] or 0)
                for column in (*REGISTERS, *APPROVALS, *COORDINATES)
            }
    return taken, rows


@cache
def settlement_table() -> tuple[
    dt.date, dict[tuple[str, str], dict[str, float]], int, int
]:
    """(date, {(area id, level): counts}, matched units, total units).

    A TKGM row is a *cadastral unit*, not a neighbourhood: the register still carries
    units under names the settlement lost decades ago (`Aşvan` in Elazığ was flooded by
    the Keban dam), and one settlement can hold several units (`İskele/karşıyaka`). So
    several rows can land on one area — they are summed, not overwritten — and the rows
    that no settlement answers to are counted rather than dropped in silence.
    """
    files = sorted(FOLDER.glob("megsis_mahalle_*.csv"))
    if not files:
        raise FileNotFoundError(f"TKGM mahalle görüntüsü yok: {FOLDER}")
    taken = dt.date.fromisoformat(files[-1].stem.rsplit("_", 1)[1])
    districts, settlements = district_key(), settlement_key()
    rows: dict[tuple[str, str], dict[str, float]] = {}
    matched = total = 0
    with files[-1].open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            total += 1
            try:
                district, level = resolve_district(
                    districts, row["il"], BRACKET.sub("", row["ilce"])
                )
            except KeyError:
                continue
            if level != "district":
                continue
            name = unit_key(row["mahalle"])
            found = settlements.get((district, name))
            if found is None:
                found = settlements.get(
                    (district, unit_key(SUBUNIT.sub("", row["mahalle"])))
                )
            if found is None:
                continue
            matched += 1
            counts = rows.setdefault(
                found, dict.fromkeys((*REGISTERS, *APPROVALS, *COORDINATES), 0.0)
            )
            for column in counts:
                counts[column] += float(row[column] or 0)
    if matched < total * 0.75:
        raise ValueError(
            f"TKGM: yerleşim eşleşmesi {matched}/{total}, kayıt defteri bozulmuş olabilir"
        )
    return taken, rows, matched, total
