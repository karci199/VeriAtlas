"""Province series re-published by drdatastats.com, where the primary source gives no series.

drdatastats.com (a secondary compiler) draws province maps from official tables and names
the source under each map ("Veri: STİGM", "Kaynak: OGM" …). Its interactive pages post a
form (`altparametresecilen`, `yilsecilen`) and answer a Google Charts table; the static ones
carry the table inline. Pulled 2026-09-26 into `drdatastats/<slug>.json` (every parameter ×
year of a page, with the source line). Only series the warehouse had from no primary source
are loaded; ratios and per-capita variants are left out because they are derived.

Every row keeps `source_id = drdatastats`; the original publisher is in the indicator's
definition. Province names are matched after spelling fixes (Afyon, Içel, Izmir …); a name
that still does not match stops the load, except the two combined regional rows OGM writes
("Bayburt-Gümüşhane"), which cannot be split and are dropped.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..config import DATA, RAW
from ..indicators import get
from ..schema import format_dims

DOWNLOADS = RAW / "drdatastats"

FIXES = {
    "Afyon": "Afyonkarahisar",
    "Içel": "Mersin",
    "İçel": "Mersin",
    "Izmir": "İzmir",
    "Istanbul": "İstanbul",
    "K.Maraş": "Kahramanmaraş",
}
DROP = {"Bayburt-Gümüşhane", "Gümüşhane-Bayburt", "Roma"}
#: Years a page lists twice with different values (the site's own error): left out.
SKIP_YEARS = {"mukhtars": {2020}}

#: indicator → (page slug, {parameter: dims}) ; a static page has parameter "_" and its year
#: in the slug.
SERIES: dict[str, tuple[str, dict[str, dict]]] = {
    "associations": ("illere-gore-turkiyede-dernek-sayilari", {"Dernek Sayıları": {}}),
    "association_members": (
        "illere-gore-turkiyede-dernek-uye-sayilari",
        {
            "Dernek Üye Sayıları (Erkekler)": {"sex": "male"},
            "Dernek Üye Sayıları (Kadınlar)": {"sex": "female"},
        },
    ),
    "associations_by_activity": (
        "illere-gore-turkiyede-faaliyet-alanlarina-gore-dernek-sayilari",
        {
            "Dış Türkler İle Dayanışma Dernekleri": {
                "association_activity": "diaspora_turks"
            },
            "Dini Hizmetlerin Gerçekleştirilmesine Yönelik Faaliyet Gösteren Dernekler": {
                "association_activity": "religious_services"
            },
            "Eğitim Araştırma Dernekleri": {
                "association_activity": "education_research"
            },
            "Engelli Dernekleri": {"association_activity": "disability"},
            "İnsani Yardım Dernekleri": {"association_activity": "humanitarian_aid"},
            "Şehit Yakını ve Gazi Dernekleri": {
                "association_activity": "martyrs_veterans"
            },
            "Hemşehri Dernekleri": {"association_activity": "hometown"},
            "Faaliyet Alanlarından Biri Kadın Hakları Olan Dernekler": {
                "association_activity": "womens_rights"
            },
        },
    ),
    "mukhtars": (
        "illere-gore-turkiyede-muhtarlar",
        {
            "Erkek Muhtar Sayıları": {"sex": "male"},
            "Kadın Muhtar Sayıları": {"sex": "female"},
        },
    ),
    "quran_courses": (
        "illere-gore-turkiyede-kuran-kurslari",
        {"Türkiyede Kuran Kursu Sayıları": {}},
    ),
    "quran_course_students": (
        "illere-gore-turkiyede-kuran-kurslari",
        {
            "Türkiyede Kuran Kursu Kursiyer Sayıları (Erkek)": {"sex": "male"},
            "Türkiyede Kuran Kursu Kursiyer Sayıları (Kadın)": {"sex": "female"},
        },
    ),
    "kyk_dormitories": (
        "illere-gore-turkiyede-yuksek-ogrenim-kredi-ve-yurtlar-kurumu-yurtlari-sayilar-ve-kontenjanlar",
        {"KYK Yurt Sayısı": {}},
    ),
    "kyk_dormitory_capacity": (
        "illere-gore-turkiyede-yuksek-ogrenim-kredi-ve-yurtlar-kurumu-yurtlari-sayilar-ve-kontenjanlar",
        {
            "KYK Yurt Kontenjanı (Erkek)": {"sex": "male"},
            "KYK Yurt Kontenjanı (Kadın)": {"sex": "female"},
        },
    ),
    "forest_fires": (
        "illere-gore-turkiyede-orman-yangin-sayilari-adet-ve-yanan-ormanlarin-buyuklugu-hektar",
        {"Orman Yangın Sayısı (adet)": {}},
    ),
    "forest_fire_area": (
        "illere-gore-turkiyede-orman-yangin-sayilari-adet-ve-yanan-ormanlarin-buyuklugu-hektar",
        {"Yanan Orman Büyüklüğü (hektar)": {}},
    ),
    "industrial_wood_production": (
        "illere-gore-turkiyede-islenmemis-odun-uretimi-endustriyel-odun-ve-yakacak-odun",
        {"Endüstriyel Odun Üretimi (metreküp)": {}},
    ),
    "fuel_wood_production": (
        "illere-gore-turkiyede-islenmemis-odun-uretimi-endustriyel-odun-ve-yakacak-odun",
        {"Yakacak Odun Üretimi (ster)": {}},
    ),
    "foster_families": (
        "illere-gore-turkiyede-koruyucu-aile-sayilari-ve-koruyucu-aile-yanindaki-cocuk-sayilari",
        {"Koruyucu Aile Sayısı": {}},
    ),
    "children_in_foster_care": (
        "illere-gore-turkiyede-koruyucu-aile-sayilari-ve-koruyucu-aile-yanindaki-cocuk-sayilari",
        {"Koruyucu Aile Yanındaki Çocuk Sayısı": {}},
    ),
    "street_markets": (
        "illere-gore-turkiyede-semt-uretici-pazarlari",
        {"Semt/Üretici Pazarlarının Sayıları": {}},
    ),
    "wholesale_produce_markets": ("illere-gore-turkiyede-toptanci-halleri", None),
    "organized_industrial_zones": (
        "illere-gore-turkiyede-faal-durumda-olan-organize-sanayi-bolgelerinin-dagilimi-{year}-yili",
        {"_": {}},
    ),
    "churches": ("illere-gore-turkiyede-kilise-sayilari-{year}-yili", {"_": {}}),
    "synagogues": ("illere-gore-turkiyede-sinagog-sayilari-{year}-yili", {"_": {}}),
    "social_security_family_share": (
        "illere-gore-turkiyenin-yuzde-kaci-{kind}-ailesi-{year}-yili",
        {
            "isci": {"scheme": "4a"},
            "esnaf": {"scheme": "4b"},
            "memur": {"scheme": "4c"},
        },
    ),
}


def year_of(label: str) -> int:
    m = re.search(r"(19|20)\d\d", label)
    if not m:
        raise ValueError("drdatastats: yil yok: " + label)
    return int(m.group(0))


def province_ids() -> dict[str, str]:
    areas = pl.read_csv(DATA / "areas_tr.csv").filter(
        pl.col("area_level") == "province"
    )
    return dict(zip(areas["name_tr"], areas["area_id"], strict=True))


def rows_of(page: dict, param: str) -> list[tuple[int, str, float]]:
    """(year, display name, value) rows of one parameter of a page."""
    out = []
    for key, rows in page["data"].items():
        p, _, year = key.partition("|")
        if p != param:
            continue
        for _code, name, value in rows:
            if value in ("null", ""):
                continue
            out.append((year_of(year), name.strip(), float(value)))
    return out


def static_pages(slug: str, raw: Path) -> list[tuple[int, Path, str]]:
    pattern = re.compile(
        "^"
        + re.escape(slug)
        .replace(r"\{year\}", r"(\d{4})")
        .replace(r"\{kind\}", r"(\w+)")
        + r"\.json$"
    )
    out = []
    for path in raw.glob("*.json"):
        m = pattern.match(path.name)
        if m:
            groups = m.groups()
            year = int(next(g for g in groups if re.fullmatch(r"\d{4}", g)))
            kind = next((g for g in groups if not re.fullmatch(r"\d{4}", g)), "")
            out.append((year, path, kind))
    return out


class DrDataStatsBase:
    source_id = "drdatastats"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 26)
    indicator_id = ""

    def fetch(self) -> Path:
        if not DOWNLOADS.exists():
            raise FileNotFoundError("drdatastats dokumu yok: " + str(DOWNLOADS))
        return DOWNLOADS

    def records(self, raw: Path) -> list[tuple[int, str, dict, float]]:
        slug, params = SERIES[self.indicator_id]
        out = []
        if "{" in slug:
            for year, path, kind in static_pages(slug, raw):
                page = json.loads(path.read_text(encoding="utf-8"))
                dims = params.get(kind or "_")
                if dims is None:
                    continue
                for _code, name, value in page["data"].get("_", []):
                    out.append((year, name.strip(), dims, float(value)))
            return out
        page = json.loads((raw / (slug + ".json")).read_text(encoding="utf-8"))
        if params is None:  # one parameter, whatever its label
            params = {page["params"][0]: {}}
        for param, dims in params.items():
            if param not in page["params"]:
                raise KeyError(
                    f"drdatastats {self.indicator_id}: parametre yok: {param}"
                )
            out += [(y, n, dims, v) for y, n, v in rows_of(page, param)]
        return out

    def parse(self, raw: Path) -> pl.DataFrame:
        ids = province_ids()
        rows, unknown = [], set()
        for year, name, dims, value in self.records(raw):
            if year in SKIP_YEARS.get(self.indicator_id, ()):
                continue
            name = FIXES.get(name, name)
            if name in DROP:
                continue
            if name == "Türkiye":
                area, level = "TR", "country"
            elif name in ids:
                area, level = ids[name], "province"
            else:
                unknown.add(name)
                continue
            rows.append((area, level, dt.date(year, 1, 1), format_dims(dims), value))
        if unknown:
            raise KeyError(
                f"drdatastats {self.indicator_id}: taninmayan il: {sorted(unknown)}"
            )
        frame = pl.DataFrame(
            rows,
            schema=["area_id", "area_level", "period_start", "dims", "value"],
            orient="row",
        )
        if frame.is_empty():
            raise ValueError(self.indicator_id + ": satir yok")
        if frame.select("area_id", "period_start", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni alan-yil-kirilim iki kez")
        indicator = get(self.indicator_id)
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit(indicator.frequency).alias("frequency"),
            pl.lit(indicator.unit.unit_id).alias("unit"),
            pl.lit("measured").alias("quality_flag"),
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


DRDATASTATS_ADAPTERS = {
    "dds_" + ident: type(
        "Dds" + "".join(p.title() for p in ident.split("_")),
        (DrDataStatsBase,),
        {"indicator_id": ident},
    )
    for ident in SERIES
}
