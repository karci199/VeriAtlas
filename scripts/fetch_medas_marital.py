"""Fetch marital status by sex and age group from MEDAS, provinces and country.

The measure is "Medeni Duruma Göre Nüfus Bilgileri (15 Yaş üstü)" and it carries three
breakdowns at once: medeni durum (5 values), cinsiyet (2) and yaş grubu (17 bands from
15-19 up). That is 170 indicators — the widest thing we have pulled — and MEDAS still
caps gösterge × düzey × zaman at 50.000. With 81 provinces that leaves room for three
years per query, so the **year chunk** is what this script sizes, and it sizes it from
the page's own counters rather than from arithmetic done here.

Medeni durum is marked red in MEDAS's breakdown list, meaning the measure refuses to be
added without it. The other two are ours to ask for.

Age starts at 15, not 0: marital status is only published for the population old enough
to have one. That is a property of the source and the band list says so — there is no
0-14 to be missing.

Raw files land in `raw/medas/medeni/` per year chunk and are never overwritten.

Run:  uv run python scripts/fetch_medas_marital.py 2025 2024
      uv run python scripts/fetch_medas_marital.py --all
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

from veriatlas.config import RAW, ensure_dirs

OUT = RAW / "medas" / "medeni"

TOPIC = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"

#: Ascii-safe fragment of "Medeni Duruma Göre Nüfus Bilgileri (15 Yaş üstü)". MEDAS serves
#: ISO-8859-9 under a header that claims otherwise, so the Turkish letters cannot be
#: matched on (docs/medas.md).
MEASURE_HINT = "Medeni Duruma G"

#: The three breakdowns, by an ascii-safe fragment each. Köy/Şehir is left out: the town
#: and village split is a separate question and doubles the width for it.
BREAKDOWN_HINTS = ("Medeni", "Cinsiyet", "Grubu")

CELL_LIMIT = 50000

FIRST_YEAR = 2007

PAUSE = 4.0

INDICATORS = re.compile(r"g[oö]sterge adedi:\s*(\d+)", re.IGNORECASE)
PICKED = re.compile(r"d[uü]zey adedi:\s*(\d+)", re.IGNORECASE)


#: The levels MEDAS offers for this measure, by the label its Düzey box uses. District is
#: left out on purpose (the page does not offer that level yet, OFFERED_LEVELS), and it
#: would be by far the largest pull of the four.
#:
#: All four are fetched rather than rolled up from provinces. The counts are additive, so
#: a roll-up would give the same numbers — but "would" is doing a lot of work there, and
#: having the source's own totals next to ours is what turns that into something we can
#: check rather than assume.
LEVELS = {
    "country": "Türkiye",
    "nuts1": "İBBS1",
    "nuts2": "İBBS2 (26 Bölge)",
    "province": "İBBS3 (İl Düzeyi)",
}


def target_path(level: str, years: list[int]):
    return OUT / (
        "nufus-medeni-" + level + "-" + str(min(years)) + "-" + str(max(years)) + ".csv"
    )


def counted(page, pattern) -> int:
    found = pattern.search(page.inner_text("body"))
    return int(found.group(1)) if found else 0


def build_query(page) -> int:
    """Topic, measure and the three breakdowns. Returns the indicator count MEDAS reports.

    Stops short of the time tab so the caller can ask "how many indicators" before
    deciding how many years to request — the limit is a product, and the only honest way
    to size one factor is to know the others.
    """
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

    # Only the breakdown list has tick boxes, which keeps this away from the measure list
    # where "Cinsiyet" also appears as "Cinsiyet oranı" — clicking that silently changes
    # what is being measured and the breakdown panel empties without an error.
    # Ticked through `tick`, which indexes the rows that *have* a box — the same list
    # `visible_rows` numbers. Clicking `.z-listitem-checkbox` by the same index is a
    # different numbering and lands on the wrong row as soon as the two lists diverge,
    # which is what left this measure with two of its three dimensions selected and an
    # indicator count of zero.
    #
    # And only where it is not already on. Medeni durum is the mandatory breakdown — the
    # one MEDAS prints in red — so it arrives *already ticked*, and clicking it turned it
    # off. The measure then went in with two dimensions instead of three, no value list
    # opened for the missing one, and the indicator count came back zero with no error
    # anywhere. A tick is a toggle, so asking first is the only way to mean "on".
    for hint in BREAKDOWN_HINTS:
        row = next((i for i, text in visible_rows(page) if hint in text), None)
        if row is None:
            print("   kirilim satiri yok:", hint)
            return 0
        if is_ticked(page, row):
            print("   · kirilim zaten acik:", hint)
            continue
        tick(page, row, "kirilim: " + hint)

    click_exact(page, "Tamam")

    # Ticking the dimension names is half of it; each opens a value list headed <Hepsi>
    # and that is what actually selects the values (docs/medas.md). Three dimensions here,
    # so three of them — re-read each time because every tick renumbers the rows.
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


def pick_level(page, level: str) -> None:
    """Answer the Düzey box, and the province box under it where there is one."""
    label = LEVELS[level]
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if select.is_visible() and label in select.locator("option").all_inner_texts():
            select.select_option(label=label)
            settle(page, "duzey: " + label)
            break

    # Only the province level has a province box beneath it; at İBBS and country there is
    # nothing to narrow, so this quietly finds nothing and that is the right outcome.
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if (
            select.is_visible()
            and "HEPSİ" in select.locator("option").all_inner_texts()
        ):
            select.select_option(label="HEPSİ")
            settle(page, "il: HEPSI")
            break


def fetch_years(page, level: str, years: list[int]) -> bool:
    """Walk the whole flow for one level and chunk of years. True if a file was written."""
    target = target_path(level, years)

    count = build_query(page)
    print("   · gosterge adedi:", count)
    # 5 medeni durum × 2 cinsiyet × 17 yaş bandı. Anything much smaller means a tick did
    # not land, and the download would look fine while carrying a narrower table.
    if count < 100:
        print("   kirilim tutmadi, atlandi")
        return False

    # Zaman
    click_exact(page, "İleri")
    for year in years:
        row = page.locator(".z-listitem", has_text=str(year)).first
        if not row.count():
            print("   yil listede yok:", year)
            return False
        box = row.locator(".z-listitem-checkbox")
        (box if box.count() else row).click()
        settle(page)

    click_exact(page, "İleri")
    pick_level(page, level)

    # Ticked, then *checked* — the click landing is not the same as the selection taking,
    # and İBBS2 came back with a ticked header and zero areas selected. One more go before
    # giving up, because the failure is a missed server round trip rather than a wrong
    # request.
    areas = 0
    for _ in range(2):
        if not check_visible(page, ".z-listheader-checkable"):
            print("   alan listesi isaretlenemedi")
            return False
        areas = counted(page, PICKED)
        if areas:
            break
        print("   · secim tutmadi, tekrar isaretleniyor")
        settle(page)

    if not areas:
        print("   alan secilemedi")
        return False
    print("   · duzey adedi:", areas, "· hucre:", count * areas * len(years))
    if count * areas * len(years) > CELL_LIMIT:
        print("   · limit asildi")
        return False

    if not click_exact(page, "Rapor Oluştur"):
        print("   rapor olusturulamadi")
        return False

    # Waited for rather than slept past: the CSV button appears when MEDAS has finished
    # building, and how long that takes goes with the size of the report. A fixed sixty
    # seconds is what cost the neighbourhood run its thirteen largest provinces.
    csv_button = page.locator(
        "img[src*='csv'], a[title*='CSV'], .z-toolbarbutton[title*='CSV']"
    ).first
    patience = min(600000, 120000 + count * areas * len(years) // 4)
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


def chunk_size(page, level: str):
    """How many years fit in one query, worked out from MEDAS's own two counters.

    Hard-coding "three years" would be a number that goes quietly wrong the moment TÜİK
    adds an age band or a province, and the failure would look like a download that
    simply did not happen."""
    count = build_query(page)
    if not count:
        return 0, []
    click_exact(page, "İleri")
    years = [y for y in offered_years(page) if y >= FIRST_YEAR]
    if not years:
        return 0, []
    row = page.locator(".z-listitem", has_text=str(years[0])).first
    box = row.locator(".z-listitem-checkbox")
    (box if box.count() else row).click()
    settle(page)
    click_exact(page, "İleri")
    pick_level(page, level)

    # Answering the level box fills the area list but selects nothing; "Seçilen düzey
    # adedi" only moves once the list header's tick-all is clicked. Read before that, it
    # is always 0 — which divided out to "331 years per query" and would have sent the
    # province level in at eighteen years, four times over MEDAS's own limit.
    check_visible(page, ".z-listheader-checkable")
    areas = counted(page, PICKED)
    if not areas:
        print(level, "· alan sayisi okunamadi")
        return 0, []

    print(level, "· gosterge:", count, "· duzey:", areas)
    return max(1, CELL_LIMIT // (count * areas)), years


def main() -> None:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)

    asked = [int(a) for a in sys.argv[1:] if a.isdigit()]
    everything = "--all" in sys.argv

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)

        for level in LEVELS:
            size, years = chunk_size(page, level)
            if not size or not years:
                print("=", level, "sorgu kurulamadi")
                continue

            wanted = sorted(years) if everything or not asked else sorted(asked)
            chunks = [wanted[i : i + size] for i in range(0, len(wanted), size)]
            print("=", level, "·", len(chunks), "sorgu ·", size, "yil/sorgu")

            for chunk in chunks:
                if target_path(level, chunk).exists():
                    print("  ", chunk[0], "-", chunk[-1], "zaten var, atlandi")
                    continue
                for attempt in (1, 2):
                    try:
                        if fetch_years(page, level, chunk):
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
