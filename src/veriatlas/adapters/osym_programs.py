"""University places and placements by province and programme — ÖSYM, yearly.

ÖSYM publishes, after each year's central placement, "Tablo-3" (associate) and "Tablo-4"
(bachelor): one row per programme with its code, university, faculty, programme name,
score type, general quota and the number placed. From 2017 each comes as a workbook too;
the list of documents is `osym/tablo/liste.json` (built from the ÖSYM archive index), the
main placement workbooks are `osym/tablo/<year>_tablo<3|4>.xlsx`. Pulled 2026-09-26.
Only the general quota is read; the school-first, earthquake and other quota columns and
the additional placements are left out.

Programmes are placed in a province and a programme group by, in order:

1. the programme code in the 2026 YÖK Atlas guide (`yokatlas/kilavuz_2026.json`, fields
   `kilavuzKodu`, `ilKodu`, `birimGrupAdi`) — codes live on across years;
2. otherwise the university's province in that guide (by normalised name), and the group
   whose programme names share this programme's base name (the name before its first
   parenthesis: "(İngilizce)", "(Burslu)" …);
3. otherwise the city ÖSYM writes after a university's name ("… ÜNİVERSİTESİ (BOLU)").

KKTC and abroad campuses are left out. A programme that none of the three places stops the
load. Values are summed to province × programme group × level × university type, and a
Türkiye row is written as the sum of the provinces.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import polars as pl

from ..config import DATA, RAW
from ..indicators import get, load
from ..schema import format_dims

DOWNLOADS = RAW / "osym" / "tablo"
GUIDE = RAW / "yokatlas" / "kilavuz_2026.json"
ABROAD = re.compile(
    r"KKTC|YURTD|KAZAKİSTAN|KIRGIZ|AZERBAYCAN|BOSNA|MOLDOVA|GÜRCİSTAN|ARNAVUT|MAKEDONYA|LEFKOŞA|GİRNE|GAZİMAĞUSA"
)


def turkish_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def slug(text: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosucgiosuaiu")
    s = text.translate(table).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def base_name(program: str) -> str:
    """The name before its first parenthesis, spaces collapsed; "Tıp Fakültesi" → "Tıp".

    Before 2021 a programme that is a whole faculty is written by the faculty's name
    ("…/Tıp Fakültesi"), which would otherwise be a group of its own.
    """
    name = re.split(r"\s+\(", program.strip(), maxsplit=1)[0]
    name = re.sub(r"\s+", " ", name).strip()
    return re.sub(r"\s+Fakültesi$", "", name)


def uni_key(name: str) -> str:
    name = re.sub(r"\([^)]*\)", "", name)
    return re.sub(r"\s+", " ", turkish_upper(name)).strip()


def number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(".", "").replace(",", "."))
    except ValueError:
        return None


def read_table(path: Path) -> list[dict]:
    import openpyxl

    year = int(re.search(r"(\d{4})_tablo", path.name).group(1))
    rows = list(
        openpyxl.load_workbook(path, read_only=True, data_only=True)
        .worksheets[0]
        .iter_rows(values_only=True)
    )
    hi = next(
        i for i, r in enumerate(rows) if r and str(r[0] or "").strip() == "Program Kodu"
    )
    head = [str(h or "").strip() for h in rows[hi]]
    title = " ".join(str(x) for r in rows[:hi] for x in r if x)
    level = "associate" if re.search(r"Ön ?[Ll]isans", title) else "bachelor"
    quota = next(
        i for i, h in enumerate(head) if h.startswith("Genel Kont") or h == "Kontenjan"
    )
    split = "Üniversite Adı" in head
    out = []
    for r in rows[hi + 1 :]:
        code = str(r[0] or "").strip()
        if not re.fullmatch(r"\d{9}", code):
            continue
        if split:
            uni, program = (
                str(r[head.index("Üniversite Adı")]),
                str(r[head.index("Program Adı")]),
            )
            utype = str(r[1] or "")
        else:
            parts = str(r[1]).split("/")
            uni, program = parts[0], parts[-1]
            utype = ""
        city = re.search(r"\(([^()]+)\)", uni)
        out.append(
            {
                "year": year,
                "level": level,
                "code": code,
                "uni": uni.strip(),
                "city": city.group(1).strip() if city else "",
                "utype_raw": turkish_upper(utype + " " + uni),
                "program": program.strip(),
                "quota": number(r[quota]) or 0.0,
                "placed": number(r[quota + 1]) or 0.0,
                "min_score": number(r[quota + 2]),
            }
        )
    return out


def placed_programmes(raw: Path) -> pl.DataFrame:
    guide = pl.DataFrame(
        json.loads(GUIDE.read_text(encoding="utf-8"))["content"],
        infer_schema_length=None,
    )
    by_code = {
        str(c): (int(i), g, t)
        for c, i, g, t in guide.select(
            "kilavuzKodu", "ilKodu", "birimGrupAdi", "universiteTuru"
        ).iter_rows()
        if i is not None and 1 <= int(i) <= 81
    }
    uni_province, uni_type = {}, {}
    for name, il, t in guide.select(
        "universiteAdi", "uniIlKodu", "universiteTuru"
    ).iter_rows():
        if il is not None and 1 <= int(il) <= 81:
            uni_province.setdefault(uni_key(name), int(il))
        uni_type.setdefault(uni_key(name), t)
    group_of = {}
    for name, g in guide.select("birimAdi", "birimGrupAdi").iter_rows():
        group_of.setdefault(base_name(name), g)
        group_of.setdefault(base_name(name).casefold(), g)
        group_of.setdefault(g.casefold(), g)
    provinces = pl.read_csv(DATA / "areas_tr.csv").filter(
        pl.col("area_level") == "province"
    )
    plate_of = {
        turkish_upper(n): int(a[3:])
        for a, n in provinces.select("area_id", "name_tr").iter_rows()
    }
    plate_of["AFYON"] = 3

    rows, missing = [], []
    for path in sorted(raw.glob("20*_tablo*.xlsx")):
        for p in read_table(path):
            if ABROAD.search(p["utype_raw"]) or ABROAD.search(turkish_upper(p["city"])):
                continue
            hit = by_code.get(p["code"])
            key = uni_key(p["uni"])
            if hit:
                plate, group, gtype = hit
            else:
                plate = uni_province.get(key) or plate_of.get(turkish_upper(p["city"]))
                if plate is None:
                    plate = next(
                        (v for n, v in plate_of.items() if re.search(rf"\b{n}\b", key)),
                        None,
                    )
                base = base_name(p["program"])
                group = group_of.get(base) or group_of.get(base.casefold()) or base
                gtype = uni_type.get(key, "")
            if plate is None:
                missing.append(p["uni"])
                continue
            raw_type = p["utype_raw"] + " " + (gtype or "")
            utype = "foundation" if "VAKIF" in raw_type else "state"
            rows.append(
                {
                    **p,
                    "area_id": f"TR-{plate:02d}",
                    "group": group,
                    "utype": utype,
                }
            )
    if missing:
        raise KeyError(
            "osym: ili bulunamayan universite: " + ", ".join(sorted(set(missing))[:20])
        )
    return pl.DataFrame(rows)


class OsymBase:
    source_id = "osym"
    vintage = "2025-08"
    retrieved_at = dt.date(2026, 9, 26)
    indicator_id = ""
    measure = ""
    _cache: dict = {}  # noqa: RUF012

    def fetch(self) -> Path:
        if not (DOWNLOADS / "liste.json").exists():
            raise FileNotFoundError("OSYM tablo dokumu yok: " + str(DOWNLOADS))
        return DOWNLOADS

    def parse(self, raw: Path) -> pl.DataFrame:
        if raw not in self._cache:
            self._cache[raw] = placed_programmes(raw)
        df = self._cache[raw].with_columns(
            pl.col("group").map_elements(slug, return_dtype=pl.String).alias("gcode")
        )
        known = set(load().dimensions["program_group"].values_tr)
        unknown = set(df["gcode"]) - known
        if unknown:
            raise KeyError(
                "osym: sozlukte olmayan program grubu: "
                + ", ".join(sorted(unknown)[:20])
            )
        keys = ["year", "gcode", "level", "utype"]
        if self.measure == "min_score":
            # A score cannot be summed: the median of the programmes' lowest placed score.
            df = df.filter(pl.col("min_score").is_not_null() & (pl.col("placed") > 0))
            agg = pl.col("min_score").median().alias("value")
        else:
            agg = pl.col(self.measure).sum().alias("value")
        prov = df.group_by(["area_id", *keys]).agg(agg)
        tr = df.group_by(keys).agg(agg)
        tr = tr.with_columns(pl.lit("TR").alias("area_id"))
        both = pl.concat([prov, tr.select(prov.columns)])
        indicator = get(self.indicator_id)
        return both.with_columns(
            pl.when(pl.col("area_id") == "TR")
            .then(pl.lit("country"))
            .otherwise(pl.lit("province"))
            .alias("area_level"),
            pl.date(pl.col("year"), 1, 1).alias("period_start"),
            pl.struct("gcode", "level", "utype")
            .map_elements(
                lambda s: format_dims(
                    {
                        "program_group": s["gcode"],
                        "program_level": s["level"],
                        "university_type": s["utype"],
                    }
                ),
                return_dtype=pl.String,
            )
            .alias("dims"),
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


class OsymQuota(OsymBase):
    indicator_id = "osym_program_quota"
    measure = "quota"


class OsymPlaced(OsymBase):
    indicator_id = "osym_program_placed"
    measure = "placed"


class OsymMinScore(OsymBase):
    indicator_id = "osym_program_min_score"
    measure = "min_score"


OSYM_ADAPTERS = {
    "osym_program_quota": OsymQuota,
    "osym_program_placed": OsymPlaced,
    "osym_program_min_score": OsymMinScore,
}
