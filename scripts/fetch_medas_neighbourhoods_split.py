"""Fetch neighbourhood population for one province in year chunks.

The plain fetcher asks for every year at once, which is right for most provinces.
It is not right for all of them. MEDAS states its cap as
`gösterge × düzey × zaman ≤ 50000`, but that arithmetic does not predict which
provinces it refuses: Gaziantep's 1,562 neighbourhoods pass thirteen years
(40,612 cells) while İstanbul is refused well under the ceiling. The refusal is
silent — the level count simply stays 0 for as long as it is waited for, and a
report asked for anyway never finishes building.

So the chunk here is the province *and* a slice of years, and the slice is found
by halving until MEDAS accepts rather than sized from a formula that does not
hold. One year always works, so the halving terminates. Each slice lands in its
own file — `nufus-mahalle-İSTANBUL-2013_2015.csv` — and `--merge` stitches a
province's slices into the single file the loader expects, the same name the
plain fetcher would have written.

Run:  uv run python scripts/fetch_medas_neighbourhoods_split.py İSTANBUL
      uv run python scripts/fetch_medas_neighbourhoods_split.py İSTANBUL --merge
"""

import sys
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from fetch_medas_neighbourhoods import (
    CELL_LIMIT,
    OUT,
    PAUSE,
    fetch_province,
    provinces_offered,
    target_path,
)

#: Two indicators per area per year, and a margin so a province that grew since
#: the count was taken does not land exactly on the ceiling.
SAFETY = 0.8


def chunk_path(province: str, years: list[int]):
    stem = target_path(province).stem
    return OUT / f"{stem}-{years[0]}_{years[-1]}.csv"


def chunks_for(years: list[int], areas: int) -> list[list[int]]:
    """Year slices that keep 2 × areas × len(slice) under MEDAS's cell limit."""
    per = max(1, int(CELL_LIMIT * SAFETY / (2 * areas)))
    return [years[i : i + per] for i in range(0, len(years), per)]


def merge(province: str) -> None:
    """Stitch a province's year slices into the file the loader reads.

    MEDAS repeats its five-line preamble in every export, and only the first row
    of a year block carries the year — later rows leave the column blank. So the
    preamble is taken from the first slice only, and body lines are carried over
    verbatim; the loader already handles the blank-year continuation.
    """
    parts = sorted(OUT.glob(target_path(province).stem + "-*.csv"))
    if not parts:
        print("parca yok:", province)
        return
    head: list[str] = []
    body: list[str] = []
    for index, part in enumerate(parts):
        lines = part.read_text(encoding="utf-8-sig").splitlines()
        start = next((i for i, ln in enumerate(lines) if ln[:4].isdigit()), 0)
        if index == 0:
            head = lines[:start]
        body += [ln for ln in lines[start:] if ln.strip(" |")]
        print(f"  {part.name}: {len(lines) - start} satir")
    target = target_path(province)
    target.write_text("\n".join(head + body) + "\n", encoding="utf-8-sig")
    print(f"birlestirildi -> {target.name}  {len(body)} satir, {len(parts)} parca")


def already_have(province: str, years: list[int]) -> bool:
    """Whether these years are already on disk, either as their own slice or
    inside the province's full-series file."""
    return target_path(province).exists() or chunk_path(province, years).exists()


def one_province(page, province: str, years: list[int], scoped: bool) -> None:
    print("=", province, years[0] if len(years) == 1 else f"{years[0]}-{years[-1]}")

    # A probe with every year asked for. Too large is the expected answer for a
    # whole-series İstanbul, and the area count it comes back with is what sizes
    # the slices. A single year usually fits, and then there is nothing to split.
    areas = fetch_province(page, province, years)

    if not areas and not target_path(province).exists() and len(years) > 1:
        # MEDAS refused the tick-all outright: the level count stays 0 however
        # long it is waited for, and no count means no size to divide by. Its
        # own stated rule does not explain which provinces this happens to —
        # Gaziantep's 1,562 neighbourhoods pass thirteen years while İstanbul's
        # 961 do not — so the years are halved and tried again rather than
        # reasoned about. One year always works, so this terminates.
        half = max(1, len(years) // 2)
        print(
            f"   duzey sayisi gelmedi, {len(years)} yil -> {half}+"
            f"{len(years) - half} olarak bolunuyor"
        )
        for part in (years[:half], years[half:]):
            if not part:
                continue
            if chunk_path(province, part).exists():
                print("  ", chunk_path(province, part).name, "zaten var, atlandi")
                continue
            one_province(page, province, part, True)
        return

    if not areas:
        # fetch_province writes the province's plain file name, which means "every
        # published year". A subset must not wear that name or the loader would
        # read a partial series as a complete one.
        plain = target_path(province)
        if scoped and plain.exists():
            # replace(), not rename(): on Windows rename() raises when the target exists.
            plain.replace(chunk_path(province, years))
            print("   ->", chunk_path(province, years).name)
        elif plain.exists():
            print("   tek seferde indi")
        else:
            # No file and nothing to split on: the walk failed somewhere rather
            # than succeeding. Saying "indi" here hid nine provinces.
            print("   INMEDI — dosya yok, bolunecek bir sayi da donmedi")
        return

    slices = chunks_for(years, areas)
    print(
        f"   {areas} mahalle, {len(years)} yil -> {len(slices)} parca "
        f"({len(slices[0])} yil/parca)"
    )

    for years_slice in slices:
        path = chunk_path(province, years_slice)
        if path.exists():
            print("  ", path.name, "zaten var, atlandi")
            continue
        print("  ", province, years_slice)
        for attempt in (1, 2):
            try:
                # fetch_province writes to the province's plain path, so the slice
                # is renamed into place before the next one overwrites it.
                plain = target_path(province)
                if plain.exists():
                    plain.unlink()
                left = fetch_province(page, province, years_slice)
                if plain.exists():
                    plain.replace(path)
                    print("   ->", path.name, path.stat().st_size, "bayt")
                    break
                if left:
                    print("   hala buyuk:", left, "mahalle")
                    break
            except PlaywrightError as error:
                print("   HATA:", type(error).__name__, str(error)[:160])
            if attempt == 1:
                print("   · tekrar deneniyor")
                time.sleep(PAUSE)
        time.sleep(PAUSE)


def main() -> None:
    argv = sys.argv[1:]
    wanted_years: list[int] = []
    if "--years" in argv:
        wanted_years = [int(y) for y in argv[argv.index("--years") + 1].split(",")]
        argv.pop(argv.index("--years") + 1)
    everything = "--all" in argv
    asked = [a for a in argv if not a.startswith("--")]
    if not asked and not everything:
        print(__doc__)
        return

    if "--merge" in argv:
        for province in asked:
            merge(province.upper())
        return

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1600, "height": 1000}, accept_downloads=True
        )
        page.set_default_timeout(60000)

        names, years = provinces_offered(page)
        if wanted_years:
            missing = [y for y in wanted_years if y not in years]
            if missing:
                print("MEDAS bu yillari sunmuyor:", missing)
                browser.close()
                return
            years = wanted_years
        print("yillar:", years, " il adedi:", len(names))

        wanted = names if everything else [a.upper() for a in asked]
        for province in wanted:
            if province not in names:
                print("=", province, "listede yok - MEDAS yazimi farkli olabilir")
                continue
            if already_have(province, years):
                print("=", province, "zaten var, atlandi")
                continue
            try:
                one_province(page, province, years, bool(wanted_years))
            except PlaywrightError as error:
                print("   HATA:", type(error).__name__, str(error)[:160])
            time.sleep(PAUSE)

        browser.close()


if __name__ == "__main__":
    main()
