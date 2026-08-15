"""Fetch births and deaths at district level from MEDAS.

These are not the province measures at a finer level — they are *separate measures*, and
MEDAS gives each of them exactly one level. `İlçelere göre doğum sayısı` and
`İlçelere göre ölüm sayısı (İkametgah yeri)` offer İlçe Düzeyi and nothing else, while the
province ones (`İkametgah yerine göre doğum/ölüm sayısı`, already loaded — K19) offer
Türkiye through İBBS3 and no district. So this is a second download, not a re-run of the
first with another box ticked.

Two consequences worth stating, because both are properties of the source rather than
choices made here:

* **Residence, not occurrence.** The death measure says so in its own name; the birth one
  is the residence series by construction — the occurrence series (`Olay yerine göre`) is
  province-only and stops at 2008. This is the same rule the province fetch follows: a
  district with a hospital in it records events belonging to the districts around it, and
  only residence belongs next to a population count.
* **Both measures come to 2 indicators, split by sex** — and the two disagree about
  whether that tick arrives on. Deaths mark it mandatory and hand it over already ticked;
  births leave it off and refuse `Tamam` until it is set. Nothing is summed here either
  way: the split reaches `raw/` whole and what to keep of it is the adapter's decision
  (K8, and see `adapters/tuik_district_vital` — deaths keep the split, births do not).

Years differ and the difference is the source's: deaths run 2009-2025, births only
**2014-2025**. Births before 2014 are not published at district level.

Size: 2 indicators × ~975 districts × 17 years = 33.150 cells, inside MEDAS's 50.000
limit, so each measure is a single query for its whole span. If the page reports more than
the limit the run says so and slices by year rather than truncating.

Raw files land in `raw/medas/ilce-vital/` and are never overwritten.

Run:  uv run python scripts/fetch_medas_vital_districts.py
      uv run python scripts/fetch_medas_vital_districts.py dogum
      uv run python scripts/fetch_medas_vital_districts.py olum --yil=2025,2024
"""

import re
import sys
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from fetch_medas_districts import (
    URL,
    check_visible,
    click_exact,
    is_ticked,
    offered_years,
    settle,
    tick,
    visible_rows,
)
from fetch_medas_simple import BIRTHS, CELL_LIMIT, DEATHS, INDICATORS, PICKED, counted

from veriatlas.config import RAW, ensure_dirs

OUT = RAW / "medas" / "ilce-vital"

PAUSE = 4.0

#: Short name for the file, topic, and an ascii-safe fragment of the measure's label —
#: MEDAS serves ISO-8859-9 under a header that says otherwise, so Turkish letters cannot
#: be matched (docs/medas.md). "elere g" is the safe middle of "İlçelere göre".
MEASURES = [
    ("dogum", BIRTHS, "elere g"),
    ("olum", DEATHS, "elere g"),
]


def target_path(name: str, part: int = 0):
    piece = "-" + str(part) if part else ""
    return OUT / ("ilce-" + name + piece + ".csv")


def pick_measure(page, topic: str, hint: str) -> int:
    """Select the topic and the district measure; return the indicator count.

    The measure is found by its label rather than by position, and the label is matched on
    the fragment that survives the encoding. Both topics hold several measures whose names
    share most of their words, so the row is checked to be the district one — it is the
    only one in its topic starting with İlçelere.
    """
    page.goto(URL, wait_until="networkidle")
    page.locator("select").first.select_option(label=topic)
    settle(page)

    items = page.locator(".z-listitem")
    index = next(
        (i for i in range(items.count()) if hint in items.nth(i).inner_text()), None
    )
    if index is None:
        print("   olcum bulunamadi:", hint)
        return 0
    print("   olcum:", " ".join(items.nth(index).inner_text().split()))
    items.nth(index).click()
    settle(page)

    # The two measures disagree about this and neither says so out loud. Deaths mark
    # `Ölenin cinsiyeti` mandatory, so it arrives already ticked; births leave `Cinsiyet`
    # off. A tick is a toggle, so clicking blind clears the one and sets the other — and
    # the run where it was cleared came back as 1 indicator with no error anywhere. Ask
    # first, tick only what is off.
    for row, text in visible_rows(page):
        if "insiyet" in text and not is_ticked(page, row):
            tick(page, row, "kirilim: " + text)

    click_exact(page, "Tamam")

    # Tamam opens a value list per dimension; the `<Hepsi>` heading each one is what
    # actually selects it. One tick at a time, re-reading the list — every tick is a
    # server round trip that renumbers the rows.
    while True:
        pending = [
            i
            for i, text in visible_rows(page)
            if "Hepsi" in text and not is_ticked(page, i)
        ]
        if not pending:
            break
        tick(page, pending[0], "alt kirilim: <Hepsi>")

    click_exact(page, "Göstergeler Ekle") or click_exact(page, "Göstergeleri Ekle")
    return counted(page, INDICATORS)


def pick_years(page, only: list | None) -> list[int]:
    """Tick the years offered, or the subset asked for. Returns what was actually ticked.

    A year is scrolled to before it is clicked and the ones that slip are retried once —
    ticking re-renders the list under the handle being held, and a click on a row below
    the fold waits the full minute and then takes the whole measure down with it.
    """
    years = offered_years(page)
    if only is not None:
        years = [y for y in years if y in only]
    missed = []
    for year in years:
        if not tick_year(page, year):
            missed.append(year)
    for year in list(missed):
        if tick_year(page, year):
            missed.remove(year)
    if missed:
        print("   · secilemeyen yil:", ", ".join(str(y) for y in missed))
    return [y for y in years if y not in missed]


def tick_year(page, year: int) -> bool:
    row = page.locator(
        ".z-listitem", has_text=re.compile(r"^\s*" + str(year) + r"\s*$")
    ).first
    if not row.count():
        return False
    box = row.locator(".z-listitem-checkbox")
    handle = box if box.count() else row
    try:
        handle.scroll_into_view_if_needed(timeout=5000)
        handle.click(timeout=10000)
    except PlaywrightError:
        return False
    settle(page)
    return True


def pick_districts(page) -> int:
    """İlçe Düzeyi, every province, every district. Returns the area count MEDAS reports."""
    for label in ("İlçe Düzeyi", "HEPSİ"):
        for index in range(page.locator("select").count()):
            select = page.locator("select").nth(index)
            if (
                select.is_visible()
                and label in select.locator("option").all_inner_texts()
            ):
                select.select_option(label=label)
                settle(page)
                break

    # The header tick does not always take on the first click, and once it does the area
    # counter *climbs* while the list fills — 33, then 39, then 82 on the province lists.
    # Reading it early is how an earlier download was sliced into pieces a third too big.
    # So: read until three readings agree.
    for _ in range(3):
        if not check_visible(page, ".z-listheader-checkable"):
            print("   ilce listesi isaretlenemedi")
            return 0
        seen = 0
        same = 0
        for _ in range(20):
            now = counted(page, PICKED)
            same = same + 1 if now == seen else 0
            seen = max(seen, now)
            if seen and same >= 2:
                break
            settle(page)
        if seen:
            return seen
    return 0


def fetch(page, name: str, topic: str, hint: str, only=None, part: int = 0):
    target = target_path(name, part)

    count = pick_measure(page, topic, hint)
    print("   gosterge:", count)
    if count < 2:
        # Both measures are 2 (male, female). One means the mandatory sex tick was
        # cleared on the way past and the file would arrive looking complete.
        print("   kirilim tutmadi")
        return False

    click_exact(page, "İleri")
    years = pick_years(page, only)
    if not years:
        print("   yil secilemedi")
        return False

    click_exact(page, "İleri")
    areas = pick_districts(page)
    if not areas:
        return False

    cells = count * areas * len(years)
    print(
        "   · gosterge:",
        count,
        "· alan:",
        areas,
        "· yil:",
        len(years),
        "· hucre:",
        cells,
    )
    if cells > CELL_LIMIT:
        print("   · limit asildi:", cells, "hucre")
        return (count, areas, years)

    if not click_exact(page, "Rapor Oluştur"):
        print("   rapor olusturulamadi")
        return False

    csv_button = page.locator(
        "img[src*='csv'], a[title*='CSV'], .z-toolbarbutton[title*='CSV']"
    ).first
    # Waiting a fixed spell is what lost thirteen provinces in the neighbourhood fetch:
    # a small query is ready in seconds and a big one takes minutes.
    patience = min(600000, 120000 + cells * 4)
    try:
        csv_button.wait_for(state="visible", timeout=patience)
    except PlaywrightError:
        print("   rapor", round(patience / 1000), "sn'de hazir olmadi")
        return False

    with page.expect_download(timeout=patience) as download:
        csv_button.click()
    download.value.save_as(str(target))

    print("  ", target.name, target.stat().st_size, "bayt")
    return True


def main() -> None:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)

    asked = [a for a in sys.argv[1:] if not a.startswith("--")]
    wanted = [m for m in MEASURES if not asked or m[0] in asked]

    picked = next(
        (a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--yil=")), ""
    )
    years_wanted = [int(y) for y in picked.replace(" ", "").split(",") if y] or None

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)

        for name, topic, hint in wanted:
            if target_path(name).exists():
                print("=", name, "zaten var, atlandi")
                continue
            print("=", name)
            outcome = None
            for attempt in (1, 2):
                try:
                    outcome = fetch(page, name, topic, hint, years_wanted)
                    if outcome:
                        break
                except PlaywrightError as error:
                    print("   HATA:", type(error).__name__, str(error)[:120])
                if attempt == 1:
                    print("   · tekrar deneniyor")
                    time.sleep(PAUSE)
            time.sleep(PAUSE)

            # Over the limit: come back a year at a time. Each year is its own file,
            # numbered by the year rather than by arrival order, so a part says what it
            # holds.
            if not isinstance(outcome, tuple):
                continue
            _, _, years = outcome
            for year in years:
                if target_path(name, year).exists():
                    continue
                print("=", name, year)
                for attempt in (1, 2):
                    try:
                        if fetch(page, name, topic, hint, [year], year) is True:
                            break
                    except PlaywrightError as error:
                        print("   HATA:", type(error).__name__, str(error)[:120])
                    if attempt == 1:
                        time.sleep(PAUSE)
                time.sleep(PAUSE)

        browser.close()

    print("\ncikti:", OUT)


if __name__ == "__main__":
    main()
