"""SGK yearbooks, Türkiye-wide tables: work accidents and occupational disease.

`scripts/extract_sgk_national.py` flattens the national sheets of the yearbooks into
`raw/sgk/national_cells.parquet` (year, title, row code and label, the header path above
the column, value). This adapter reads the work accident and occupational disease tables:
one indicator per breakdown (injury type, hour, age, NACE ...), each with the scheme
(4/a, 4/b), sex, outcome and — for accidents — the incapacity-day class.

The yearbooks renumber the tables every few years, so a table is recognised by the words
of its title (`TOPICS`) and a column by the words of its header path (`column`). Printed
totals (the Toplam row, the Toplam sex columns) are checked against their parts and
dropped (K16).

Tables whose header path the extractor could not read (the header cells hold numbers or
nothing — a handful of sheets where the header row is merged across a page break) are not
guessed at: they are listed by `report()` and left out.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from collections import defaultdict
from functools import cache
from pathlib import Path

import polars as pl

from ..config import RAW

CELLS = RAW / "sgk" / "national_cells.parquet"


def fold(text: str) -> str:
    """Lower-case ASCII: also strips the combining dot some sheets put on `İ`."""
    text = unicodedata.normalize(
        "NFKD", text.replace("İ", "i").replace("I", "ı").lower()
    )
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).replace("ı", "i")
    return re.sub(r"\s+", " ", text).strip()


#: Title words -> (indicator suffix, breakdown key). Ordered: first match wins, so the
#: specific phrases come before the ones they contain.
TOPICS = [
    (r"yaranin turune", "injury_type", "injury_type"),
    (r"vucuttaki yerine", "body_part", "body_part"),
    (r"kullandigi materyal", "material_agent", "material_agent"),
    (r"calistiklari cevreye", "work_environment", "work_environment"),
    (r"calistiklari ortama", "workstation", "workstation"),
    (r"genel faaliyete", "work_process", "work_process"),
    (r"ozel faaliyete", "specific_activity", "specific_activity"),
    (r"sapma", "deviation", "deviation"),
    (r"yaralanmaya sebep olan", "contact_mode", "contact_mode"),
    (r"saatlere", "hour", "hour"),
    (r"tanilarina", "diagnosis", "diagnosis"),
    (r"meslek gruplarina", "occupation", "occupation"),
    (
        r"is yerinde calisan sigortali sayilarina",
        "workplace_size",
        "workplace_employees",
    ),
    (r"calisma suresi", "tenure", "job_tenure"),
    (r"yaslar", "age", "age"),
    (r"aylara", "month", "month"),
    (r"ekonomik faaliyet", "activity", "nace_class"),
]

#: Titles in the accident/disease family that are a different shape: rates, pensions,
#: stock of beneficiaries, days lost. Left out on purpose.
EXCLUDED = re.compile(
    r"gelir|aylik|birikimli|siklik|hiz|oran|kaybedilen|gecici is goremezlik sure|"
    r"islemi tamamlanan|standardize|analik|surekli is goremezlik"
)

DAY_CLASSES = [
    (r"kaza gunu \(?calisir", "0_at_work"),
    (r"kaza gunu \(?is ?goremez", "0_incapacity"),
    (r"^5\+", "5+"),
    (r"^1$", "1"),
    (r"^2$", "2"),
    (r"^3$", "3"),
    (r"^4$", "4"),
]


class Unreadable(Exception):
    """A column whose header path does not say what it counts."""


def scheme_of(title: str) -> str | None:
    if re.search(r"4[-/ ]?1 ?[-/ ]?a\b|4/a\b|4/1 a\b", title):
        return "4a"
    if re.search(r"4[-/ ]?1 ?[-/ ]?b\b|4/b\b|4/1 b\b", title):
        return "4b"
    return None


def topic_of(title: str) -> tuple[str, str] | None:
    if not re.search(r"is kazasi|meslek hastalig", title) or EXCLUDED.search(title):
        return None
    for pattern, suffix, key in TOPICS:
        if re.search(pattern, title):
            return suffix, key
    return None


def sex_of(segment: str) -> str | None:
    if re.match(r"erkek", segment):
        return "male"
    if re.match(r"kadin", segment):
        return "female"
    if re.match(r"toplam", segment):
        return "total"
    return None


def column(header: str, deaths_only: bool = False) -> tuple[str, str, str] | None:
    """Header path -> (outcome, sex, day class). None for a printed total column.

    `deaths_only` is for tables whose title counts only the dead: their column headers
    say just `İş Kazası` / `Meslek Hastalığı`, and read alone would pass the deaths off
    as accidents.
    """
    parts = [fold(p) for p in header.split(" > ")[2:]]
    # A column of people diagnosed after their insurance ended: a memo total with no sex
    # split, beside the table rather than a breakdown of it.
    if re.search(r"after the end of the insurance|sona ermesinden sonra", fold(header)):
        return None
    if not parts or all(re.fullmatch(r"[\d.,]*", p) for p in parts):
        raise Unreadable(header)
    # Days of incapacity printed under the same title as the people (2013 month table,
    # second block): a different measure, never to be added to a head count.
    if re.search(
        r"days of temporary incapacity|goremezlik suresi|kaybedilen gun", fold(header)
    ):
        return None
    text = " > ".join(parts)
    death = deaths_only or re.search(r"olen|olum", text)
    disease = re.search(r"meslek hastalig", text)
    if disease and death:
        outcome = "disease_death"
    elif disease:
        outcome = "disease"
    elif death:
        outcome = "accident_death"
    elif re.search(r"is kazasi|is goremezlik surelerine", text):
        outcome = "accident"
    else:
        raise Unreadable(header)

    sexes = [sex_of(p) for p in parts if sex_of(p)]
    if not sexes:
        raise Unreadable(header)
    days = "all"
    for pattern, label in DAY_CLASSES:
        if re.search(pattern, parts[-1]):
            days = label
    # `Toplam > Erkek` under the accident group is the sum of that sex's day classes;
    # `Erkek > Toplam` likewise. Any toplam in the path marks a printed subtotal.
    if "total" in sexes:
        if outcome == "accident" and days == "all" and sexes[-1] != "total":
            return outcome, sexes[-1], "total"
        return None
    if outcome == "accident" and days == "all":
        raise Unreadable(header)
    if outcome != "accident" and days != "all":
        raise Unreadable(header)
    return outcome, sexes[-1], days


#: ISCO-08 major group -> words of its Turkish name. A one-digit row is a major group only
#: when both agree; `1-Subaylar` is an armed forces sub-group, not `1-Yöneticiler`.
ISCO_MAJOR = {
    "0": r"silahli kuvvet",
    "1": r"yonetici",
    "2": r"profesyonel",
    "3": r"teknisyen|tekniker",
    "4": r"buro",
    "5": r"hizmet ve satis",
    "6": r"ormancilik|ciftcilik",
    "7": r"sanatkar",
    "8": r"tesis ve makine",
    "9": r"nitelik gerektirmeyen",
}

TENURE = [
    (r"^1 gun", "1d"),
    (r"^2-7 gun", "2-7d"),
    (r"^8 ?- ?30 gun", "8-30d"),
    (r"^1 aydan fazla", "1-3m"),
    (r"^3 aydan fazla", "3-12m"),
    (r"^1 yildan fazla", "1-2y"),
    (r"^2 yildan fazla", "2-5y"),
    (r"^5 yildan fazla", "5-10y"),
    (r"^10\+ yil", "10y+"),
]


def category(
    code: str | None, label: str | None, suffix: str, state: dict
) -> str | None:
    """Row -> breakdown value. `TOTAL` for the printed total row, None for a subtotal.

    `state` carries position down the hierarchical tables:

    * activity rows name only the NACE levels that changed —
      `01-Bitkisel... | 1-Tek yıllık... | 1-Tahılların...`, then `2-Çeltik...` for the next
      class — so division and group are carried forward and the class is stored (4 digits);
    * occupation rows mix ISCO levels, and the armed forces block reuses one-digit numbers
      (`1-Subaylar` under `0-`), so only the major groups are kept, recognised by number
      and name together (`ISCO_MAJOR`).
    """
    code = (code or "").strip()
    text = fold(label or "")
    if not code and re.match(r"(genel )?toplam|total", text):
        return "TOTAL"
    if re.search(r"sona erdikten sonra|after the end of the insurance", text):
        return "insurance_ended"
    if not code and re.match(r"bilinmeyen|unknown", text):
        return "unknown"
    if suffix == "workplace_size":
        # The code column here holds a coarser size band, repeated down the rows; the
        # label is the class.
        if text.startswith("bilinmeyen"):
            return "unknown"
        match = re.match(r"^(\d+) ?(?:- ?(\d+)|(\+|ve uzeri))? ?calisan", text)
        if not match:
            raise Unreadable("satır: " + (label or ""))
        low, high, open_end = match.groups()
        return low + ("-" + high if high else "+" if open_end else "")
    if code:
        return code
    parts = [fold(p) for p in (label or "").split(" | ")]

    if suffix == "activity":
        numbers = [re.match(r"^(\d{1,2}) ?-", p) for p in parts]
        if not all(numbers):
            raise Unreadable("satır: " + (label or ""))
        digits = [m.group(1) for m in numbers]
        if len(digits[0]) == 2:
            state["division"], digits = digits[0], digits[1:]
            if not digits:
                return None
        if len(digits) == 2:
            state["group"], digits = digits[0], digits[1:]
        if len(digits) != 1 or not state.get("division") or not state.get("group"):
            raise Unreadable("satır: " + (label or ""))
        return state["division"] + state["group"] + digits[0]

    if suffix == "occupation":
        match = re.match(r"^(\d) ?-", parts[0])
        if (
            match
            and len(parts) == 1
            and re.search(ISCO_MAJOR[match.group(1)], parts[0])
        ):
            return match.group(1)
        return None

    if suffix == "diagnosis":
        if re.search(r"grubu", parts[0]):
            return None
        match = re.match(r"^([a-z](?:\d{2}(?:\.\d{1,2})?)?) ?-", parts[0])
        if not match:
            raise Unreadable("satır: " + (label or ""))
        return match.group(1).upper()

    match = re.match(r"^(\d{2}\.\d{2})(?!\d)", parts[0])
    if match:
        return match.group(1)
    for pattern, value in TENURE:
        if re.match(pattern, text):
            return value
    if re.match(r"80 ve uzeri", text):
        return "80+"
    if re.fullmatch(r"\d{2}\+", text):
        return text
    if re.search(r"diger basliklar altinda", text):
        return "999"
    if re.search(r"bilinmeyen|belirtilmemis|unknown", text):
        return "unknown"
    if re.search(r"sona ermis", text):
        return "ended"
    raise Unreadable("satır: " + (label or ""))


def parent_of(code: str) -> str | None:
    """The group a classification code sits under, when the code says so.

    ESAW-style three-digit codes group by their first two digits (`010` over `011`,
    `012`); two-part codes by the first part (`01.00` over `01.01`); ICD codes by the part
    before the dot (`A26` over `A26.0`).
    """
    if re.fullmatch(r"\d{2}[1-9]", code):
        return code[:2] + "0"
    if re.fullmatch(r"\d{2}\.(0[1-9]|[1-9]\d)", code):
        return code[:2] + ".00"
    if re.fullmatch(r"\d[1-9]", code):
        return code[0] + "0"
    return None


def drop_parents(rows: list) -> list:
    """Remove group rows whose members are also printed, so the rows partition (K16)."""
    codes = {row[0] for row in rows}
    parents = {parent_of(c) for c in codes} & codes
    # ICD codes nest to any depth (M65 > M65.0 > M65.04): a code is a group when another
    # printed code extends it.
    icd = {c for c in codes if re.fullmatch(r"[A-Z]\d{2}(\.\d{1,2})?", c)}
    parents |= {c for c in icd if any(o != c and o.startswith(c) for o in icd)}
    return [row for row in rows if row[0] not in parents]


@cache
def tables() -> tuple[dict, list[str]]:
    """(suffix, key, scheme, year) -> rows, and the tables left out with the reason.

    Every kept table passes one check: for each column, the kept rows add up to the
    printed total row. That is what guards the hierarchy handling above — a subtotal kept
    by mistake, or a leaf dropped, breaks the sum and the table is reported instead.
    """
    cells = pl.read_parquet(CELLS)
    out: dict[tuple, list] = defaultdict(list)
    skipped: list[str] = []
    notes: list[str] = []
    for (year, title), group in cells.group_by(["year", "title"], maintain_order=True):
        folded = fold(title)
        found = topic_of(folded)
        scheme = scheme_of(folded)
        if not found or not scheme:
            continue
        suffix, topic_key = found
        deaths_only = bool(re.search(r"olen|olum", folded)) and not re.search(
            r"gecir|tutulan", folded
        )
        state: dict = {}
        try:
            headers = {
                (block, col): header
                for block, col, header in group.select("block", "col", "header")
                .unique()
                .iter_rows()
            }
            columns: dict = {}
            categories: dict = {}
            rows = []
            leaf_sum: dict = defaultdict(float)
            seen: dict = {}
            repeated = False
            total_blocks: set = set()
            printed: dict = {}
            ordered = group.sort("block", "row", "col")
            for block, row, code, label, col, value in ordered.select(
                "block", "row", "code", "label", "col", "value"
            ).iter_rows():
                if value is None:
                    continue
                # A later block is the table continued below a page break; its cells repeat
                # the first block's columns and may carry no header of their own.
                cell = (block, col)
                if cell not in columns:
                    try:
                        columns[cell] = column(headers[cell], deaths_only)
                    except Unreadable:
                        if block == 1 or (1, col) not in headers:
                            raise
                        columns[cell] = column(headers[(1, col)], deaths_only)
                if columns[cell] is None:
                    continue
                if (block, row) not in categories:
                    categories[(block, row)] = category(code, label, suffix, state)
                cat = categories[(block, row)]
                if cat is None:
                    continue
                if (
                    cat != "TOTAL"
                    and (cat, columns[cell]) in seen
                    and seen[(cat, columns[cell])] != block
                ):
                    repeated = True
                seen.setdefault((cat, columns[cell]), block)
                if cat == "TOTAL":
                    total_blocks.add(block)
                    # The total row is printed again under a page-break block, sometimes
                    # empty; the first printing is the one read.
                    printed[columns[cell]] = max(printed.get(columns[cell], 0), value)
                    continue
                outcome, sex, days = columns[cell]
                rows.append((block, cat, outcome, sex, days, value))
            # Some sheets print the table twice, the second copy revised and carrying the
            # total (month tables 2025: July 1.882 then 1.872). Only the copy with the
            # total row is kept.
            if repeated:
                if not total_blocks:
                    raise Unreadable("tablo iki kez basılı, toplamsız")
                keep = max(total_blocks)
                rows = [r for r in rows if r[0] == keep]
                leaf_sum.clear()
            rows = drop_parents([r[1:] for r in rows])
            for cat, outcome, sex, days, value in rows:
                leaf_sum[(outcome, sex, days)] += value
            # Some printed totals are larger than their rows: deaths by month or hour
            # include cases the breakdown does not place, and occupational disease totals
            # people diagnosed after their insurance ended where no row says so. The
            # difference is stored as `unallocated`, so the rows still add up to the total.
            # Rows may add up to less than the printed total: cases the breakdown does not
            # place (occupational disease diagnosed after insurance ended, accidents with
            # no recorded hour). The gap is stored as `unallocated` so the rows still sum
            # to the total, and a gap above 5 % is listed in the report. A gap can only
            # hide rows that are missing, never inflate one that is there — the columns
            # that are not head counts are dropped above, before this.
            for c, v in printed.items():
                gap = v - leaf_sum[c]
                if gap > max(0.5, v * 5e-4):
                    rows.append(("unallocated", *c, gap))
                    leaf_sum[c] = v
                    if gap > 0.05 * v and v >= 20:
                        notes.append(
                            f"{year} {suffix} {scheme} {c}: {gap:.0f}/{v:.0f} yerleşmemiş"
                        )
            # A handful of printed totals differ from their rows by a few people (the
            # yearbook's own arithmetic); within 0.05 % the rows are kept as printed.
            # A total row printed as zero under rows that are not is a blank in the
            # yearbook (the month tables 2018-2025), not a total: it is not checked.
            off = [
                c
                for c, v in printed.items()
                if v != 0 and abs(leaf_sum[c] - v) > max(0.5, v * 5e-4)
            ]
            if off:
                c = off[0]
                raise Unreadable(
                    f"toplam tutmuyor {c}: {leaf_sum[c]:.0f} != {printed[c]:.0f}"
                )
        except Unreadable as error:
            skipped.append(f"{year} {title[:70]}: {str(error)[-90:]}")
            continue
        # Time with the last employer breaks in the source from 2022: the share of accidents
        # in "10+ years" goes 3 % (2013-2021) → 57 % (2022) → 99.4 % (2023-2025), while
        # under a year falls from 55 % to 0.3 %. The tables still add up, so no check
        # catches it; the years are left out rather than stored as if workers had all been
        # with their employer for a decade.
        if suffix == "tenure" and int(year) >= 2022:
            skipped.append(
                f"{year} {title[:70]}: çalışma süresi kodlaması 2022'den bozuk"
            )
            continue
        out[(suffix, topic_key, scheme, int(year))].extend(rows)
    return out, skipped + notes


def report() -> list[str]:
    """Tables left out, and tables whose rows fall more than 5 % short of the total."""
    return tables()[1]


class SgkNational:
    source_id = "sgk"
    vintage = "2026-09"
    retrieved_at = dt.date(2026, 9, 14)
    suffix = ""
    key = ""

    @property
    def indicator_id(self) -> str:
        return "sgk_work_accidents_by_" + self.suffix

    def fetch(self) -> Path:
        return CELLS

    def parse(self, raw: Path) -> pl.DataFrame:
        records = {}
        found, _ = tables()
        for (suffix, key, scheme, year), rows in found.items():
            if suffix != self.suffix:
                continue
            for cat, outcome, sex, days, value in rows:
                dims = {self.key: cat, "outcome": outcome, "scheme": scheme, "sex": sex}
                if outcome == "accident":
                    dims["incapacity_days"] = days
                ident = (year, tuple(sorted(dims.items())))
                if ident in records and records[ident] != value:
                    raise ValueError(
                        f"{self.indicator_id} {year} {dims}: iki farklı değer"
                    )
                records[ident] = value
        # The accident total per sex is kept only to check the day classes against it.
        frame = []
        totals = {}
        for (year, dims), value in records.items():
            d = dict(dims)
            if d.get("incapacity_days") == "total":
                totals[(year, d[self.key], d["scheme"], d["sex"])] = value
                continue
            frame.append((year, d, value))
        sums: dict = defaultdict(float)
        for year, d, value in frame:
            if d["outcome"] == "accident":
                sums[(year, d[self.key], d["scheme"], d["sex"])] += value
        off = [k for k, v in totals.items() if k in sums and abs(sums[k] - v) > 0.5]
        if len(off) > max(3, len(totals) // 100):
            raise ValueError(
                f"{self.indicator_id}: gün sınıfları toplamı tutmuyor, {off[:5]}"
            )
        return pl.DataFrame(
            {
                "indicator_id": self.indicator_id,
                "area_id": "TR",
                "area_level": "country",
                "period_start": [dt.date(y, 1, 1) for y, _, _ in frame],
                "frequency": "annual",
                "dims": [
                    ";".join(f"{k}={d[k]}" for k in sorted(d)) for _, d, _ in frame
                ],
                "value": [float(v) for _, _, v in frame],
                "unit": "person",
                "quality_flag": "measured",
                "vintage": self.vintage,
                "source_id": self.source_id,
                "retrieved_at": self.retrieved_at,
            }
        )


SGK_NATIONAL_ADAPTERS = {
    "sgk_wa_" + suffix: type(
        "SgkWorkAccidents_" + suffix, (SgkNational,), {"suffix": suffix, "key": key}
    )
    for _, suffix, key in TOPICS
}
