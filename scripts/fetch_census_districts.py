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

Run:  python scripts/fetch_census_districts.py [--yil 1990 ...] [--sekme 1 2 3] [--degisken "*"]
      [--ayrinti ilce sehir koy]   (--sekme 0: every settlement's population, 1965-2000)
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
    print(dt.datetime.now().astimezone().strftime("%H:%M:%S"), *parts, flush=True)


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


#: tab index -> file prefix; 0 is the administrative tab (settlement populations)
TABS = {0: "idari", 1: "", 2: "eko", 3: "hane"}


class Census:
    def __init__(self, year: int, tab: int = 1):
        app, page = APPS[year]
        z.BASE = f"https://biruni.tuik.gov.tr/{app}/"
        self.k = z.ZK(page=page)
        self.tab = tab
        tabbox = re.search(r'id="(z_\w+)"[^>]*z\.type="zul\.tab\.Tabbox"', self.k.html)
        tabs = re.findall(r'id="(z_\w+)" z\.type="Tab"', self.k.html)
        if tab >= len(tabs):
            raise LookupError(f"{year}: {tab}. sekme yok ({len(tabs)} sekme)")
        if tabbox and len(tabs) > 1:
            self.k.event(tabbox.group(1), "onSelect", tabs[tab])
        boxes = list(selects(self.k.html).items())
        if tab == 0:
            # the administrative tab's level box comes first; "Tüm idari birimler" lists
            # every town and village of the chosen districts
            self.level, levels = boxes[0][0], {t: i for i, t in boxes[0][1]}
            self.district_level = next(
                v for t, v in levels.items() if t.startswith("Tüm idari")
            )
        else:
            # Each characteristics tab has an identical "Türkiye / İl / İlçe / Belde ve
            # Köyler" box; the tab-th one in document order belongs to this tab (taking the
            # newest landed on the household tab's variables).
            level_boxes = [
                (sid, {t: i for i, t in options})
                for sid, options in boxes
                if len(options) == 4 and options[0][1] == "Türkiye"
            ]
            self.level, levels = level_boxes[tab - 1]
            self.district_level = next(
                v for t, v in levels.items() if t.startswith("İlç")
            )

    def select(self, box: str, option: str) -> str:
        body = self.k.event(box, "onSelect", option)
        self.k.settle(body)
        return body

    def provinces(self) -> dict[str, str]:
        body = self.select(self.level, self.district_level)
        self.province_box, found = box_with(body, lambda ts: len(ts) > 50)
        return found

    def _to_details(self, province: str) -> str:
        body = self.select(self.province_box, self.provinces_map[province])
        try:
            box, found = box_with(body, lambda ts: ts[0].startswith("<<"))
        except KeyError:
            # the 1965-1980 application has no district box: a province is enough
            return body
        return self.select(box, found[next(iter(found))])

    def variables(self, province: str, detail: str) -> dict[str, str]:
        """Walk to the variable box and return {label: option uuid}; {} on the admin tab."""
        body = self._to_details(province)
        if self.tab == 0:
            return {}
        box, found = box_with(
            body, lambda ts: any(t.startswith("İlçe top") for t in ts)
        )
        key = next(t for t in found if t.startswith(detail))
        body = self.select(box, found[key])
        self.variable_box, found = box_with(
            body, lambda ts: not any(t.startswith("İlçe top") for t in ts)
        )
        return found

    def report(self, province: str, variable: str, detail: str) -> bytes:
        found = self.variables(province, detail)
        if self.tab:
            if variable not in found:
                raise KeyError(f"degisken yok: {variable!r} ({list(found)})")
            self.select(self.variable_box, found[variable])
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
        # three format radios per tab, HTML first; one report button per tab
        self.k.event(radios[3 * self.tab], "onCheck", "true")
        self.k.redirect = None
        answer = self.k.event(buttons[self.tab], "onClick")
        self.k.settle(answer)
        if not self.k.redirect:
            said = [
                html.unescape(x).strip()
                for x in re.findall(r">([^<>]{3,200})<", answer)
                if x.strip()
            ]
            raise RuntimeError(f"rapor yok: {said[:6]}")
        url = self.k.redirect.replace("http://", "https://")
        return self.k.opener.open(url, timeout=300).read()


def safe(name: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU-")
    return re.sub(r"[^A-Za-z0-9-]", "", name.translate(table)).lower()


def open_census(year: int, tab: int) -> Census:
    census = Census(year, tab)
    census.provinces_map = census.provinces()
    return census


def fetch(year: int, tab: int, wanted: list[str], details: list[str]) -> None:
    try:
        census = open_census(year, tab)
    except LookupError as error:
        log("  ", error)
        return
    names = list(census.provinces_map)
    if tab == 0:
        variables = ["tum"]
        details = ["yerlesim"]
    elif wanted == ["*"]:
        variables = list(census.variables(names[0], DETAILS["ilce"]))
    else:
        variables = wanted
    log(
        "==",
        year,
        TABS[tab] or "sosyal",
        len(names),
        "il,",
        len(variables),
        "degisken:",
        variables,
    )
    done = 0
    prefix = TABS[tab] + "-" if TABS[tab] else ""
    for n, province in enumerate(names, 1):
        for variable in variables:
            for detail in details:
                target = (
                    OUT
                    / str(year)
                    / f"{prefix}{safe(province)}-{safe(variable)}-{detail}.html"
                )
                if target.exists() and target.stat().st_size > 1000:
                    continue
                for attempt in (1, 2, 3):
                    try:
                        data = census.report(
                            province, variable, DETAILS.get(detail, "")
                        )
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                        done += 1
                        log(
                            f"   {year} {n}/{len(names)} {province} {variable} {detail} {len(data)} bayt"
                        )
                        break
                    except Exception as error:  # noqa: BLE001
                        log(
                            f"   HATA {year} {province} {variable} {detail} deneme {attempt}: {error}"
                        )
                        time.sleep(10 * attempt)
                        census = open_census(year, tab)
                time.sleep(1.5)
    log("==", year, TABS[tab] or "sosyal", "bitti,", done, "yeni rapor")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yil", type=int, nargs="*", default=SOCIAL_TAB_YEARS)
    ap.add_argument(
        "--sekme",
        type=int,
        nargs="*",
        default=[1],
        help="0 idari, 1 sosyal, 2 ekonomik, 3 hanehalkı",
    )
    ap.add_argument(
        "--degisken",
        nargs="*",
        default=["Beşerli Yaş Grubu", "Tek Yaş"],
        help='"*" = sekmedeki hepsi',
    )
    ap.add_argument("--ayrinti", nargs="*", default=["ilce"], choices=list(DETAILS))
    args = ap.parse_args()
    for tab in args.sekme:
        for year in args.yil:
            fetch(year, tab, args.degisken, args.ayrinti)


if __name__ == "__main__":
    main()
