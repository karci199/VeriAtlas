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
        return self.submit()

    # -- town and village level: province > district > bucak > all towns and villages
    def village_start(self) -> None:
        levels = {
            t: i
            for sid, options in selects(self.k.html).items()
            if sid == self.level
            for i, t in options
        }
        body = self.select(self.level, levels["Belde ve Köyler"])
        self.v_province_box, self.v_provinces = box_with(body, lambda ts: len(ts) > 50)

    def village_districts(self, province: str) -> list[str]:
        body = self.select(self.v_province_box, self.v_provinces[province])
        self.v_district_box, self.v_districts = box_with(body, lambda ts: True)
        return list(self.v_districts)

    def village_bucaks(self, province: str, district: str) -> list[str]:
        self.village_districts(province)
        body = self.select(self.v_district_box, self.v_districts[district])
        self.v_bucak_box, self.v_bucaks = box_with(body, lambda ts: True)
        return list(self.v_bucaks)

    def village_report(
        self, province: str, district: str, bucak: str, variable: str
    ) -> bytes:
        self.village_bucaks(province, district)
        body = self.select(self.v_bucak_box, self.v_bucaks[bucak])
        box, units = box_with(body, lambda ts: ts[0].startswith("<<"))
        body = self.select(box, units[next(iter(units))])
        self.variable_box, found = box_with(body, lambda ts: not ts[0].startswith("<<"))
        if variable not in found:
            raise KeyError(f"degisken yok: {variable!r} ({list(found)})")
        self.select(self.variable_box, found[variable])
        return self.submit()

    def submit(self) -> bytes:
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


def table_rows(data: bytes) -> list[list[str]]:
    text = data.decode("cp1254", "replace")
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.DOTALL | re.IGNORECASE):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip()
            for c in re.findall(
                r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL | re.IGNORECASE
            )
        ]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return rows


def number(cell: str) -> int | None:
    cell = cell.replace(".", "")
    return int(cell) if cell.isdigit() else None


SEX = ("Toplam", "Erkek", "Kadın")


def check_report(data: bytes) -> tuple[bool, str]:
    """Logic checks on a report before it is kept.

    A report without a single numeric row is an error page, not an empty table: refused,
    so it is asked again. Where Toplam, Erkek and Kadın appear, the parts must add up:
    as the last three columns (settlement tables) or as three consecutive rows
    (characteristics tables print a Toplam row, then Erkek, then Kadın). A mismatch is
    counted and logged, not refused: it is the source's, and the adapter decides.
    """
    rows = table_rows(data)
    numeric = [r for r in rows if any(number(c) is not None for c in r)]
    if not numeric:
        return False, "sayisal satir yok"
    checked = bad = 0
    # Tables whose header ends with exactly Toplam | Erkek | Kadın (settlements, single
    # age). Empty cells are dropped when rows are read, so only rows as wide as the
    # header are compared: age 73 printed as "1 | 1 | (empty)" would read as 73 = 1 + 1.
    widths = {len(r) for r in rows if tuple(r[-3:]) == SEX}
    if widths:
        for r in (r for r in numeric if len(r) in widths):
            tail = [number(c) for c in r[-3:]]
            if len(tail) == 3 and None not in tail:
                checked += 1
                bad += tail[0] != tail[1] + tail[2]
    for i in range(len(rows) - 2):
        three = rows[i : i + 3]
        marks = [next((j for j, c in enumerate(r) if c in SEX), None) for r in three]
        if None in marks or [three[k][marks[k]] for k in range(3)] != list(SEX):
            continue
        values = [[number(c) for c in r[m + 1 :]] for r, m in zip(three, marks)]
        width = min(len(v) for v in values)
        for a, b, c in zip(*(v[-width:] for v in values)):
            if None not in (a, b, c):
                checked += 1
                bad += a != b + c
    return True, f"{len(numeric)} satir, {checked} denetim, {bad} tutmayan"


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
    else:
        offered = list(census.variables(names[0], DETAILS["ilce"]))
        variables = offered if wanted == ["*"] else [v for v in wanted if v in offered]
        missing = [v for v in wanted if v != "*" and v not in offered]
        if missing:
            log("   bu yilda yok, atlandi:", missing)
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
                        ok, note = check_report(data)
                        if not ok:
                            raise RuntimeError("kontrol: " + note)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                        done += 1
                        log(
                            f"   {year} {n}/{len(names)} {province} {variable} {detail} {len(data)} bayt | {note}"
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


def fetch_villages(year: int, variables: list[str]) -> None:
    """Town and village level: one report per (province, district, bucak, variable)."""
    census = Census(year, 1)
    census.village_start()
    provinces = list(census.v_provinces)
    log("== koy", year, len(provinces), "il,", variables)
    done = 0
    for n, province in enumerate(provinces, 1):
        for district in census.village_districts(province):
            for bucak in census.village_bucaks(province, district):
                for variable in variables:
                    target = (
                        OUT
                        / str(year)
                        / "koy"
                        / f"{safe(province)}-{safe(district)}-{safe(bucak)}-{safe(variable)}.html"
                    )
                    if target.exists() and target.stat().st_size > 1000:
                        continue
                    for attempt in (1, 2, 3):
                        try:
                            data = census.village_report(
                                province, district, bucak, variable
                            )
                            ok, note = check_report(data)
                            if not ok:
                                raise RuntimeError("kontrol: " + note)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(data)
                            done += 1
                            log(
                                f"   koy {year} {n}/{len(provinces)} {province}/{district}/{bucak} {variable} {len(data)} bayt | {note}"
                            )
                            break
                        except Exception as error:  # noqa: BLE001
                            log(
                                f"   HATA koy {year} {province}/{district}/{bucak} {variable} deneme {attempt}: {error}"
                            )
                            time.sleep(10 * attempt)
                            census = Census(year, 1)
                            census.village_start()
                    time.sleep(1.5)
    log("== koy", year, "bitti,", done, "yeni rapor")


ALL_YEARS = [2000, 1990, 1985, 1980, 1975, 1970, 1965]
KEY_SOCIAL = [
    "0-14,15-64,65+",
    "Eğitim Durumu",
    "Okuryazarlık",
    "Medeni Durum",
    "Doğum Yeri",
    "Cinsiyet",
]
#: The whole job, small and important first, the village level last:
#: (label, kind, years, tab, variables, details)
QUEUE = [
    (
        "ilce yas",
        "tab",
        SOCIAL_TAB_YEARS,
        1,
        ["Beşerli Yaş Grubu", "Tek Yaş"],
        ["ilce"],
    ),
    ("yerlesim nufuslari", "tab", ALL_YEARS, 0, ["tum"], ["yerlesim"]),
    ("ilce sosyal onemli", "tab", SOCIAL_TAB_YEARS, 1, KEY_SOCIAL, ["ilce"]),
    ("ilce ekonomik", "tab", SOCIAL_TAB_YEARS, 2, ["*"], ["ilce"]),
    ("ilce hanehalki", "tab", SOCIAL_TAB_YEARS, 3, ["*"], ["ilce"]),
    ("ilce sosyal kalan", "tab", SOCIAL_TAB_YEARS, 1, ["*"], ["ilce"]),
    ("sehir/koy sosyal", "tab", SOCIAL_TAB_YEARS, 1, ["*"], ["sehir", "koy"]),
    ("sehir/koy ekonomik", "tab", SOCIAL_TAB_YEARS, 2, ["*"], ["sehir", "koy"]),
    ("sehir/koy hanehalki", "tab", SOCIAL_TAB_YEARS, 3, ["*"], ["sehir", "koy"]),
    (
        "koy koy yas",
        "koy",
        SOCIAL_TAB_YEARS,
        1,
        ["Beşerli Yaş Grubu", "0-14,15-64,65+"],
        [],
    ),
    (
        "koy koy egitim/medeni",
        "koy",
        SOCIAL_TAB_YEARS,
        1,
        ["Eğitim Durumu", "Okuryazarlık", "Medeni Durum", "Cinsiyet"],
        [],
    ),
    (
        "koy koy kalan",
        "koy",
        SOCIAL_TAB_YEARS,
        1,
        [
            "Onarlı Yaş Grubu",
            "Canlı Doğan ve Yaşayan Çocuk",
            "Canlı Doğan Çocuk Sayısına Göre Kadın Nüfus",
        ],
        [],
    ),
]


def run_queue() -> None:
    for n, (label, kind, years, tab, variables, details) in enumerate(QUEUE, 1):
        log(f"#### [{n}/{len(QUEUE)}] {label}")
        for year in years:
            if kind == "koy":
                fetch_villages(year, variables)
            else:
                fetch(year, tab, variables, details)
    log("#### KUYRUK BITTI")


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
    ap.add_argument("--koy", action="store_true", help="belde ve köy düzeyi")
    ap.add_argument("--kuyruk", action="store_true", help="bütün işi sırayla (QUEUE)")
    args = ap.parse_args()
    if args.kuyruk:
        run_queue()
        return
    if args.koy:
        for year in args.yil:
            fetch_villages(year, args.degisken)
        return
    for tab in args.sekme:
        for year in args.yil:
            fetch(year, tab, args.degisken, args.ayrinti)


if __name__ == "__main__":
    main()
