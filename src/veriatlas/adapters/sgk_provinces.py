"""SGK statistical yearbooks: insured, workplaces, pensions, work accidents by province.

`scripts/fetch_sgk_yillik.py` downloads the yearbooks (2007-2025) and
`scripts/extract_sgk_provinces.py` flattens every province table into
`raw/sgk/province_cells.parquet`: one row per printed cell, with the table title and the
header text above the column. This adapter reads that file.

The yearbooks renumber tables and reshape their columns from year to year, so nothing
here addresses a table number or a column position. A table is recognised by its title
(`TOPICS`), a cell by the words in its header (`classify`). A header that no rule
recognises stops the load, with the header in the message; a table that is deliberately
left out is listed in `SKIPPED_TOPICS` with the reason.

What the checks guarantee, beyond that:

* every table lists all 81 provinces (checked by the extractor's output here);
* a subtotal the source prints (Toplam, the column that sums the kinds) is compared with
  the sum of its parts and then dropped, so the stored rows partition (K16). Where the
  source prints only the total for a year, the total is kept without the breakdown key;
* the same number printed in two yearbooks (a table carrying five years) is kept from the
  yearbook of that year; a later yearbook's different figure is counted as a revision and
  reported, not silently preferred.

Breaks in definition are in `docs/sgk.md`.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path
from typing import ClassVar

import polars as pl

from ..config import RAW
from ..indicators import get, load
from ..schema import format_dims

CELLS = RAW / "sgk" / "province_cells.parquet"


def fold(text: str) -> str:
    text = text.replace("İ", "i").replace("I", "ı").lower()
    for a, b in zip("ıöüçşğâîû", "ioucsgaiu", strict=True):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


#: Title → topic. Ordered, first match wins; patterns run on the folded title.
TOPICS = [
    ("coverage", r"sosyal guvenlik kapsam"),
    ("ssk_population", r"ssk\)? kapsamindaki nufus|kapsamindaki nufusun"),
    ("voluntary_old", r"istege bagli sigortalilarin cinsiyet"),
    ("law2022", r"2022 sayili"),
    ("patriotic", r"vatani"),
    ("wa_days_disease", r"meslek hastaligina tutulan.*gecici is goremezlik"),
    (
        "wa_days_accident",
        r"is kazasi gecirenlerin gecici|is kazasi geciren sigortalilarin gecici",
    ),
    ("wa_days_old", r"vak.alari sonucu toplam gecici"),
    ("wa_cases_old", r"islemi tamamlanan is kazalari, meslek hastaliklari, surekli"),
    ("wa_cases", r"is kazasi ?(geciren|/meslek hastaligi geciren)"),
    ("wa_deaths", r"(sonucu|dolayi) olenlerin"),
    ("wa_new_permanent", r"yil icinde.*surekli is ?goremezlik geliri baglanan"),
    ("wa_permanent", r"surekli is ?goremezlik geliri alan"),
    ("wa_new_death_income", r"yil icinde olum geliri baglanan|yil icinde \(gecmis"),
    ("wa_death_income", r"olum geliri (baglanan|alan) hak sahip"),
    ("sickness", r"hastalik olay"),
    ("earnings", r"ortalama gunluk kazanc"),
    (
        "insured_by_size",
        (
            r"zorunlu sigortali(larin| sayilarinin) il(ler)?de is ?yeri buyuklu"
            r"|zorunlu sigortalilarin il ve is ?yeri buyuklu"
        ),
    ),
    (
        "workplaces_by_size",
        (
            r"is ?yeri sayilari buyukluklerinin|is ?yeri sayilarinin is ?yeri buyukluk"
            r"|is ?yerlerinin (il ve )?is ?yeri buyuklu"
        ),
    ),
    (
        "workplaces",
        (
            r"is ?yerlerinin (yillar ve )?il|is ?yerlerinin ile gore"
            r"|is ?yeri sayilari ve zorunlu|aylik bildirgesi alinan"
        ),
    ),
    ("earnings_bands_4b", r"aktif sigortalilarin.*kazanc aral"),
    ("profession_4b", r"meslek kuruluslarina"),
    ("active_by_sex", r"4-?/?1?-?/?[bc].*aktif sigortalilarin (il ve )?cinsiyet"),
    (
        "active_by_sex",
        r"4-1/b maddesi kapsamindaki aktif sigortalilarin yas ve cinsiyet",
    ),
    ("active_passive_4b", r"4-?1/b.*aktif ve pasif"),
    ("active_pensioners_4c", r"4-1/c.*aktif sigortalilarin ve aylik alanlarin"),
    ("coverage", r"4-1/a.*aktif ve pasif sigortalilar ile"),
    ("active_passive_2010", r"4\. maddesi kapsamindaki aktif ve pasif"),
    ("compulsory_by_sex", r"zorunlu sigortalilarin (il ve )?cinsiyet"),
    ("active", r"aktif sigortalilarin (illere gore|il ve sigortalilik)"),
    ("new_pensions", r"yili? icinde (aylik|gelir)"),
    ("survivors_4b", r"olum ayligi alan hak sahip|olum sigortasindan"),
    ("pensions", r"(aylik|gelir) (ve gelir )?alan|aylik alan hak sahip"),
]

#: Tables read by the extractor and deliberately not stored.
SKIPPED_TOPICS = {
    "unnamed": "2007-2008 'Sayfa2': an untitled working sheet (columns named after staff).",
    "ssk_population": (
        "2007-2009 SSK coverage population: superseded by the coverage tables from 2010, "
        "and its columns are marked n' (a revised count) without saying of what."
    ),
    "voluntary_old": "2007-2009 SSK voluntary insured: no successor table to continue it.",
    "active_passive_2010": (
        "2010 'active and passive insured': the table is transposed (provinces repeat "
        "down the rows under each measure) and every figure is in the 2010 coverage table."
    ),
    "earnings_bands_4b": (
        "4/b insured by declared earnings band: the bands follow the minimum wage and "
        "change every year, so no band is comparable across years."
    ),
    "profession_4b": "2011-2012 4/b insured by professional chamber: two years only.",
}


def topic_of(title: str) -> str:
    folded = fold(title)
    if not folded:
        return "unnamed"
    for topic, pattern in TOPICS:
        if re.search(pattern, folded):
            return topic
    raise KeyError("SGK tablosu tanınmadı: " + title)


# --- header vocabulary --------------------------------------------------------------

_EN = re.compile(
    # Prefixes (compulsor → compulsory, compulsorily) and a few whole words that would
    # otherwise eat Turkish ones ("son" in "sonucu").
    r"\b(?:(?:number|total|male|female|insured|active|province|compulsor|compusory|"
    r"voluntar|apprentic|partial|collective|self|agricultur|demarch|chief|pension|income|"
    r"invalid|death|survivor|surviors|workplace|work|average|daily|earning|size|sector|"
    r"service|temporar|temporal|permanent|occupational|accident|disease|people|person|"
    r"within|scope|article|coverage|population|ratio|beneficiar|recipient|widow|orphan|"
    r"mother|mather|father|parent|employee|employer|civil|public|private|seasonal|"
    r"general|spouse|husband|wife|daughter|doughter|children|child|green|addition|long|"
    r"ordinary|duty|disab|patriotic|oneself|those|receiv|monthly|employment|injur|"
    r"inpatient|outpatient|duration|veteran|silicosis|regist|social|security|intern|"
    r"trainee|dependent)\w*|(?:son|old|act|and|of|the|days?|rate|type|file|card|place|"
    r"under|years?|others?))\b.*",
    re.IGNORECASE,
)


def segments(header: str) -> list[str]:
    """The header path, folded, without the table title rows, the English half of each
    label or the roman-numeral column references."""
    out = []
    for seg in header.split(" > "):
        text = seg.strip()
        if re.match(r"(tablo|table)\b", text, re.IGNORECASE):
            continue
        if re.fullmatch(r"\d+\.0|(19|20)\d\d(\(\*+\))?", text):
            # A stray year label (a column of a multi-year table) or a column number
            # read as a float: kept for column_year, dropped from the text.
            out.append(text)
            continue
        text = re.sub(r"\((x|v|i)[ivx+=\-()\s]*\)", "", text, flags=re.IGNORECASE)
        text = _EN.sub("", text).strip(" -/(")
        out.append(fold(text) or "~")
    return out


def column_year(segs: list[str]) -> int | None:
    for seg in segs:
        match = re.fullmatch(r"((?:19|20)\d\d)(\.0)?(\(\*+\))?", seg.replace(" ", ""))
        if match:
            return int(match.group(1))
    return None


def scheme_of(text: str) -> str | None:
    if re.search(r"4 ?[-/_]? ?1? ?[-/_]? ?a\b|4-a\b|\bssk\b", text):
        return "4a"
    if re.search(r"4 ?[-/_]? ?1? ?[-/_]? ?b\b|4-b\b|bag-?kur", text):
        return "4b"
    if re.search(r"4 ?[-/_]? ?1? ?[-/_]? ?c\b|4-c\b|emekli ?sandig", text):
        return "4c"
    return None


def sex_of(leaf: str) -> str | None:
    if re.fullmatch(r"kadin|kadin ~", leaf):
        return "female"
    if re.fullmatch(r"erkek|erkek ~", leaf):
        return "male"
    if re.fullmatch(r"toplam|top\.|toplam toplam|toplam ~|~", leaf):
        return "total"
    return None


SIZE = {
    "1": "1",
    "2-3": "2-3",
    "4-6": "4-6",
    "7-9": "7-9",
    "10-19": "10-19",
    "20-29": "20-29",
    "30-49": "30-49",
    "50-99": "50-99",
    "100-249": "100-249",
    "250-499": "250-499",
    "500-749": "500-749",
    "750-999": "750-999",
    "1000+": "1000+",
}

RECIPIENT = [
    (r"kadin es", "wife"),
    (r"erkek es", "husband"),
    (r"kiz cocuk", "daughter"),
    (r"erkek cocuk", "son"),
    (r"^es\b|esler", "spouse"),
    (r"cocuk", "child"),
    (r"^ana\b", "mother"),
    (r"^baba\b", "father"),
]


def recipient_of(leaf: str) -> str | None:
    for pattern, value in RECIPIENT:
        if re.search(pattern, leaf):
            return value
    if re.search(r"toplam|kisi|genel toplam|hak ?sahi", leaf):
        return "total"
    return None


# --- classification -----------------------------------------------------------------


class Skip(Exception):
    """A cell known and deliberately not stored (a ratio, a copy of TÜİK population)."""


def classify(topic: str, title: str, path: str, header: str, row_label: str):
    """(indicator, dims, period year or None) for one printed cell."""
    segs = segments(header)
    # "~" is a header row that held only English: nothing to read in it.
    text = " > ".join(
        s
        for s in segs
        if s != "~" and not re.fullmatch(r"\d+\.0|(19|20)\d\d(\(\*+\))?", s)
    )
    leaf = text.split(" > ")[-1] if text else ""
    whole = fold(title) + " || " + text
    year = column_year(segs)
    handler = HANDLERS[topic]
    return handler(
        text=text, leaf=leaf, whole=whole, year=year, title=fold(title), path=fold(path)
    )


def _has(text: str, pattern: str) -> bool:
    return re.search(pattern, text) is not None


def h_active(text, leaf, whole, year, title, path):
    if _has(text, r"^toplam aktif sigortali \(4"):
        return "sgk_active_insured", {"scheme": "total", "insured_type": "total"}, None
    scheme = scheme_of(text.split(" > ")[0])
    if scheme is None:
        raise KeyError(text)
    kind = _insured_type(scheme, text, leaf)
    return "sgk_active_insured", {"scheme": scheme, "insured_type": kind}, None


def _insured_type(scheme: str, text: str, leaf: str) -> str:
    if scheme == "4a":
        rules = [
            (r"^toplam", "total"),
            (r"cirak", "apprentice"),
            (r"tarim", "agriculture_2925"),
            (r"kismi sureli", "part_time"),
            (r"topluluk", "collective_abroad"),
            (r"staj", "intern"),
            (r"^diger", "other"),
            (r"uzun vade", "long_term"),
            (r"ek-9", "domestic_ek9"),
            (r"zorunlu", "compulsory"),
        ]
    elif scheme == "4b":
        if _has(text, r"\(tarim\)|tarim zorunlu") and not _has(leaf, r"haric"):
            return "agriculture_compulsory"
        rules = [
            (r"muhtar", "muhtar"),
            (r"istege", "voluntary"),
            (r"tarim haric", "self_employed_compulsory"),
            (r"^toplam", "total"),
            (r"zorunlu", "compulsory"),
        ]
        if _has(text, r"kendi nam|esnaf|bagimsiz"):
            rules = [
                (r"muhtar", "muhtar"),
                (r"istege", "voluntary"),
                (r"^toplam", "self_employed_total"),
                (r"zorunlu", "self_employed_compulsory"),
            ]
    else:
        rules = [
            (r"istege", "voluntary"),
            (r"^toplam|aktif sigortali$", "total"),
            (r"zorunlu", "compulsory"),
        ]
    for pattern, value in rules:
        if _has(leaf, pattern):
            return value
    raise KeyError(text)


def h_compulsory_by_sex(text, leaf, whole, year, title, path):
    sex = sex_of(leaf)
    if _has(text, r"^toplam zorunlu sigortali"):
        return (
            "sgk_compulsory_insured",
            {"scheme": "total", "insured_type": "total", "sex": "total"},
            None,
        )
    scheme = scheme_of(text.split(" > ")[0])
    if scheme is None or sex is None:
        raise KeyError(text)
    middle = text.split(" > ")[1:-1]
    group = " > ".join(middle)
    if scheme != "4b" or not group or _has(group, r"zorunlu sigortali toplam"):
        kind = "total"
    elif _has(group, r"muhtar"):
        kind = "muhtar"
    elif _has(group, r"tarim haric|1479"):
        kind = "self_employed"
    elif _has(group, r"tarim|2926"):
        kind = "agriculture"
    elif _has(group, r"bagimsiz"):
        kind = "self_employed"
    else:
        raise KeyError(text)
    return (
        "sgk_compulsory_insured",
        {"scheme": scheme, "insured_type": kind, "sex": sex},
        None,
    )


def h_active_by_sex(text, leaf, whole, year, title, path):
    scheme = "4c" if _has(title, r"4-?/?1?-?/?c") else "4b"
    sex = sex_of(leaf)
    if sex is None:
        if _has(text, r"genel toplam"):
            sex = "total"
        else:
            raise KeyError(text)
    if scheme == "4c":
        if year is None:
            raise KeyError(text)
        return (
            "sgk_active_insured_by_sex",
            {"scheme": "4c", "insured_type": "total", "sex": sex},
            year,
        )
    group = text.rsplit(" > ", 1)[0] if " > " in text else ""
    if _has(text, r"genel toplam") or not group:
        kind = "total"
    elif _has(group, r"istege"):
        kind = "voluntary"
    elif _has(group, r"muhtar"):
        kind = "muhtar"
    elif _has(group, r"tarim haric|1479"):
        kind = "self_employed_compulsory"
    elif _has(group, r"tarim|2926"):
        # 2012 labels the farmers "bağımsız çalışanlar 2926": the law number decides.
        kind = "agriculture_compulsory"
    elif _has(group, r"bagimsiz"):
        kind = "self_employed_compulsory"
    elif _has(group, r"zorunlu sigortali > toplam$|^zorunlu sigortali$"):
        kind = "compulsory"
    else:
        raise KeyError(text)
    return (
        "sgk_active_insured_by_sex",
        {"scheme": "4b", "insured_type": kind, "sex": sex},
        None,
    )


def h_workplaces(text, leaf, whole, year, title, path):
    if year is not None:
        if _has(text, r"zorunlu sigortali"):
            return (
                "sgk_compulsory_insured",
                {"scheme": "4a", "insured_type": "total", "sex": "total"},
                year,
            )
        return "sgk_workplaces", {}, year
    # 2010: the workplace table is the earnings table under another title.
    return h_earnings(text, leaf, whole, year, title, path)


def h_by_size(text, leaf, whole, year, title, path, indicator):
    band = re.sub(r"\s*kisi$", "", leaf)
    if band in SIZE:
        return indicator, {"workplace_size": SIZE[band]}, None
    if _has(leaf, r"^toplam|^~$"):
        if indicator == "sgk_workplaces_by_size":
            return "sgk_workplaces", {}, None
        return (
            "sgk_compulsory_insured",
            {"scheme": "4a", "insured_type": "total", "sex": "total"},
            None,
        )
    raise KeyError(text)


SEGMENT = [
    (r"kamu", "public"),
    (r"ozel", "private"),
    (r"daimi", "permanent"),
    (r"mevsimlik", "seasonal"),
    (r"gecici", "temporary"),
    (r"^kadin", "female"),
    (r"^erkek", "male"),
    (r"^toplam|^~$|ortalama kazanc|^genel|^ortalama$", "total"),
]


def h_earnings(text, leaf, whole, year, title, path):
    parts = [p for p in text.split(" > ") if p not in ("~",)]
    head = parts[0] if parts else ""
    last = parts[-1] if parts else "~"
    if _has(head, r"is ?yeri"):
        measure = "workplaces"
    elif _has(head, r"zorunlu sigortali"):
        measure = "insured"
    elif _has(head, r"ortalama|^genel$|^kadin$"):
        # A lone "Kadın" at the top is the earnings column whose parent label the
        # extractor could not carry (2011-2017): the insured columns keep theirs.
        measure = "earnings"
    else:
        raise KeyError(text)
    segment = None
    for pattern, value in SEGMENT:
        if _has(last, pattern):
            segment = value
            break
    if segment is None:
        raise KeyError(text)
    if measure == "earnings":
        return "sgk_average_daily_earnings", {"earnings_segment": segment}, None
    if segment in ("female", "male"):
        if measure == "workplaces":
            raise KeyError(text)
        return (
            "sgk_compulsory_insured",
            {"scheme": "4a", "insured_type": "total", "sex": segment},
            None,
        )
    if segment == "total":
        if measure == "workplaces":
            return "sgk_workplaces", {}, None
        return (
            "sgk_compulsory_insured",
            {"scheme": "4a", "insured_type": "total", "sex": "total"},
            None,
        )
    axis = "sector" if segment in ("public", "private") else "tenure"
    indicator = {
        ("workplaces", "sector"): "sgk_workplaces_by_sector",
        ("workplaces", "tenure"): "sgk_workplaces_by_tenure",
        ("insured", "sector"): "sgk_compulsory_insured_by_sector",
        ("insured", "tenure"): "sgk_compulsory_insured_by_tenure",
    }[(measure, axis)]
    return indicator, {"employer_" + axis: segment}, None


BENEFIT = [
    (r"vatani", "patriotic"),
    (r"vazife malul", "duty_invalidity"),
    (r"surekli is ?goremezlik", "permanent_incapacity_income"),
    (r"olum geliri", "survivor_income"),
    (r"olum ayligi|^olum\b|olum > ", "survivor_pension"),
    (r"malul", "invalidity"),
    (r"yasli", "old_age"),
]


def _pension_scheme(title, path, text):
    scheme = scheme_of(title) or scheme_of(path)
    group = "all"
    if scheme == "4b":
        if _has(title + " " + text, r"tarim haric|1479|bagimsiz calisanlar 1479"):
            group = "self_employed"
        if _has(text, r"^tarim haric"):
            group = "self_employed"
        elif _has(text, r"^tarim\b") or _has(title, r"2926|tarimsal"):
            group = "agriculture"
    return scheme, group


def h_pensions(text, leaf, whole, year, title, path, stock=True):
    scheme, group = _pension_scheme(title, path, text)
    if scheme is None:
        raise KeyError(title)
    # From 2014 pensions (aylık) and incomes (gelir) are separate tables, each with its
    # own "all" column; before, one table covered both.
    pensions, incomes = _has(title, r"aylik"), _has(title, r"gelir")
    all_benefits = (
        "total"
        if pensions == incomes
        else ("all_pensions" if pensions else "all_incomes")
    )
    body = re.sub(r"^tarim( haric)? > ", "", text)
    body = re.sub(
        r"^(malulluk\W+yaslilik\W+(ve )?(olum )?sigortasi|is\.? ?kaz\w*\.? ?ile meslek hastaligi sigortasi\w*)[^>]* > ",
        "",
        body,
    )
    indicator = "sgk_pension_recipients" if stock else "sgk_new_pension_awards"
    if _has(body, r"dosya"):
        indicator = "sgk_pension_files" if stock else "sgk_new_pension_files"
        benefit = all_benefits if _has(body, r"^toplam") else _benefit(body)
        return (
            indicator,
            {"scheme": scheme, "scheme_group": group, "benefit": benefit},
            None,
        )
    if _has(
        body,
        r"^(toplam|genel toplam|kisi|toplam \(kisi\)|toplam kisi)( > kisi)?$|^aylik alanlar \(kisi\)$|^toplam > (kisi|0\.0)$",
    ):
        return (
            indicator,
            {
                "scheme": scheme,
                "scheme_group": group,
                "benefit": all_benefits,
                "recipient": "total",
            },
            None,
        )
    if _has(body, r"^toplam \(dosya\)$"):
        return (
            "sgk_pension_files" if stock else "sgk_new_pension_files",
            {"scheme": scheme, "scheme_group": group, "benefit": all_benefits},
            None,
        )
    if _has(body, r"^olum ayligi > (adi malulluk|vazife malullugu|yaslilik) > "):
        raise Skip  # 2012 4/c: survivors split by the deceased's benefit, one year only
    benefit = _benefit(body)
    rest = body.split(" > ", 1)[1] if " > " in body else ""
    if benefit in ("survivor_pension", "survivor_income"):
        who = recipient_of(rest.split(" > ")[-1]) if rest else "total"
        if who is None:
            raise KeyError(text)
        return (
            indicator,
            {
                "scheme": scheme,
                "scheme_group": group,
                "benefit": benefit,
                "recipient": who,
            },
            None,
        )
    sex = sex_of(rest.split(" > ")[-1]) if rest else "total"
    if sex is None:
        raise KeyError(text)
    return (
        indicator,
        {"scheme": scheme, "scheme_group": group, "benefit": benefit, "recipient": sex},
        None,
    )


def _benefit(body: str) -> str:
    for pattern, value in BENEFIT:
        if _has(body, pattern):
            return value
    raise KeyError(body)


def h_new_pensions(**kw):
    return h_pensions(**kw, stock=False)


def h_patriotic(text, leaf, whole, year, title, path):
    if _has(text, r"genel toplam"):
        return (
            "sgk_pension_recipients",
            {
                "scheme": "non_contributory",
                "scheme_group": "all",
                "benefit": "total",
                "recipient": "total",
            },
            None,
        )
    sex = sex_of(leaf)
    if sex is None:
        raise KeyError(text)
    if _has(text, r"kendisi"):
        benefit = "patriotic_self"
    elif _has(text, r"hak ?sahi"):
        benefit = "patriotic_survivor"
    else:
        raise KeyError(text)
    return (
        "sgk_pension_recipients",
        {
            "scheme": "non_contributory",
            "scheme_group": "all",
            "benefit": benefit,
            "recipient": sex,
        },
        None,
    )


def h_law2022(text, leaf, whole, year, title, path):
    if _has(text, r"yesil kart"):
        return "sgk_green_card_holders", {}, None
    if _has(text, r"^aylik alanlar \(kisi\)"):
        return (
            "sgk_pension_recipients",
            {
                "scheme": "non_contributory",
                "scheme_group": "all",
                "benefit": "total",
                "recipient": "total",
            },
            None,
        )
    sex = sex_of(leaf)
    kinds = [
        (r"18 yas alti", "law2022_disabled_under18"),
        (r"sakat", "law2022_disabled"),
        (r"malul", "law2022_invalidity"),
        (r"yasli", "law2022_old_age"),
        (r"silikozis", "law2022_silicosis"),
    ]
    for pattern, benefit in kinds:
        if _has(text, pattern) and sex:
            return (
                "sgk_pension_recipients",
                {
                    "scheme": "non_contributory",
                    "scheme_group": "all",
                    "benefit": benefit,
                    "recipient": sex,
                },
                None,
            )
    raise KeyError(text)


COMPONENT = [
    (r"genel saglik sigortasi", None),
    (r"yesil kart", None),
    (r"aktif", "active"),
    (r"aylik alan|gelir ve aylik", "pensioners"),
    (r"bakmakla", "dependents"),
    (r"2022 sayili", None),
]


def h_coverage(text, leaf, whole, year, title, path):
    if _has(text, r"il nufus|orani|^~$|gelir testi yapilan"):
        raise Skip
    if _has(text, r"\(aktif\+ ?pasif ?\+ ?(yesil ?kart|gelir testi)"):
        # 2010-2012 print coverage twice, with and without green-card holders (2012: the
        # income-tested); the narrower one continues into 2013.
        raise Skip
    if _has(text, r"yesil kartlilar haric|gelir testi yaptiranlar haric"):
        return (
            "sgk_social_security_coverage",
            {"scheme": "total", "coverage_component": "total"},
            None,
        )
    if _has(text, r"2022 sayili"):
        # Not inside the coverage total it is printed beside (2010: total + this = sum).
        return "sgk_law2022_beneficiaries", {}, None
    if _has(text, r"genel saglik sigortasi"):
        # From 2013 the coverage total includes those registered only for GSS.
        return (
            "sgk_social_security_coverage",
            {"scheme": "total", "coverage_component": "gss_registered"},
            None,
        )
    if _has(text, r"yesil kart"):
        return "sgk_green_card_holders", {}, None
    if _has(text, r"sosyal guvenlik kapsami\b"):
        scheme = scheme_of(text) or (
            "4a" if _has(title, r"4-1/a.*aktif ve pasif sigortalilar ile") else "total"
        )
        return (
            "sgk_social_security_coverage",
            {"scheme": scheme, "coverage_component": "total"},
            None,
        )
    head = text.split(" > ")[0]
    component = None
    for pattern, value in COMPONENT:
        if value and _has(head, pattern):
            component = value
            break
    if component is None:
        raise KeyError(text)
    if head in ("aktif sigortalilar", "aylik alanlar") and " > " in text:
        # 2012's coverage table repeats the active and pension breakdowns stored from
        # their own tables; only its totals are coverage.
        if not _has(leaf, r"^toplam"):
            raise Skip
        if component == "pensioners" and not _has(leaf, r"kisi"):
            raise Skip
    default = (
        "4a" if _has(title, r"4-1/a.*aktif ve pasif sigortalilar ile") else "total"
    )
    scheme = scheme_of(leaf) or (
        default if _has(leaf, r"toplam") or leaf == head else None
    )
    if scheme is None:
        raise KeyError(text)
    return (
        "sgk_social_security_coverage",
        {"scheme": scheme, "coverage_component": component},
        None,
    )


def h_active_passive_4b(text, leaf, whole, year, title, path):
    group = (
        "self_employed"
        if _has(title, r"1479") and not _has(title, r"2926")
        else (
            "agriculture"
            if _has(title, r"2926") and not _has(title, r"1479")
            else "all"
        )
    )
    if _has(text, r"sosyal guvenlik kapsami"):
        if group != "all":
            raise Skip  # the 1479 and 2926 sheets split the 4/b coverage stored whole
        return (
            "sgk_social_security_coverage",
            {"scheme": "4b", "coverage_component": "total"},
            None,
        )
    if _has(text, r"aktif sigortali"):
        kind = {
            "self_employed": "self_employed_total",
            "agriculture": "agriculture_compulsory",
            "all": "total",
        }[group]
        for pattern, value in [
            (r"istege", "voluntary"),
            (r"muhtar", "muhtar"),
            (r"zorunlu", "self_employed_compulsory"),
        ]:
            if _has(leaf, pattern):
                kind = value
        return "sgk_active_insured", {"scheme": "4b", "insured_type": kind}, None
    if _has(text, r"^~ > toplam > (dosya|kisi)$"):
        text = "aylik alanlar > " + text[4:]
    if _has(text, r"aylik"):
        body = re.sub(
            r"^aylik (ve gelir )?alanlar( toplam)?( > pensioners)? > ",
            lambda m: "toplam > " if m.group(2) else "",
            text,
        )
        body = body.replace("pensioners > ", "").replace(" > ~", "")
        if _has(body, r"^toplam > dosya"):
            return (
                "sgk_pension_files",
                {"scheme": "4b", "scheme_group": group, "benefit": "total"},
                None,
            )
        if _has(body, r"^toplam > kisi"):
            return (
                "sgk_pension_recipients",
                {
                    "scheme": "4b",
                    "scheme_group": group,
                    "benefit": "total",
                    "recipient": "total",
                },
                None,
            )
        benefit = _benefit(body)
        if _has(body, r"dosya"):
            return (
                "sgk_pension_files",
                {"scheme": "4b", "scheme_group": group, "benefit": benefit},
                None,
            )
        return (
            "sgk_pension_recipients",
            {
                "scheme": "4b",
                "scheme_group": group,
                "benefit": benefit,
                "recipient": "total",
            },
            None,
        )
    raise KeyError(text)


def h_active_pensioners_4c(text, leaf, whole, year, title, path):
    if _has(text, r"^aktif sigortali$"):
        return "sgk_active_insured", {"scheme": "4c", "insured_type": "total"}, None
    if _has(text, r"sosyal guvenlik kapsami"):
        return (
            "sgk_social_security_coverage",
            {"scheme": "4c", "coverage_component": "total"},
            None,
        )
    body = text.replace("aylik alanlar > ", "", 1)
    if _has(body, r"aylik alanlar \(kisi\)"):
        return (
            "sgk_pension_recipients",
            {
                "scheme": "4c",
                "scheme_group": "all",
                "benefit": "total",
                "recipient": "total",
            },
            None,
        )
    if _has(body, r"toplam dosya"):
        return (
            "sgk_pension_files",
            {"scheme": "4c", "scheme_group": "all", "benefit": "total"},
            None,
        )
    if _has(body, r"vatani"):
        raise Skip  # stored from the patriotic-service tables, which split self/survivor
    benefit = _benefit(body)
    if _has(body, r"dosya"):
        return (
            "sgk_pension_files",
            {"scheme": "4c", "scheme_group": "all", "benefit": benefit},
            None,
        )
    return (
        "sgk_pension_recipients",
        {
            "scheme": "4c",
            "scheme_group": "all",
            "benefit": benefit,
            "recipient": "total",
        },
        None,
    )


def h_survivors_4b(text, leaf, whole, year, title, path):
    group = "agriculture" if _has(title, r"2926|tarimsal") else "self_employed"
    benefit = (
        "survivor_income" if _has(title, r"olum geliri|surekli") else "survivor_pension"
    )
    if _has(title, r"surekli"):
        raise Skip  # 2013 1479 'death insurance permanent incapacity': one year, one column
    if text in ("genel toplam", "toplam", "toplam toplam"):
        return (
            "sgk_pension_recipients",
            {
                "scheme": "4b",
                "scheme_group": group,
                "benefit": benefit,
                "recipient": "total",
            },
            None,
        )
    if _has(text, r"> toplam"):
        raise Skip  # a subtotal of spouses, children or parents: the leaves are stored
    who = recipient_of(leaf.replace(" ~", "")) or recipient_of(
        text.split(" > ")[-2] if " > " in text else ""
    )
    if who is None:
        raise KeyError(text)
    return (
        "sgk_pension_recipients",
        {"scheme": "4b", "scheme_group": group, "benefit": benefit, "recipient": who},
        None,
    )


def _event(text: str) -> str | None:
    """The innermost header segment that names one event: a group label such as "iş
    kazası veya meslek hastalığı" names both and decides nothing."""
    for seg in reversed(text.split(" > ")):
        disease, accident = _has(seg, r"meslek hastalig"), _has(seg, r"is ?kaza")
        if disease != accident:
            return "occupational_disease" if disease else "accident"
    return None


def _wa_scheme(title: str) -> str:
    return scheme_of(title) or "4a"


def h_wa_cases(text, leaf, whole, year, title, path):
    scheme = _wa_scheme(title)
    sex = sex_of(leaf)
    if _has(text, r"is goremezlik surelerine"):
        middle = text.split(" > ")
        if len(middle) == 3 and sex_of(middle[1]) in ("female", "male"):
            band = {
                "kaza gunu (calisir)": "accident_day_working",
                "kaza gunu (is goremez)": "accident_day_incapacitated",
                "5+(1)": "5plus",
            }.get(middle[2], middle[2])
            if band not in (
                "accident_day_working",
                "accident_day_incapacitated",
                "2",
                "3",
                "4",
                "5plus",
            ):
                raise KeyError(text)
            return (
                "sgk_work_accidents_by_incapacity",
                {"scheme": scheme, "incapacity_band": band, "sex": sex_of(middle[1])},
                None,
            )
        if len(middle) == 3 and middle[1] == "toplam" and sex:
            return (
                "sgk_work_accident_cases",
                {"scheme": scheme, "event": "accident", "sex": sex},
                None,
            )
        raise KeyError(text)
    event = _event(text)
    if _has(text, r"^toplam$"):
        return (
            "sgk_work_accident_cases",
            {"scheme": scheme, "event": "occupational_disease", "sex": "total"},
            None,
        )
    if event is None or sex is None:
        raise KeyError(text)
    return (
        "sgk_work_accident_cases",
        {"scheme": scheme, "event": event, "sex": sex},
        None,
    )


def h_wa_cases_old(text, leaf, whole, year, title, path):
    sex = sex_of(leaf)
    if sex is None:
        raise KeyError(text)
    head = text.split(" > ")[0]
    if head == "toplam":
        raise Skip  # accidents + diseases: both stored
    if _has(head, r"olum sayisi"):
        event = _event(text.split(" > ", 1)[1] if " > " in text else "")
        if event is None:
            if _has(text, r"> toplam >"):
                raise Skip  # accidents + diseases: both stored
            raise KeyError(text)
        return (
            "sgk_work_accident_deaths",
            {"scheme": "4a", "event": event, "sex": sex},
            None,
        )
    if _has(head, r"surekli is goremezlik"):
        event = _event(text)
        if event is None:
            if _has(text, r"> toplam >"):
                raise Skip
            raise KeyError(text)
        return (
            "sgk_permanent_incapacity_cases",
            {"scheme": "4a", "event": event, "sex": sex},
            None,
        )
    event = _event(head)
    if event is None:
        raise KeyError(text)
    return "sgk_work_accident_cases", {"scheme": "4a", "event": event, "sex": sex}, None


def h_wa_deaths(text, leaf, whole, year, title, path):
    sex = sex_of(leaf)
    event = _event(text)
    if sex is None:
        raise KeyError(text)
    if event is None:
        if _has(text, r"^toplam"):
            raise Skip
        raise KeyError(text)
    return (
        "sgk_work_accident_deaths",
        {"scheme": _wa_scheme(title), "event": event, "sex": sex},
        None,
    )


def _care(text: str) -> str | None:
    if _has(text, r"ayakta"):
        return "outpatient"
    if _has(text, r"yatar"):
        return "inpatient"
    if _has(text, r"ayakta\+|^toplam"):
        return "total"
    return None


def h_wa_days(text, leaf, whole, year, title, path, event_default=None):
    scheme = _wa_scheme(title)
    parts = [p for p in text.split(" > ") if p != "~"]
    if parts == ["toplam"] or parts == ["erkek"] or parts == ["kadin"]:
        raise Skip  # a lone trailing column whose parent the extractor could not carry
    event = _event(parts[0]) or event_default
    if parts[0] == "toplam" and event_default is None:
        raise Skip  # accidents + diseases: both stored
    care = "total" if _has(text, r"toplam gecici is goremezlik suresi") else _care(text)
    sexes = [sex_of(p) for p in parts]
    sex = next((s for s in sexes if s in ("female", "male")), None) or (
        "total" if "total" in sexes else None
    )
    band = parts[-1] if re.fullmatch(r"[1-4]|5\+(\(1\))?", parts[-1]) else None
    if event is None or care is None or sex is None:
        raise KeyError(text)
    dims = {"scheme": scheme, "event": event, "care": care, "sex": sex}
    if band:
        dims["incapacity_band"] = "5plus" if band.startswith("5") else band
    else:
        dims["incapacity_band"] = "total"
    return "sgk_temporary_incapacity_days", dims, None


def h_wa_days_accident(**kw):
    return h_wa_days(**kw, event_default="accident")


def h_wa_days_disease(**kw):
    return h_wa_days(**kw, event_default="occupational_disease")


def h_wa_permanent(text, leaf, whole, year, title, path, new=False):
    scheme = _wa_scheme(title)
    parts = text.split(" > ")
    if text == "toplam toplam":
        raise Skip
    if recipient_of(leaf) not in (None, "total") or _has(text, r"genel toplam|^kisi"):
        raise Skip  # 2013: a survivors' table filed under this title
    sex = sex_of(parts[-1])
    event = _event(text)
    if sex is None:
        raise KeyError(text)
    if len(parts) == 1 or parts == ["toplam toplam"]:
        raise Skip  # a lone trailing column whose parent the extractor could not carry
    if new:
        if _has(parts[0], r"gecmis yil"):
            timing = "earlier_years"
        elif _has(parts[0], r"yil(i|inda) icinde|yilinda"):
            timing = "same_year"
        elif parts[0] == "toplam":
            timing = "total"
        else:
            if parts in (["kadin"], ["toplam"]):
                raise Skip
            raise KeyError(text)
        if event is None:
            raise KeyError(text)
        return (
            "sgk_new_permanent_incapacity_income",
            {"scheme": scheme, "event": event, "timing": timing, "sex": sex},
            None,
        )
    if event is None:
        if parts[0] == "toplam":
            raise Skip
        raise KeyError(text)
    return (
        "sgk_permanent_incapacity_income",
        {"scheme": scheme, "event": event, "sex": sex},
        None,
    )


def h_wa_new_permanent(**kw):
    return h_wa_permanent(**kw, new=True)


def h_wa_death_income(text, leaf, whole, year, title, path, new=False):
    scheme = _wa_scheme(title)
    indicator = (
        "sgk_new_survivor_income_awards" if new else "sgk_survivor_income_recipients"
    )
    files = "sgk_new_survivor_income_files" if new else "sgk_survivor_income_files"
    parts = text.split(" > ")
    event = _event(parts[0]) or (
        "total"
        if parts[0] in ("toplam", "genel toplam", "kisi", "toplam toplam")
        else None
    )
    if event is None:
        who = recipient_of(leaf)
        if who and len(parts) == 1:
            raise Skip  # 2013: the recipients table without the event split, kept from 2014
        raise KeyError(text)
    if _has(leaf, r"dosya"):
        if event == "total":
            raise Skip
        return files, {"scheme": scheme, "event": event}, None
    who = recipient_of(leaf) if len(parts) > 1 else "total"
    if who is None:
        raise KeyError(text)
    if event == "total":
        raise Skip
    return indicator, {"scheme": scheme, "event": event, "recipient": who}, None


def h_wa_new_death_income(**kw):
    return h_wa_death_income(**kw, new=True)


def h_sickness(text, leaf, whole, year, title, path):
    if _has(text, r"orani|ortalama|basina"):
        raise Skip  # derived: cases per insured, share, days per case
    sex = sex_of(leaf)
    if sex is None:
        raise KeyError(text)
    if _has(text, r"gecici is goremezlik suresi"):
        return "sgk_sickness_incapacity_days", {"sex": sex}, None
    if _has(text, r"hastalik olay sayisi"):
        return "sgk_sickness_cases", {"sex": sex}, None
    raise KeyError(text)


HANDLERS = {
    "active": h_active,
    "compulsory_by_sex": h_compulsory_by_sex,
    "active_by_sex": h_active_by_sex,
    "workplaces": h_workplaces,
    "workplaces_by_size": lambda **kw: h_by_size(
        **kw, indicator="sgk_workplaces_by_size"
    ),
    "insured_by_size": lambda **kw: h_by_size(
        **kw, indicator="sgk_compulsory_insured_by_size"
    ),
    "earnings": h_earnings,
    "pensions": h_pensions,
    "new_pensions": h_new_pensions,
    "patriotic": h_patriotic,
    "law2022": h_law2022,
    "coverage": h_coverage,
    "active_passive_4b": h_active_passive_4b,
    "active_pensioners_4c": h_active_pensioners_4c,
    "survivors_4b": h_survivors_4b,
    "wa_cases": h_wa_cases,
    "wa_cases_old": h_wa_cases_old,
    "wa_deaths": h_wa_deaths,
    "wa_days_old": lambda **kw: h_wa_days(**kw),
    "wa_days_accident": h_wa_days_accident,
    "wa_days_disease": h_wa_days_disease,
    "wa_permanent": h_wa_permanent,
    "wa_new_permanent": h_wa_new_permanent,
    "wa_death_income": h_wa_death_income,
    "wa_new_death_income": h_wa_new_death_income,
    "sickness": h_sickness,
}

#: Indicators whose values cannot be summed: every printed breakdown is kept.
NOT_ADDITIVE = {"sgk_average_daily_earnings"}


# --- assembly -----------------------------------------------------------------------


#: Titles the yearbook got wrong, checked against the neighbouring tables.
TITLE_FIXES = {
    # 2.35 is the 2926 (farmers) income table, as in every other year; its title repeats
    # 2.21's "1479" and the two collide.
    (
        2014,
        "TABLO-2.35",
        "Tablo 2.35- 5510 Sayılı Kanunun 4-1/b Maddesi Kapsamında (Bağımsız Çalışanlar 1479 S.K.) Gelir Alanların Cinsiyet, İl ve Gelir Türüne Göre Dağılımı, 2014",
    ): "Tablo 2.35- 5510 Sayılı Kanunun 4-1/b Maddesi Kapsamında (Bağımsız Çalışanlar 2926 S.K.) Gelir Alanların Cinsiyet, İl ve Gelir Türüne Göre Dağılımı, 2014",
}


def classified() -> tuple[pl.DataFrame, dict]:
    cells = pl.read_parquet(CELLS)
    report: dict = {
        "skipped_topics": defaultdict(int),
        "skipped_cells": defaultdict(int),
        "unknown": [],
    }
    records = []
    for (title, path, sheet, header, row_label), group in cells.group_by(
        "title", "file", "sheet", "header", "row_label", maintain_order=True
    ):
        title = TITLE_FIXES.get((group["year"][0], sheet, title), title)
        topic = topic_of(title)
        if topic in SKIPPED_TOPICS:
            report["skipped_topics"][topic] += group.height
            continue
        try:
            indicator, dims, year = classify(topic, title, path, header, row_label)
        except Skip:
            report["skipped_cells"][topic] += group.height
            continue
        except KeyError as error:
            report["unknown"].append(
                (
                    topic,
                    str(error),
                    fold(title)[:80],
                    group["year"].unique().sort().to_list(),
                )
            )
            continue
        for row in group.iter_rows(named=True):
            records.append(
                {
                    "indicator_id": indicator,
                    "area_id": f"TR-{row['plate']:02d}",
                    "yearbook": row["year"],
                    "year": year or row["year"],
                    "dims": dims,
                    "value": row["value"],
                    "where": f"{row['year']}/{row['sheet']}/r{row['row']}c{row['col']}",
                }
            )
    return records, report


def resolve(records: list[dict], report: dict) -> list[dict]:
    """One value per indicator-area-year-dims: the yearbook of that year, else the latest.
    Differences between yearbooks are counted, the subtotals verified and dropped."""
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        key = (
            r["indicator_id"],
            r["area_id"],
            r["year"],
            tuple(sorted(r["dims"].items())),
        )
        by_key[key].append(r)
    chosen = []
    revisions = conflicts = 0
    for key, rows in by_key.items():
        same = [r for r in rows if r["yearbook"] == r["year"]]
        if (
            len({r["yearbook"] for r in same}) < len(same)
            and len({r["value"] for r in same}) > 1
        ):
            # Two different figures for one cell inside one yearbook: two tables disagree.
            conflicts += 1
            report.setdefault("conflict_examples", []).append(
                (key, [(r["where"], r["value"]) for r in same])
            )
        pick = same[0] if same else max(rows, key=lambda r: r["yearbook"])
        if len({round(r["value"], 2) for r in rows}) > 1:
            revisions += 1
        chosen.append(pick)
    report["revised_cells"] = revisions
    report["conflicting_cells"] = conflicts

    return _partition(chosen, report)


#: Values that are the sum of other values of the same dimension. A subtotal row is an
#: aggregate only where its children are printed beside it; otherwise it is itself a leaf
#: (4/a "compulsory" before 2017, when it was not yet split).
SUBTOTALS = {
    "insured_type": {
        "self_employed_total": {"self_employed_compulsory", "voluntary", "muhtar"},
        "compulsory": {
            "long_term",
            "domestic_ek9",
            "self_employed_compulsory",
            "agriculture_compulsory",
            "muhtar",
        },
    },
}

#: Dimensions whose printed total is not the sum of its values, and is stored as printed:
#: a person drawing two benefits is counted once in "all benefits"; the file total
#: counts old-age and invalidity files the table does not list.
NON_PARTITION = {"benefit"}
NON_PARTITION_VALUES = {"total", "all_pensions", "all_incomes"}


def _partition(rows: list[dict], report: dict) -> list[dict]:
    """Verify every printed total against the leaves it covers, then keep the leaves.

    A leaf is a row with no total or effective subtotal in its breakdown. Aggregates are
    taken most specific first; one with no leaves under it (the source printed only the
    total) becomes a leaf itself, without the keys it totals over."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["indicator_id"], r["area_id"], r["year"])].append(r)
    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    examples = report.setdefault("subtotal_examples", defaultdict(list))
    out: list[dict] = []
    for (indicator, _, _), members in groups.items():
        if indicator in NOT_ADDITIVE:
            out.extend(members)
            continue
        fixed = [
            m
            for m in members
            if any(m["dims"].get(d) in NON_PARTITION_VALUES for d in NON_PARTITION)
        ]
        rest = [m for m in members if m not in fixed]
        out.extend(fixed)

        def effective(row: dict, dim: str, rest: list[dict] = rest) -> set[str] | None:
            children = SUBTOTALS.get(dim, {}).get(row["dims"].get(dim))
            if not children:
                return None
            others = {k: v for k, v in row["dims"].items() if k != dim}
            for m in rest:
                if m["dims"].get(dim) in children and all(
                    m["dims"].get(k) == v for k, v in others.items()
                ):
                    return children
            return None

        def level(row: dict) -> int:
            return sum(
                1
                for d, v in row["dims"].items()
                if v == "total" or effective(row, d) is not None
            )

        leaves = [m for m in rest if level(m) == 0]
        aggregates = sorted((m for m in rest if level(m) > 0), key=level)
        for agg in aggregates:
            rules = {}
            for d, v in agg["dims"].items():
                if v == "total":
                    continue
                rules[d] = effective(agg, d) or {v}
            under = [
                leaf
                for leaf in leaves
                if all(leaf["dims"].get(d) in allowed for d, allowed in rules.items())
            ]
            label = (
                indicator
                + ":"
                + ",".join(
                    d
                    for d, v in sorted(agg["dims"].items())
                    if v == "total" or d not in rules or rules[d] != {v}
                )
            )
            if under:
                total = agg["value"]
                summed = sum(u["value"] for u in under)
                stats[label][0] += 1
                if abs(summed - total) > max(1.0, abs(total) * 0.001):
                    stats[label][1] += 1
                    if len(examples[label]) < 4:
                        examples[label].append(
                            (agg["where"], total, round(summed, 2), len(under))
                        )
            else:
                kept = dict(agg)
                kept["dims"] = {d: v for d, v in agg["dims"].items() if v != "total"}
                leaves.append(kept)
        out.extend(leaves)
    report["subtotals"] = dict(stats)
    return out


class SgkProvinces:
    source_id = "sgk"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 14)
    indicator_id = ""

    _cache: ClassVar[dict] = {}

    def fetch(self) -> Path:
        return CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        if "rows" not in SgkProvinces._cache:
            records, report = classified()
            if report["unknown"]:
                lines = [
                    f"{t} {y}: {h} [{ti}]" for t, h, ti, y in report["unknown"][:40]
                ]
                raise KeyError(
                    f"SGK: {len(report['unknown'])} tanınmayan başlık\n"
                    + "\n".join(lines)
                )
            SgkProvinces._cache["rows"] = resolve(records, report)
            SgkProvinces._cache["report"] = report
        rows = [
            r
            for r in SgkProvinces._cache["rows"]
            if r["indicator_id"] == self.indicator_id
        ]
        indicator = get(self.indicator_id)
        declared = load().dimensions
        for r in rows:
            for k, v in r["dims"].items():
                if k not in indicator.dims:
                    raise KeyError(f"{self.indicator_id}: tanımsız kırılım {k}")
                if declared[k].values_tr and v not in declared[k].values_tr:
                    raise KeyError(f"{self.indicator_id}: {k}={v} sözlükte yok")
        frame = pl.DataFrame(
            {
                "area_id": [r["area_id"] for r in rows],
                "period_start": [dt.date(r["year"], 1, 1) for r in rows],
                "dims": [format_dims(r["dims"]) for r in rows],
                "value": [float(r["value"]) for r in rows],
            },
            schema={
                "area_id": pl.String,
                "period_start": pl.Date,
                "dims": pl.String,
                "value": pl.Float64,
            },
        )
        if frame.select("area_id", "period_start", "dims").is_duplicated().any():
            raise ValueError(self.indicator_id + ": ayni il-yil-kirilim iki kez")
        return frame.with_columns(
            pl.lit(self.indicator_id).alias("indicator_id"),
            pl.lit("province").alias("area_level"),
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


INDICATORS = [
    "sgk_active_insured",
    "sgk_active_insured_by_sex",
    "sgk_compulsory_insured",
    "sgk_compulsory_insured_by_size",
    "sgk_compulsory_insured_by_sector",
    "sgk_compulsory_insured_by_tenure",
    "sgk_workplaces",
    "sgk_workplaces_by_size",
    "sgk_workplaces_by_sector",
    "sgk_workplaces_by_tenure",
    "sgk_average_daily_earnings",
    "sgk_pension_recipients",
    "sgk_pension_files",
    "sgk_new_pension_awards",
    "sgk_new_pension_files",
    "sgk_social_security_coverage",
    "sgk_green_card_holders",
    "sgk_law2022_beneficiaries",
    "sgk_work_accident_cases",
    "sgk_work_accidents_by_incapacity",
    "sgk_work_accident_deaths",
    "sgk_permanent_incapacity_cases",
    "sgk_temporary_incapacity_days",
    "sgk_permanent_incapacity_income",
    "sgk_new_permanent_incapacity_income",
    "sgk_survivor_income_recipients",
    "sgk_survivor_income_files",
    "sgk_new_survivor_income_awards",
    "sgk_new_survivor_income_files",
    "sgk_sickness_cases",
    "sgk_sickness_incapacity_days",
]

SGK_ADAPTERS = {
    ident: type(
        "".join(p.title() for p in ident.split("_")),
        (SgkProvinces,),
        {"indicator_id": ident},
    )
    for ident in INDICATORS
}
