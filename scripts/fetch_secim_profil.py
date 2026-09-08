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

VARIABLES = ["Yaş grubu", "Eğitim durumu", "Medeni durum"]

#: Each variable crossed with each later one — three passes cover all three variables
#: without fetching the same pair twice.
PAIRS = [(a, b) for i, a in enumerate(VARIABLES) for b in VARIABLES[i + 1 :]]

ALL_DISTRICTS = "&lt;&lt; Tüm İlçeler &gt;&gt;"
LEVEL = "İBBS-Düzey4 (İlçe)"
SECOND = "2'nci değişken istiyor musunuz?"

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


def dest(page: str, year: str, pair: tuple[str, str], province: str) -> pathlib.Path:
    name = f"{slug(year)}__{slug(pair[0])}__{slug(pair[1])}__{slug(province)}.html"
    return OUT / page / name


def open_page(page: str, year: str, pair: tuple[str, str]) -> ZK:
    """A session with the year, the scope and both variables already answered."""
    z = ZK(PAGES[page], timeout=300)
    z.check(year)
    try:
        z.check("Yurt içi seçmen")
    except KeyError:
        pass  # only the voter page splits home from abroad
    z.check(pair[0])
    z.check(SECOND)
    z.pick("2 inci değişkenler:", pair[1], exact=True)
    z.check(LEVEL)
    return z


def provinces(page: str, year: str, pair: tuple[str, str]) -> list[str]:
    z = open_page(page, year, pair)
    return [p for p in z.options("İl Seçimi:")[1] if "Tüm" not in p]


def fetch_one(
    z: ZK, page: str, year: str, pair: tuple[str, str], province: str
) -> None:
    z.pick("İl Seçimi:", province, exact=True)
    z.pick("İlçe Seçimi:", ALL_DISTRICTS, exact=True)
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


def sweep(page: str, year: str, pair: tuple[str, str], names: list[str]) -> list[str]:
    """One pass over the provinces still missing for this year and variable pair."""
    todo = [p for p in names if not dest(page, year, pair, p).exists()]
    if not todo:
        return []
    print(f"  {year} {pair[0]} x {pair[1]}: {len(todo)} il eksik", flush=True)
    z, used = None, 0
    for province in todo:
        try:
            if z is None or used >= 40:
                z, used = open_page(page, year, pair), 0
            fetch_one(z, page, year, pair, province)
            used += 1
        except Exception as error:  # noqa: BLE001 - log and carry on
            print(f"    HATA {province}: {str(error)[:80]}", flush=True)
            z = None
        time.sleep(PAUSE)
    return [p for p in names if not dest(page, year, pair, p).exists()]


def fetch(page: str, rounds: int = 8) -> None:
    """Every year and every variable pair, swept until a pass gains nothing."""
    for year in YEARS:
        for pair in PAIRS:
            try:
                names = provinces(page, year, pair)
            except Exception as error:  # noqa: BLE001 - this combination may not exist
                print(f"  {year} {pair}: il listesi alinamadi ({str(error)[:60]})")
                continue
            if not names:
                print(f"  {year} {pair}: il listesi bos, atlandi")
                continue
            missing = None
            for _ in range(rounds):
                left = sweep(page, year, pair, names)
                if not left:
                    break
                if missing is not None and len(left) >= missing:
                    print(f"    kazanc yok, {len(left)} il eksik:", ", ".join(left[:8]))
                    break
                missing = len(left)


def main(argv: list[str]) -> None:
    wanted = argv or list(PAGES)
    for page in wanted:
        if page not in PAGES:
            raise SystemExit(f"bilinmeyen sayfa: {page} ({', '.join(PAGES)})")
        print("==", page, PAGES[page], flush=True)
        fetch(page)
        n = len(list((OUT / page).glob("*.html"))) if (OUT / page).exists() else 0
        print(f"== {page} bitti: {n} rapor", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
