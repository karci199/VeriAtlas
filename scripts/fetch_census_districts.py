"""District tables of the 1965-2000 population censuses, from TÜİK's census applications.

TÜİK serves each census as a ZK application on biruni.tuik.gov.tr (menu:
`nufusmenuapp/`): 2000 `nufusapp`, 1990 `nufus90app`, 1985 `nufus85app`, 1980 and
1965-1975 `nufus80app` (`?yil=`). From 1985 the second tab, "Sosyal ve Demografik Nitelikler",
answers one variable at a time (sex, single age, five-year age group, literacy,
education, place of birth, marital status, ...) for Türkiye, a province, the districts of
a province, or its towns and villages, split into district total / district centre /
towns and villages.

One report per (census, province, variable): level "İlçe", the province, "<< Tüm
İlçeler >>", the chosen settlement detail, the variable, HTML format. The report is a
plain HTML page on rapory.tuik.gov.tr (windows-1254) and is saved as it comes; parsing is
the adapter's job.

The page is driven over plain HTTP with `zk_client.ZK` (component ids change per session,
so everything is found by its label). Two things the page does not say:

  * the report button reads the selected tab on the server, so the tab must be selected
    with an `onSelect` on the Tabbox first, otherwise the answer is "İdari birim seçiniz"
  * the variable box looks multi-select but the report uses only the first variable;
    one variable per report

Output: C:/veri-ham/tuik_sayim/<year>/<plate-less province name>-<variable>-<detail>.html.
The same command resumes: an existing non-empty file is skipped.

Run:  python scripts/fetch_census_districts.py [--yil 1990 ...] [--degisken "Beşerli Yaş Grubu"]
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import zk_client as z

RAW = Path(os.environ.get("VERIATLAS_RAW") or "C:/veri-ham")
OUT = RAW / "tuik_sayim"
APPS = {
    2000: ("nufusapp", "idari.zul"),
    1990: ("nufus90app", "idari.zul"),
    1985: ("nufus85app", "idari.zul"),
    1980: ("nufus80app", "idari.zul"),
    1975: ("nufus80app", "idari.zul?yil=1975"),
    1970: ("nufus80app", "idari.zul?yil=1970"),
    1965: ("nufus80app", "idari.zul?yil=1965"),
}
#: 1965-1980 (`nufus80app`, ZK 2.3) have only the administrative tab: population totals by
#: settlement, no age or other characteristics. The social tab exists from 1985.
SOCIAL_TAB_YEARS = [2000, 1990, 1985]
DETAILS = {"ilce": "İlçe toplamı", "sehir": "Şehir", "koy": "Belde ve Köyler"}
RE_SELECT = re.compile(r'<select id="(z_\w+)"[^>]*>(.*?)</select>', re.DOTALL)
RE_OPTION = re.compile(r'<option id="(z_\w+)"[^>]*>([^<]*)<')


def log(*parts) -> None:
    print(dt.datetime.now().strftime("%H:%M:%S"), *parts, flush=True)


def selects(text: str) -> dict[str, list[tuple[str, str]]]:
    return {
        sid: [(i, html.unescape(t).strip()) for i, t in RE_OPTION.findall(body)]
        for sid, body in RE_SELECT.findall(text)
    }


def box_with(text: str, test) -> tuple[str, dict[str, str]]:
    """The newest select whose options pass `test`: (uuid, {label: option uuid})."""
    for sid, options in reversed(list(selects(text).items())):
        if options and test([t for _, t in options]):
            return sid, {t: i for i, t in options}
    raise KeyError("liste bulunamadi")


class Census:
    def __init__(self, year: int):
        app, page = APPS[year]
        z.BASE = f"https://biruni.tuik.gov.tr/{app}/"
        self.k = z.ZK(page=page)
        tabbox = re.search(r'id="(z_\w+)"[^>]*z\.type="zul\.tab\.Tabbox"', self.k.html)
        tabs = re.findall(r'id="(z_\w+)" z\.type="Tab"', self.k.html)
        self.k.event(tabbox.group(1), "onSelect", tabs[1])
        # the social tab's level box is the first four-option box after the first tab's
        self.level, levels = box_with(
            self.k.html, lambda ts: len(ts) == 4 and ts[0] == "Türkiye"
        )
        self.district_level = next(v for t, v in levels.items() if t.startswith("İlç"))

    def select(self, box: str, option: str) -> str:
        body = self.k.event(box, "onSelect", option)
        self.k.settle(body)
        return body

    def provinces(self) -> dict[str, str]:
        body = self.select(self.level, self.district_level)
        self.province_box, found = box_with(body, lambda ts: len(ts) > 50)
        return found

    def report(self, province: str, variable: str, detail: str) -> bytes:
        body = self.select(self.province_box, self.provinces_map[province])
        box, found = box_with(body, lambda ts: ts[0].startswith("<<"))
        body = self.select(box, found[next(iter(found))])
        box, found = box_with(
            body, lambda ts: any(t.startswith("İlçe top") for t in ts)
        )
        key = next(t for t in found if t.startswith(detail))
        body = self.select(box, found[key])
        box, found = box_with(body, lambda ts: "Cinsiyet" in ts)
        if variable not in found:
            raise KeyError(f"degisken yok: {variable!r} ({list(found)})")
        self.select(box, found[variable])
        radios = list(
            dict.fromkeys(
                re.findall(
                    r'<span id="(z_\w+)" z\.type="zul\.widget\.Radio"', self.k.html
                )
            )
        )
        buttons = list(
            dict.fromkeys(
                re.findall(
                    r'<button[^>]*id="(z_\w+)"[^>]*z\.type="zul\.widget\.Button"',
                    self.k.html,
                )
            )
        )
        # the second tab's first format radio is HTML; its report button is the second
        self.k.event(radios[3], "onCheck", "true")
        self.k.redirect = None
        answer = self.k.event(buttons[1], "onClick")
        self.k.settle(answer)
        if not self.k.redirect:
            said = [
                html.unescape(x).strip()
                for x in re.findall(r">([^<>]{3,200})<", answer)
                if x.strip()
            ]
            raise RuntimeError(f"rapor yok: {said[:6]}")
        url = self.k.redirect.replace("http://", "https://")
        return self.k.opener.open(url, timeout=180).read()


def safe(name: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU-")
    return re.sub(r"[^A-Za-z0-9-]", "", name.translate(table)).lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yil", type=int, nargs="*", default=SOCIAL_TAB_YEARS)
    ap.add_argument("--degisken", nargs="*", default=["Beşerli Yaş Grubu", "Tek Yaş"])
    ap.add_argument("--ayrinti", nargs="*", default=["ilce"], choices=list(DETAILS))
    args = ap.parse_args()
    for year in args.yil:
        census = Census(year)
        census.provinces_map = census.provinces()
        names = list(census.provinces_map)
        log("==", year, len(names), "il")
        done = 0
        for n, province in enumerate(names, 1):
            for variable in args.degisken:
                for detail in args.ayrinti:
                    target = (
                        OUT
                        / str(year)
                        / f"{safe(province)}-{safe(variable)}-{detail}.html"
                    )
                    if target.exists() and target.stat().st_size > 1000:
                        continue
                    for attempt in (1, 2, 3):
                        try:
                            data = census.report(province, variable, DETAILS[detail])
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(data)
                            done += 1
                            log(
                                f"   {year} {n}/{len(names)} {province} {variable} {detail} {len(data)} bayt"
                            )
                            break
                        except Exception as error:  # noqa: BLE001
                            log(
                                f"   HATA {year} {province} {variable} deneme {attempt}: {error}"
                            )
                            time.sleep(5 * attempt)
                            census = Census(year)
                            census.provinces_map = census.provinces()
                    time.sleep(1.5)
        log("==", year, "bitti,", done, "yeni rapor")


if __name__ == "__main__":
    main()
