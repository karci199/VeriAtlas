"""Fetch total population for every settlement — village, town and neighbourhood.

The neighbourhood fetcher asks for the `18 yaş ve üzeri` breakdown, and MEDAS
answers that breakdown only for neighbourhoods: tick it and `Köy` and `Belediye`
drop out of the level box (docs/medas.md). So villages have no age split, and
outside the 30 metropolitan provinces — where 6360 left no villages at all —
that is most of the country's settlements.

What villages *do* have is a total. This script asks the same measure with **no**
breakdown, which puts `Köy` and `Belediye` back in the level box and costs one
indicator per area instead of two, so the cell budget stretches twice as far.

Together with the neighbourhood files this gives every settlement a total, and
the ones inside a municipality an 18+/0-17 split as well.

Raw files land in `raw/medas/yerlesim/` as `nufus-<level>-<province>.csv` and are
never overwritten.

Run:  uv run python scripts/fetch_medas_settlement_totals.py --level Köy --all
      uv run python scripts/fetch_medas_settlement_totals.py --level Belediye VAN
"""

import sys
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from fetch_medas_districts import URL, check_visible, click_exact, settle
from fetch_medas_neighbourhoods import (
    CELL_LIMIT,
    INDICATORS,
    MEASURE_HINT,
    PAUSE,
    TOPIC,
    choose,
    picked_levels,
    provinces_offered,
)

from veriatlas.config import RAW, ensure_dirs

OUT = RAW / "medas" / "yerlesim"

#: One indicator now, not two: the measure carries no breakdown here.
PER_AREA = 1

CSV_BUTTON = "img[src*='csv'], a[title*='CSV'], .z-toolbarbutton[title*='CSV']"


def has_rows(path) -> bool:
    """Whether an export carries data and not just MEDAS's preamble.

    Every export opens with five header lines; a data line starts with the year
    or continues a year block with the area name in brackets. An export with none
    of those is the empty pane's CSV, which downloads perfectly happily.
    """
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return any("(" in line and ")-" in line for line in text.splitlines())


def download_csv(page, target, patience: int) -> bool:
    """Click the report's CSV button and save what comes back, if it has data.

    Two things bite here, and neither announces itself:

    A plain click is right when it works, and for the neighbourhood measure it
    does. At the `Köy` level it never does: once the report is built ZK leaves a
    `.z-modal-mask` over the page, `elementFromPoint` on the button's own centre
    returns the mask, and Playwright's actionability check waits out its timeout
    rather than clicking what a user could not have clicked. `force=True` does
    not help — the click lands on the mask and no download follows. Dispatching
    the event straight at the button does work.

    And the page offers *two* CSV buttons. One of them belongs to an empty pane
    and downloads a thirty-byte file of headers, which looks like success at
    every level except the only one that matters. So each candidate is saved to a
    temporary file and kept only if it actually carries rows.
    """
    staging = target.with_suffix(".part")
    for how in ("click", "dispatch"):
        for index in range(page.locator(CSV_BUTTON).count()):
            button = page.locator(CSV_BUTTON).nth(index)
            if not button.is_visible():
                continue
            try:
                with page.expect_download(timeout=patience) as download:
                    if how == "click":
                        button.click(timeout=5000)
                    else:
                        button.dispatch_event("click")
                download.value.save_as(str(staging))
            except PlaywrightError:
                continue
            if has_rows(staging):
                staging.replace(target)
                return True
            print(f"   [{index}/{how}] bos dosya, sonraki aday")
            staging.unlink(missing_ok=True)
    print("   CSV indirilemedi")
    return False


def target_path(level: str, province: str):
    safe = level.replace("ö", "o").replace("Ö", "O").lower()
    return OUT / f"nufus-{safe}-{province.replace(' ', '_')}.csv"


def scoped_path(level: str, province: str, years: list[int]):
    """Name for a subset of years. A partial series must not wear the plain name,
    which the loader reads as 'every published year'."""
    return OUT / f"{target_path(level, province).stem}-{years[0]}_{years[-1]}.csv"


def fetch(page, level: str, province: str, years: list[int]) -> int:
    """Walk the flow once. Returns 0 on success, or the area count when the
    request is too large for the years asked."""
    page.goto(URL, wait_until="networkidle")
    page.locator("select").first.select_option(label=TOPIC)
    settle(page)

    items = page.locator(".z-listitem")
    index = next(
        (i for i in range(items.count()) if MEASURE_HINT in items.nth(i).inner_text()),
        None,
    )
    if index is None:
        print("   olcum bulunamadi")
        return 0
    items.nth(index).click()
    settle(page)

    # No breakdown is ticked at all — that is the whole point, and it is what
    # keeps Köy and Belediye in the level box further down.
    click_exact(page, "Tamam")
    click_exact(page, "Göstergeler Ekle") or click_exact(page, "Göstergeleri Ekle")

    found = INDICATORS.search(page.inner_text("body"))
    count = int(found.group(1)) if found else 0
    if count != PER_AREA:
        print("   gosterge adedi", count, "- kirilimsiz olmasi gerekiyordu, atlandi")
        return 0

    click_exact(page, "İleri")
    for year in years:
        row = page.locator(".z-listitem", has_text=str(year)).first
        if not row.count():
            continue
        box = row.locator(".z-listitem-checkbox")
        (box if box.count() else row).click()
        settle(page)

    click_exact(page, "İleri")
    if not choose(page, lambda label: label == level):
        print("   duzey kutuda yok:", level)
        return 0
    if not choose(page, lambda label: label == province):
        print("   il kutuda yok:", province)
        return 0
    if not choose(page, lambda label: label.startswith("TÜM İLÇ")):
        print("   ilce kutusu dolmadi")
        return 0

    if not check_visible(page, ".z-listheader-checkable"):
        print("   liste isaretlenemedi")
        return 0

    # The tick-all is a server round trip and the footer's count is what it
    # updates. On a long list — Sivas offers about twelve hundred villages —
    # settle()'s fixed wait ends before the count arrives and the province reads
    # as empty, which is indistinguishable from a province that genuinely has no
    # villages. So the count is waited for rather than sampled once.
    areas = picked_levels(page)
    for _ in range(10):
        if areas:
            break
        page.wait_for_timeout(2000)
        areas = picked_levels(page)
    print("   ·", level, "adedi:", areas)
    if not areas:
        print("   bu ilde bu duzeyde yerlesim yok")
        return 0
    if PER_AREA * areas * len(years) > CELL_LIMIT:
        return areas

    if not click_exact(page, "Rapor Oluştur"):
        print("   rapor olusturulamadi")
        return 0

    csv_button = page.locator(CSV_BUTTON).first
    patience = min(600000, 120000 + areas * 300)
    try:
        csv_button.wait_for(state="visible", timeout=patience)
    except PlaywrightError:
        print("   rapor", round(patience / 1000), "sn'de hazir olmadi")
        return 0

    target = target_path(level, province)
    if not download_csv(page, target, patience):
        return 0
    print("  ", province, "->", target.name, target.stat().st_size, "bayt")
    return 0


def main() -> None:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)

    argv = sys.argv[1:]
    level = "Köy"
    if "--level" in argv:
        level = argv[argv.index("--level") + 1]
    wanted_years: list[int] = []
    if "--years" in argv:
        wanted_years = [int(y) for y in argv[argv.index("--years") + 1].split(",")]
    consumed = {level, ",".join(str(y) for y in wanted_years)}
    asked = [a for a in argv if not a.startswith("--") and a not in consumed]
    everything = "--all" in argv

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)

        names, years = provinces_offered(page)
        if wanted_years:
            missing = [y for y in wanted_years if y not in years]
            if missing:
                print("MEDAS bu yillari sunmuyor:", missing)
                browser.close()
                return
            years = wanted_years
        print("duzey:", level, " yillar:", years, " il adedi:", len(names))

        wanted = names if everything else [a.upper() for a in asked]
        for province in wanted:
            if province not in names:
                print("=", province, "listede yok")
                continue
            done = target_path(level, province)
            scoped = scoped_path(level, province, years)
            if done.exists() or (wanted_years and scoped.exists()):
                print("=", province, "zaten var, atlandi")
                continue
            print("=", province)

            chunk = years
            while chunk:
                areas = 0
                for attempt in (1, 2):
                    try:
                        areas = fetch(page, level, province, chunk)
                    except PlaywrightError as error:
                        print("   HATA:", type(error).__name__, str(error)[:160])
                    if target_path(level, province).exists() or areas:
                        break
                    if attempt == 1:
                        print("   · tekrar deneniyor")
                        time.sleep(PAUSE)
                if not areas:
                    # A subset of years lands under the plain name, which claims the
                    # whole series. Renamed before anything reads it.
                    if wanted_years and done.exists():
                        done.rename(scoped)
                        print("   ->", scoped.name)
                    break
                # Too large even at one indicator per area: halve the years and
                # say so rather than writing a file that silently covers less.
                print(
                    "   BOLME GEREKIYOR:", province, areas, "alan,", len(chunk), "yil"
                )
                break
            time.sleep(PAUSE)

        browser.close()

    print("\ncikti:", OUT)


if __name__ == "__main__":
    main()
