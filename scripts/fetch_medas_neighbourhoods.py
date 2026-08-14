"""Fetch neighbourhood population, split at 18, from MEDAS — one province per run.

The district fetcher's chunk is the year, because 973 districts × 38 indicators already
fills MEDAS's own `gösterge × düzey × zaman ≤ 50000`. Here the shape is the other way
round: the measure carries a single breakdown, so there are only **2** indicators, and
the level list is what is enormous — fifty thousand neighbourhoods nationwide. So the
chunk is the **province**, and with two indicators most provinces fit every published
year in one query.

That inversion is the reason this is a separate script rather than a flag on the other:
the flow differs at the Düzey tab, which asks for a province and then a district before
it will list anything, and has no "TÜM İLLER" that stays under the limit.

Flow learned by `probe_medas_neighbourhood.py`:

1. Konu = Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları
2. Ölçüm = `Belediye, köy ve mahalle nüfusları` — lower case in the list, whatever the
   export header says
3. Kırılım = `18 yaş ve üzeri`, then its `<Hepsi>` in the value list that Tamam opens
   (the two-step trap, docs/medas.md)
4. Zaman = every year offered
5. Düzey = Mahalle · one province · TÜM İLÇELER, then the list header's tick-all

Raw files land in `raw/medas/mahalle/` per province and are never overwritten.

Run:  uv run python scripts/fetch_medas_neighbourhoods.py YOZGAT
      uv run python scripts/fetch_medas_neighbourhoods.py --all
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
    visible_rows,
)

from veriatlas.config import RAW, ensure_dirs

OUT = RAW / "medas" / "mahalle"

TOPIC = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"

#: Matched on an ascii-safe fragment, and on the casing MEDAS's own list uses rather than
#: the export header's Title Case — "Mahalle N" found nothing at all.
MEASURE_HINT = "Belediye,"

#: The measure's only breakdown. Its two values become the `0-17` / `18+` age bands.
BREAKDOWN_HINT = "18 ya"

#: MEDAS states this in its own footer: gösterge × düzey × zaman ≤ 50000.
CELL_LIMIT = 50000

#: Neighbourhood figures start with the 2013 address registry.
FIRST_YEAR = 2013

PAUSE = 4.0

#: "Seçilen düzey adedi: 239" and "Seçilen gösterge adedi: 2", both read off the footer.
PICKED = re.compile(r"d[uü]zey adedi:\s*(\d+)", re.IGNORECASE)
INDICATORS = re.compile(r"g[oö]sterge adedi:\s*(\d+)", re.IGNORECASE)


def target_path(province: str):
    return OUT / ("nufus-mahalle-" + province.replace(" ", "_") + ".csv")


def picked_levels(page) -> int:
    """How many areas the Düzey tab says are selected. The page's own count, because it
    is the one the limit is measured against — counting list rows would miss that the
    list is virtual and only renders what is on screen."""
    found = PICKED.search(page.inner_text("body"))
    return int(found.group(1)) if found else 0


def choose(page, wanted) -> bool:
    """Pick the first visible select that offers a matching option. Returns whether one
    was found — the Düzey tab's boxes fill in a chain and asking too early finds nothing.
    """
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if not select.is_visible():
            continue
        labels = [
            option.strip() for option in select.locator("option").all_inner_texts()
        ]
        hit = next((label for label in labels if wanted(label)), None)
        if hit:
            select.select_option(index=labels.index(hit))
            settle(page, "secildi: " + hit)
            return True
    return False


def fetch_province(page, province: str, years: list[int]) -> int:
    """Walk the flow for one province. Returns 0 on success, or the number of areas the
    page reported when the request was too large — which is what sizes the year chunk."""
    target = target_path(province)

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

    rows = visible_rows(page)
    index = next((i for i, text in rows if BREAKDOWN_HINT in text), None)
    if index is None:
        print("   18 yas kirilimi yok")
        return 0
    page.locator(".z-listitem-checkbox").nth(index).click()
    settle(page, "kirilim: 18 yas")

    click_exact(page, "Tamam")

    # Ticking the dimension is half of it; the value list's <Hepsi> is the other half.
    # Skipped, MEDAS quietly adds the unbroken measure and the file comes back as a plain
    # total that looks perfectly fine (docs/medas.md).
    while True:
        pending = [
            i
            for i, text in visible_rows(page)
            if "Hepsi" in text and not is_ticked(page, i)
        ]
        if not pending:
            break
        page.locator(".z-listitem-checkbox").nth(pending[0]).click()
        settle(page, "alt kirilim: <Hepsi>")

    click_exact(page, "Göstergeler Ekle") or click_exact(page, "Göstergeleri Ekle")

    # 18+ and under-18, and nothing else. One means the breakdown did not take and the
    # download would be a plain total wearing the right file name.
    found = INDICATORS.search(page.inner_text("body"))
    count = int(found.group(1)) if found else 0
    print("   · gosterge adedi:", count)
    if count != 2:
        print("   kirilim tutmadi, atlandi")
        return 0

    # Zaman
    click_exact(page, "İleri")
    for year in years:
        row = page.locator(".z-listitem", has_text=str(year)).first
        if not row.count():
            print("   yil listede yok:", year)
            continue
        box = row.locator(".z-listitem-checkbox")
        (box if box.count() else row).click()
        settle(page)

    # Düzey: Mahalle · this province · every district. The boxes chain, so they are
    # answered in order and each one is what makes the next appear.
    click_exact(page, "İleri")
    choose(page, lambda label: label == "Mahalle")
    if not choose(page, lambda label: label == province):
        print("   il kutuda yok:", province)
        return 0
    if not choose(page, lambda label: label.startswith("TÜM İLÇ")):
        print("   ilce kutusu dolmadi")
        return 0

    if not check_visible(page, ".z-listheader-checkable"):
        print("   mahalle listesi isaretlenemedi")
        return 0

    areas = picked_levels(page)
    print("   · mahalle adedi:", areas)
    if areas and 2 * areas * len(years) > CELL_LIMIT:
        print("   · limit asildi, yillar bolunecek")
        return areas

    if not click_exact(page, "Rapor Oluştur"):
        print("   rapor olusturulamadi")
        return 0

    # The CSV button only appears once MEDAS has finished building the report, and how
    # long that takes goes with the size of it: the small provinces came back in seconds
    # while İstanbul, Ankara, İzmir and Konya all failed on the default sixty — thirteen
    # provinces lost to a wait, not to anything about the data. Waited for explicitly,
    # with a ceiling that scales with the number of areas asked for.
    csv_button = page.locator(
        "img[src*='csv'], a[title*='CSV'], .z-toolbarbutton[title*='CSV']"
    ).first
    patience = min(600000, 120000 + areas * 300)
    try:
        csv_button.wait_for(state="visible", timeout=patience)
    except PlaywrightError:
        print("   rapor", round(patience / 1000), "sn'de hazir olmadi")
        return 0

    with page.expect_download(timeout=patience) as download:
        csv_button.click()
    download.value.save_as(str(target))

    print("  ", province, "->", target.name, target.stat().st_size, "bayt")
    return 0


def provinces_offered(page) -> tuple[list[str], list[int]]:
    """The province names the Düzey tab lists — the only spelling that selects — and the
    years the Zaman tab offers, both asked of the page rather than assumed."""
    page.goto(URL, wait_until="networkidle")
    page.locator("select").first.select_option(label=TOPIC)
    settle(page)
    items = page.locator(".z-listitem")
    index = next(
        (i for i in range(items.count()) if MEASURE_HINT in items.nth(i).inner_text()),
        None,
    )
    items.nth(index).click()
    settle(page)
    click_exact(page, "Tamam")
    click_exact(page, "Göstergeler Ekle") or click_exact(page, "Göstergeleri Ekle")
    click_exact(page, "İleri")
    years = [y for y in offered_years(page) if y >= FIRST_YEAR]

    # The Düzey tab stays empty until the time tab has been answered — with no year
    # ticked the province box never renders and the province list came back empty.
    if years:
        row = page.locator(".z-listitem", has_text=str(years[0])).first
        box = row.locator(".z-listitem-checkbox")
        (box if box.count() else row).click()
        settle(page)

    click_exact(page, "İleri")

    # The province box does not exist until the level box is answered — the boxes chain
    # the whole way down. Without this the province list came back empty and every
    # province read as "listede yok".
    choose(page, lambda label: label == "Mahalle")

    names: list[str] = []
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        labels = [
            option.strip() for option in select.locator("option").all_inner_texts()
        ]
        if "TÜM İLLER" in labels:
            names = [
                label
                for label in labels
                if label not in ("Seçiniz", "TÜM İLLER", "YABANCI ÜLKE")
            ]
            break
    return names, years


def main() -> None:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)

    asked = [a for a in sys.argv[1:] if not a.startswith("--")]
    everything = "--all" in sys.argv

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)

        names, years = provinces_offered(page)
        print("yillar:", years)
        print("il adedi:", len(names))

        wanted = names if everything else [a.upper() for a in asked]
        for province in wanted:
            if province not in names:
                print("=", province, "listede yok")
                continue
            if target_path(province).exists():
                print("=", province, "zaten var, atlandi")
                continue
            print("=", province)

            # Two goes at each province. The failure that actually happens is a timing
            # one: the value list's <Hepsi> ticks are a server round trip each, and when
            # one does not land before "Göstergeleri Ekle" the count comes back 0 and the
            # province is skipped. It succeeds on a second walk. Guarded by the
            # already-downloaded check above, so a retry cannot download twice.
            chunks = [years]
            while chunks:
                chunk = chunks.pop(0)
                areas = 0
                for attempt in (1, 2):
                    try:
                        areas = fetch_province(page, province, chunk)
                    except PlaywrightError as error:
                        print("   HATA:", type(error).__name__, str(error)[:160])
                    if target_path(province).exists() or areas:
                        break
                    if attempt == 1:
                        print("   · tekrar deneniyor")
                        time.sleep(PAUSE)
                if not areas:
                    break
                # Too large: split the years and take the halves. The file name has no
                # year in it, so a province that needs splitting is a case to handle
                # before running the rest — say so rather than writing a partial file.
                print(
                    "   BOLME GEREKIYOR:",
                    province,
                    areas,
                    "mahalle,",
                    len(chunk),
                    "yil",
                )
                break
            time.sleep(PAUSE)

        browser.close()

    print("\ncikti:", OUT)


if __name__ == "__main__":
    main()
