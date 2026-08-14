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

TOPIC = "Adrese Dayalı Nüfus Kayıt Sistemi Sonuçları"

CELL_LIMIT = 50000

PAUSE = 4.0

INDICATORS = re.compile(r"g[oö]sterge adedi:\s*(\d+)", re.IGNORECASE)
PICKED = re.compile(r"d[uü]zey adedi:\s*(\d+)", re.IGNORECASE)

#: What to fetch: a short name for the file, an ascii-safe fragment of the measure's label
#: (MEDAS serves ISO-8859-9 under a lying header, so Turkish letters cannot be matched),
#: and whether the measure's breakdowns should be opened. The indicator counts in the
#: comments are measured, not guessed — see raw/medas/kesif/.
MEASURES = [
    ("yogunluk", "Nüfus yoğunluğu", False),  # 1
    ("cinsiyet-orani", "Cinsiyet oranı", False),  # 1
    ("artis-hizi", "Yıllık nüfus artış hızı", False),  # 1
    ("bagimlilik-cocuk", "Çocuk bağımlılık", False),  # 1
    ("bagimlilik-yasli", "Yaşlı bağımlılık", False),  # 1
    ("bagimlilik-toplam", "Toplam yaş bağımlılık", False),  # 1
    ("hane-buyuklugu", "Ortalama hanehalkı büyüklüğü", False),  # 1
    ("hane-sayisi", "Toplam hanehalkı sayısı", False),  # 1
    ("hane-tipleri", "Hanehalkı tiplerine göre", True),  # 9
    ("goc-net", "Bölgelerin net göç bilgileri", False),  # 1
    ("goc-net-hizi", "Bölgelerin net göç hızı", False),  # 1
    ("goc-aldigi", "Bölgelerin aldığı göç", True),  # 28
    ("goc-verdigi", "Bölgelerin verdiği göç", True),  # 28
    ("yabanci-uyruklu", "Yabancı uyruklu nüfus", True),  # 2
    ("goc-disaridan", "Yurt dışından Türkiye'ye gelen göç", False),  # 1
    ("goc-disariya", "Türkiye'den yurt dışına giden göç", False),  # 1
]

#: The Düzey box labels for the levels kept here.
LEVELS = {"country": "Türkiye", "province": "İBBS3 (İl Düzeyi)"}


def counted(page, pattern) -> int:
    found = pattern.search(page.inner_text("body"))
    return int(found.group(1)) if found else 0


def target_path(name: str, level: str):
    return OUT / ("nufus-" + name + "-" + level + ".csv")


def build_query(page, hint: str, breakdowns: bool) -> int:
    """Topic and measure, with its breakdowns opened or not. Returns the indicator count."""
    page.goto(URL, wait_until="networkidle")
    page.locator("select").first.select_option(label=TOPIC)
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
        # A tick is a toggle and the mandatory ones arrive already on (docs/medas.md).
        for row, _ in visible_rows(page):
            if not is_ticked(page, row):
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


def fetch(page, name: str, hint: str, breakdowns: bool, level: str) -> bool:
    """One measure at one level, every year the page offers."""
    target = target_path(name, level)

    count = build_query(page, hint, breakdowns)
    if not count:
        return False

    click_exact(page, "İleri")
    years = offered_years(page)
    if not years:
        print("   yil listesi bos")
        return False
    for year in years:
        row = page.locator(".z-listitem", has_text=str(year)).first
        if not row.count():
            continue
        box = row.locator(".z-listitem-checkbox")
        (box if box.count() else row).click()
        settle(page)

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

    areas = 0
    for _ in range(2):
        if not check_visible(page, ".z-listheader-checkable"):
            print("   alan listesi isaretlenemedi")
            return False
        areas = counted(page, PICKED)
        if areas:
            break
        settle(page)
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
        # Not expected for this batch — every one of them was measured as narrow. Said
        # plainly rather than silently truncated, because a measure that outgrew this
        # script belongs in one of the chunking ones.
        print("   · limit asildi, bu olcum bu betige sigmiyor")
        return False

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

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)

        for name, hint, breakdowns in wanted:
            for level in LEVELS:
                if target_path(name, level).exists():
                    print("=", name, level, "zaten var, atlandi")
                    continue
                print("=", name, level)
                for attempt in (1, 2):
                    try:
                        if fetch(page, name, hint, breakdowns, level):
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
