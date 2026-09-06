"""Neighbourhood 0-17 / 18+ counts for the years before 2013, one province per run.

fetch_medas_neighbourhoods.py stops at 2013 on the assumption that the split began with
the 2013 address registry. MEDAS offers the measure with its `18 yaş ve üzeri` breakdown
for earlier years too (checked 2026-08-23, Bursa); this asks for exactly those years and
writes `raw/medas/mahalle/nufus-mahalle-<PROVINCE>-2007_2012.csv`, leaving the plain
file — the 2013+ series the loader reads as complete — untouched.

Run:  uv run python scripts/fetch_medas_neighbourhoods_early.py BURSA
      uv run python scripts/fetch_medas_neighbourhoods_early.py --all
"""

import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

import fetch_medas_neighbourhoods as nb

FIRST, LAST = 2007, 2012


def scoped_path(province: str):
    return nb.OUT / f"nufus-mahalle-{province}-{FIRST}_{LAST}.csv"


def main(arg: str) -> None:
    nb.FIRST_YEAR = 0
    nb.target_path = scoped_path  # the fetcher writes where this points
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)
        names, years = nb.provinces_offered(page)
        early = [y for y in years if FIRST <= y <= LAST]
        print("sunulan yillar:", sorted(years), "istenen:", early)
        if not early:
            print("MEDAS bu olcumde 2013 oncesini kirilimla sunmuyor")
            return
        wanted = names if arg == "--ALL" else [arg]
        for province in wanted:
            scoped = scoped_path(province)
            if scoped.exists():
                print("=", province, "zaten var")
                continue
            if province not in names:
                print("=", province, "listede yok")
                continue
            print("=", province, flush=True)
            for attempt in (1, 2):
                try:
                    nb.fetch_province(page, province, early)
                except Exception as error:  # noqa: BLE001 — log and move on
                    print(
                        "   HATA:", type(error).__name__, str(error)[:120], flush=True
                    )
                if scoped.exists():
                    break
            print("   dosya:", scoped.exists() and scoped.stat().st_size, flush=True)
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1].upper())
