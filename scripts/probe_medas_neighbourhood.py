"""Walk the MEDAS flow up to the Düzey tab for the neighbourhood measure and report it.

The district fetcher knows its own flow by heart because it was probed first; this does
the same for the level below. What has to be learned here is the Düzey tab: the district
run picks "İlçe Düzeyi" and then province "HEPSİ", and 973 × 38 fits MEDAS's own 50.000
cell limit. Fifty thousand neighbourhoods cannot, so the province select has to become
the chunk — one province per query — and this prints what that select actually offers.

Run:  uv run python scripts/probe_medas_neighbourhood.py [yıl]
"""

import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")

from fetch_medas_districts import (
    URL,
    check_visible,
    click_exact,
    is_ticked,
    settle,
    visible_rows,
)

TOPIC = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"

#: "Belediye, Köy Ve Mahalle Nüfusları" — the measure the Bursa export came from. Matched
#: on an ascii-safe fragment: MEDAS serves ISO-8859-9 under a header that claims otherwise
#: and the Turkish letters arrive broken, so full-text matching does not work (medas.md).
#: Not the label the earlier export's header carried ("Belediye, Köy Ve Mahalle
#: Nüfusları") — MEDAS's own list writes it lower case, and matching the header's casing
#: found nothing at all.
MEASURE_HINT = "Belediye,"

#: "18 yaş ve üzeri" — the only breakdown this measure carries. Its two values are the
#: `18+` / `0-17` age bands the adapter stores.
BREAKDOWN_HINT = "18 ya"


def report_selects(page, note: str) -> None:
    print("\n--", note)
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if not select.is_visible():
            continue
        options = select.locator("option").all_inner_texts()
        print("  select", index, "->", len(options), "secenek:", options[:12])


def main() -> None:
    year = next((a for a in sys.argv[1:] if a.isdigit()), "2025")

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.set_default_timeout(60000)

        page.goto(URL, wait_until="networkidle")
        page.locator("select").first.select_option(label=TOPIC)
        settle(page)

        items = page.locator(".z-listitem")
        hits = [
            (i, items.nth(i).inner_text().strip())
            for i in range(items.count())
            if MEASURE_HINT in items.nth(i).inner_text()
        ]
        print("olcum adaylari:", hits[:6])
        if not hits:
            print("olcum bulunamadi")
            browser.close()
            return
        items.nth(hits[0][0]).click()
        settle(page)

        rows = visible_rows(page)
        print("kirilim satirlari:", rows[:12])
        index = next((i for i, t in rows if BREAKDOWN_HINT in t), None)
        if index is None:
            print("18 yas kirilimi yok — olcum kirilimsiz mi?")
        else:
            page.locator(".z-listitem-checkbox").nth(index).click()
            settle(page, "kirilim: 18 yas")

        click_exact(page, "Tamam")

        # The same two-step trap as the district run: ticking the dimension is half of it,
        # the value list's <Hepsi> is the other half (medas.md).
        while True:
            pending = [
                i
                for i, t in visible_rows(page)
                if "Hepsi" in t and not is_ticked(page, i)
            ]
            if not pending:
                break
            page.locator(".z-listitem-checkbox").nth(pending[0]).click()
            settle(page, "alt kirilim: <Hepsi>")

        click_exact(page, "Göstergeler Ekle") or click_exact(page, "Göstergeleri Ekle")
        print("footer:", " ".join(page.inner_text("body")[-260:].split())[-120:])

        # Zaman
        click_exact(page, "İleri")
        row = page.locator(".z-listitem", has_text=year).first
        if row.count():
            box = row.locator(".z-listitem-checkbox")
            (box if box.count() else row).click()
            settle(page, "yil: " + year)
        else:
            print("yil listede yok")

        # Düzey — the whole point of this probe.
        click_exact(page, "İleri")
        report_selects(page, "Duzey sekmesi")
        print(
            "liste basligi isaretlenebilir mi:",
            check_visible(page, ".z-listheader-checkable"),
        )
        print("footer:", " ".join(page.inner_text("body")[-400:].split())[-200:])

        # Picking a province is what fills the neighbourhood list; the count it reports is
        # how the year chunk gets sized, since MEDAS caps gösterge × düzey × zaman at
        # 50.000 and the neighbourhood count varies fivefold between provinces.
        province = next((a for a in sys.argv[1:] if not a.isdigit()), None)
        if not province:
            browser.close()
            return

        for index in range(page.locator("select").count()):
            select = page.locator("select").nth(index)
            if select.is_visible() and any(
                o.strip() == province
                for o in select.locator("option").all_inner_texts()
            ):
                select.select_option(label=province)
                settle(page, "il: " + province)
                break

        report_selects(page, "il secildikten sonra")

        # The district box only fills once a province is chosen, and it has to be answered
        # too — "TÜM İLÇELER" is what makes the province's whole neighbourhood list appear.
        for index in range(page.locator("select").count()):
            select = page.locator("select").nth(index)
            labels = [o.strip() for o in select.locator("option").all_inner_texts()]
            if select.is_visible() and any(
                l.startswith("TÜM İL") and "İLLER" not in l for l in labels
            ):
                select.select_option(
                    index=labels.index(
                        next(l for l in labels if l.startswith("TÜM İL"))
                    )
                )
                settle(page, "ilce: TUM ILCELER")
                break

        print(
            "liste basligi isaretlenebilir mi:",
            check_visible(page, ".z-listheader-checkable"),
        )
        print("liste satiri:", page.locator(".z-listitem").count())
        print("footer:", " ".join(page.inner_text("body")[-400:].split())[-220:])

        browser.close()


if __name__ == "__main__":
    main()
