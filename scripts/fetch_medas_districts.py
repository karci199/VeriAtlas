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
    the cells by 32 (16 bands × 2 sexes): 973 × 32 = 31.136 for one year, still inside
    MEDAS's own 50.000 limit — but only one year at a time, which is why the year is the
    chunk either way.
    """
    target = OUT / ("nufus-ilce-" + ("kirilim-" if breakdown else "") + str(year) + ".csv")
    if target.exists():
        print("  ", year, "zaten var, atlandi")
        return False

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
        # A ZK "checkbox" is a span inside the row, and only the breakdown list has them —
        # which keeps this away from the measure list, where "Cinsiyet" also appears as
        # "Cinsiyet oranı" and clicking it silently changes what is being measured.
        tickable = page.locator(".z-listitem:has(.z-listitem-checkbox)")
        for hint in ("Cinsiyet", "Grubu"):
            for index in range(tickable.count()):
                item = tickable.nth(index)
                if hint in item.inner_text():
                    box = item.locator(".z-listitem-checkbox")
                    (box if box.count() else item).click()
                    settle(page, "kirilim: " + hint)
                    break

    click_exact(page, "Tamam")
    click_exact(page, "Göstergeler Ekle") or click_exact(page, "Göstergeleri Ekle")

    # Zaman
    click_exact(page, "İleri")
    year_row = page.locator(".z-listitem", has_text=str(year)).first
    if not year_row.count():
        print("  ", year, "listede yok")
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
            print("=", year)
            try:
                fetch_year(page, year, breakdown)
            except PlaywrightError as error:
                print("   HATA:", type(error).__name__, str(error)[:160])
            time.sleep(PAUSE)

        browser.close()

    print("\ncikti:", OUT)


if __name__ == "__main__":
    main()
