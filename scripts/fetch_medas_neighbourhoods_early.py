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
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

import fetch_medas_neighbourhoods as nb

FIRST, LAST = 2007, 2012


def scoped_path(province: str, chunk=None, all_years=None):
    """Where this province's early years land — same shape as the 2013+ fetcher's.

    It stands in for `nb.target_path`, which the fetcher calls with the year chunk it is
    actually asking for, so it has to accept those arguments: taking only the province
    raised TypeError inside the fetch and every province failed with an error that looked
    like MEDAS's, not ours. A province split into chunks writes one file per range, the
    same way the 2013+ side does.
    """
    name = f"nufus-mahalle-{province.replace(' ', '_')}-{FIRST}_{LAST}"
    if chunk and all_years and len(chunk) != len(all_years):
        name += f"__{min(chunk)}-{max(chunk)}"
    return nb.OUT / (name + ".csv")


def early_covered(province: str, years) -> bool:
    """True when the province is on disk whole, or in chunks covering every early year."""
    if scoped_path(province).exists():
        return True
    have = set()
    stem = f"nufus-mahalle-{province.replace(' ', '_')}-{FIRST}_{LAST}__"
    for path in nb.OUT.glob(stem + "*.csv"):
        lo, hi = path.stem.split("__")[1].split("-")
        have |= set(range(int(lo), int(hi) + 1))
    return bool(years) and have >= set(years)


def sweep(arg: str, early: list[int], names: list[str]) -> list[str]:
    """One pass over the provinces still missing. Returns the ones still missing after it."""
    wanted = names if arg == "--ALL" else [arg]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)
        for province in wanted:
            if province not in names:
                print("=", province, "listede yok")
                continue
            if early_covered(province, early):
                continue
            print("=", province, flush=True)
            for attempt in (1, 2):
                try:
                    nb.fetch_province(page, province, early)
                except Exception as error:  # noqa: BLE001 - log and move on
                    print(
                        "   HATA:", type(error).__name__, str(error)[:120], flush=True
                    )
                if early_covered(province, early):
                    break
                if attempt == 1:
                    print("   . tekrar deneniyor", flush=True)
            path = scoped_path(province)
            print(
                "   dosya:", path.stat().st_size if path.exists() else "YOK", flush=True
            )
        browser.close()
    return [q for q in wanted if q in names and not early_covered(q, early)]


def offered(arg: str, tries: int = 4) -> tuple[list[str], list[int]]:
    """Ask MEDAS which provinces and which of 2007-2012 it serves for this measure.

    Retried, because it is one walk through the flow like any other and fails the same
    way: a click that timed out here used to raise through main and end the whole run
    before a single province was tried.
    """
    for attempt in range(1, tries + 1):
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                page = browser.new_page(
                    viewport={"width": 1600, "height": 1000}, accept_downloads=True
                )
                page.set_default_timeout(60000)
                names, years = nb.provinces_offered(page)
                browser.close()
            if names:
                early = sorted(y for y in years if FIRST <= y <= LAST)
                print("sunulan yillar:", sorted(years), "istenen:", early)
                return names, early
            print(f"   il listesi bos geldi ({attempt}/{tries})", flush=True)
        except Exception as error:  # noqa: BLE001 - retry, then give up loudly
            print(
                f"   HATA ({attempt}/{tries}):", type(error).__name__, str(error)[:100]
            )
        time.sleep(10 * attempt)
    return [], []


def main(arg: str, rounds: int = 12) -> None:
    """Sweep until a pass gains nothing.

    Same shape as the 2013+ fetcher, for the same reason: a province fails on a tick that
    did not land in time and succeeds on a later walk, so a single pass ends quietly short
    and the run looks finished. Each pass opens its own browser; what is still missing at
    the end is named.
    """
    nb.FIRST_YEAR = 0
    nb.target_path = scoped_path  # the fetcher writes where this points

    names, early = offered(arg)
    if not names:
        # An empty province list used to report success: nothing was missing because
        # nothing was asked for. Silence like that is what let this measure sit at zero
        # files while the log said "butun iller tamam".
        raise SystemExit("il listesi bos geldi — MEDAS cevap vermedi, bitmis sayilmaz")
    if not early:
        print("MEDAS bu olcumde 2013 oncesini kirilimla sunmuyor")
        return

    missing = None
    for turn in range(1, rounds + 1):
        left = sweep(arg, early, names)
        print(f"--- gecis {turn} bitti: {len(left)} il eksik ---", flush=True)
        if not left:
            print("butun iller tamam")
            return
        if missing is not None and len(left) >= missing:
            print(f"gecis kazanc getirmedi, {len(left)} il eksik:", ", ".join(left))
            return
        missing = len(left)
    print("hala eksik var")


if __name__ == "__main__":
    main(sys.argv[1].upper())
