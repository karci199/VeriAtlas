"""TKGM "Tapu ve Kadastro Veri Onay İstatistiği" (MEGSİS), province table, raw.

cbs.tkgm.gov.tr/istatistik/MegsisGenel.aspx is an ASP.NET page: the first answer holds
only the grand total; the province rows arrive after a postback with the "Kapsam"
dropdown set to İl (option 3). Scope choices are Bölge and İl only. Province names sit
in the `value` of a per-row submit button (which opens that province's detail).

A snapshot, not a series: the page shows today's state ("Güncelleme Tarihi").
The province rows are checked against the page's own TOPLAM row before saving.

Output: `$VERIATLAS_RAW/tkgm/megsis_il.html` and `megsis_il_<update date>.csv`.

Run:  uv run python scripts/fetch_tkgm_megsis.py
"""

from __future__ import annotations

import csv
import html
import re
import sys
import warnings

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

URL = "https://cbs.tkgm.gov.tr/istatistik/MegsisGenel.aspx"
COLUMNS = [
    "il",
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


def number(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def main() -> None:
    warnings.filterwarnings("ignore")
    out = RAW / "tkgm"
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        timeout=120,
        verify=False,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as client:
        first = client.get(URL).text
        hidden = dict(
            re.findall(
                r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', first
            )
        )
        select = re.search(r'<select name="([^"]+)"', first).group(1)
        page = client.post(
            URL,
            data={
                **{k: html.unescape(v) for k, v in hidden.items()},
                select: "3",
                "__EVENTTARGET": select,
                "__EVENTARGUMENT": "",
            },
        ).text
    (out / "megsis_il.html").write_text(page, encoding="utf-8")
    date = re.search(r"G.ncelleme Tarihi:\s*(\d+)\.(\d+)\.(\d+)", page)
    stamp = f"{date.group(3)}-{date.group(2)}-{date.group(1)}"

    rows, total = [], None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(cells) < 10:
            continue
        button = re.search(r'value="([^"]+)"', cells[0])
        name = html.unescape(
            button.group(1) if button else re.sub(r"<[^>]+>", "", cells[0])
        ).strip()
        values = [
            number(html.unescape(re.sub(r"<[^>]+>", "", c)).strip())
            for c in cells[1:10]
        ]
        if name == "TOPLAM":
            total = values
        else:
            rows.append([name, *values])
    if len(rows) != 81 or total is None:
        raise ValueError(f"81 il ve TOPLAM beklenirdi: {len(rows)} satir")
    for j in range(8):
        if abs(sum(r[j + 1] for r in rows) - total[j]) > 1:
            raise ValueError(f"{COLUMNS[j + 1]}: il toplami TOPLAM satirini tutmuyor")
    with (out / f"megsis_il_{stamp}.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(len(rows), "il,", stamp)


if __name__ == "__main__":
    main()
