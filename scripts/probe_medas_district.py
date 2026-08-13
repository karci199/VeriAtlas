"""Continue the MEDAS flow past the indicator tab: Zaman, Düzey, Rapor Oluştur.

`probe_medas.py` gets as far as adding the measurement. This one keeps walking and
reports what each remaining tab offers, because the district question is decided there:
the Düzey tab is where "İlçe" either exists as a level or does not.

Nothing is downloaded here. It is a probe: every step dumps a screenshot and the HTML to
`raw/medas/ilce/` so the flow can be read afterwards without driving the browser again.

Run:  uv run python scripts/probe_medas_district.py
"""

import sys

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")

from veriatlas.config import RAW, ensure_dirs

URL = "https://biruni.tuik.gov.tr/medas/?locale=tr"
OUT = RAW / "medas" / "ilce"

TOPIC = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"
MEASURE_HINT = "BBS-D"


def dump(page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / (name + ".png")), full_page=True)
    (OUT / (name + ".html")).write_text(page.content(), encoding="utf-8")


def settle(page, note: str) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    print("  ·", note)


#: Anything that behaves like a button in ZK. Real <button> elements are the minority.
BUTTONS = "button, .z-button, .z-toolbarbutton, input[type=button], input[type=submit]"


def buttons(page) -> list[tuple[int, str]]:
    """Every button-ish element with its text, indexed."""
    found = page.locator(BUTTONS)
    return [
        (i, found.nth(i).inner_text().strip().replace("\n", " "))
        for i in range(found.count())
    ]


def click_button(page, want: str, note: str = "") -> bool:
    """Click a button whose *whole* label matches.

    Searching page text for "leri" matches "Bölgelerin aldığı göç bilgileri" long before
    it reaches the İleri button — the first version of this walked the flow without ever
    leaving the first tab and reported success. Match the element's full label instead,
    and only among things that are actually buttons.
    """
    # ZK's buttons are not <button> elements and carry no text of their own — the label
    # lives in a child span — so element-based matching finds only blanks. Text search
    # works, but it has to be exact: "İleri" as a substring hits every "…bilgileri" row
    # on the page, and the walk silently stays on the first tab.
    exact = page.get_by_text(want, exact=True)
    for index in range(exact.count()):
        element = exact.nth(index)
        try:
            if element.is_visible() and element.is_enabled():
                element.click()
                settle(page, "tiklandi: " + want + " " + note)
                return True
        except PlaywrightError as error:
            # A stale handle after a server round trip: try the next match.
            print("   atlandi:", str(error).splitlines()[0][:60])
            continue
    print("   etkin buton yok:", want)
    return False


def rows(page, limit: int = 40) -> list[str]:
    texts = [
        t.strip().replace("\n", " | ")
        for t in page.locator(".z-listitem, tr").all_inner_texts()
        if t.strip()
    ]
    return texts[:limit]


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

        tickable = page.locator(".z-listitem:has(.z-listitem-checkbox)")
        for hint in ("Cinsiyet", "Grubu"):
            for index in range(tickable.count()):
                item = tickable.nth(index)
                if hint in item.inner_text():
                    box = item.locator(".z-listitem-checkbox")
                    (box if box.count() else item).click()
                    settle(page, "isaretlendi: " + hint)
                    break

        print("\n== butonlar (gosterge sekmesi) ==")
        print("  ", [t for _, t in buttons(page)][:20])
        click_button(page, "Tamam")
        if not click_button(page, "Göstergeleri Ekle"):
            click_button(page, "Ekle")
        dump(page, "01-gosterge")

        print("\n== ZAMAN sekmesi ==")
        click_button(page, "İleri")
        dump(page, "02-zaman")
        for row in rows(page, 25):
            print("   ·", row[:100])

        # The Zaman tab refuses to advance with nothing ticked ("Lütfen zaman seçiniz!"),
        # and the footer states the real constraint: gösterge × düzey × zaman ≤ 50000.
        # One year is enough to find out what the Düzey tab offers.
        print("\n== ZAMAN: yil isaretleniyor ==")
        year_row = page.locator(".z-listitem", has_text="2023").first
        if year_row.count():
            box = year_row.locator(".z-listitem-checkbox")
            (box if box.count() else year_row).click()
            settle(page, "2023 isaretlendi")
        dump(page, "02b-zaman-secili")

        print("\n== DUZEY sekmesi ==")
        click_button(page, "İleri")
        dump(page, "03-duzey")
        for row in rows(page, 40):
            print("   ·", row[:100])

        print("\n== DUZEY: acilir kutular ==")
        for index in range(page.locator("select").count()):
            select = page.locator("select").nth(index)
            if not select.is_visible():
                continue
            options = select.locator("option").all_inner_texts()
            print("   select[" + str(index) + "]:", [o.strip() for o in options][:15])

        print("\n== DUZEY: Ilce secimi ==")
        for index in range(page.locator("select").count()):
            select = page.locator("select").nth(index)
            if (
                select.is_visible()
                and "İlçe Düzeyi" in select.locator("option").all_inner_texts()
            ):
                select.select_option(label="İlçe Düzeyi")
                settle(page, "duzey = Ilce")
                break
        dump(page, "04-ilce")

        # District level asks for a province first; "HEPSİ" is what makes it national.
        print("\n== DUZEY: il = HEPSI ==")
        for index in range(page.locator("select").count()):
            select = page.locator("select").nth(index)
            if (
                select.is_visible()
                and "HEPSİ" in select.locator("option").all_inner_texts()
            ):
                select.select_option(label="HEPSİ")
                settle(page, "il = HEPSI")
                break
        dump(page, "04b-il-hepsi")

        ticks = page.locator(".z-listitem:has(.z-listitem-checkbox)")
        print("   isaretlenebilir satir:", ticks.count())
        for index in range(min(8, ticks.count())):
            print("   ·", ticks.nth(index).inner_text().strip()[:60])

        # The list header row ("Düzey") carries a checkbox that ticks every district at
        # once — 973 clicks otherwise.
        print("\n== DUZEY: ilceler isaretleniyor ==")
        # Every tab keeps its listbox in the DOM, so this class matches several headers —
        # only one of them is on screen.
        boxes = page.locator(".z-listheader-checkable")
        for index in range(boxes.count()):
            box = boxes.nth(index)
            if box.is_visible():
                box.click()
                settle(page, "hepsi tiklandi")
                break
        else:
            print("   basliktaki kutu bulunamadi:", boxes.count(), "aday")

        dump(page, "04c-ilce-secili")
        print("   secim satiri:", page.inner_text("body")[-200:].replace("\n", " | "))

        print("\n== RAPOR sekmesi ==")
        click_button(page, "İleri")
        settle(page, "rapor sekmesi")
        dump(page, "05-rapor")
        print("  ", sorted({t for _, t in buttons(page) if t})[:25])
        print("   metin:", page.inner_text("body")[:300].replace("\n", " | "))

        click_button(page, "Rapor Oluştur")
        page.wait_for_timeout(6000)
        dump(page, "06-tablo")
        tables = page.locator("table")
        print("   tablo sayisi:", tables.count())
        print("   metin:", page.inner_text("body")[:600].replace("\n", " | "))

        print("\n== RAPOR ==")
        click_button(page, "İleri")
        dump(page, "05-rapor-sekmesi")
        print("  ", sorted({t for _, t in buttons(page) if t})[:25])
        print(
            "   sayfa metni (ilk 400):",
            page.inner_text("body")[:400].replace("\n", " | "),
        )

        browser.close()

    print("\ncikti:", OUT)


if __name__ == "__main__":
    main()
