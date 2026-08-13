"""Walk the MEDAS flow step by step and report what each step offers.

MEDAS is a ZK (Java) application: ids are generated per session, the page is rebuilt on
the server after every click, and nothing is addressable by a stable CSS id. So the
handles we look for are text-based — option labels, row text, tab names — because those
are the only things that survive a new session.

Each step dumps a screenshot and the HTML to `raw/medas/probe/`, so the flow can be
studied without re-running the browser.

Run:  uv run python scripts/probe_medas.py
"""

import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")

from veriatlas.config import RAW, ensure_dirs

URL = "https://biruni.tuik.gov.tr/medas/?locale=tr"
OUT = RAW / "medas" / "probe"

TOPIC = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"
# MEDAS serves ISO-8859-9 while declaring something else, so Turkish characters arrive
# mangled and an exact-text match fails. Match on the ascii-safe part of the label.
MEASURE_HINT = "BBS-D"


def dump(page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / (name + ".png")), full_page=True)
    (OUT / (name + ".html")).write_text(page.content(), encoding="utf-8")


def rows(page) -> list[str]:
    """Visible row texts, flattened — the closest thing MEDAS has to a list API."""
    return [
        text.strip().replace("\n", " | ")
        for text in page.locator("tr, .z-listitem").all_inner_texts()
        if text.strip()
    ]


def settle(page, note: str) -> None:
    """ZK rebuilds the page on the server after every click; wait for it to come back."""
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)
    print("  ·", note)


def main() -> None:
    ensure_dirs()

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.set_default_timeout(45000)

        page.goto(URL, wait_until="networkidle")
        dump(page, "01-acilis")

        print("1) konu seciliyor:", TOPIC)
        page.locator("select").first.select_option(label=TOPIC)
        settle(page, "konu secildi")
        dump(page, "02-konu")

        print("2) olcum listesi:")
        measures = [r for r in rows(page) if r and "Ölçüm Seçiniz" not in r]
        for row in measures[:12]:
            print("   -", row[:90])

        print("3) olcum tiklaniyor, ipucu:", MEASURE_HINT)
        items = page.locator(".z-listitem")
        print("   listitem sayisi:", items.count())
        clicked = False
        for index in range(items.count()):
            text = items.nth(index).inner_text().strip()
            if MEASURE_HINT in text:
                print(f"   [{index}] eslesti:", text[:60])
                items.nth(index).click()
                settle(page, "olcum tiklandi")
                dump(page, "03-olcum")
                clicked = True
                break
        if not clicked:
            print("   BULUNAMADI. ilk 10 satir:")
            for index in range(min(10, items.count())):
                print(f"     [{index}]", items.nth(index).inner_text().strip()[:60])

        print("4) kirilim isaretleniyor")
        # ZK does not use real inputs: a "checkbox" is a span inside the list row. Only
        # the breakdown list has them, which is what keeps this search away from the
        # measure list — where "Cinsiyet" also appears, as "Cinsiyet oranı", and clicking
        # it silently changes the measurement instead of ticking a breakdown.
        tickable = page.locator(".z-listitem:has(.z-listitem-checkbox)")
        print("   isaretlenebilir satir:", tickable.count())
        for hint in ("Cinsiyet", "Grubu"):
            row = None
            for index in range(tickable.count()):
                item = tickable.nth(index)
                if hint in item.inner_text():
                    row = item
                    break
            if row is None:
                print("   bulunamadi:", hint)
                continue
            box = row.locator(".z-listitem-checkbox")
            (box if box.count() else row).click()
            settle(page, "isaretlendi: " + hint)

        dump(page, "04-kirilim")

        print("5) Tamam ve Gostergeleri Ekle")
        for label in ("Tamam", "Ekle"):
            candidates = page.get_by_text(label, exact=False)
            for index in range(candidates.count()):
                button = candidates.nth(index)
                if button.is_enabled():
                    button.click()
                    settle(page, "tiklandi: " + label)
                    break
            else:
                print("   etkin buton yok:", label)
        dump(page, "05-eklendi")

        print(
            "6) secim sayaci:",
            page.get_by_text("Se", exact=False).last.inner_text()[:90],
        )

        print("7) kirilim secenekleri (dokum):")
        checkboxes = page.locator(".z-listitem-checkbox")
        print("   kutucuk sayisi:", checkboxes.count())
        for index in range(min(checkboxes.count(), 8)):
            box = checkboxes.nth(index)
            near = box.evaluate(
                "el => (el.closest('tr, .z-listitem, td') || el.parentElement).innerText"
            )
            print(f"   kutucuk[{index}]:", (near or "").strip()[:50])
        labels = [t.strip() for t in rows(page) if len(t.strip()) < 40]
        for label in labels[:20]:
            print("   ·", label[:60])

        print("5) buton metinleri:")
        buttons = {
            t.strip().replace("\n", " ")
            for t in page.locator(
                "button, .z-button, input[type=button]"
            ).all_inner_texts()
            if t.strip()
        }
        print("  ", sorted(buttons)[:20])

        browser.close()

    print("\ncikti:", OUT)


if __name__ == "__main__":
    main()
