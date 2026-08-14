"""Measure how big each measurement in a MEDAS topic is, before deciding to fetch it.

MEDAS caps `gösterge × düzey × zaman` at 50.000, so the cost of a dataset is decided
before a single row is downloaded: a measure with no breakdown is one query for every
year at once, and one carrying three breakdowns is a query per handful of years. Guessing
that from the measure's name does not work — "Medeni Duruma Göre Nüfus Bilgileri" is 151
indicators and "Ortanca yaş" is 2.

So this walks a topic and reports, per measure: how many indicators it becomes with every
breakdown turned on, which levels it offers, and how many years. From those three the
query count is arithmetic rather than a surprise halfway through a download.

Nothing is downloaded. This is the survey you do before the dig.

Run:  uv run python scripts/scan_medas_topic.py "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"
"""

import json
import re
import sys
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from fetch_medas_districts import (
    URL,
    click_exact,
    is_ticked,
    offered_years,
    settle,
    tick,
    visible_rows,
)

from veriatlas.config import RAW

OUT = RAW / "medas" / "kesif"

CELL_LIMIT = 50000

INDICATORS = re.compile(r"g[oö]sterge adedi:\s*(\d+)", re.IGNORECASE)

#: District is deliberately out of scope, so a level list that ends there is reported but
#: not counted towards the work.
SKIP_LEVELS = ("İlçe",)


def counted(page) -> int:
    found = INDICATORS.search(page.inner_text("body"))
    return int(found.group(1)) if found else 0


def survey(page, topic: str, index: int) -> dict:
    """One measure: its indicator count with every breakdown on, levels, and years."""
    page.goto(URL, wait_until="networkidle")
    page.locator("select").first.select_option(label=topic)
    settle(page)

    items = page.locator(".z-listitem")
    if index >= items.count():
        return {}
    name = " ".join(items.nth(index).inner_text().split())
    items.nth(index).click()
    settle(page)

    # Every breakdown this measure offers, turned on — the widest the table can get. A
    # tick is a toggle and the mandatory ones arrive already on, so ask before clicking
    # (docs/medas.md).
    breakdowns = []
    for row, text in visible_rows(page):
        breakdowns.append(text)
        if not is_ticked(page, row):
            try:
                tick(page, row, "")
            except PlaywrightError:
                pass

    click_exact(page, "Tamam")

    while True:
        pending = [
            i
            for i, text in visible_rows(page)
            if "Hepsi" in text and not is_ticked(page, i)
        ]
        if not pending:
            break
        tick(page, pending[0], "")

    click_exact(page, "Göstergeler Ekle") or click_exact(page, "Göstergeleri Ekle")
    indicators = counted(page)

    click_exact(page, "İleri")
    years = offered_years(page)
    if years:
        row = page.locator(".z-listitem", has_text=str(years[0])).first
        box = row.locator(".z-listitem-checkbox")
        (box if box.count() else row).click()
        settle(page)

    click_exact(page, "İleri")
    levels = []
    for pos in range(page.locator("select").count()):
        select = page.locator("select").nth(pos)
        if not select.is_visible():
            continue
        options = [o.strip() for o in select.locator("option").all_inner_texts()]
        # The level box is the short one; the province box has eighty-odd entries.
        if 1 <= len(options) <= 8 and "Seçiniz" not in options[:1]:
            levels = options
            break

    return {
        "measure": name,
        "breakdowns": breakdowns,
        "indicators": indicators,
        "levels": levels,
        "years": years,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    topic = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    if not topic:
        raise SystemExit("konu adi verin")

    target = OUT / (re.sub(r"[^A-Za-z0-9]+", "-", topic).strip("-").lower() + ".json")

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.set_default_timeout(60000)

        page.goto(URL, wait_until="networkidle")
        page.locator("select").first.select_option(label=topic)
        settle(page)
        total = page.locator(".z-listitem").count()
        print("olcum adedi:", total)

        found = []
        for index in range(total):
            try:
                row = survey(page, topic, index)
            except PlaywrightError as error:
                print(index, "HATA:", str(error)[:100])
                continue
            if not row.get("measure"):
                continue
            found.append(row)
            print(
                index,
                "|",
                row["measure"][:52],
                "| gosterge:",
                row["indicators"],
                "| duzey:",
                ",".join(row["levels"])[:40],
                "| yil:",
                len(row["years"]),
            )
            time.sleep(1.0)

        browser.close()

    target.write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nyazildi:", target)


if __name__ == "__main__":
    main()
