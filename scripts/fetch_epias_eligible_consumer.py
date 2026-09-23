r"""Download EXIST (EPİAŞ) eligible-consumer counts per district and profile group.

`POST /v1/consumption/data/eligible-consumer-count` answers, for one month, the number of
meters whose usage type is "eligible consumer" — broken down by province, district and
profile subscriber group. It is the first district-level energy series in the store.

Two things about this API cost a session if they are not respected:

*   **Endpoint names are not guessed.** A wrong path earns a WAF 403, not a 404, and the
    address then looks blocked rather than wrong. Every path here was read off the service
    documentation at `/electricity-service/technical/tr/index.html`.
*   **Every call needs a TGT.** `giris.epias.com.tr/cas/v1/tickets` trades the account's
    username and password for a ticket-granting ticket, which travels in a `TGT` header.
    The ticket expires, so it is fetched again when a call comes back 401.

The response pages; `page.total` is the row count, not the page count. Each month is saved
whole to `C:\veri-ham\epias\eligible_consumer\<YYYY-MM>.json` and months already on disk
are not fetched again, so an interrupted run resumes by being run again.

The source warns that district names may be historical ones. Name matching is the
adapter's problem, not this script's: what is downloaded is kept verbatim.

Credentials live in `.env` (EPIAS_USERNAME, EPIAS_PASSWORD) and never in the repository.

Run:  uv run python scripts/fetch_epias_eligible_consumer.py [YYYY-MM] [YYYY-MM]
"""

from __future__ import annotations

import datetime as dt
import json
import sys

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW, settings

TICKETS = "https://giris.epias.com.tr/cas/v1/tickets"
API = "https://seffaflik.epias.com.tr/electricity-service/v1"
PATH = "/consumption/data/eligible-consumer-count"
OUT = RAW / "epias" / "eligible_consumer"
#: The panel's own page size. A larger one is accepted but answers slower and the total is
#: only ~4.400 rows a month, so this is one or two calls per month either way.
PAGE = 5000
#: Monthly series; the first month published is discovered by walking back until the API
#: answers with no rows, so the default start is deliberately early but not absurd.
DEFAULT_START = "2018-01"


def ticket(client: httpx.Client) -> str:
    """Trade username and password for a ticket-granting ticket."""
    if not (settings.epias_username and settings.epias_password):
        raise SystemExit(
            "EPIAS_USERNAME / EPIAS_PASSWORD tanimli degil — .env dosyasina eklenmeli"
        )
    answer = client.post(
        TICKETS,
        data={
            "username": settings.epias_username,
            "password": settings.epias_password,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60,
    )
    if answer.status_code not in (200, 201):
        raise SystemExit(f"TGT alinamadi: {answer.status_code} {answer.text[:200]}")
    return answer.text.strip()


def months(first: str, last: str) -> list[dt.date]:
    start = dt.date.fromisoformat(f"{first}-01")
    end = dt.date.fromisoformat(f"{last}-01")
    out = []
    while start <= end:
        out.append(start)
        start = (start.replace(day=28) + dt.timedelta(days=7)).replace(day=1)
    return out


def fetch_month(
    client: httpx.Client, tgt: str, month: dt.date
) -> tuple[list[dict], str]:
    """Return every row of one month, following the paging, and the ticket in force."""
    period = f"{month:%Y-%m-%d}T00:00:00+03:00"
    rows: list[dict] = []
    page = 1
    while True:
        body = {"period": period, "page": {"number": page, "size": PAGE}}
        answer = client.post(API + PATH, json=body, headers={"TGT": tgt}, timeout=120)
        if answer.status_code == 401:
            # The ticket expired mid-run; a fresh one retries the same page.
            tgt = ticket(client)
            continue
        answer.raise_for_status()
        payload = answer.json()
        items = payload.get("items") or []
        rows += items
        total = (payload.get("page") or {}).get("total")
        if not items or total is None or len(rows) >= total:
            return rows, tgt
        page += 1


def main() -> None:
    first = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_START
    today = dt.datetime.now(tz=dt.UTC).date()
    last = (
        sys.argv[2]
        if len(sys.argv) > 2
        else f"{today.replace(day=1) - dt.timedelta(days=1):%Y-%m}"
    )
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client() as client:
        tgt = ticket(client)
        for month in months(first, last):
            target = OUT / f"{month:%Y-%m}.json"
            if target.exists():
                continue
            rows, tgt = fetch_month(client, tgt, month)
            if not rows:
                print(f"{month:%Y-%m}: satir yok, atlandi", flush=True)
                continue
            target.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            print(f"{month:%Y-%m}: {len(rows)} satir", flush=True)


if __name__ == "__main__":
    main()
