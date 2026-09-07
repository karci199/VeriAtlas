"""Show how far the running pulls have got, as a bar each.

Counts files rather than parsing logs: a pull is done when its file exists, which is the
same thing the fetchers use to decide what to skip. Safe to run at any time.

Run:  uv run python scripts/cekim_durumu.py
"""

from __future__ import annotations

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


def count(pattern: str, where: Path) -> int:
    return len(list(where.glob(pattern))) if where.exists() else 0


ROWS = [
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
        count("nufus-hemsehrilik-ilce-*-2007-2025.csv", RAW / "medas" / "hemsehrilik"),
        PROVINCES,
    ),
    (
        "Okuma-yazma (il il)",
        count("nufus-okuma-yazma-ilce-*-2008-2025.csv", RAW / "medas" / "egitim"),
        PROVINCES,
    ),
]

for label, done, total in ROWS:
    print(f"{label:<34} {bar(done, total)}")
