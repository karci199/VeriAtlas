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

The measure is a parameter, because the flow is the same for every ADNKS measure that
reaches district level -- only the row to click and the breakdowns to tick change. The
defaults are the population measure this script was written for; `--olcum` and
`--kirilim-adi` point it at another one without a second copy of the flow.

Run:  uv run python scripts/fetch_medas_districts.py 2023 2022
      uv run python scripts/fetch_medas_districts.py --all
      uv run python scripts/fetch_medas_districts.py --all --kirilim           --olcum "Yabancı uyruklu nüfus" --kirilim-adi Cinsiyet --ad yabanci
"""

import os
import pathlib
import re
import sys
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")

from veriatlas.config import RAW, ensure_dirs

URL = "https://biruni.tuik.gov.tr/medas/?locale=tr"
OUT = RAW / "medas" / "ilce"

#: The topic to open. Overridden by `--konu`, because the district flow is the same
#: whatever the subject heading is — literacy lives under education, not under ADNKS, and
#: the only thing that changes is which heading the first select is set to. The Turkish
#: label cannot come from argv (git-bash re-encodes it), so `--konu` takes a short ascii
#: key instead and the full label is written here.
TOPIC = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"

TOPICS = {
    "adnks": "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları",
    "egitim": "Ulusal Eğitim İstatistikleri",
    "olum": "Ölüm İstatistikleri",
    "dogum": "Doğum İstatistikleri",
    "evlenme": "Evlenme İstatistikleri",
    "bosanma": "Boşanma İstatistikleri",
}

#: Enough of the measure's row text to pick it out of the list. Overridden by `--olcum`.
MEASURE_HINT = "BBS-D"

#: Breakdown rows to tick when `--kirilim` is given. Overridden by `--kirilim-adi`.
BREAKDOWN_HINTS = ("Cinsiyet", "Grubu")

#: Level labels from the deepest upward. MEDAS offers a different set per measure — the
#: population measure reaches Mahalle, marital status stops at İlçe — so the level is not
#: assumed, it is read off the box and the deepest one offered is taken. Asking for a level
#: a measure does not have silently selects nothing and the report comes back at whatever
#: was already picked, which is how a district table once arrived labelled as provinces.
#:
#: Sandık is deliberately absent: the ballot-box level exists in the election application,
#: not here, and the standing instruction is to stop above it (docs/cekiciler.md).
LEVEL_ORDER = ("Mahalle", "Köy", "Belediye", "İlçe", "İl Düzeyi", "İBBS")

#: Overridden by `--duzey`, which pins one level instead of taking the deepest.
LEVEL_PIN = None


def deepest(labels: list[str]) -> str | None:
    """The deepest level this box offers, or the pinned one when `--duzey` named it."""
    if LEVEL_PIN:
        return next((label for label in labels if LEVEL_PIN in label), None)
    for wanted in LEVEL_ORDER:
        for label in labels:
            if wanted in label:
                return label
    return None


#: File stem, so a second measure does not overwrite the first. Overridden by `--ad`.
STEM = "nufus-ilce-"

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


#: When set, the value list is ticked name by name instead of with <Hepsi>. MEDAS caps
#: gösterge × düzey × zaman at 50.000, and this measure is 81 provinces × 973 districts =
#: 78.813 for a single year -- over the cap, so the report is refused. Ticking forty
#: provinces at a time brings it to 38.920 and two passes cover the year.
SLICE: tuple[str, ...] = ()
#: Set by `--il-no`: which entry of the province dropdown to choose, counting from 1 and
#: skipping "HEPSİ". A number rather than a name, because a Turkish string handed through
#: git-bash argv arrives re-encoded and would select nothing -- the same trap that makes
#: the measure label live in the wrapper instead of the command line.
PROVINCE_INDEX = 0
#: Set by `--tum-yillar`: tick every year the Zaman tab offers, not one.
ALL_YEARS = False


def tick_by_name(page, names: tuple[str, ...]) -> int:
    """Tick these rows in the open value list. Returns how many were ticked.

    The list is virtual: about a dozen rows exist in the DOM at a time and the rest are
    not merely off screen, they are not there. Scrolling a row into view therefore cannot
    reach them -- the *list* has to be scrolled so the missing rows get drawn. The walk
    ticks what is present, scrolls a page, and repeats until the list stops moving. A
    first attempt without this ticked nine provinces of forty-one and wrote a file that
    looked like a success.
    """
    wanted = {" ".join(n.split()) for n in names}
    done: set[str] = set()
    # Not `.last`: the page holds four listboxes and the last one is an empty shell with
    # no height, so scrolling it does nothing at all. The value list is the one carrying
    # the "<Hepsi>" row -- found by its content rather than by position, which changes.
    bodies = page.locator(".z-listbox-body")
    body = bodies.last
    for index in range(bodies.count()):
        if bodies.nth(index).locator(".z-listitem", has_text="Hepsi").count():
            body = bodies.nth(index)
            break
    last_top = -1
    while True:
        rows = tickable(page)
        for index in range(rows.count()):
            row = rows.nth(index)
            if not row.is_visible():
                continue
            text = " ".join(row.inner_text().split())
            if text not in wanted or text in done:
                continue
            if not is_ticked(page, index):
                row.locator(".z-listitem-checkbox").first.click()
                settle(page)
            done.add(text)
        if done == wanted:
            break
        top = body.evaluate(
            "el => { el.scrollTop += el.clientHeight - 40; return el.scrollTop; }"
        )
        settle(page)
        if top == last_top:
            break
        last_top = top
    missing = wanted - done
    if missing:
        print("   · bulunamayan gosterge:", sorted(missing)[:5], f"({len(missing)})")
    return len(done)


def indicator_count(page) -> int:
    """The footer's "Seçilen gösterge adedi: N". Zero means nothing was really added."""
    match = re.search(r"adedi:\s*(\d+)", page.inner_text("body")[-320:])
    return int(match.group(1)) if match else -1


def target_path(year: int, breakdown: bool):
    return OUT / (STEM + ("kirilim-" if breakdown else "") + str(year) + ".csv")


def offered_years(page, tries: int = 6) -> list[int]:
    """Years the Zaman tab lists, newest first.

    Retried, and this is the whole point of the function having a loop: MEDAS answers the
    tab before it has drawn the rows, and a list that has not been drawn yet is
    indistinguishable from a measure that publishes no years — both are `[]`. Taking the
    first answer is how literacy and three ADNKS measures were each written off as "this
    measure offers no years" while the data was there. An empty list is now waited on, not
    believed.
    """
    for attempt in range(1, tries + 1):
        years = []
        rows = page.locator(".z-listitem")
        for index in range(rows.count()):
            text = rows.nth(index).inner_text().strip()
            if text.isdigit() and len(text) == 4:
                years.append(int(text))
        if years:
            return sorted(set(years), reverse=True)
        if attempt < tries:
            print(f"   yil listesi bos, bekleniyor ({attempt}/{tries})", flush=True)
            time.sleep(3 * attempt)
            settle(page)
    return []


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
        if BREAKDOWN_HINTS == ("*",):
            # Every breakdown the measure offers, which is what the topic scan does when
            # it reports a measure as 81 indicators. Naming one of them is not always
            # enough: "İkamet edilen ilçeye göre nüfusa kayıtlı olunan il" answers with
            # "gösterge adedi: 0" when only the province dimension is ticked, and zero
            # indicators reads exactly like a measure that has no data.
            for index, text in visible_rows(page):
                if not is_ticked(page, index):
                    try:
                        tick(page, index, "kirilim: " + " ".join(text.split())[:40])
                    except Exception as error:  # noqa: BLE001
                        print("   · kirilim atlandi:", str(error)[:60])
        else:
            for hint in BREAKDOWN_HINTS:
                index = next((i for i, t in visible_rows(page) if hint in t), None)
                if index is None:
                    print("  ", year, "kirilim satiri yok:", hint)
                    return False
                # Some measures (okuma-yazma) arrive with dimensions pre-ticked by MEDAS
                # itself. Ticking is a toggle, so clicking an already-ticked row turns it
                # back off -- only click what is not already on.
                if not is_ticked(page, index):
                    tick(page, index, "kirilim: " + hint)
                else:
                    print("   · zaten isaretli:", hint)

    click_exact(page, "Tamam")

    if breakdown:
        # Ticking the dimension names is only half of it: Tamam opens a value list per
        # dimension and the page then asks "Lütfen alt kırılım seçiniz!". Skipping this
        # is why the first breakdown run came back byte-identical to the plain total —
        # MEDAS just added the unbroken measure. One `<Hepsi>` heads each value list, and
        # ticking those beats looping over 19 age bands that scroll off screen.
        if SLICE:
            tick_by_name(page, SLICE)
        while not SLICE:
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
    if ALL_YEARS:
        # One province at a time costs little: 81 indicators x ~15 districts x 19 years is
        # 23.000, well inside the 50.000 cap, so the whole series comes in one query
        # instead of one per year. Nineteen times fewer trips through the flow.
        for label in offered_years(page):
            row = page.locator(".z-listitem", has_text=str(label)).first
            box = row.locator(".z-listitem-checkbox")
            (box if box.count() else row).click()
            settle(page)
    else:
        year_row = page.locator(".z-listitem", has_text=str(year)).first
        if not year_row.count():
            print("  ", year, "listede yok; sunulan:", offered_years(page)[:25])
            return False
        box = year_row.locator(".z-listitem-checkbox")
        (box if box.count() else year_row).click()
        settle(page)

    # Düzey: as deep as this measure goes, every province, every unit
    click_exact(page, "İleri")
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if not select.is_visible():
            continue
        labels = select.locator("option").all_inner_texts()
        chosen = deepest(labels)
        if chosen:
            print("   duzey:", chosen)
            select.select_option(label=chosen)
            settle(page)
            break

    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if (
            select.is_visible()
            and "HEPSİ" in select.locator("option").all_inner_texts()
        ):
            # One province instead of all of them. The measure is 81 indicators and the
            # country is 973 districts: 78.813 for a single year, which MEDAS refuses.
            # Asked province by province it is a few thousand, and every year fits too.
            if PROVINCE_INDEX:
                labels = select.locator("option").all_inner_texts()
                # The dropdown opens with a placeholder and an all-provinces entry
                # before the provinces themselves; counting from the raw list selects
                # "Seçiniz" and the report then comes back with nothing chosen.
                # Matched on a fragment, not on an upper-cased whole: "Seçiniz".upper()
                # is "SEÇINIZ" in Python and "SEÇİNİZ" in Turkish, so a set of spellings
                # misses one of them and the placeholder gets selected as if it were a
                # province -- the report then has no level at all.
                rest = [
                    t
                    for t in labels
                    if t.strip()
                    and "eçiniz" not in t
                    and "EPS" not in t.upper()
                    and "YABANCI" not in t.upper()
                ]
                if PROVINCE_INDEX > len(rest):
                    print("  ", year, "il sirasi yok:", PROVINCE_INDEX, len(rest))
                    return False
                name = rest[PROVINCE_INDEX - 1]
                print("   il:", name)
                select.select_option(label=name)
            else:
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

    global MEASURE_HINT, BREAKDOWN_HINTS, STEM, LEVEL_PIN, TOPIC
    if "--konu" in sys.argv:
        key = sys.argv[sys.argv.index("--konu") + 1]
        if key not in TOPICS:
            raise SystemExit(f"bilinmeyen konu: {key} ({', '.join(TOPICS)})")
        TOPIC = TOPICS[key]
    if "--duzey" in sys.argv:
        LEVEL_PIN = sys.argv[sys.argv.index("--duzey") + 1]
    if "--olcum" in sys.argv:
        MEASURE_HINT = sys.argv[sys.argv.index("--olcum") + 1]
    if "--kirilim-adi" in sys.argv:
        BREAKDOWN_HINTS = tuple(
            sys.argv[sys.argv.index("--kirilim-adi") + 1].split(",")
        )
    if "--gosterge-dosya" in sys.argv:
        # The names come from a file, not from argv: a Turkish string passed through
        # git-bash arrives re-encoded and would match nothing.
        global SLICE
        SLICE = tuple(
            line.strip()
            for line in pathlib.Path(sys.argv[sys.argv.index("--gosterge-dosya") + 1])
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
    # From the environment, not argv: a bare number sitting after a flag is also read as
    # a year by the loop below, and every province was writing a second, meaningless file
    # named after its own index.
    global PROVINCE_INDEX
    PROVINCE_INDEX = int(os.environ.get("VERIATLAS_IL_NO", "0") or 0)
    if "--tum-yillar" in sys.argv:
        global ALL_YEARS
        ALL_YEARS = True
    if "--ad" in sys.argv:
        STEM = sys.argv[sys.argv.index("--ad") + 1] + "-ilce-"
    print("olcum:", MEASURE_HINT, " kirilim:", BREAKDOWN_HINTS if breakdown else "-")

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
            if breakdown:
                # This discovery pass used to skip the breakdown entirely, which is fine
                # for a measure with no mandatory dimension -- but a measure that arrives
                # with dimensions pre-ticked (okuma-yazma) still needs its value lists
                # answered with <Hepsi> before "Tamam" will let the year tab open at all.
                for hint in BREAKDOWN_HINTS:
                    index = next((i for i, t in visible_rows(page) if hint in t), None)
                    if index is not None and not is_ticked(page, index):
                        tick(page, index, "kirilim: " + hint)
            click_exact(page, "Tamam")
            if breakdown:
                while True:
                    pending = [
                        index
                        for index, text in visible_rows(page)
                        if "Hepsi" in text and not is_ticked(page, index)
                    ]
                    if not pending:
                        break
                    tick(page, pending[0], "alt kirilim: <Hepsi>")
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
