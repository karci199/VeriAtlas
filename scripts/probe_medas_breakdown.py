"""Find out what actually ticks a breakdown on the MEDAS indicator tab.

`fetch_medas_districts.py --kirilim` produced a file byte-identical to the plain total,
so the sex / age-group boxes were never really ticked. Guessing again is cheap and
wrong; this probe reports the *state* of every tickable row before and after a click, so
the marker that says "checked" is read off the page instead of assumed.

First pass found that clicking `.z-listitem-checkbox` only *selects* the row
(`z-listitem-selected`) and leaves the tick alone, so this pass looks at the box itself:
its size, its markup, and what ZK's own widget object reports.

Nothing is downloaded. Screenshots and HTML go to `raw/medas/kirilim/`.

Run:  uv run python scripts/probe_medas_breakdown.py
"""

import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")

from veriatlas.config import RAW, ensure_dirs

URL = "https://biruni.tuik.gov.tr/medas/?locale=tr"
OUT = RAW / "medas" / "kirilim"

TOPIC = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"
MEASURE_HINT = "BBS-D"

#: MEDAS serves the page as ISO-8859-9 while declaring something else, so Turkish
#: letters arrive broken in the DOM as well. Every hint here is the ascii-safe part of
#: a label.
DIMENSION_HINTS = ("Cinsiyet", "Grubu")


def settle(page, note: str = "") -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    if note:
        print("  ·", note)


def dump(page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / (name + ".png")), full_page=True)
    (OUT / (name + ".html")).write_text(page.content(), encoding="utf-8")


def tickable(page):
    return page.locator(".z-listitem:has(.z-listitem-checkbox)")


def visible_rows(page) -> list[tuple[int, str]]:
    rows = tickable(page)
    out = []
    for index in range(rows.count()):
        row = rows.nth(index)
        if row.is_visible():
            out.append((index, " ".join(row.inner_text().split())[:24]))
    return out


def anatomy(page, index: int) -> None:
    """What the checkbox of one row is made of, and where it sits."""
    row = tickable(page).nth(index)
    box = row.locator(".z-listitem-checkbox").first
    print("   satir html:", " ".join(row.inner_html().split())[:400])
    print("   kutu kutusu:", box.bounding_box())
    print(
        "   zk durumu:",
        row.evaluate(
            """el => {
                const w = window.zk && zk.Widget && zk.Widget.$(el);
                if (!w) return 'zk widget yok';
                return {tip: w.className, checkable: w.isCheckable && w.isCheckable(),
                        selected: w.isSelected && w.isSelected()};
            }"""
        ),
    )


def main() -> None:
    ensure_dirs()

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.set_default_timeout(45000)

        page.goto(URL, wait_until="networkidle")
        page.locator("select").first.select_option(label=TOPIC)
        settle(page, "konu secildi")

        items = page.locator(".z-listitem")
        for index in range(items.count()):
            if MEASURE_HINT in items.nth(index).inner_text():
                items.nth(index).click()
                settle(page, "olcum secildi")
                break

        print("\n== gorunur isaretlenebilir satirlar ==")
        for index, text in visible_rows(page):
            print("  ", index, text)

        # The listbox runs in checkmark mode, where the tick *is* the selection: the
        # `<i class="z-icon-check">` sits in the markup either way and CSS reveals it
        # when the item is selected. So `isSelected()` is the state to trust, not a
        # class on the box.
        for hint in DIMENSION_HINTS:
            target = next((i for i, t in visible_rows(page) if hint in t), None)
            if target is None:
                print("  ", hint, "icin gorunur satir yok")
                continue
            tickable(page).nth(target).locator(".z-listitem-checkbox").first.click()
            settle(page, "isaretlendi: " + hint)
            anatomy(page, target)

        print("\n== Tamam'dan once gorunur satirlar ==")
        for index, text in visible_rows(page):
            print("  ", index, text)

        # If the value rows (Erkek / Kadın, the age bands) only show up after Tamam,
        # then *they* are what the fetcher never ticked — the dimension rows alone add
        # the plain total, which is exactly the file that came back.
        page.get_by_text("Tamam", exact=True).first.click()
        settle(page, "Tamam")

        print("\n== Tamam'dan sonra gorunur satirlar ==")
        for index, text in visible_rows(page):
            print("  ", index, text)

        # One `<Hepsi>` heads each value list. Ticking those two is what "Lütfen alt
        # kırılım seçiniz!" is asking for, and it beats ticking 16 age bands by hand —
        # the list scrolls, so a per-band loop would silently miss the ones off screen.
        while True:
            pending = [i for i, t in visible_rows(page) if "Hepsi" in t]
            done = 0
            for index in pending:
                row = tickable(page).nth(index)
                if row.evaluate("el => !!(zk.Widget.$(el) || {}).isSelected?.()"):
                    continue
                row.locator(".z-listitem-checkbox").first.click()
                settle(page, "alt kirilim: <Hepsi> #" + str(index))
                done += 1
                break
            if not done:
                break

        page.get_by_text("Göstergeleri Ekle", exact=True).first.click()
        settle(page, "Göstergeleri Ekle")

        dump(page, "02-kirilim-tiklandi")
        print("\n== sayfa alt metni ==")
        print("  ", " ".join(page.inner_text("body")[-300:].split())[-160:])

        browser.close()

    print("\ncikti:", OUT)


if __name__ == "__main__":
    main()
