"""Children brought to or coming to police and gendarmerie units — MEDAS, Türkiye, 2015-2025.

Pulled 2026-09-13 (`fetch_medas_topic.py cocuk-guvenlik=...`) as
`medas/basit/nufus-cocuk-guvenlik-NN-country.csv`. Unlike the other topic exports these
come with the years across the columns and one row per breakdown combination
(`Suç türü:Hırsızlık ve Cinsiyeti:Erkek|34120.0|40600.0|...`), so they get their own
reader. Country only: MEDAS offers no province level for this table.

Every label part must be known; an unknown offence or reason stops the load rather than
dropping a row, since the stored rows must add up to what TÜİK publishes.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ..config import RAW
from ..indicators import get
from ..schema import format_dims
from .tuik_simple import read_text

DOWNLOADS = RAW / "medas" / "basit"

OFFENCE = {
    "Adliyeye Karşı Suçlar": "against_justice",
    "Aile Düzenine Karşı Suçlar": "against_family",
    "Bilişim Suçları": "cyber",
    "Çevreye Karşı Suçlar": "environmental",
    "Cinsel Suçlar": "sexual",
    "Diğer": "other",
    "Dolandırıcılık": "fraud",
    "Genel Ahlaka Karşı Suçlar": "public_morality",
    "Genel Tehlike Yaratan Suçlar": "public_danger",
    "Göçmen Kaçakçılığı": "migrant_smuggling",
    "Görevli Memura Mukavemet": "resisting_officer",
    "Hakaret": "insult",
    "Hırsızlık": "theft",
    "Kamu Sağlığına Karşı Suçlar": "public_health",
    "Kişiyi Hürriyetinden Yoksun Kılma": "deprivation_of_liberty",
    "Konut Dokunulmazlığının İhlali": "trespass",
    "Mala Zarar Verme": "property_damage",
    "Mal Varlığına Karşı Diğer Suçlar": "other_property",
    "Öldürme": "homicide",
    "Pasaport Kanununa Muhalefet": "passport_law",
    "Sahtecilik": "forgery",
    "Tehdit": "threat",
    "Toplumsal Olaylar": "social_unrest",
    "Uyuşturucu Veya Uyarıcı Madde Kullanmak, Satmak, Satın Almak": "drugs",
    "Yağma (Gasp)": "robbery",
    "Yaralama": "assault",
}

NAMES = {
    "Geliş nedeni": (
        "police_referral",
        {
            "Mağdur": "victim",
            "Suça Sürüklenme": "pushed_into_crime",
            "Bilgisine Başvurma": "information",
            "Kayıp (Bulunan)": "missing_found",
            "Kabahat İşleme": "misdemeanour",
            "Diğer": "other",
        },
    ),
    "Cinsiyeti": ("sex", {"Erkek": "male", "Kadın": "female"}),
    "Yaş grubu": (
        "child_age_band",
        {"-11": "0-11", "12-14": "12-14", "15-17": "15-17", "Bilinmeyen": "unknown"},
    ),
    "Suç türü": ("offence", OFFENCE),
}

#: indicator id -> file number
FILES = {
    "child_police_referrals": "01",
    "children_pushed_into_crime": "02",
    "child_crime_victims": "03",
    "child_incident_victims": "04",
    "child_misdemeanour_victims": "05",
}


def parse_label(label: str) -> dict[str, str]:
    dims = {}
    for part in label.split(" ve "):
        name, _, value = part.partition(":")
        dim, values = NAMES[name.strip()]
        dims[dim] = values[" ".join(value.split())]
    return dims


def read_years_across(path: Path, indicator_id: str) -> list[dict]:
    lines = read_text(path).splitlines()
    years = next(
        [int(c) if c.strip().isdigit() else None for c in line.split("|")]
        for line in lines
        if sum(c.strip().isdigit() and len(c.strip()) == 4 for c in line.split("|")) > 2
    )
    rows = []
    for line in lines:
        cells = line.split("|")
        if ":" not in cells[0]:
            continue
        try:
            dims = parse_label(cells[0].strip())
        except KeyError as missing:
            raise KeyError(f"{indicator_id}: tanimsiz etiket {missing}: {cells[0]}")
        for index, cell in enumerate(cells[1:], start=1):
            if index < len(years) and years[index] and cell.strip():
                rows.append(
                    {
                        "year": years[index],
                        "dims": format_dims(dims),
                        "value": float(cell),
                    }
                )
    return rows


class ChildPolice:
    source_id = "tuik_medas"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 13)
    indicator_id = ""

    def fetch(self) -> Path:
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        path = raw / f"nufus-cocuk-guvenlik-{FILES[self.indicator_id]}-country.csv"
        frame = pl.DataFrame(read_years_across(path, self.indicator_id))
        if frame.select("year", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni yil-kirilim iki kez")
        indicator = get(self.indicator_id)
        return frame.select(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("TR").alias("area_id"),
            pl.lit("country").alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.lit(indicator.frequency).alias("frequency"),
            "dims",
            "value",
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
            pl.lit(self.vintage).alias("vintage"),
            pl.lit(self.source_id).alias("source_id"),
            pl.lit(self.retrieved_at).alias("retrieved_at"),
        )


CHILD_POLICE_ADAPTERS = {
    "tuik_" + ident: type(
        "Tuik" + "".join(p.title() for p in ident.split("_")),
        (ChildPolice,),
        {"indicator_id": ident},
    )
    for ident in FILES
}
