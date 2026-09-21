"""Show how far the running pulls have got, as a bar each.

Counts files rather than parsing logs: a pull is done when its file exists, which is the
same thing the fetchers use to decide what to skip. Safe to run at any time.

Run:  uv run python scripts/cekim_durumu.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
YEARS = 19
PROVINCES = 81
DISTRICTS = 973


def bar(done: int, total: int, width: int = 32) -> str:
    done = min(done, total)
    filled = round(width * done / total) if total else 0
    pct = 100 * done / total if total else 0
    return f"[{'#' * filled}{'.' * (width - filled)}] {done:>4}/{total:<4} %{pct:4.0f}"


HALK = Path("C:/veri/raw/tuik_secim/html_halk")
YEREL = [
    f"yerel_{t}_{y}"
    for t in ("bsb", "bel", "belmec", "ilgen")
    for y in ("2024", "2019", "2014", "2009", "2004", "1999", "1994", "1989")
]
VOTES = [
    "cb2023t1",
    "cb2023t2",
    "cb2018",
    "cb2014",
    "ho2017",
    "ho2010",
    "ho2007",
    "ho1988",
    "ho1987",
    "ho1982",
]


def plan_size(vote: str) -> int:
    """How many reports this vote needs, from the plan the fetcher wrote.

    Unknown until the plan exists — reported as 1 then, so an unplanned vote reads as
    empty rather than as finished.
    """
    path = Path("C:/veri/raw/tuik_secim") / f"zk_plan_{vote}.json"
    if not path.exists():
        # No plan on disk (it is deleted when a vote is re-planned): fall back to what was
        # fetched, so a finished vote does not read as one report out of one.
        return max(len(list(HALK.glob(vote + "__*.html"))) if HALK.exists() else 0, 1)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return len(data)
    if data.get("bitti"):
        return len(data.get("alanlar") or data.get("iller") or [])
    return sum(len(v) for v in data.get("ilceler", {}).values()) or 1


def count(pattern: str, where: Path) -> int:
    return len(list(where.glob(pattern))) if where.exists() else 0


def provinces(pattern: str, where: Path) -> int:
    """Provinces with at least one file, whatever year range the pieces carry.

    A province too wide for one query comes back in chunks (İstanbul: 2007-2021 and
    2022-2025), so counting files with the full range would call a finished province
    missing.
    """
    if not where.exists():
        return 0
    stems = {
        re.sub(r"-\d{4}-\d{4}\.csv$", "", path.name) for path in where.glob(pattern)
    }
    return len(stems)


ROWS = [
    *[
        # Referendums and presidential rounds. The presidential application answers per
        # province (81 reports), the referendum one per district (~970) — so the target
        # is read from each vote's own plan file rather than assumed.
        (
            "Secim: " + vote,
            len(list(HALK.glob(vote + "__*.html"))) if HALK.exists() else 0,
            plan_size(vote),
        )
        for vote in VOTES
    ],
    (
        # Local elections: four offices x eight years, one report per province.
        "Yerel secim (4 ofis x 8 yil)",
        sum(
            len(list(HALK.glob(v + "__*.html"))) if HALK.exists() else 0 for v in YEREL
        ),
        sum(plan_size(v) for v in YEREL),
    ),
    (
        "Endeksa mahalle demografisi",
        count("*.json", RAW / "endeksa" / "demography"),
        DISTRICTS,
    ),
    (
        "Cocuk nufus (ilce, yil yil)",
        count("nufus-cocuk-nufus-ilce-district-*.csv", RAW / "medas" / "basit"),
        YEARS,
    ),
    (
        # Household types start in 2014, not 2007: the measure is twelve years long.
        "Hanehalki tipleri (ilce, yil yil)",
        count("nufus-hane-tipleri-ilce-district-*.csv", RAW / "medas" / "basit"),
        12,
    ),
    (
        "Hemsehrilik (il il)",
        provinces("nufus-hemsehrilik-ilce-*.csv", RAW / "medas" / "hemsehrilik"),
        PROVINCES,
    ),
    (
        "Okuma-yazma (il il)",
        provinces("nufus-okuma-yazma-ilce-*.csv", RAW / "medas" / "egitim"),
        PROVINCES,
    ),
]

for label, done, total in ROWS:
    print(f"{label:<34} {bar(done, total)}")
