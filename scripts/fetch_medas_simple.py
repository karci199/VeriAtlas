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
ORGUN = "Örgün Eğitim İstatistikleri"

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
    # The same two household measures at district level: 973 × 19 years is 18.487 cells,
    # one query. Separate names so levels_for() sends them to İlçe Düzeyi only.
    ("hane-buyuklugu-ilce", ADNKS, "Ortalama hanehalkı büyüklüğü", False),  # 1
    ("hane-sayisi-ilce", ADNKS, "Toplam hanehalkı sayısı", False),  # 1
    ("goc-net", ADNKS, "Bölgelerin net göç bilgileri", False),  # 1
    ("goc-net-hizi", ADNKS, "Bölgelerin net göç hızı", False),  # 1
    ("goc-aldigi", ADNKS, "Bölgelerin aldığı göç", True),  # 28
    ("goc-verdigi", ADNKS, "Bölgelerin verdiği göç", True),  # 28
    ("yabanci-uyruklu", ADNKS, "Yabancı uyruklu nüfus", True),  # 2
    # Migration out of each province, broken down by *why* people left. The measure is
    # 972 indicators — 81 provinces giving migration x 12 reasons — at the country level,
    # which is 7.776 cells over eight years and one query. It is not the province-to-
    # province matrix it sounds like: there is no destination in it, only origin and
    # reason. What it adds to , which is the same flow with no breakdown,
    # is the reason.
    ("goc-neden", ADNKS, "İller arası verdiği göç", True),
    # The flow matrices. There is no province-to-province one — "İller arası verdiği göç"
    # carries the origin and the reason but never the destination — and at İBBS2 there is:
    # 26 indicators (one per receiving region) across 26 regions, which is the 26×26 matrix
    # itself, eighteen years deep and 12.168 cells in one query. "Aldığı" and "verdiği"
    # are the same matrix read along its two axes; both are taken because each names its
    # own axis, and having them side by side is what makes the transpose checkable.
    ("goc-alinan-ibbs2", ADNKS, "İBBS-Düzey2 bölgeler arası aldığı", True),
    ("goc-verilen-ibbs2", ADNKS, "İBBS-Düzey2 bölgeler arası verdiği", True),
    ("goc-disaridan", ADNKS, "Yurt dışından Türkiye'ye gelen göç", False),  # 1
    ("goc-disariya", ADNKS, "Türkiye'den yurt dışına giden göç", False),  # 1
    # Kontrol icin: tek yas hesabimizla karsilastirilacak, MEDAS'in kendi ortanca yas
    # sayisi. Cinsiyet kirilimi kapatilamiyor (2 gosterge), toplam ayri sorulmali (K12).
    ("ortanca-yas", ADNKS, "Ortanca yaş", True),  # 2
    # Dogum yerine gore nufus: Turkiye capinda tek satir (83 gosterge, dogum yeri
    # kirilimi zaten acik), il duzeyinde ayni sekilde -- ikisi de 50.000 siniri altinda
    # tek yil sorgusu ile.
    ("dogum-yeri-tr", ADNKS, "Doğum yerlerine göre nüfus", False),  # 83, yalniz Turkiye
    ("dogum-yeri-il", ADNKS, "İkamet edilen illere göre doğum yerleri", False),  # 83
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
    # The other reading of the register square.  is "nüfusa kayıtlı olunan
    # ile göre ikamet edilen il" — registered province down the rows. This is the same
    # square transposed: province of residence down the rows, where they are registered
    # across. Fetched to check the one against the other, since a square read on the wrong
    # axis produces totals that look right at the country level and are wrong everywhere
    # else — which is exactly the trap K24 records falling into.
    (
        "ikamet-kutuk",
        ADNKS,
        "İkamet edilen ile göre nüfusa kayıtlı olunan il",
        False,
    ),  # 81
    # The province-level twin of the district hemşehrilik measure (fetch_medas_hemsehrilik.py):
    # same 81-indicators-already-open shape, but 81 x 81 areas is small enough for one
    # query per year here rather than the province-by-province split the district version
    # needs. --yil= batches years the same way kutuk-nufusu does.
    (
        "hemsehrilik-il",
        ADNKS,
        "İkamet edilen ile göre nüfusa kayıtlı olunan il",
        False,
    ),  # 81
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
    # Births by the mother's age group — the same trade the age breakdown makes on the
    # death side. It is what separates "more women of childbearing age" from "more births
    # per woman", which a total birth count cannot answer on its own, and it is the
    # numerator the age-specific fertility rate wants. Month and sex are left closed: they
    # multiply the cells by twenty-four to answer a different question.
    ("dogum-anne-yasi", BIRTHS, "İkametgah yerine göre doğum", "Annenin yaş grubu"),
    # The rest of the death measure's seven breakdowns, one query each. Opened alone for
    # the same reason `olum-yas` is: together they multiply out past any limit, and each
    # answers its own question.
    #
    # Single year of age is the one that supersedes rather than adds: K16 says store the
    # finest grain published and derive the coarse one, so once this lands the age-group
    # file is a roll-up we can compute instead of a second series to keep in step. It is
    # also the widest — about a hundred indicators — so it comes a year at a time.
    ("olum-tek-yas", DEATHS, "İkametgah yerine göre ölüm", "Ölenin yaşı"),
    # Marital status of the deceased is **not fetchable**, and the failure is MEDAS's own.
    # The breakdown ticks, the value list opens ([1] Hiç Evlenmedi … [99] Bilinmeyen), and
    # the moment any value is selected the "Göstergeleri Ekle" button is removed from the
    # page — display:none, no bounding box, on every route tried: scrolled to, forced,
    # dispatched, tab re-opened, viewport grown to 1600px, values picked one by one
    # instead of <Hepsi>. Without that button the query cannot be built, so the measure
    # comes back as zero indicators. Left here named rather than deleted: the next person
    # to notice "ölenin medeni durumu" in the breakdown list should find out here that it
    # has already been tried, rather than spending the afternoon finding out again.
    # ("olum-medeni", DEATHS, "İkametgah yerine göre ölüm", "medeni"),
    # How old the baby was when it died, in days and in months — neonatal against
    # post-neonatal. Not the month of death, which is the calendar breakdown above.
    ("bebek-olum-gun", DEATHS, "İkametgah yerine göre ölüm", "Günlük bebek"),
    ("bebek-olum-ay", DEATHS, "İkametgah yerine göre ölüm", "Aylık bebek"),
    ("evlenme", MARRIAGES, "Evlenme sayısı", False),  # 1
    ("kaba-evlenme-hizi", MARRIAGES, "Kaba evlenme", False),  # 1
    ("evlenme-yasi-erkek", MARRIAGES, "Erkeğin ortalama evlenme", False),  # 1
    ("evlenme-yasi-kadin", MARRIAGES, "Kadının ortalama evlenme", False),  # 1
    ("ilk-evlenme-yasi-erkek", MARRIAGES, "Erkeğin ortalama ilk evlenme", False),  # 1
    ("ilk-evlenme-yasi-kadin", MARRIAGES, "Kadının ortalama ilk evlenme", False),  # 1
    ("bosanma", DIVORCES, "Boşanma sayısı", False),
    # Marriage and divorce at district level, one indicator each and twelve years — the
    # cheapest thing in either topic and the only district-level rows they have. Both are
    # named unlike their province measures: marriages by the place the wedding happened,
    # divorces by the man's registered address, because that is what MEDAS publishes below
    # the province. Those are different questions from the provincial series (residence of
    # the couple), so they are stored as what they are rather than as "the same measure,
    # lower level" — see the note in the dictionary.
    ("evlenme-ilce", MARRIAGES, "lçelere göre evlenmeler", False),  # 1
    ("bosanma-ilce", DIVORCES, "Erkeğin ikametgah yeri", False),  # 1  # 1
    ("kaba-bosanma-hizi", DIVORCES, "Kaba boşanma", False),  # 1
    # Orgun egitim: okul/derslik/sube/ogretmen/ogrenci sayimi yalniz il duzeyine kadar
    # iniyor (ilce yok) -- yalniz "Okuma yazma orani" ilce duzeyine iniyor, o yuzden
    # ayri, fetch_medas_districts.py --konu orgun ile cekiliyor (bkz. docs/medas.md).
    ("orgun-okul", ORGUN, "Okul sayısı", True),  # 6, egitim seviyeleri
    ("orgun-ogrenci", ORGUN, "Öğrenci sayısı", True),  # 12, egitim seviyeleri x cinsiyet
    ("orgun-sube", ORGUN, "Şube sayısı", True),  # 6
    ("orgun-derslik", ORGUN, "Derslik sayısı", True),  # 6
    ("orgun-ogretmen", ORGUN, "Öğretmen sayısı", True),  # 12, egitim seviyeleri x cinsiyet
    ("orgun-net-okullasma", ORGUN, "Net okullaşma oranı", True),  # 8
    ("orgun-brut-okullasma", ORGUN, "Brüt okullaşma oranı", True),  # 6
    ("orgun-okul-basina", ORGUN, "Okul başına düşen öğrenci", True),  # 5
    ("orgun-sube-basina", ORGUN, "Şube başına düşen öğrenci", True),  # 5
    ("orgun-ogretmen-basina", ORGUN, "Öğretmen başına düşen öğrenci", True),  # 5
    ("orgun-derslik-basina", ORGUN, "Derslik başına düşen öğrenci", True),  # 4
]

#: The Düzey box labels for the levels kept here.
LEVELS = {
    "country": "Türkiye",
    "province": "İBBS3 (İl Düzeyi)",
    "district": "İlçe Düzeyi",
    "nuts2": "İBBS2 (26 Bölge)",
}


#: Measures published for the country and nowhere else. The single-year life table is
#: the case: TÜİK computes it nationally because a province's deaths at age 93 are a
#: handful of people and the resulting probability would be noise.
#: Deaths by single year of age belongs here for a reason worth writing down: the measure
#: itself offers İBBS3, but ticking the `Ölenin yaşı` breakdown takes the province option
#: out of the Düzey box — the level list narrows to Türkiye alone. It is the same rule the
#: neighbourhood fetcher meets from the other side (tick the age split and Köy drops out).
#: So the finest grain K16 asks for stops at the country here, and the province series
#: keeps the age *group* it already has.
#: Birthplace for Türkiye as a whole is a country-only measure by construction.
COUNTRY_ONLY = {"hayat-tablosu", "olum-tek-yas", "dogum-yeri-tr"}


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
    # The region-to-region flow matrices exist at one level and only one: the breakdown is
    # the *other* end of the flow, so "İBBS2 bölgeler arası" asked for at province level
    # would be a 26-column table of provinces, which is not a matrix and not a thing TÜİK
    # publishes.
    if name.endswith("-ibbs2"):
        return ["nuts2"]
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

    # Compared with whitespace folded: the waste topic writes its measure names with
    # non-breaking spaces, and a plain `in` found none of its eight measures.
    wanted = " ".join(hint.split())
    items = page.locator(".z-listitem")
    index = next(
        (
            i
            for i in range(items.count())
            if wanted in " ".join(items.nth(i).inner_text().split())
        ),
        None,
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

    add_indicators(page)

    # Waited for, not read straight after the click: the count is written by the server
    # round trip the click starts, so reading it immediately gives the count from before.
    settle(page)
    return counted(page, INDICATORS)


def select_by_option(page, label: str) -> bool:
    """Pick `label` in whichever select offers it, scrolling to the box if it is off view.

    Matching on the option list rather than on visibility: the boxes live in tabs that
    keep their widgets in the DOM, so several selects match a generic query, but only one
    of them carries this option.
    """
    for index in range(page.locator("select").count()):
        select = page.locator("select").nth(index)
        try:
            if label not in select.locator("option").all_inner_texts():
                continue
        except PlaywrightError:
            continue
        # Scrolling is best-effort and must not disqualify the box: a select that cannot
        # be scrolled to is usually still selectable, and treating the failure as "wrong
        # box" skipped the only box that had the option.
        try:
            select.scroll_into_view_if_needed(timeout=5000)
        except PlaywrightError:
            pass
        try:
            select.select_option(label=label)
        except PlaywrightError:
            continue
        settle(page, "secildi: " + label)
        return True
    return False


def add_indicators(page) -> bool:
    """Press "Göstergeleri Ekle", scrolling to it first and dispatching if it hides.

    Ticking the value lists grows the panel, and past a certain length the button leaves
    the visible area — `is_visible()` turns False and Playwright declines to click what a
    user could not have clicked. One breakdown stays short enough to hide this; ölüm ×
    medeni durum, at two lists and sixteen rows, does not. The measure then came back
    with an indicator count of zero and was reported as "kirilim tutmadi", though the
    query underneath it was built correctly — the same shape of silence the district
    fetcher hit behind its modal mask, and the same answer: scroll, then dispatch.
    """
    for label in ("Göstergeler Ekle", "Göstergeleri Ekle"):
        button = page.get_by_text(label, exact=True)
        if not button.count():
            continue
        try:
            button.first.scroll_into_view_if_needed(timeout=5000)
        except PlaywrightError:
            pass
        if click_exact(page, label):
            return True

        # Still out of view. Two things were tried before this and neither works: a
        # dispatched click gets ZK to report success without building the query (worse
        # than not clicking, since the count then reads zero with no error), and growing
        # the viewport does not bring the button back because ZK sizes the panel itself.
        # `force` is the one that fits: it skips only the actionability check, and still
        # sends the real mouse sequence ZK listens for.
        try:
            button.first.click(force=True, timeout=10000)
        except PlaywrightError as error:
            print("   Ekle tiklanamadi:", str(error).splitlines()[0][:60])
            continue
        settle(page, "zorlandi: " + label)
        return True
    return False


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

    # Chosen by what the box *offers*, not by whether it is on screen. A long indicator
    # panel pushes the Düzey box out of view, `is_visible()` turns False, the loop finds
    # nothing and falls through — leaving the query at whatever level was already set,
    # which is Türkiye. Nothing errors; the download simply answers a different question
    # than the one asked, under a file name that says otherwise.
    if not select_by_option(page, label):
        print("   duzey kutusu bulunamadi:", label)
        return False

    # The province box under it, where there is one. Absent at country level, and that is
    # the right outcome — nothing to narrow.
    select_by_option(page, "HEPSİ")

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

    # The level box can fail to take without erroring, and then the query runs at whatever
    # level was already selected. That is how seventeen files named `-province-` came back
    # holding nothing but Türkiye-TR: the download succeeded, the name said province, the
    # contents were the country, and loading them would have written the national total
    # into eighty-one provinces. A level that means many areas must come back with many.
    if level != "country" and areas < 2:
        print("   duzey tutmadi:", level, "icin alan =", areas)
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
