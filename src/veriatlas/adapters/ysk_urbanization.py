"""Urbanization rate, from the 2015 election workbook: not a party number.

TÜİK never publishes an urban/rural split of the population at district level — the
population adapters carry only province and district totals (K16: finest grain
published, not derived). The one place a kent/kır split of *people* exists at district
grain is a workbook built from YSK sandık data (`AATOPLU 7H.xlsx`), which files every
ballot box under an urban or rural sheet. The party columns in that workbook are not
read here — only `Kayıtlı`, the registered-voter count, which stands in for population.

That substitution is the adapter's only real assumption, so it is worth being explicit
about what it buys and what it costs. It buys a genuine geographic split TÜİK does not
publish, at the finest grain we have anywhere: 973 districts. It costs two things —
`Kayıtlı` is voters (18+), not everyone, so a district with an unusual age structure
(students, seasonal workers) reads slightly off; and the split is frozen at a single
2015 sandık configuration, not an annual series like the rest of this table.

**Districts carry no code in this source — only a name.** Every other adapter resolves
an area from a MEDAS or plate code (K15); this one has to match `(il_adı, ilçe_adı)`
text against the registry, and text drifts for reasons that have nothing to do with
geography: a rename law didn't propagate to both sheets, a cell was typed with a
trailing space, a letter came out dotted where the registry has it dotless. None of
these fail the same way twice, so `DISTRICT_FIXES` grew one entry per mismatch actually
found rather than a general fuzzy matcher — a fuzzy match would have papered over the
"Ordu Merkez" / "Altınordu" rename (a real 2013 boundary event, not a typo) exactly the
way it would paper over "Batman " (a stray space). Distinguishing those is the point:
`resolve_district` raises on anything not in the table instead of guessing, so a new
mismatch in a future edition of this workbook fails loudly at load time rather than
silently dropping a district.

Two areas are simply missing from the source and stay missing here: Siirt has no
district-level row in `İLÇE KIR` (only the province total), and Aydın's province rows
carry a registered-voter count of zero on both the urban and rural sheet — not a small
number, an absent one. Neither is a matching bug; both are logged as skipped.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..adapters.base import cached_copy
from ..areas import load_areas, load_districts
from ..config import RAW
from ..indicators import get
from ..schema import format_dims

SOURCE_DESKTOP = r"C:\Users\katan\OneDrive\Desktop\demografi\AATOPLU 7H.xlsx"
DOWNLOADS = RAW / "ysk" / "aatoplu_7h.xlsx"

YEAR = 2015

#: Province name as the workbook spells it -> registry spelling. Only renames/typos
#: actually found in this file; not a general transliteration table.
PROVINCE_FIXES = {
    "Afyon": "Afyonkarahisar",
    "AFYON": "Afyonkarahisar",
}

#: (registry province name, workbook district name) -> registry district name.
DISTRICT_FIXES = {
    ("Ordu", "Ordu Merkez"): "Altınordu",  # renamed 2013, not a typo
    ("Adıyaman", "Kahta"): "Kâhta",
    ("Kastamonu", "Devrekani"): "Devrekâni",
    ("Tekirdağ", "Marmaraereğlisi"): "Marmara Ereğlisi",
    ("İstanbul", "Gaziosmanpaşa"): "Gazi Osmanpaşa",
    ("Erzurum", "Pazayolu"): "Pazaryolu",
    ("Gaziantep", "Islahiye"): "İslahiye",
    ("Konya", "Hadım"): "Hadim",
    ("Çorum", "Laçin"): "Lâçin",
    ("Samsun", "Ondokuzmayıs"): "19 Mayıs",
    ("Afyonkarahisar", "Afyon Merkez"): "Afyonkarahisar",
    ("Kahramanmaraş", "Onikişubat"): "Oniki Şubat",
    ("Çanakkale", "Lapseki"): "Lâpseki",
}

#: Known source gaps, skipped rather than guessed at (see module docstring).
KNOWN_GAPS = {"Siirt"}


def fetch() -> Path:
    return cached_copy(Path(SOURCE_DESKTOP), DOWNLOADS)


def _casefold_tr(name: str) -> str:
    """Upper-case with dotted/dotless İ/I collapsed to one symbol.

    `İL - KENT` writes provinces upper-case (`AFYON`, `İZMİR`), and Python's plain
    `.upper()` disagrees with itself on the dotted İ two different ways depending on
    which letter it started from — `"İzmir".upper()` keeps the dot on the first letter
    but drops it on the third. Matching would silently fail for a third of the provinces
    without this: not a rename, not a typo, just two valid upper-casings of the same
    word.
    """
    return name.upper().replace("İ", "I")


def _registry() -> tuple[dict[str, str], dict[tuple[str, str], str], dict[str, str]]:
    provinces = load_areas().filter(pl.col("area_level") == "province")
    province_by_name = dict(
        zip(provinces["name_tr"], provinces["area_id"], strict=True)
    )

    districts = load_districts()
    district_by_key: dict[tuple[str, str], str] = {}
    merkez_by_province: dict[str, str] = {}
    for row in districts.to_dicts():
        district_by_key[(row["parent_id"], row["name_tr"])] = row["area_id"]
        if row["name_tr"] == "Merkez":
            merkez_by_province[row["parent_id"]] = row["area_id"]
    return province_by_name, district_by_key, merkez_by_province


def resolve_province(name: str, province_by_name: dict[str, str]) -> str | None:
    stripped = PROVINCE_FIXES.get((name or "").strip(), (name or "").strip())
    if stripped in province_by_name:
        return province_by_name[stripped]
    folded = _casefold_tr(stripped)
    for registry_name, area_id in province_by_name.items():
        if _casefold_tr(registry_name) == folded:
            return area_id
    return None


def _normalize_pair(il_raw: str, ilce_raw: str) -> tuple[str, str]:
    """Apply the known province/district renames before anything keys on the pair.

    Must run ahead of the urban/rural combine, not just ahead of the final lookup: two
    spellings of one district ("Altınordu" in the urban sheet, "Ordu Merkez" in the
    rural one) would otherwise combine as two separate areas and then both resolve to
    the same `area_id` — one district's voters counted twice under one code.
    """
    il = (il_raw or "").strip()
    ilce = (ilce_raw or "").strip()
    il = PROVINCE_FIXES.get(il, il)
    ilce = DISTRICT_FIXES.get((il, ilce), ilce)
    return il, ilce


def resolve_district(
    il_raw: str,
    ilce_raw: str,
    province_by_name: dict[str, str],
    district_by_key: dict[tuple[str, str], str],
    merkez_by_province: dict[str, str],
) -> tuple[str | None, str]:
    il, ilce = _normalize_pair(il_raw, ilce_raw)

    province_id = resolve_province(il, province_by_name)
    if province_id is None:
        return None, "il eşlenmedi: " + il_raw

    area_id = district_by_key.get((province_id, ilce))
    if area_id is None and ilce == f"{il} Merkez":
        area_id = merkez_by_province.get(province_id) or district_by_key.get(
            (province_id, il)
        )
    if area_id is None:
        return None, "ilçe eşlenmedi: " + il_raw + " / " + ilce_raw
    return area_id, ""


def _rate(kent: pl.DataFrame, kir: pl.DataFrame, keys: list[str]) -> list[dict]:
    """Urban share of registered voters, urban and rural sheet combined by key."""
    kent = kent.with_columns(pl.col("Kayıtlı").cast(pl.Float64, strict=False))
    kir = kir.with_columns(pl.col("Kayıtlı").cast(pl.Float64, strict=False))
    kent_map = {tuple(row[k] for k in keys): row["Kayıtlı"] for row in kent.to_dicts()}
    kir_map = {tuple(row[k] for k in keys): row["Kayıtlı"] for row in kir.to_dicts()}

    rows = []
    for key in set(kent_map) | set(kir_map):
        kayitli_kent = kent_map.get(key) or 0.0
        kayitli_kir = kir_map.get(key) or 0.0
        toplam = kayitli_kent + kayitli_kir
        if toplam <= 0:
            continue  # Aydın-shaped gap: present in name only, no voters behind it.
        rows.append(
            {**dict(zip(keys, key, strict=True)), "value": kayitli_kent / toplam * 100}
        )
    return rows


class YskUrbanization2015:
    """Urbanization rate (registered-voter share, urban ballot boxes), province + district."""

    source_id = "ysk_aatoplu"
    indicator_id = "district_urbanization"

    vintage = "2026-08"
    retrieved_at = dt.date(2026, 8, 19)

    def fetch(self) -> Path:
        return fetch()

    def parse(self, raw: Path) -> pl.DataFrame:
        indicator = get(self.indicator_id)
        province_by_name, district_by_key, merkez_by_province = _registry()

        il_kent = pl.read_excel(raw, sheet_name="İL - KENT", engine="calamine")
        il_kir = pl.read_excel(raw, sheet_name="İL - KIR", engine="calamine")
        province_rows = _rate(il_kent, il_kir, ["İL"])

        ilce_kent = pl.read_excel(raw, sheet_name="İLÇE - KENT", engine="calamine")
        ilce_kir = pl.read_excel(
            raw, sheet_name="İLÇE KIR", engine="calamine", has_header=False
        )
        ilce_kir.columns = [
            "İL",
            "İLÇE",
            "Kayıtlı",
            "Geçerli",
            "MHP",
            "HDP",
            "SP",
            "CHP",
            "AK PARTİ",
        ]
        ilce_kir = ilce_kir.slice(1)

        def normalize_frame(frame: pl.DataFrame) -> pl.DataFrame:
            pairs = [
                _normalize_pair(il, ilce)
                for il, ilce in zip(frame["İL"], frame["İLÇE"], strict=True)
            ]
            return frame.with_columns(
                pl.Series("İL", [p[0] for p in pairs]),
                pl.Series("İLÇE", [p[1] for p in pairs]),
            )

        ilce_kent = normalize_frame(
            ilce_kent.with_columns(
                pl.col("İL").str.strip_chars(), pl.col("İLÇE").str.strip_chars()
            )
        )
        ilce_kir = normalize_frame(
            ilce_kir.with_columns(
                pl.col("İL").str.strip_chars(), pl.col("İLÇE").str.strip_chars()
            )
        )
        district_rows = _rate(ilce_kent, ilce_kir, ["İL", "İLÇE"])

        records: list[dict] = []
        skipped: list[str] = []

        for row in province_rows:
            area_id = resolve_province(row["İL"], province_by_name)
            if area_id is None:
                skipped.append("il eşlenmedi: " + row["İL"])
                continue
            records.append(
                {"area_id": area_id, "area_level": "province", "value": row["value"]}
            )

        for row in district_rows:
            if row["İL"].strip() in KNOWN_GAPS:
                continue
            area_id, reason = resolve_district(
                row["İL"],
                row["İLÇE"],
                province_by_name,
                district_by_key,
                merkez_by_province,
            )
            if area_id is None:
                skipped.append(reason)
                continue
            records.append(
                {"area_id": area_id, "area_level": "district", "value": row["value"]}
            )

        if skipped:
            # Every fix found so far is in DISTRICT_FIXES/PROVINCE_FIXES; anything left
            # is new and must be looked at, not summed away — K1's "no silent breakage".
            raise KeyError(
                str(len(skipped)) + " alan eşlenemedi:\n" + "\n".join(sorted(skipped))
            )

        frame = pl.DataFrame(records)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.date(pl.lit(YEAR), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(format_dims(None)).alias("dims"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("estimated").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
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
