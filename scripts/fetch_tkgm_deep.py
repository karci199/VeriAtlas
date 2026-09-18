r"""TKGM MEGSİS, all the way down: province → district → neighbourhood parcel counts.

The page (cbs.tkgm.gov.tr/istatistik/MegsisGenel.aspx) only offers Bölge and İl in its
scope box, but the statistics list page says the same figures exist "Bölge, İl, İlçe ve
Birim bazında" — and indeed every row's first cell is a submit button that drills one
level down. Province → district → **neighbourhood**: parcel counts for roughly 50.000
settlements, which no other source in this repository has.

ASP.NET mechanics, worked out against the live page, not assumed:

* The scope box is a `__EVENTTARGET` postback with the select's value `3` (İl).
* A row's button is posted by its own `name=value` pair together with the hidden fields
  (`__VIEWSTATE` and friends) **of the page that button is on**.
* Those hidden fields stay valid for repeated posts, so one district listing can be used
  to walk all of its districts rather than re-climbing the tree for each.

Every level's own TOPLAM row is checked against the parent's numbers; a drill that comes
back for the wrong parent would otherwise look like perfectly good data.

The site drops a connection every few hundred posts, so each request is retried and each
province is written as its own file under `megsis_derin/` before the run moves on: a
broken run resumes instead of losing an hour's walk.

Output (`$VERIATLAS_RAW/tkgm/`): `megsis_ilce_<date>.csv`, `megsis_mahalle_<date>.csv`.
"""

from __future__ import annotations

import csv
import html
import re
import sys
import time
import warnings

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

URL = "https://cbs.tkgm.gov.tr/istatistik/MegsisGenel.aspx"
COLUMNS = [
    "tapu_parsel",
    "kadastro_parsel",
    "tapuda_olmayan_parsel",
    "onayli_parsel",
    "onaysiz_parsel",
    "kesin_koordinatli",
    "gecici_koordinatli",
    "iyilestirilmis_koordinatli",
    "onayli_oran",
]
HIDDEN = re.compile(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"')
BUTTON = re.compile(r'<input type="submit" name="([^"]+)" value="([^"]+)"')


def number(text: str) -> float:
    """A blank cell is a zero: the page prints nothing rather than 0 in count columns."""
    if not text.strip():
        return 0.0
    return float(text.replace(".", "").replace(",", "."))


def post(client: httpx.Client, data: dict[str, str]) -> str:
    """One postback, retried: the server drops connections under a long walk."""
    for attempt in range(5):
        try:
            answer = client.post(URL, data=data)
            answer.raise_for_status()
            return answer.text
        except httpx.HTTPError as problem:
            if attempt == 4:
                raise
            print(f"    yeniden: {type(problem).__name__}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def hidden(page: str) -> dict[str, str]:
    return {k: html.unescape(v) for k, v in HIDDEN.findall(page)}


def buttons(page: str) -> list[tuple[str, str]]:
    """(name, label) of the drill-down buttons, in page order, without repeats."""
    seen: dict[str, str] = {}
    for name, label in BUTTON.findall(page):
        seen.setdefault(name, html.unescape(label).strip())
    return list(seen.items())


def table(page: str) -> tuple[list[tuple[str, list[float]]], list[float] | None]:
    """The rows as (name, numbers) and the TOPLAM row, which is kept apart."""
    rows: list[tuple[str, list[float]]] = []
    total: list[float] | None = None
    for block in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", block, re.DOTALL)
        if len(cells) < 10:
            continue
        label = BUTTON.search(cells[0])
        name = html.unescape(
            label.group(2) if label else re.sub(r"<[^>]+>", "", cells[0])
        ).strip()
        values = [
            number(html.unescape(re.sub(r"<[^>]+>", "", cell)).strip())
            for cell in cells[1:10]
        ]
        if name.upper() == "TOPLAM":
            total = values
        else:
            rows.append((name, values))
    return rows, total


def agrees(parent: list[float], total: list[float] | None, where: str) -> None:
    """The child table must add up to the row it was opened from (share column aside)."""
    if total is None:
        raise ValueError(f"{where}: TOPLAM satırı yok")
    for index in range(8):
        if abs(parent[index] - total[index]) > 1:
            raise ValueError(
                f"{where}: {COLUMNS[index]} üst satırla tutmuyor "
                f"({parent[index]} / {total[index]})"
            )


def main() -> None:
    warnings.filterwarnings("ignore")
    out = RAW / "tkgm"
    parts = out / "megsis_derin"
    parts.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        timeout=180,
        verify=False,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as client:
        home = client.get(URL).text
        scope = re.search(r'<select name="([^"]+)"', home).group(1)
        provinces_page = post(
            client,
            {**hidden(home), scope: "3", "__EVENTTARGET": scope, "__EVENTARGUMENT": ""},
        )
        stamp = re.search(r"G.ncelleme Tarihi:\s*(\d+)\.(\d+)\.(\d+)", provinces_page)
        date = f"{stamp.group(3)}-{stamp.group(2)}-{stamp.group(1)}"
        province_rows = dict(table(provinces_page)[0])
        province_state = hidden(provinces_page)
        for name, label in buttons(provinces_page):
            done = parts / f"{label}.csv"
            if done.exists():
                continue
            page = post(client, {**province_state, scope: "3", name: label})
            rows, total = table(page)
            agrees(province_rows[label], total, f"{label} ilçe tablosu")
            state = hidden(page)
            harvest: list[list] = []
            for button, district in buttons(page):
                sub = post(client, {**state, scope: "3", button: district})
                inner, inner_total = table(sub)
                agrees(dict(rows)[district], inner_total, f"{label}/{district}")
                for quarter, numbers in inner:
                    harvest.append([label, district, quarter, *numbers])
                time.sleep(0.2)
            with done.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["il", "ilce", "mahalle", *COLUMNS])
                writer.writerows(harvest)
            with (parts / f"{label}_ilce.csv").open(
                "w", newline="", encoding="utf-8"
            ) as handle:
                writer = csv.writer(handle)
                writer.writerow(["il", "ilce", *COLUMNS])
                writer.writerows(
                    [label, district, *values] for district, values in rows
                )
            print(f"{label}: {len(rows)} ilçe, {len(harvest)} mahalle", flush=True)
            time.sleep(0.2)
    combine(out, parts, date)


def combine(out, parts, date: str) -> None:
    """The per-province files into the two tables the adapter reads."""
    for suffix, head, kind in (
        ("_ilce.csv", ["il", "ilce", *COLUMNS], "ilce"),
        (".csv", ["il", "ilce", "mahalle", *COLUMNS], "mahalle"),
    ):
        rows: list[list[str]] = []
        for path in sorted(parts.glob("*.csv")):
            if path.name.endswith("_ilce.csv") != suffix.startswith("_ilce"):
                continue
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                next(reader)
                rows.extend(reader)
        target = out / f"megsis_{kind}_{date}.csv"
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(head)
            writer.writerows(rows)
        print(f"{target.name}: {len(rows)} satır")


if __name__ == "__main__":
    main()
