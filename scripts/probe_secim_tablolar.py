"""List what the election application offers: pages, their tables, and their level boxes.

Candidate, voter and elected-candidate profiles are separate tables inside the same ZK
application the vote counts come from, so before fetching them the table names have to be
read rather than guessed — `pick` matches on the label and a wrong one silently selects
nothing.

This is a survey, not a fetch: one session per page, no reports built. Safe to run beside
a download of the same source, unlike a second crawl (docs/cekiciler.md 3).

Run:  uv run python scripts/probe_secim_tablolar.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, "scripts")

import urllib.request

from zk_client import BASE, ZK, text_of

OUT = pathlib.Path("C:/veri-ham/secim/tablolar.json")

PAGES = ["secim.zul", "halkoylama.zul", "cumhursecim.zul", "yerel.zul"]


def pages_offered() -> list[str]:
    """Every .zul the application's own index links to, plus the ones we already use."""
    try:
        html = (
            urllib.request.urlopen(BASE, timeout=60).read().decode("utf-8", "replace")
        )
    except Exception as error:  # noqa: BLE001 - the known list is enough
        print("indeks alinamadi:", str(error)[:80])
        return PAGES
    found = sorted(set(re.findall(r"([A-Za-z0-9_]+\.zul)", html)))
    return sorted(set(PAGES) | set(found))


def survey(page: str) -> dict:
    z = ZK(page, timeout=120)
    boxes = {}
    for header in ("Tablo seçimi:", "Mahalli İdareler Seçimi:"):
        try:
            _, options = z.options(header)
        except Exception as error:  # noqa: BLE001 - not every page has every box
            print("   ", header, "yok", str(error)[:60])
            continue
        if options:
            boxes[header] = list(options)
    body = text_of(z.html)
    levels = sorted(
        {m for m in re.findall(r"(Sandık|Mahalle|Köy|İlçe|İl|Bölge)\b", body)}
    )
    return {"kutular": boxes, "sayfada gecen duzeyler": levels}


def main() -> None:
    result = {}
    for page in pages_offered():
        print("==", page, flush=True)
        try:
            result[page] = survey(page)
        except Exception as error:  # noqa: BLE001 - report and carry on
            print("   HATA:", type(error).__name__, str(error)[:100])
            continue
        for header, options in result[page]["kutular"].items():
            print("  ", header)
            for option in options:
                print("     -", option)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nyazildi:", OUT)


if __name__ == "__main__":
    main()
