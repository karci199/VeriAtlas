"""Fetch TÜİK election reports at settlement level, for every kind of election.

One application, three sections, three shapes — and the differences are not cosmetic:

    milletvekili   secim.zul        report per district   (Seçim çevresi: + İlçe:)
    halkoylaması   halkoylama.zul   report per district   (İl: + İlçe:)
    cumhurbaşkanı  cumhursecim.zul  report per PROVINCE   (İller:)
    yerel          yerel.zul        report per province   (İl seçimi:), after an office
                                    and the "Bölge sonucu" scope are chosen

Asking the wrong box finds an empty list, which is indistinguishable from a year with no
data — so the box names are part of the table below, not guessed at runtime.

Everything is resumable: a report already on disk is skipped, so a run may be stopped and
restarted at any time. Sessions are recycled every SESSION_REPORTS reports because the
server slows down and eventually drops long-lived ones.

Data goes outside the repository, to `VERIATLAS_HAM` (default C:/veri-ham).

Run:  uv run python scripts/fetch_secim.py cb2023t1
      uv run python scripts/fetch_secim.py ho2017 --isci=2
      uv run python scripts/fetch_secim.py --liste
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from zk_client import ZK

HAM = pathlib.Path(os.environ.get("VERIATLAS_HAM", "C:/veri-ham"))
OUT = HAM / "secim"
PAUSE = 1.0
SESSION_REPORTS = 60

MV_TABLE = "Seçim çevresi ve bölgelerine göre"
HO_TABLE = "İl, ilçe ve bölgelerine göre yurt içi halk oylaması sonuçları"
# The district table, kept for a year the settlement one cannot answer. Measured, not
# assumed: 1961-1988 answer from BOTH, so they are asked for the deeper one. An empty
# province list is not proof of a missing year -- the application returns one when it is
# busy, and a plan cached from such a moment reads as "this year has no data" forever.
HO_TABLE_OLD = "İl ve ilçelere göre yurt içi halk oylaması sonuçları"
CB_TABLE = "İl, ilçe ve bölgelerine göre Cumhurbaşkanlığı yurt içi seçim sonuçları"
YEREL_SCOPE = "Bölge sonucu"
YEREL_SCOPE_FROM = 2014
# Before 2014 the settlement cut does not exist, and which of the remaining cuts answers
# depends on the office: the two belediye offices and the metropolitan one are counted by
# belediye, the provincial council by district. Asking the other one leaves the province
# list populated and the report button silent -- a failure with no message.
YEREL_SCOPE_OLD = {
    "ilgen": "İl ve ilçe sonucu",
    "belmec": "Belediye sonucu",
    "bel": "Belediye sonucu",
    "bsb": "Belediye sonucu",
}

YEREL_OFFICES = {
    "bsb": "Büyükşehir belediye başkanlığı",
    "bel": "Belediye başkanlığı",
    "belmec": "Belediye meclisi üyeliği",
    "ilgen": "İl genel meclisi üyeliği",
}


def mv(year_label: str) -> dict:
    return {
        "page": "secim.zul",
        "table": MV_TABLE,
        "year": year_label,
        "box": "Seçim çevresi:",
        "sub": "İlçe:",
    }


def ho(year_label: str, old: bool = False) -> dict:
    """One report per district, or -- for 1961-1988 -- one per province.

    Measured, not assumed. Those four years offer no district at all: the district box
    stays empty however long it is waited on, and the settlement table answers the report
    button with nothing. The district table does answer, one report per province, and that
    report carries the districts inside it. Asking the newer shape instead produced a plan
    of zero areas, which reads exactly like a year with no data -- and did, for months.
    """
    return {
        "page": "halkoylama.zul",
        "table": HO_TABLE_OLD if old else HO_TABLE,
        "year": year_label,
        "box": "İl:",
        "sub": None if old else "İlçe:",
    }


def cb(year_label: str, round_label: str | None = None) -> dict:
    return {
        "page": "cumhursecim.zul",
        "table": CB_TABLE,
        "year": year_label,
        "round": round_label,
        "box": "İller:",
        "sub": None,
    }


def aday(year_label: str) -> dict:
    """Candidates who stood, per electoral district.

    Not per ilçe: a candidacy is registered to a seçim çevresi, so the province (or the
    numbered slice of one, "İstanbul (1)") is the lowest level the table has. Asking it for
    a district would not be a deeper cut of the same thing, it would be nothing.
    """
    return {
        "page": "secim.zul",
        "table": "Milletvekili genel seçimine katılan adaylar",
        "year": year_label,
        "box": "Seçim çevresi:",
        "sub": None,
        # The label carries its own angle brackets, HTML-escaped as the page serves them.
        "sabit": (("Siyasi parti:", "&lt;&lt; Tüm partiler &gt;&gt;"),),
    }


def cikan(year_box: str) -> dict:
    """Seats each party and independent took — one report for the whole country.

    Two things this table wants that the vote tables do not: the year comes from its own
    `Yıllar:` box rather than the year radio, and the province box has a "<< Tüm iller >>"
    entry that answers for all eighty-one at once. Asking province by province returned a
    report with the two column headings and nothing under them — 3 KB that looked like a
    successful download. One report per year is 96 KB and carries every province.
    """
    return {
        "page": "secim.zul",
        "table": (
            "Yıllara ve illere göre siyasi parti ve bağımsızların çıkardığı "
            "milletvekili sayısı"
        ),
        "year": None,
        "box": "Seçim çevresi:",
        "sub": None,
        "alanlar": ["&lt;&lt; Tüm iller &gt;&gt;"],
        "sabit": (("Yıllar:", year_box),),
        "ad": year_box,
    }


def yerel(office: str, year: str) -> dict:
    return {
        "page": "yerel.zul",
        "office": YEREL_OFFICES[office],
        "scope": (
            YEREL_SCOPE if int(year) >= YEREL_SCOPE_FROM else YEREL_SCOPE_OLD[office]
        ),
        "year": year,
        "box": "İl seçimi:",
        "sub": None,
    }


VOTES: dict[str, dict] = {
    "mv2023": mv("2023"),
    "mv2018": mv("2018"),
    "mv2015k": mv("2015 seçimi (1 Kasım)"),
    "mv2015h": mv("2015 seçimi (7 Haziran)"),
    "mv2011": mv("2011 seçimi"),
    "mv2007": mv("2007 seçimi"),
    "mv2002": mv("2002 seçimi"),
    "mv1999": mv("1999 seçimi"),
    "mv1995": mv("1995 seçimi"),
    "mv1991": mv("1991 seçimi"),
    "aday2023": aday("2023"),
    "aday2018": aday("2018"),
    "aday2015k": aday("2015 seçimi (1 Kasım)"),
    "aday2015h": aday("2015 seçimi (7 Haziran)"),
    "aday2011": aday("2011"),
    "aday2007": aday("2007"),
    "aday2002": aday("2002"),
    "aday1999": aday("1999"),
    "aday1995": aday("1995"),
    "aday1991": aday("1991"),
    # Nothing before 1991 for either of these two tables, and it was measured rather than
    # assumed. The seats table's "Yıllar:" box holds ten years, 1991 to 2023, and no more.
    # The candidate table shows radios reading "1977-1950 seçimi" and "2023-1983 seçimi",
    # but choosing one leaves every list on the page empty and the report button silent --
    # they select a section the application no longer serves. So 1950-1987 candidates and
    # seats are not fetchable here; they are missing from the source, not from this file.
    "cikan2023": cikan("2023"),
    "cikan2018": cikan("2018"),
    "cikan2015h": cikan("2015 (7 Haziran)"),
    "cikan2015k": cikan("2015 (1 Kasım)"),
    "cikan2011": cikan("2011"),
    "cikan2007": cikan("2007"),
    "cikan2002": cikan("2002"),
    "cikan1999": cikan("1999"),
    "cikan1995": cikan("1995"),
    "cikan1991": cikan("1991"),
    "cb2023t1": cb("2023 Cumhurbaşkanlığı seçimi", "1.Tur"),
    "cb2023t2": cb("2023 Cumhurbaşkanlığı seçimi", "2.Tur"),
    "cb2018": cb("2018 Cumhurbaşkanlığı seçimi"),
    "cb2014": cb("2014 Cumhurbaşkanlığı seçimi"),
    "ho2017": ho("2017 Halk oylaması"),
    "ho2010": ho("2010 Halk oylaması"),
    "ho2007": ho("2007 Halk oylaması"),
    "ho1988": ho("1988 Halk oylaması", old=True),
    "ho1987": ho("1987 Halk oylaması", old=True),
    "ho1982": ho("1982 Halk oylaması", old=True),
    "ho1961": ho("1961 Halk oylaması", old=True),
}
for _office in YEREL_OFFICES:
    for _year in ("2024", "2019", "2014", "2009", "2004", "1999", "1994", "1989"):
        VOTES[f"yerel_{_office}_{_year}"] = yerel(_office, _year)

_log_lock = threading.Lock()


def slug(text: str) -> str:
    text = text.strip()
    for a, b in zip("İIçğıöşüÇĞÖŞÜ", "iicgiosucgosu", strict=False):
        text = text.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def log(vote: str, message: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {vote}: {message}"
    with _log_lock:
        print(line, flush=True)
        (OUT / "cekim.log").parent.mkdir(parents=True, exist_ok=True)
        with (OUT / "cekim.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def open_session(vote: str) -> ZK:
    """A session already on the right page, table, office, scope, year and round."""
    spec = VOTES[vote]
    # Five minutes, not two: a province-wide report (a CB one runs to five megabytes) is
    # built while the click request is open, and the default timeout cut Adana and Konya
    # off mid-build.
    z = ZK(spec["page"], timeout=300)
    if spec["page"] == "yerel.zul":
        # Order matters: the province list stays empty until the office, the scope and the
        # year are all answered, and an empty list reads as "this year has no data".
        z.pick("Mahalli İdareler Seçimi:", spec["office"], exact=True)
        z.check(spec["scope"])
        z.check(spec["year"])
    else:
        z.pick("Tablo seçimi:", spec["table"])
        if spec.get("year"):
            z.check(spec["year"])
        if spec.get("round"):
            z.check(spec["round"])
    return z


def dest(vote: str, area) -> pathlib.Path:
    spec = VOTES[vote]
    if spec.get("ad"):
        return OUT / vote / (slug(spec["ad"]) + ".html")
    parts = [area] if isinstance(area, str) else list(area)
    return OUT / vote / ("__".join(slug(p) for p in parts) + ".html")


def plan(vote: str) -> list:
    """The areas this vote offers, read from the application and cached on disk.

    Not the same list every year — 1982 has sixty-seven provinces, 2017 eighty-one — so it
    is read rather than assumed. Where a district is needed too, the walk is eighty-one
    round trips and the server drops connections along the way, so it is written down
    province by province and resumed.
    """
    spec = VOTES[vote]
    if spec.get("alanlar"):
        return list(spec["alanlar"])
    cache = OUT / f"plan_{vote}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    done: dict[str, list[str]] = {}
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("bitti"):
            return data["alanlar"]
        done = data.get("kismi", {})

    z = open_session(vote)
    provinces = list(z.options(spec["box"])[1])
    if not provinces:
        raise RuntimeError(f"{spec['box']} bos")
    if not spec["sub"]:
        cache.write_text(
            json.dumps({"bitti": True, "alanlar": provinces}, ensure_ascii=False),
            encoding="utf-8",
        )
        return provinces

    used = 0
    for province in provinces:
        if province in done:
            continue
        for attempt in range(4):
            try:
                if used >= 40:
                    z, used = open_session(vote), 0
                z.pick(spec["box"], province, exact=True)
                used += 1
                done[province] = list(z.options(spec["sub"])[1])
                break
            except Exception as exc:  # noqa: BLE001
                log(vote, f"  {province} alt listesi alinamadi ({str(exc)[:80]})")
                z, used = open_session(vote), 0
                time.sleep(4 * (attempt + 1))
        cache.write_text(
            json.dumps({"bitti": False, "kismi": done}, ensure_ascii=False),
            encoding="utf-8",
        )
    areas = [[p, d] for p in provinces for d in done.get(p, [])]
    cache.write_text(
        json.dumps({"bitti": True, "alanlar": areas}, ensure_ascii=False),
        encoding="utf-8",
    )
    log(vote, f"plan hazir — {len(areas)} alan")
    return areas


def fetch_one(z: ZK, vote: str, area) -> None:
    spec = VOTES[vote]
    if spec["sub"]:
        z.pick(spec["box"], area[0], exact=True)
        z.pick(spec["sub"], area[1], exact=True)
    else:
        z.pick(spec["box"], area, exact=True)
    for header, label in spec.get("sabit", ()):
        # A box that only fills once the area is chosen, and that the report will not be
        # built without. The candidate table's party list is one: leaving it alone gave no
        # redirect at all, for every province, with no message saying why.
        z.pick(header, label, exact=True)
    z.click("Raporu Oluştur")
    if not z.redirect:
        raise RuntimeError("rapor url yok")
    url = z.redirect.replace("http://", "https://")
    data = urllib.request.urlopen(url, timeout=300).read()
    if len(data) < 2000:
        raise RuntimeError(f"kucuk rapor {len(data)}")
    path = dest(vote, area)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def sweep(vote: str, workers: int) -> int:
    """One pass over what is missing. Returns how many are still missing after it."""
    areas = plan(vote)
    todo = [a for a in areas if not dest(vote, a).exists()]
    log(vote, f"{len(areas)} alan, {len(todo)} eksik")
    if not todo:
        return 0

    lock = threading.Lock()
    counters = {"done": 0, "fail": 0}
    share = (len(todo) + workers - 1) // workers

    def lane(index: int) -> None:
        mine = todo[index * share : (index + 1) * share]
        z, used = None, 0
        for area in mine:
            try:
                if z is None or used >= SESSION_REPORTS:
                    # Opening sits inside the try on purpose: a read timeout while opening
                    # used to escape the loop and kill the whole run, leaving the year
                    # merely unfinished rather than obviously crashed.
                    z, used = open_session(vote), 0
                fetch_one(z, vote, area)
                used += 1
                with lock:
                    counters["done"] += 1
                    if counters["done"] % 25 == 0:
                        log(vote, f"  {counters['done']}/{len(todo)}")
            except Exception as exc:  # noqa: BLE001
                with lock:
                    counters["fail"] += 1
                log(vote, f"  HATA {area}: {str(exc)[:90]}")
                z = None
            time.sleep(PAUSE)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lane, range(workers)))
    log(vote, f"gecis bitti — {counters['done']} yeni, {counters['fail']} hata")
    return counters["fail"]


def fetch(vote: str, workers: int = 1, rounds: int = 12) -> None:
    """Fetch, then sweep again for whatever failed.

    Failures are transient — the server resets a connection every few hundred reports, and
    a dropdown occasionally answers before it is filled — so a district missed in one pass
    is simply retried in the next. Without the sweep a year finishes quietly short, which
    is worse than finishing slowly.

    A fixed round count stopped while the gap was still closing: mv2011 ended 70 short with
    every pass still gaining. So the loop now stops when a pass gains nothing, not after a
    set number of tries; `rounds` is only the ceiling.
    """
    missing = None
    for _ in range(rounds):
        left = sweep(vote, workers)
        if not left:
            return
        if missing is not None and left >= missing:
            log(vote, f"gecis kazanc getirmedi, {left} eksikle birakiliyor")
            return
        missing = left
    log(vote, "hala eksik var")


def main(argv: list[str]) -> None:
    """One session at a time by default.

    Two parallel sessions look harmless and are not: asking the application for two
    province reports at once made both time out, while the same two fetched one after the
    other took two seconds each. Parallelism belongs between sources (Endeksa, MEDAS,
    seçim), not inside one.
    """
    if "--liste" in argv:
        for key in VOTES:
            path = OUT / key
            have = len(list(path.glob("*.html"))) if path.exists() else 0
            print(f"{key:16} {have:>5} rapor")
        return
    workers = int(next((a.split("=")[1] for a in argv if a.startswith("--isci=")), 1))
    wanted = [a for a in argv if not a.startswith("--")] or list(VOTES)
    for vote in wanted:
        if vote not in VOTES:
            print("bilinmeyen secim:", vote)
            continue
        fetch(vote, workers)


if __name__ == "__main__":
    main(sys.argv[1:])
