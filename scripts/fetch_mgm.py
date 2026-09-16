r"""Download MGM's provincial climate tables.

mgm.gov.tr/veridegerlendirme/il-ve-ilceler-istatistik.aspx serves one page per province,
chosen by `m=<PROVINCE>` in MGM's own ASCII spelling (Mersin is still filed as "ICEL"), with
`k=A` for the normals over the station's whole measurement period and `k=H` for the 1991-2020
normals (not published for every province). The page is plain HTML tables.

Writes the parsed tables to `C:\veri-ham\mgm\iklim.json`: for each province, the rows of each
table as lists of cells, so the adapter never touches the network.
"""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

import httpx

FOLDER = Path("C:/veri-ham/mgm")
URL = "https://www.mgm.gov.tr/veridegerlendirme/il-ve-ilceler-istatistik.aspx?k={}&m={}"
AREAS = Path("src/veriatlas/data/areas_tr.csv")
ASCII = str.maketrans({"İ": "I", "Ş": "S", "Ç": "C", "Ğ": "G", "Ö": "O", "Ü": "U"})
NAMES = {"Mersin": "ICEL"}  # MGM never renamed İçel


def tables(client: httpx.Client, kind: str, name: str) -> list[list[list[str]]]:
    text = client.get(URL.format(kind, name.replace(" ", "%20"))).text
    out = []
    for table in re.findall(r"<table.*?</table>", text, re.DOTALL):
        rows = []
        for row in re.findall(r"<tr.*?</tr>", table, re.DOTALL):
            cells = [
                " ".join(html.unescape(re.sub(r"<[^>]+>", "", cell)).split())
                for cell in re.findall(r"<t[dh].*?</t[dh]>", row, re.DOTALL)
            ]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(cells)
        if rows:
            out.append(rows)
    return out


def main() -> None:
    FOLDER.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=60, follow_redirects=True
    )
    provinces = [
        row
        for row in csv.DictReader(AREAS.open(encoding="utf-8"))
        if row["area_level"] == "province"
    ]
    data = {}
    for row in provinces:
        name = NAMES.get(row["name_tr"], row["name_tr"].upper().translate(ASCII))
        found = {kind: tables(client, kind, name) for kind in ("A", "H")}
        data[row["area_id"]] = {
            "name": row["name_tr"],
            "mgm": name,
            "tables": {k: v for k, v in found.items() if v},
        }
        print(
            row["area_id"],
            row["name_tr"],
            {k: len(v) for k, v in found.items() if v},
            flush=True,
        )
    (FOLDER / "iklim.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    print(len(data), "il")


if __name__ == "__main__":
    main()
