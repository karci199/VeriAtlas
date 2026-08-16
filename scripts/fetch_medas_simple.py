"""Fetch the narrow MEDAS measures — the ones a single query covers.

`scan_medas_topic.py` measured them: nüfus yoğunluğu, cinsiyet oranı, the three dependency
ratios, average household size, net migration and the rest come to **one indicator each**,
so 1 × 82 areas × 19 years is 1.558 cells against MEDAS's 50.000 limit. Every year in one
go, and the whole batch in one run of the flow.

That is the entire reason this script exists separately from the district and marital
ones: those are shaped by a limit, this one is not shaped by anything. What varies between
measures here is only the name to click and whether to open its breakdowns.

Levels: country and province. The İBBS ones are exact sums of provinces where the measure
is a count, and where it is a *rate* they are not sums at all — so they are left to the
roll-up, which knows to weight them (aggregate.to_level), rather than being mixed in here.

Raw files land in `raw/medas/basit/` per measure and are never overwritten.

Run:  uv run python scripts/fetch_medas_simple.py            # hepsi
      uv run python scripts/fetch_medas_simple.py yogunluk   # tek tek
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

OUT = RAW / "medas" / "basit"

ADNKS = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"
BIRTHS = "Doğum İstatistikleri"
DEATHS = "Ölüm İstatistikleri"
MARRIAGES = "Evlenme İstatistikleri"
LIFE = "Hayat Tabloları"
DIVORCES = "Boşanma İstatistikleri"

CELL_LIMIT = 50000

PAUSE = 4.0

INDICATORS = re.compile(r"g[oö]sterge adedi:\s*(\d+)", re.IGNORECASE)
PICKED = re.compile(r"d[uü]zey adedi:\s*(\d+)", re.IGNORECASE)

#: What to fetch: a short name for the file, the topic it lives under, an ascii-safe
#: fragment of the measure's label (MEDAS serves ISO-8859-9 under a lying header, so
#: Turkish letters cannot be matched), and whether the measure's breakdowns should be
#: opened. The indicator counts in the comments are measured, not guessed — see
#: raw/medas/kesif/.
#:
#: Births and deaths are taken **by place of residence**, not by place of occurrence.
#: MEDAS publishes both and they are different questions: a province with a large
#: maternity hospital records births belonging to the provinces around it, and a province
#: with a large hospital records their deaths. Residence is the one that belongs next to a
#: population count. It also runs seventeen years against the other's eight.
MEASURES = [
    ("yogunluk", ADNKS, "Nüfus yoğunluğu", False),  # 1
    ("cinsiyet-orani", ADNKS, "Cinsiyet oranı", False),  # 1
    ("artis-hizi", ADNKS, "Yıllık nüfus artış hızı", False),  # 1
    ("bagimlilik-cocuk", ADNKS, "Çocuk bağımlılık", False),  # 1
    ("bagimlilik-yasli", ADNKS, "Yaşlı bağımlılık", False),  # 1
    ("bagimlilik-toplam", ADNKS, "Toplam yaş bağımlılık", False),  # 1
    ("hane-buyuklugu", ADNKS, "Ortalama hanehalkı büyüklüğü", False),  # 1
    ("hane-sayisi", ADNKS, "Toplam hanehalkı sayısı", False),  # 1
    ("hane-tipleri", ADNKS, "Hanehalkı tiplerine göre", True),  # 9
    ("goc-net", ADNKS, "Bölgelerin net göç bilgileri", False),  # 1
    ("goc-net-hizi", ADNKS, "Bölgelerin net göç hızı", False),  # 1
    ("goc-aldigi", ADNKS, "Bölgelerin aldığı göç", True),  # 28
    ("goc-verdigi", ADNKS, "Bölgelerin verdiği göç", True),  # 28
    ("yabanci-uyruklu", ADNKS, "Yabancı uyruklu nüfus", True),  # 2
    ("goc-disaridan", ADNKS, "Yurt dışından Türkiye'ye gelen göç", False),  # 1
    ("goc-disariya", ADNKS, "Türkiye'den yurt dışına giden göç", False),  # 1
    # Kütük nüfusu. The measure's name reads as though the rows were the register, and
    # they are not: rows are where people live, columns are where they are registered, and
    # the number wanted is a *column* total (see adapters/tuik_registry). The breakdown
    # cannot be closed, so this one comes a year at a time — `--yil=2019` — at 6.642 cells
    # a year against 126.000 for the whole span.
    (
        "kutuk-nufusu",
        ADNKS,
        "Nüfusa kayıtlı olunan ile göre ikamet edilen il",
        False,
    ),  # 1
    ("dogum", BIRTHS, "İkametgah yerine göre doğum", True),  # 12
    ("kaba-dogum-hizi", BIRTHS, "Kaba doğum hızı", False),  # 1
    ("olum", DEATHS, "İkametgah yerine göre ölüm", True),  # 24
    ("kaba-olum-hizi", DEATHS, "Kaba ölüm hızı", False),  # 1
    ("bebek-olum-hizi", DEATHS, "Bebek ölüm hızı", False),  # 1
    ("bes-yas-alti-olum-hizi", DEATHS, "Beş yaş altı ölüm", False),  # 1
    # Marriage and divorce. Both counts carry ten or more breakdowns — the woman's age
    # group, the education of each spouse, the length of the marriage, who the children
    # were left with — and every one of them is left closed here. With them open the
    # measure is 121 indicators and the download is a query per two years; closed it is
    # one indicator and twenty-five years in one go. The breakdowns are a session of their
    # own, not a checkbox on the way past.
    # District-level vital events are their own measures, not the province ones asked for
    # at another level: MEDAS offers "İlçelere göre doğum sayısı" beside "İkametgah yerine
    # göre doğum sayısı" and the district level only exists on the first. They are also
    # shorter — districts start in 2014 for births and 2009 for deaths — and they carry
    # no breakdown to open, which is what makes a two-year probe one query of 1.946 cells.
    # The life table is the only thing here that answers "did mortality change" without
    # the age structure in the way: it is a death probability per single year of age, so
    # it holds the composition still by construction. 202 indicators — 101 ages × two
    # sexes — but one area and thirteen years, which is 2.626 cells and one query.
    ("hayat-tablosu", LIFE, "Tek yaş hayat tablosu", True),  # 202, yalnız Türkiye
    ("yasam-suresi", LIFE, "Do", True),  # 2, Türkiye + il, yalnız 5 yıl
    ("dogum-ilce", BIRTHS, "lçelere göre doğum", False),  # 2
    ("olum-ilce", DEATHS, "lçelere göre ölüm", False),  # 2
    # Deaths by the age of the deceased, which is what turns "did mortality change or did
    # the population age" from an argument into a subtraction. Only the age breakdown is
    # opened: with the month beside it the same question costs twelve times the cells.
    ("olum-yas", DEATHS, "İkametgah yerine göre ölüm", "yaş grubu"),
    ("evlenme", MARRIAGES, "Evlenme sayısı", False),  # 1
    ("kaba-evlenme-hizi", MARRIAGES, "Kaba evlenme", False),  # 1
    ("evlenme-yasi-erkek", MARRIAGES, "Erkeğin ortalama evlenme", False),  # 1
    ("evlenme-yasi-kadin", MARRIAGES, "Kadının ortalama evlenme", False),  # 1
    ("ilk-evlenme-yasi-erkek", MARRIAGES, "Erkeğin ortalama ilk evlenme", False),  # 1
    ("ilk-evlenme-yasi-kadin", MARRIAGES, "Kadının ortalama ilk evlenme", False),  # 1
    ("bosanma", DIVORCES, "Boşanma sayısı", False),  # 1
    ("kaba-bosanma-hizi", DIVORCES, "Kaba boşanma", False),  # 1
]

#: The Düzey box labels for the levels kept here.
LEVELS = {
    "country": "Türkiye",
    "province": "İBBS3 (İl Düzeyi)",
    "district": "İlçe Düzeyi",
}


#: Measures published for the country and nowhere else. The single-year life table is
#: the case: TÜİK computes it nationally because a province's deaths at age 93 are a
#: handful of people and the resulting probability would be noise.
COUNTRY_ONLY = {"hayat-tablosu"}


def levels_for(name: str) -> list[str]:
    """Which levels a measure is asked for.

    Carried by the name rather than by a fifth field on all thirty entries: `-ilce`
    measures exist *only* at district level, and asking for Türkiye there would download
    the same national total a second time under another measure's name.
    """
    if name.endswith("-ilce"):
        return ["district"]
    if name in COUNTRY_ONLY:
        return ["country"]
    return ["country", "province"]


def counted(page, pattern) -> int:
    found = pattern.search(page.inner_text("body"))
    return int(found.group(1)) if found else 0


def target_path(name: str, level: str, part: int = 0):
    #: Part 0 keeps the plain name every existing file already has; a sliced measure
    #: numbers its pieces from one.
    piece = "-" + str(part) if part else ""
    return OUT / ("nufus-" + name + "-" + level + piece + ".csv")


def build_query(page, topic: str, hint: str, breakdowns) -> int:
    """Topic and measure, with its breakdowns opened or not. Returns the indicator count.

    `breakdowns` is False for none, True for all, or a string to open exactly one of them.
    That last case is what deaths by age needs: the measure carries seven breakdowns and
    opening them all multiplies out to a query no limit will take, while opening the month
    alongside the age would ask for twelve times more cells to answer a question about age.
    One is the whole point — the others are still there for a later session.
    """
    page.goto(URL, wait_until="networkidle")
    page.locator("select").first.select_option(label=topic)
    settle(page)

    items = page.locator(".z-listitem")
    index = next(
        (i for i in range(items.count()) if hint in items.nth(i).inner_text()), None
    )
    if index is None:
        print("   olcum bulunamadi:", hint)
        return 0
    items.nth(index).click()
    settle(page)

    if breakdowns:
        wanted = breakdowns if isinstance(breakdowns, str) else None
        for row, text in visible_rows(page):
            keep = wanted is None or wanted.lower() in text.lower()
            # Only ever turned on, never off. A tick is a toggle and the mandatory ones
            # arrive already on (docs/medas.md) — deaths always carry the sex of the
            # deceased — so unticking what we did not ask for empties the query instead of
            # narrowing it, and MEDAS then refuses the whole measure without saying why.
            if keep and not is_ticked(page, row):
                tick(page, row, "")

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
    return counted(page, INDICATORS)


def fetch(
    page,
    name: str,
    topic: str,
    hint: str,
    breakdowns: bool,
    level: str,
    only: list | None = None,
    part: int = 0,
) -> bool:
    """One measure at one level, every year the page offers — or the years in `only`.

    `only` is how a measure too wide for one query is taken in slices. Kütük nüfusu is
    the case: its breakdown is the province of residence and MEDAS will not let it be
    closed, so the measure is 81 indicators however it is asked for, and 81 × 82 areas ×
    19 years is 126.000 cells against a limit of 50.000. Seven years at a time fits.
    Each slice lands in its own numbered file and the adapter reads them together.
    """
    target = target_path(name, level, part)

    count = build_query(page, topic, hint, breakdowns)
    if not count:
        return False

    click_exact(page, "İleri")
    years = offered_years(page)
    if not years:
        print("   yil listesi bos")
        return False
    if only is not None:
        years = [y for y in years if y in only]
        if not years:
            print("   istenen yillar bu olcumde yok")
            return False
    # A year at a time, scrolled to before it is clicked. The list is long enough at
    # twenty-five years that the last ones sit below the fold, and a click on a row that
    # is off-screen waits the full minute and then takes the whole measure down with it —
    # which is how the average marriage age came back with two files out of eight while
    # the counts, four years shorter, went through untouched.
    #
    # A year that still will not take is dropped and *named*. Silently, the file would
    # come back short and look complete.
    missed = []
    for year in years:
        row = page.locator(
            ".z-listitem", has_text=re.compile(r"^\s*" + str(year) + r"\s*$")
        ).first
        if not row.count():
            continue
        box = row.locator(".z-listitem-checkbox")
        target_row = box if box.count() else row
        try:
            target_row.scroll_into_view_if_needed(timeout=5000)
            target_row.click(timeout=10000)
        except PlaywrightError:
            missed.append(year)
            continue
        settle(page)

    # One year out of twenty-five failed on every long measure, and never the same one:
    # 2004, then 2002, then 2006. That is not a bad row, it is a race — ticking a year
    # re-renders the list under the handle we are holding. A second pass over just the
    # ones that slipped, with the row found again from scratch, has taken every one of
    # them so far.
    for year in list(missed):
        row = page.locator(
            ".z-listitem", has_text=re.compile(r"^\s*" + str(year) + r"\s*$")
        ).first
        if not row.count():
            continue
        box = row.locator(".z-listitem-checkbox")
        target_row = box if box.count() else row
        try:
            target_row.scroll_into_view_if_needed(timeout=5000)
            target_row.click(timeout=10000)
        except PlaywrightError:
            continue
        settle(page)
        missed.remove(year)

    if missed:
        print("   · secilemeyen yil:", ", ".join(str(y) for y in missed))
    if len(missed) == len(years):
        print("   hicbir yil secilemedi")
        return False

    click_exact(page, "İleri")
    label = LEVELS[level]
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        if select.is_visible() and label in select.locator("option").all_inner_texts():
            select.select_option(label=label)
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

    # Two things go wrong here and they pull in opposite directions.
    #
    # The header tick does not always take on the first click, so it is worth clicking
    # again — the count is still zero, meaning the box is still off, so a second click
    # turns it on rather than clearing anything.
    #
    # And once it does take, the counter *climbs* while the list works through: read
    # straight away it says 33 where the answer is 82, and every cell estimate built on
    # it comes out a third of the truth. That is how kütük nüfusu was cut into "slices"
    # each of which was still over the limit — the arithmetic was right and its input was
    # half-finished. So after each click, read until the number stops moving.
    areas = 0
    for _ in range(3):
        if not check_visible(page, ".z-listheader-checkable"):
            print("   alan listesi isaretlenemedi")
            return False
        # Three readings the same, not two. The counter does not climb smoothly — it
        # rests: 33 for two reads running, then 39, then 82. Two agreeing reads called
        # 33 the answer and sliced the download into pieces a third too big, twice over.
        seen = 0
        same = 0
        for _ in range(20):
            now = counted(page, PICKED)
            same = same + 1 if now == seen else 0
            seen = max(seen, now)
            if seen and same >= 2:
                break
            settle(page)
        if seen:
            areas = seen
            break
    if not areas:
        print("   alan secilemedi")
        return False

    cells = count * areas * len(years)
    print(
        "   · gosterge:",
        count,
        "· alan:",
        areas,
        "· yil:",
        len(years),
        "· hucre:",
        cells,
    )
    if cells > CELL_LIMIT:
        # Said plainly rather than silently truncated. The caller reads the numbers back
        # out of this to work out how many years fit, and comes round again in slices.
        print("   · limit asildi:", cells, "hucre")
        return (count, areas, years)

    if not click_exact(page, "Rapor Oluştur"):
        print("   rapor olusturulamadi")
        return False

    csv_button = page.locator(
        "img[src*='csv'], a[title*='CSV'], .z-toolbarbutton[title*='CSV']"
    ).first
    patience = min(600000, 120000 + cells * 4)
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


def main() -> None:
    ensure_dirs()
    OUT.mkdir(parents=True, exist_ok=True)

    asked = [a for a in sys.argv[1:] if not a.startswith("--")]
    wanted = [m for m in MEASURES if not asked or m[0] in asked]

    # `--yil=2019,2009`: take these years only, one query each, one file each.
    #
    # This is the way in for a measure whose breakdown cannot be closed. Kütük nüfusu is
    # 81 indicators × 82 areas however it is asked for — 6.642 cells for a single year,
    # comfortably inside the limit, and 126.000 for all nineteen, which is three times
    # over it. Slicing it automatically failed because MEDAS's own area counter climbs
    # while the list fills (33 → 39 → 82), so the batch size was computed off a third of
    # the truth. Naming the years takes the counter out of the arithmetic entirely.
    #
    # The years are asked for in the order given, not sorted: 2019 first and 2009 second
    # is a comparison, and the first file is the one worth having if the second run never
    # happens.
    picked = next(
        (a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--yil=")), ""
    )
    years_wanted = [int(y) for y in picked.replace(" ", "").split(",") if y]

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)

        for name, topic, hint, breakdowns in wanted:
            for level in levels_for(name):
                if years_wanted:
                    # One file per year, numbered by the year itself so the pieces say
                    # what they hold rather than what order they arrived in.
                    for year in years_wanted:
                        if target_path(name, level, year).exists():
                            print("=", name, level, year, "zaten var")
                            continue
                        print("=", name, level, year)
                        for attempt in (1, 2):
                            try:
                                if (
                                    fetch(
                                        page,
                                        name,
                                        topic,
                                        hint,
                                        breakdowns,
                                        level,
                                        [year],
                                        year,
                                    )
                                    is True
                                ):
                                    break
                            except PlaywrightError as error:
                                print(
                                    "   HATA:", type(error).__name__, str(error)[:120]
                                )
                            if attempt == 1:
                                print("   · tekrar deneniyor")
                                time.sleep(PAUSE)
                        time.sleep(PAUSE)
                    continue

                if target_path(name, level).exists():
                    print("=", name, level, "zaten var, atlandi")
                    continue
                print("=", name, level)
                outcome = None
                for attempt in (1, 2):
                    try:
                        outcome = fetch(page, name, topic, hint, breakdowns, level)
                        if outcome:
                            break
                    except PlaywrightError as error:
                        print("   HATA:", type(error).__name__, str(error)[:120])
                    if attempt == 1:
                        print("   · tekrar deneniyor")
                        time.sleep(PAUSE)
                time.sleep(PAUSE)

                # Too wide for one query: come back in year-sized slices. How many years
                # fit is arithmetic off what the page just reported, not a guess — and one
                # year that does not fit on its own is a measure for a different script,
                # said out loud rather than half-downloaded.
                if not isinstance(outcome, tuple):
                    continue
                count, areas, years = outcome
                # Nine tenths of the limit, not all of it: the indicator count MEDAS
                # reports for the whole span is not always the count it applies to a
                # slice of it, and a batch sized to the millimetre came back over the
                # line by 2%. The slack costs one extra query and never a wasted one.
                per_query = int(CELL_LIMIT * 0.9) // max(1, count * areas)
                if per_query < 1:
                    print("   · tek yil bile sigmiyor, bu betik yetmez")
                    continue
                slices = [
                    years[i : i + per_query] for i in range(0, len(years), per_query)
                ]
                print("   ·", len(slices), "parcaya bolunuyor,", per_query, "yil")
                for part, batch in enumerate(slices, start=1):
                    if target_path(name, level, part).exists():
                        print("  ", part, "zaten var")
                        continue
                    for attempt in (1, 2):
                        try:
                            # `is True` on purpose: over the limit, fetch returns the
                            # counts, and a tuple is truthy. Read as a plain boolean it
                            # counted a refused slice as a downloaded one and moved on,
                            # which is how the first run came back holding one year of
                            # nineteen and calling it done.
                            if (
                                fetch(
                                    page,
                                    name,
                                    topic,
                                    hint,
                                    breakdowns,
                                    level,
                                    batch,
                                    part,
                                )
                                is True
                            ):
                                break
                        except PlaywrightError as error:
                            print("   HATA:", type(error).__name__, str(error)[:120])
                        if attempt == 1:
                            print("   · tekrar deneniyor")
                            time.sleep(PAUSE)
                    time.sleep(PAUSE)

        browser.close()

    print("\ncikti:", OUT)


if __name__ == "__main__":
    main()
