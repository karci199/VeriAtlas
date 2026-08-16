"""Fetch the marriage and divorce measures the province files do not carry.

Four queries, and none of them needs chunking — the scan in `raw/medas/kesif/` gave the
sizes and every one of them fits inside MEDAS's own limit of gösterge × düzey × zaman ≤
50.000:

* **İlçelere göre evlenmeler** — 973 × 1 × 12 = 11.676
* **Boşanma, erkeğin ikametgah yeri** — 973 × 1 × 12 = 11.676
* **Yaş grubuna göre ilk defa evlenen** — 81 × 11 × 25 = 22.275
* **Yaş grubu ve eğitim durumuna göre ilk defa evlenen** — 1 × 82 × 17 = 1.394

That last one is Türkiye only and the first two are district only; the levels are not a
choice we are making but what TÜİK publishes each measure at.

**The two district measures allocate differently, and that is not a detail.** Marriages
are counted where the wedding happened; divorces at district level are counted at *the
man's registered address*. Both add up to the published national totals exactly, so the
events are the same events — but within a district they answer differently shaped
questions, and dividing one by the other divides two allocation rules. They can be read
side by side and they cannot be made into a ratio.

Raw files land in `raw/medas/evlenme/` and are never overwritten.

Run:  uv run python scripts/fetch_medas_marriage.py           # hepsi
      uv run python scripts/fetch_medas_marriage.py ilce-evlenme
"""

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
    indicator_count,
    is_ticked,
    offered_years,
    settle,
    tick,
    visible_rows,
)

from veriatlas.config import RAW, ensure_dirs

OUT = RAW / "medas" / "evlenme"

MARRIAGE = "Evlenme İstatistikleri"
DIVORCE = "Boşanma İstatistikleri"

PAUSE = 5.0

#: name → (topic, the text that identifies the measure in the list, the level to pick,
#: and whether the measure's breakdowns have to be opened).
#:
#: The measure is matched on a distinctive fragment rather than the whole label: MEDAS
#: writes some of them with a trailing count and one of them differs by a single word from
#: its neighbour ("ortalama evlenme yaşı" and "ortalama ilk evlenme yaşı"), so the
#: fragment is chosen to be the part that cannot match anything else in its own list.
QUERIES = {
    "ilce-evlenme": (MARRIAGE, "İlçelere göre evlenmeler", "İlçe Düzeyi", False),
    "ilce-bosanma": (DIVORCE, "Erkeğin ikametgah yeri", "İlçe Düzeyi", False),
    "ilk-evlenme-yas": (
        MARRIAGE,
        "Yaş grubuna göre ilk defa evlenen",
        "İBBS3 (İl Düzeyi)",
        True,
    ),
    "ilk-evlenme-egitim": (
        MARRIAGE,
        "Yaş grubu ve eğitim durumuna göre ilk defa evlenen",
        "Türkiye",
        True,
    ),
}


def pick_measure(page, hint: str) -> bool:
    """Click the measure whose row contains `hint`.

    Longest match wins. "Yaş grubuna göre ilk defa evlenen sayısı" is a substring of
    "Yaş grubu ve eğitim durumuna göre…" in every way that matters to a naive `in`, and
    picking the wrong one downloads a file that looks right and is a different measure.
    """
    items = page.locator(".z-listitem")
    best, best_length = None, -1
    for index in range(items.count()):
        text = items.nth(index).inner_text().strip()
        if hint in text and len(text) > best_length and text.startswith(hint[:12]):
            best, best_length = index, len(text)
    if best is None:
        print("   ! olcu bulunamadi:", hint)
        print(
            "     sunulanlar:",
            [
                items.nth(i).inner_text().strip()[:60]
                for i in range(min(items.count(), 12))
            ],
        )
        return False
    items.nth(best).click()
    settle(page, "olcu: " + hint)
    return True


def open_breakdowns(page) -> None:
    """Tick every breakdown, then every `<Hepsi>` under it.

    Both halves are needed and the second is the one that gets forgotten: ticking the
    dimension alone makes MEDAS add the *unbroken* measure, so the download comes back
    byte-identical to the plain total and nothing says otherwise (docs/medas.md).
    """
    for index, text in visible_rows(page):
        if not is_ticked(page, index):
            tick(page, index, "kirilim: " + text[:40])

    click_exact(page, "Tamam")

    while True:
        pending = [
            index
            for index, text in visible_rows(page)
            if "Hepsi" in text and not is_ticked(page, index)
        ]
        if not pending:
            break
        # Each tick is a server round trip that renumbers the rows, so the list is read
        # again rather than walked over a stale index set.
        tick(page, pending[0], "alt kirilim: <Hepsi>")


def pick_level(page, level: str) -> bool:
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if select.is_visible() and level in select.locator("option").all_inner_texts():
            select.select_option(label=level)
            settle(page, "duzey: " + level)
            return True
    print("   ! duzey bulunamadi:", level)
    return False


def fetch(page, name: str) -> bool:
    topic, hint, level, breakdown = QUERIES[name]
    target = OUT / ("nufus-" + name + ".csv")
    if target.exists():
        print("  ", name, "zaten var, atlandi")
        return True

    page.goto(URL, wait_until="networkidle")
    settle(page)
    page.locator("select").first.select_option(label=topic)
    settle(page, "konu: " + topic)

    if not pick_measure(page, hint):
        return False

    if breakdown:
        open_breakdowns(page)
    else:
        click_exact(page, "Tamam")

    click_exact(page, "Göstergeler Ekle") or click_exact(page, "Göstergeleri Ekle")
    count = indicator_count(page)
    print("   · gosterge adedi:", count)
    if breakdown and count < 2:
        print("   ! kirilim tutmadi:", name)
        return False

    # Zaman: every year offered. These measures are small enough that the whole span fits
    # in one query, which is the reason this script has no year loop at all.
    click_exact(page, "İleri")
    years = offered_years(page)
    print("   · yillar:", min(years), "-", max(years), f"({len(years)})")
    header = page.locator(".z-listheader-checkable")
    if header.count():
        header.first.click()
        settle(page, "butun yillar")
    else:
        for year in years:
            row = page.locator(".z-listitem", has_text=str(year)).first
            box = row.locator(".z-listitem-checkbox")
            (box if box.count() else row).click()
        settle(page, "yillar tek tek")

    # Düzey
    click_exact(page, "İleri")
    if not pick_level(page, level):
        return False

    if level != "Türkiye":
        for index in range(page.locator("select").count()):
            select = page.locator("select").nth(index)
            if (
                select.is_visible()
                and "HEPSİ" in select.locator("option").all_inner_texts()
            ):
                select.select_option(label="HEPSİ")
                settle(page, "il: HEPSI")
                break

    if not check_visible(page, ".z-listheader-checkable"):
        print("   ! alan listesi isaretlenemedi:", name)
        return False

    footer = page.inner_text("body")[-260:].replace("\n", " ")
    print("   ·", " ".join(footer.split())[-100:])

    if not click_exact(page, "Rapor Oluştur"):
        print("   ! rapor olusturulamadi:", name)
        return False
    page.wait_for_timeout(8000)

    with page.expect_download(timeout=240000) as download:
        page.locator(
            "img[src*='csv'], a[title*='CSV'], .z-toolbarbutton[title*='CSV']"
        ).first.click()
    download.value.save_as(str(target))
    print("  ", name, "->", target.name, target.stat().st_size, "bayt")
    return True


def main() -> None:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)

    wanted = [a for a in sys.argv[1:] if not a.startswith("--")] or list(QUERIES)
    bilinmeyen = [a for a in wanted if a not in QUERIES]
    if bilinmeyen:
        raise SystemExit("bilinmeyen sorgu: " + ", ".join(bilinmeyen))

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        basarili = []
        for name in wanted:
            print("==", name)
            try:
                if fetch(page, name):
                    basarili.append(name)
            except (PlaywrightError, TimeoutError) as hata:
                print("   ! hata:", str(hata).splitlines()[0][:120])
            # MEDAS is a public service on a small budget; hammering it is both rude and
            # the fastest way to get blocked.
            time.sleep(PAUSE)
        browser.close()

    print("\ncikti:", OUT)
    print("basarili:", len(basarili), "/", len(wanted), "-", ", ".join(basarili))


if __name__ == "__main__":
    main()
