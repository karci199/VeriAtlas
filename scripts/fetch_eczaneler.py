r"""Every pharmacy in the country, from the registry that licenses them.

Pharmacies are the one shop type with a real register: opening one needs a licence, and
TİTCK — the medicines agency — keeps the list. That makes this a **census**, not a store
finder's snapshot of a brand, which is why it can answer "how many pharmacies are there"
where `chain_stores` can only answer "how many branches of this brand".

The list sits behind a Kendo grid on the agency's public page, and the grid reads through:

    POST ebs.titck.gov.tr/Ecza/Eczane/grdEczaneListesi_Read
         IlLookUpId=<il id>&page=1&pageSize=<n>

**The province is compulsory.** An empty `IlLookUpId` answers `{"Total":0,"Data":[]}` —
a valid request with an empty answer, not an error and not "no pharmacies in Türkiye".
The province ids are the agency's own (Adana is 18324, not 01) and are read from its own
dropdown feed, `GET /Public/GetCascadeIl?isPageAnon=True`, rather than guessed from plate
numbers.

**The page size is asked for in thousands and answered in silence.** With
`pageSize=5000` İstanbul — 5.846 pharmacies, the largest province — comes back
`{"Total":0,"Data":[]}`, HTTP 200 and no error anywhere. The first run recorded 80
provinces and left İstanbul out, which reads as a fact about the country rather than a
request that was too big. The sweep therefore pages at 1.000 and walks to `Total`, and a
province whose pages do not add up to its own `Total` stops the run.

Each row carries name, province and district. `Adres` comes back null on the list view;
it is written out anyway so the column exists if the agency starts filling it.

The district is the registry's own label here, and that is the right source for once: a
licence is issued *to* a district, so this is the licensing authority's own answer rather
than a chain's marketing geography. Matching those labels to the area registry is the
adapter's job.

TİTCK's robots.txt is readable and allows this path.

Run:  uv run python scripts/fetch_eczaneler.py
Out:  C:\veri-ham\eczane\eczaneler_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
import time

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

OUT = RAW / "eczane"
PAGE = "https://ebs.titck.gov.tr/ecza/eczane/eczanelistesi"
PROVINCES = "https://ebs.titck.gov.tr/Public/GetCascadeIl?isPageAnon=True"
GRID = "https://ebs.titck.gov.tr/Ecza/Eczane/grdEczaneListesi_Read"
UA = "ClaudeBot/1.0 (+https://claude.com/claudebot)"
DELAY = 0.4
#: Rows per request. Kept well under the size that makes the grid answer with an empty
#: list instead of an error — see the module docstring.
PAGE_SIZE = 1000
COLUMNS = ["id", "ad", "il", "ilce", "adres"]


def provinces(client: httpx.Client) -> list[dict]:
    answer = client.get(PROVINCES)
    answer.raise_for_status()
    found = answer.json()
    if len(found) != 81:
        raise SystemExit(f"il listesi 81 değil {len(found)} geldi")
    return found


def page_of(client: httpx.Client, province_id: int, page: int) -> tuple[list[dict], int]:
    answer = client.post(
        GRID, data={"IlLookUpId": province_id, "page": page, "pageSize": PAGE_SIZE}
    )
    answer.raise_for_status()
    payload = answer.json()
    return payload.get("Data") or [], payload.get("Total") or 0


def pharmacies_in(client: httpx.Client, province_id: int) -> list[dict]:
    rows, total = page_of(client, province_id, 1)
    page = 1
    while len(rows) < total:
        page += 1
        more, total_again = page_of(client, province_id, page)
        if not more:
            break
        if total_again != total:
            raise SystemExit(
                f"il {province_id}: Total sayfa {page}'de {total} iken {total_again} oldu"
            )
        rows.extend(more)
        time.sleep(DELAY)
    # The grid reports the size of the answer it *should* have given. Anything short of it
    # is a truncated count, and a truncated count is invisible downstream.
    if len(rows) != total:
        raise SystemExit(f"il {province_id}: {len(rows)} satır geldi, Total {total}")
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": UA, "X-Requested-With": "XMLHttpRequest"}
    rows: list[dict] = []
    with httpx.Client(headers=headers, timeout=120, follow_redirects=True) as client:
        client.get(PAGE)  # the session cookie the grid expects
        for province in provinces(client):
            found = pharmacies_in(client, province["ID"])
            if not found:
                print(f"  {province['Name']}: kayıt yok", flush=True)
            for record in found:
                rows.append(
                    {
                        "id": record.get("Id", ""),
                        "ad": record.get("Adi") or "",
                        "il": record.get("Il") or province["Name"],
                        "ilce": record.get("Ilce") or "",
                        "adres": record.get("Adres") or "",
                    }
                )
            time.sleep(DELAY)

    if not rows:
        raise SystemExit("hiç eczane dönmedi")
    path = OUT / f"eczaneler_{dt.datetime.now(tz=dt.UTC).date().isoformat()}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    districts = {(row["il"], row["ilce"]) for row in rows}
    print(
        f"{len(rows)} eczane, {len({r['il'] for r in rows})} il, {len(districts)} ilce: {path}"
    )


if __name__ == "__main__":
    main()
