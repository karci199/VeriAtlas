"""Fetch district population from MEDAS, one year per run of the flow.

MEDAS states its own limit in the footer: gösterge × düzey × zaman ≤ 50000. With 973
districts that leaves room for a single year per query, so the flow is walked once per
year and the results are appended. That is also why the year is the natural chunk: each
year's district list *is* that year's administrative map, which is the observation the
validity table needs (K11).

The report page offers a CSV button. Downloading it beats reading the 33-page table:
paging a ZK grid is where the earlier attempt lost rows without noticing.

Raw files are kept per year under `raw/medas/ilce/` and never overwritten — the parse
can be fixed and replayed without going back to TÜİK.

Run:  uv run python scripts/fetch_medas_districts.py 2023 2022
      uv run python scripts/fetch_medas_districts.py --all
"""

import re
import sys
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")

from veriatlas.config import RAW, ensure_dirs

URL = "https://biruni.tuik.gov.tr/medas/?locale=tr"
OUT = RAW / "medas" / "ilce"

TOPIC = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"
MEASURE_HINT = "BBS-D"

#: ADNKS starts in 2007. The upper end is discovered from the page, not assumed.
FIRST_YEAR = 2007

#: Seconds to wait between years. MEDAS is a public service on a small budget; hammering
#: it is both rude and the fastest way to get blocked.
PAUSE = 4.0


def settle(page, note: str = "") -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    if note:
        print("   ·", note)


def click_exact(page, label: str) -> bool:
    """Click the first visible element whose whole text is this label.

    Exact matching matters: "İleri" as a substring also matches every "…bilgileri" row
    in the indicator list, and the click lands on a row instead of the button.
    """
    found = page.get_by_text(label, exact=True)
    for index in range(found.count()):
        element = found.nth(index)
        try:
            if element.is_visible() and element.is_enabled():
                element.click()
                settle(page, "tiklandi: " + label)
                return True
        except PlaywrightError as error:
            # A stale handle after a server round trip: try the next match.
            print("   atlandi:", str(error).splitlines()[0][:60])
            continue
    return False


def check_visible(page, selector: str) -> bool:
    """Tick the first *visible* match. Every tab keeps its widgets in the DOM, so a
    selector matches several and most of them are on hidden tabs."""
    boxes = page.locator(selector)
    for index in range(boxes.count()):
        box = boxes.nth(index)
        if box.is_visible():
            box.click()
            settle(page)
            return True
    return False


def tickable(page):
    """Rows that carry a tick box. The indicator tab uses them for two different things:
    the dimension names first, then the value lists those dimensions open up."""
    return page.locator(".z-listitem:has(.z-listitem-checkbox)")


def visible_rows(page) -> list[tuple[int, str]]:
    rows = tickable(page)
    return [
        (index, " ".join(rows.nth(index).inner_text().split()))
        for index in range(rows.count())
        if rows.nth(index).is_visible()
    ]


def is_ticked(page, index: int) -> bool:
    """The listbox runs in checkmark mode, where the tick *is* the selection — the
    `<i class="z-icon-check">` is in the markup either way and CSS reveals it. So no
    class on the box ever changes and the state has to come from ZK's own widget."""
    return bool(
        tickable(page)
        .nth(index)
        .evaluate("el => !!(zk.Widget.$(el) || {}).isSelected?.()")
    )


def tick(page, index: int, note: str) -> None:
    tickable(page).nth(index).locator(".z-listitem-checkbox").first.click()
    settle(page, note)


def indicator_count(page) -> int:
    """The footer's "Seçilen gösterge adedi: N". Zero means nothing was really added."""
    match = re.search(r"adedi:\s*(\d+)", page.inner_text("body")[-320:])
    return int(match.group(1)) if match else -1


def target_path(year: int, breakdown: bool):
    return OUT / (
        "nufus-ilce-" + ("kirilim-" if breakdown else "") + str(year) + ".csv"
    )


def offered_years(page) -> list[int]:
    """Years the Zaman tab lists, newest first."""
    years = []
    rows = page.locator(".z-listitem")
    for index in range(rows.count()):
        text = rows.nth(index).inner_text().strip()
        if text.isdigit() and len(text) == 4:
            years.append(int(text))
    return sorted(set(years), reverse=True)


def fetch_year(page, year: int, breakdown: bool = False) -> bool:
    """Walk the whole flow for one year and save the CSV. True if a file was written.

    With `breakdown`, sex and age group are ticked on the indicator tab. That multiplies
    the indicators by 38 (19 bands × 2 sexes): 973 × 38 = 36.974 for one year, still
    inside MEDAS's own 50.000 limit — but only one year at a time, which is why the year
    is the chunk either way.
    """
    target = target_path(year, breakdown)

    page.goto(URL, wait_until="networkidle")
    page.locator("select").first.select_option(label=TOPIC)
    settle(page)

    items = page.locator(".z-listitem")
    for index in range(items.count()):
        if MEASURE_HINT in items.nth(index).inner_text():
            items.nth(index).click()
            settle(page)
            break

    if breakdown:
        # Only the breakdown list has tick boxes, which keeps this away from the measure
        # list, where "Cinsiyet" also appears as "Cinsiyet oranı" and clicking it
        # silently changes what is being measured.
        for hint in ("Cinsiyet", "Grubu"):
            index = next((i for i, t in visible_rows(page) if hint in t), None)
            if index is None:
                print("  ", year, "kirilim satiri yok:", hint)
                return False
            tick(page, index, "kirilim: " + hint)

    click_exact(page, "Tamam")

    if breakdown:
        # Ticking the dimension names is only half of it: Tamam opens a value list per
        # dimension and the page then asks "Lütfen alt kırılım seçiniz!". Skipping this
        # is why the first breakdown run came back byte-identical to the plain total —
        # MEDAS just added the unbroken measure. One `<Hepsi>` heads each value list, and
        # ticking those beats looping over 19 age bands that scroll off screen.
        while True:
            pending = [
                index
                for index, text in visible_rows(page)
                if "Hepsi" in text and not is_ticked(page, index)
            ]
            if not pending:
                break
            # Each tick is a server round trip that renumbers the rows, so re-read the
            # list rather than walking a stale index set.
            tick(page, pending[0], "alt kirilim: <Hepsi>")

    click_exact(page, "Göstergeler Ekle") or click_exact(page, "Göstergeleri Ekle")

    count = indicator_count(page)
    print("   · gosterge adedi:", count)
    if breakdown and count < 2:
        # 19 age bands × 2 sexes = 38. Anything less means the tick did not take, and
        # the download would look like a success while carrying plain totals.
        print("  ", year, "kirilim tutmadi, atlandi")
        return False

    # Zaman
    click_exact(page, "İleri")
    year_row = page.locator(".z-listitem", has_text=str(year)).first
    if not year_row.count():
        print("  ", year, "listede yok; sunulan:", offered_years(page)[:25])
        return False
    box = year_row.locator(".z-listitem-checkbox")
    (box if box.count() else year_row).click()
    settle(page)

    # Düzey: district level, every province, every district
    click_exact(page, "İleri")
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if (
            select.is_visible()
            and "İlçe Düzeyi" in select.locator("option").all_inner_texts()
        ):
            select.select_option(label="İlçe Düzeyi")
            settle(page)
            break

    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if (
            select.is_visible()
            and "HEPSİ" in select.locator("option").all_inner_texts()
        ):
            select.select_option(label="HEPSİ")
            settle(page)
            break

    if not check_visible(page, ".z-listheader-checkable"):
        print("  ", year, "ilce listesi isaretlenemedi")
        return False

    footer = page.inner_text("body")[-260:].replace("\n", " ")
    print("   ·", " ".join(footer.split())[-90:])

    # Rapor
    if not click_exact(page, "Rapor Oluştur"):
        print("  ", year, "rapor olusturulamadi")
        return False
    page.wait_for_timeout(6000)

    # The CSV button is an image link, not a labelled button.
    with page.expect_download(timeout=180000) as download:
        page.locator(
            "img[src*='csv'], a[title*='CSV'], .z-toolbarbutton[title*='CSV']"
        ).first.click()
    download.value.save_as(str(target))

    print("  ", year, "->", target.name, target.stat().st_size, "bayt")
    return True


def main() -> None:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)

    wanted = [a for a in sys.argv[1:] if a.isdigit()]
    everything = "--all" in sys.argv
    breakdown = "--kirilim" in sys.argv

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)

        if everything:
            # Ask the page which years exist rather than assuming 2007..today: ADNKS
            # publishes late in the year, so "this year" is often not there yet.
            page.goto(URL, wait_until="networkidle")
            page.locator("select").first.select_option(label=TOPIC)
            settle(page)
            items = page.locator(".z-listitem")
            for index in range(items.count()):
                if MEASURE_HINT in items.nth(index).inner_text():
                    items.nth(index).click()
                    settle(page)
                    break
            click_exact(page, "Tamam")
            click_exact(page, "Göstergeleri Ekle")
            click_exact(page, "İleri")
            years = [y for y in offered_years(page) if y >= FIRST_YEAR]
            print("yillar:", years)
        else:
            years = [int(y) for y in wanted] or [2023]

        for year in years:
            if target_path(year, breakdown).exists():
                print("=", year, "zaten var, atlandi")
                continue
            print("=", year)
            # A tab now and then comes back half-built and the year list reads as empty.
            # It is the same request either way, so one retry is enough; the existing-file
            # check keeps a retry from downloading twice.
            for attempt in (1, 2):
                try:
                    if fetch_year(page, year, breakdown):
                        break
                except PlaywrightError as error:
                    print("   HATA:", type(error).__name__, str(error)[:160])
                if attempt == 1:
                    print("   · tekrar deneniyor")
                    time.sleep(PAUSE)
            time.sleep(PAUSE)

        browser.close()

    print("\ncikti:", OUT)


if __name__ == "__main__":
    main()
