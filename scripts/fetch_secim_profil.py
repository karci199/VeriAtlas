"""Voter, candidate and elected-candidate profiles from the TÜİK election application.

These live behind the application's menu page, not on the results page the vote fetcher
drives, which is why they were missed for so long: `secim.zul` opened directly shows ten
result tables and nothing else. `menusecim.zul` is the actual front door and offers four
doors — results, voter profile, candidate profile, elected-candidate profile.

The profile pages cross **two** variables at a time. One is chosen from Yaş grubu /
Eğitim durumu / Medeni durum, and a checkbox — "2'nci değişken istiyor musunuz?" — opens
a second list holding whichever two remain. So the three variables are covered by three
pairs, and each pair is one pass over the provinces.

Level goes down to district: Türkiye / İBBS1 / İBBS2 / İBBS3 (İl) / İBBS4 (İlçe). At
district level the province box must be answered and its district box offers
"<< Tüm İlçeler >>", so one report per province carries all of its districts.

Output: `<data root>/secim/profil/<sayfa>/<yil>__<degisken1>__<degisken2>__<il>.html`

Run:  uv run python scripts/fetch_secim_profil.py secmen
      uv run python scripts/fetch_secim_profil.py secmen aday kazanan
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
import time
import urllib.request

sys.path.insert(0, "scripts")

from zk_client import ZK

HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
OUT = HAM / "secim" / "profil"

PAGES = {
    "secmen": "secimsecmen.zul",
    "aday": "secimaday.zul",
    "kazanan": "secimadaykazanan.zul",
}

YEARS = ["2023", "2018", "2015 (1 Kasım)", "2015 (7 Haziran)", "2011"]

#: The three pages are not the same shape, and assuming they were is what this table is
#: here to prevent. The candidate pages carry a fourth variable — which party the
#: candidate stood for — and stop one level higher: a candidacy belongs to a province's
#: electoral district, so there is no district row to ask for. The voter pages have no
#: party (a voter does not have one) but do reach the district.
PAGE_VARS = {
    "secmen": ["Yaş grubu", "Eğitim durumu", "Medeni durum"],
    "aday": ["Yaş grubu", "Eğitim durumu", "Medeni durum", "Siyasi parti / Bağımsız"],
    "kazanan": [
        "Yaş grubu",
        "Eğitim durumu",
        "Medeni durum",
        "Siyasi parti / Bağımsız",
    ],
}

#: Abroad is a separate scope with its own level list — no province, no district; the
#: deepest it goes is the consulate. Asked for with `--yurtdisi`.
YURTDISI_LEVEL = "Ülke temsilcilikler"

PAGE_LEVEL = {
    "secmen": "İBBS-Düzey4 (İlçe)",
    "aday": "İBBS-Düzey3 (İl)",
    "kazanan": "İBBS-Düzey3 (İl)",
}

ALL_DISTRICTS = "&lt;&lt; Tüm İlçeler &gt;&gt;"
ALL_LEVELS = "&lt;&lt; Tüm Düzeyler &gt;&gt;"
SECOND = "2'nci değişken istiyor musunuz?"


def pairs(page: str) -> list[tuple[str, str]]:
    """Each variable crossed with each later one — no pair fetched twice."""
    names = PAGE_VARS[page]
    return [(a, b) for i, a in enumerate(names) for b in names[i + 1 :]]


PAUSE = 1.0


def slug(text: str) -> str:
    text = (
        text.replace("ı", "i")
        .replace("İ", "i")
        .replace("ş", "s")
        .replace("Ş", "s")
        .replace("ğ", "g")
        .replace("Ğ", "g")
        .replace("ü", "u")
        .replace("Ü", "u")
        .replace("ö", "o")
        .replace("Ö", "o")
        .replace("ç", "c")
        .replace("Ç", "c")
    )
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def dest(
    page: str, year: str, pair: tuple[str, str], province: str, abroad: bool = False
) -> pathlib.Path:
    name = f"{slug(year)}__{slug(pair[0])}__{slug(pair[1])}__{slug(province)}.html"
    return OUT / (page + ("-yurtdisi" if abroad else "")) / name


def open_page(page: str, year: str, pair: tuple[str, str], abroad: bool = False) -> ZK:
    """A session with the year, the scope and both variables already answered."""
    z = ZK(PAGES[page], timeout=300)
    z.check(year)
    try:
        z.check("Yurt dışı seçmen" if abroad else "Yurt içi seçmen")
    except KeyError:
        pass  # only the voter page splits home from abroad
    z.check(pair[0])
    z.check(SECOND)
    z.pick("2 inci değişkenler:", pair[1], exact=True)
    z.check(YURTDISI_LEVEL if abroad else PAGE_LEVEL[page])
    return z


def provinces(
    page: str, year: str, pair: tuple[str, str], abroad: bool = False
) -> list[str]:
    """What one pass has to walk: every province for the voter page, one whole-country
    report for the candidate pages, whose level box answers for all of them at once."""
    if abroad:
        z = open_page(page, year, pair, abroad=True)
        return [p for p in z.options("Ülke Seçimi:")[1] if "Tüm" not in p]
    if page != "secmen":
        return [ALL_LEVELS]
    z = open_page(page, year, pair)
    return [p for p in z.options("İl Seçimi:")[1] if "Tüm" not in p]


def fetch_one(
    z: ZK,
    page: str,
    year: str,
    pair: tuple[str, str],
    province: str,
    abroad: bool = False,
) -> None:
    if abroad:
        z.pick("Ülke Seçimi:", province, exact=True)
    elif page == "secmen":
        z.pick("İl Seçimi:", province, exact=True)
        z.pick("İlçe Seçimi:", ALL_DISTRICTS, exact=True)
    else:
        z.pick("Düzey Seçimi:", province, exact=True)
    z.click("Raporu Oluştur")
    if not z.redirect:
        raise RuntimeError("rapor url yok")
    data = urllib.request.urlopen(
        z.redirect.replace("http://", "https://"), timeout=300
    ).read()
    if len(data) < 2000:
        raise RuntimeError(f"kucuk rapor {len(data)}")
    path = dest(page, year, pair, province)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def sweep(
    page: str, year: str, pair: tuple[str, str], names: list[str], abroad: bool = False
) -> list[str]:
    """One pass over the areas still missing for this year and variable pair."""
    todo = [p for p in names if not dest(page, year, pair, p, abroad).exists()]
    if not todo:
        return []
    print(f"  {year} {pair[0]} x {pair[1]}: {len(todo)} il eksik", flush=True)
    z, used = None, 0
    for province in todo:
        try:
            if z is None or used >= 40:
                z, used = open_page(page, year, pair, abroad), 0
            fetch_one(z, page, year, pair, province, abroad)
            used += 1
        except Exception as error:  # noqa: BLE001 - log and carry on
            print(f"    HATA {province}: {str(error)[:80]}", flush=True)
            z = None
        time.sleep(PAUSE)
    return [p for p in names if not dest(page, year, pair, p, abroad).exists()]


def fetch(page: str, rounds: int = 8, abroad: bool = False) -> None:
    """Every year and every variable pair, swept until a pass gains nothing."""
    for year in YEARS:
        for pair in pairs(page):
            try:
                names = provinces(page, year, pair, abroad)
            except Exception as error:  # noqa: BLE001 - this combination may not exist
                print(f"  {year} {pair}: il listesi alinamadi ({str(error)[:60]})")
                continue
            if not names:
                print(f"  {year} {pair}: il listesi bos, atlandi")
                continue
            missing = None
            for _ in range(rounds):
                left = sweep(page, year, pair, names, abroad)
                if not left:
                    break
                if missing is not None and len(left) >= missing:
                    print(f"    kazanc yok, {len(left)} il eksik:", ", ".join(left[:8]))
                    break
                missing = len(left)


def main(argv: list[str]) -> None:
    abroad = "--yurtdisi" in argv
    wanted = [a for a in argv if not a.startswith("--")] or list(PAGES)
    for page in wanted:
        if page not in PAGES:
            raise SystemExit(f"bilinmeyen sayfa: {page} ({', '.join(PAGES)})")
        print("==", page, PAGES[page], "yurtdisi" if abroad else "", flush=True)
        fetch(page, abroad=abroad)
        klasor = OUT / (page + ("-yurtdisi" if abroad else ""))
        n = len(list(klasor.glob("*.html"))) if klasor.exists() else 0
        print(f"== {page} bitti: {n} rapor", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
