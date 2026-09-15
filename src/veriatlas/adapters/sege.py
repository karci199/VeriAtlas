"""İlçe SEGE-2022: socio-economic development score, rank and level of the 973 districts.

Published by the Ministry of Industry and Technology (General Directorate of Development
Agencies), February 2022; the ministry's page blocks automated access, so the PDF is the
copy the development agencies host (`raw/sege/sege-2022.pdf`, from geka.gov.tr). The report
publishes the score, the national and in-province rank and the level (kademe 1-6) of every
district — not the 56 input variables, which stay with the ministry.

The report prints the ranking twice: a national list (rank, province, district, score) and a
table per province (district, national rank, province rank, score, level). Both are read and
must agree on every district's score; the national list must hold ranks 1-973 exactly once
and every district must resolve to one current district of the area register.

Most inputs are 2019-2021 data; the figures are stored under 2022, the study's year.
"""

from __future__ import annotations

import datetime as dt
import re
from functools import cache
from pathlib import Path

import pdfplumber
import polars as pl

from ..config import RAW
from .kgm import district_key, province_id, resolve_district

PDF = RAW / "sege" / "sege-2022.pdf"

#: Edition -> (PDF, number of districts, vintage). İlçe SEGE-2017 uses 2014 data and 970
#: districts (bebka.org.tr copy); SEGE-2022 973.
EDITIONS = {
    2017: (RAW / "sege" / "sege-2017.pdf", 970, "2017-12"),
    2022: (PDF, 973, "2022-02"),
}

NATIONAL = re.compile(r"(\d{1,3}) (\D+?) (-?\d,\d{3})")
PROVINCE_TABLE = re.compile(
    r"([A-ZÇĞİÖŞÜa-zçğıöşü][^\d]*?) (\d{1,3}) (\d{1,2}) (-?\d,\d{3}) ([1-6])(?!\d)"
)


def score(text: str) -> float:
    return float(text.replace(",", "."))


MISSING: dict[int, list[int]] = {2017: [], 2022: []}


@cache
def sege(edition: int = 2022) -> list[dict]:
    pdf, count, _ = EDITIONS[edition]
    national: dict[int, tuple[list[str], str]] = {}
    by_rank: dict[int, tuple[int, str, int]] = {}
    with pdfplumber.open(pdf) as document:
        for page in document.pages:
            text = page.extract_text() or ""
            is_national = "Sıra İl Adı" in text and "Skor" in text
            for line in text.splitlines():
                if is_national:
                    for m in NATIONAL.finditer(line):
                        rank = int(m.group(1))
                        if rank in national:
                            raise ValueError(f"SEGE: {rank}. sıra iki kez")
                        national[rank] = (m.group(2).split(), m.group(3))
                for m in PROVINCE_TABLE.finditer(line):
                    by_rank[int(m.group(2))] = (
                        int(m.group(3)),
                        m.group(4),
                        int(m.group(5)),
                    )
    if sorted(national) != list(range(1, count + 1)):
        raise ValueError(f"SEGE: ulusal liste {len(national)} sıra")
    key = district_key()
    out = []
    for rank, (words, printed) in sorted(national.items()):
        if rank not in by_rank:
            # The 2017 report leaves two Kars districts (Kağızman, Digor) out of its
            # province table; their score and rank are in the national list, their level
            # is not stored rather than guessed.
            if len(MISSING[edition]) >= 5:
                raise ValueError(f"SEGE {edition}: il tablolarında çok eksik sıra")
            MISSING[edition].append(rank)
            by_rank[rank] = (None, printed, None)
        province_rank, province_score, level = by_rank[rank]
        if province_score != printed:
            raise ValueError(
                f"SEGE: {rank}. sıra skoru iki tabloda farklı {printed}/{province_score}"
            )
        for n in range(1, len(words)):
            try:
                province_id(" ".join(words[:n]))
            except KeyError:
                continue
            area, level_name = resolve_district(
                key, " ".join(words[:n]), " ".join(words[n:])
            )
            break
        else:
            raise KeyError(f"SEGE: il adı çözülemedi {words}")
        if level_name != "district":
            raise ValueError(f"SEGE: {words} ilçeye değil ile eşlendi")
        out.append(
            {
                "area_id": area,
                "rank": rank,
                "province_rank": province_rank,
                "score": score(printed),
                "level": level,
            }
        )
    areas = [o["area_id"] for o in out]
    if len(set(areas)) != count:
        raise ValueError("SEGE: iki sıra aynı ilçeye eşlendi")
    return out


class Sege:
    source_id = "sanayi_sege"
    indicator_id = ""
    column = ""
    unit = ""

    def fetch(self) -> Path:
        return PDF

    def parse(self, raw: Path) -> pl.DataFrame:
        frames = []
        for edition, (_pdf, _count, vintage) in EDITIONS.items():
            rows = sege(edition)
            frames.append(
                pl.DataFrame(
                    {
                        "indicator_id": self.indicator_id,
                        "area_id": [
                            r["area_id"] for r in rows if r[self.column] is not None
                        ],
                        "area_level": "district",
                        "period_start": dt.date(edition, 1, 1),
                        "frequency": "annual",
                        "dims": "",
                        "value": [
                            float(r[self.column])
                            for r in rows
                            if r[self.column] is not None
                        ],
                        "unit": self.unit,
                        "quality_flag": "measured",
                        "vintage": vintage,
                        "source_id": self.source_id,
                        "retrieved_at": dt.date(2026, 9, 15),
                    }
                )
            )
        return pl.concat(frames)


class SegeScore(Sege):
    indicator_id = "sege_district_score"
    column = "score"
    unit = "index"


class SegeRank(Sege):
    indicator_id = "sege_district_rank"
    column = "rank"
    unit = "rank"


class SegeLevel(Sege):
    indicator_id = "sege_district_level"
    column = "level"
    unit = "development_level"


SEGE_ADAPTERS = {
    "sege_district_score": SegeScore,
    "sege_district_rank": SegeRank,
    "sege_district_level": SegeLevel,
}


# region Province SEGE-2017

PROVINCE_PDF = RAW / "sege" / "il-sege-2017.pdf"
PROVINCE_ROW = re.compile(r"(\d{1,2}) (\D+?) (-?\d,\d{3}) ([1-6])(?=\s|$)")


@cache
def province_sege() -> list[dict]:
    """İllerin SEGE-2017 (2015 data, 52 variables): rank, province, score, level, 81 rows.

    `kalkinmakutuphanesi.gov.tr` copy. The table is printed in two side-by-side halves on one
    page; ranks 1-81 must each appear once and the scores must fall with the rank.
    """
    with pdfplumber.open(PROVINCE_PDF) as document:
        text = next(
            p.extract_text()
            for p in document.pages
            if "İllerin Sosyo-Ekonomik Gelişmişlik Sıralaması"
            in (p.extract_text() or "")
            and "Skor Kademe" in (p.extract_text() or "")
        )
    found: dict[int, dict] = {}
    for m in PROVINCE_ROW.finditer(text):
        rank = int(m.group(1))
        if rank in found:
            raise ValueError(f"il SEGE: {rank}. sıra iki kez")
        found[rank] = {
            "area_id": province_id(m.group(2).replace("â", "a")),
            "rank": rank,
            "score": score(m.group(3)),
            "level": int(m.group(4)),
        }
    if sorted(found) != list(range(1, 82)):
        raise ValueError(f"il SEGE: {len(found)} sıra")
    scores = [found[r]["score"] for r in range(1, 82)]
    if scores != sorted(scores, reverse=True):
        raise ValueError("il SEGE: skorlar sıraya göre azalmıyor")
    if len({f["area_id"] for f in found.values()}) != 81:
        raise ValueError("il SEGE: iki sıra aynı ile eşlendi")
    return list(found.values())


class ProvinceSege(Sege):
    def fetch(self) -> Path:
        return PROVINCE_PDF

    def parse(self, raw: Path) -> pl.DataFrame:
        rows = province_sege()
        return pl.DataFrame(
            {
                "indicator_id": self.indicator_id,
                "area_id": [r["area_id"] for r in rows],
                "area_level": "province",
                "period_start": dt.date(2017, 1, 1),
                "frequency": "annual",
                "dims": "",
                "value": [float(r[self.column]) for r in rows],
                "unit": self.unit,
                "quality_flag": "measured",
                "vintage": "2019-12",
                "source_id": self.source_id,
                "retrieved_at": dt.date(2026, 9, 15),
            }
        )


class ProvinceSegeScore(ProvinceSege):
    indicator_id = "sege_province_score"
    column = "score"
    unit = "index"


class ProvinceSegeRank(ProvinceSege):
    indicator_id = "sege_province_rank"
    column = "rank"
    unit = "rank"


class ProvinceSegeLevel(ProvinceSege):
    indicator_id = "sege_province_level"
    column = "level"
    unit = "development_level"


SEGE_ADAPTERS.update(
    {
        "sege_province_score": ProvinceSegeScore,
        "sege_province_rank": ProvinceSegeRank,
        "sege_province_level": ProvinceSegeLevel,
    }
)

# endregion
