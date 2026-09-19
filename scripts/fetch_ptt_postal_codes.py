r"""PTT postal codes: province, district, neighbourhood, street, code — from the source.

The semt layer has been resting on a 2022 third-party dump of the PTT table
(`raw/ptt/pk_20220810.xlsx`, see `docs/semt.md`) because today's PTT site looked like a
form with no table behind it. It has one: the query page at ptt.gov.tr/posta-kodu talks
to a single endpoint and hands back every row for a district at once.

    POST https://www.ptt.gov.tr/api/posta-kodu
    {"action": "ilceler",   "il_kodu": "14"}                    -> the province's districts
    {"action": "postakodu", "il_kodu": "14", "ilce_kodu": "1346"} -> every address row

Two things the endpoint will not forgive:

* **Browser headers are required.** A bare request gets IIS's `403 - Forbidden` with no
  explanation, which reads like a blocked path rather than a missing `User-Agent`.
* **The endpoint name was not guessed.** It was read off the page's own request, which is
  the only way these have ever been found here (`docs/cekiciler.md`).

The district codes the endpoint returns are the same ids the atlas already carries as
`endeksa_id` — Seyhan is 1104 in both. They are not translated here: this script writes
what the source said, and the registry match belongs to the adapter.

Run:  uv run python scripts/fetch_ptt_postal_codes.py
Out:  C:\veri-ham\ptt\postakodu_<YYYY-MM-DD>.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://www.ptt.gov.tr/api/posta-kodu"
OUT = Path("C:/veri-ham/ptt")

#: Without these the WAF answers 403. The referer matters as much as the agent.
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Origin": "https://www.ptt.gov.tr",
    "Referer": "https://www.ptt.gov.tr/posta-kodu",
}

#: Plate number -> the code the endpoint wants. They are the same thing, but the province
#: list lives in the page's HTML rather than behind the API, so it is written out.
PROVINCES = {
    "ADANA": 1,
    "ADIYAMAN": 2,
    "AFYONKARAHİSAR": 3,
    "AĞRI": 4,
    "AMASYA": 5,
    "ANKARA": 6,
    "ANTALYA": 7,
    "ARTVİN": 8,
    "AYDIN": 9,
    "BALIKESİR": 10,
    "BİLECİK": 11,
    "BİNGÖL": 12,
    "BİTLİS": 13,
    "BOLU": 14,
    "BURDUR": 15,
    "BURSA": 16,
    "ÇANAKKALE": 17,
    "ÇANKIRI": 18,
    "ÇORUM": 19,
    "DENİZLİ": 20,
    "DİYARBAKIR": 21,
    "EDİRNE": 22,
    "ELAZIĞ": 23,
    "ERZİNCAN": 24,
    "ERZURUM": 25,
    "ESKİŞEHİR": 26,
    "GAZİANTEP": 27,
    "GİRESUN": 28,
    "GÜMÜŞHANE": 29,
    "HAKKARİ": 30,
    "HATAY": 31,
    "ISPARTA": 32,
    "MERSİN": 33,
    "İSTANBUL": 34,
    "İZMİR": 35,
    "KARS": 36,
    "KASTAMONU": 37,
    "KAYSERİ": 38,
    "KIRKLARELİ": 39,
    "KIRŞEHİR": 40,
    "KOCAELİ": 41,
    "KONYA": 42,
    "KÜTAHYA": 43,
    "MALATYA": 44,
    "MANİSA": 45,
    "KAHRAMANMARAŞ": 46,
    "MARDİN": 47,
    "MUĞLA": 48,
    "MUŞ": 49,
    "NEVŞEHİR": 50,
    "NİĞDE": 51,
    "ORDU": 52,
    "RİZE": 53,
    "SAKARYA": 54,
    "SAMSUN": 55,
    "SİİRT": 56,
    "SİNOP": 57,
    "SİVAS": 58,
    "TEKİRDAĞ": 59,
    "TOKAT": 60,
    "TRABZON": 61,
    "TUNCELİ": 62,
    "ŞANLIURFA": 63,
    "UŞAK": 64,
    "VAN": 65,
    "YOZGAT": 66,
    "ZONGULDAK": 67,
    "AKSARAY": 68,
    "BAYBURT": 69,
    "KARAMAN": 70,
    "KIRIKKALE": 71,
    "BATMAN": 72,
    "ŞIRNAK": 73,
    "BARTIN": 74,
    "ARDAHAN": 75,
    "IĞDIR": 76,
    "YALOVA": 77,
    "KARABÜK": 78,
    "KİLİS": 79,
    "OSMANİYE": 80,
    "DÜZCE": 81,
}

#: The province dropdown's own placeholder comes back inside the district list too.
PLACEHOLDER = -1

DELAY = 0.4
#: Seconds before the first retry; it doubles each attempt (0,4 - 3 - 6 - 12 - 24 sn).
BACKOFF = 3.0


def ask(payload: dict, tries: int = 5) -> list[dict]:
    """One request, with backoff.

    The endpoint rate-limits at a few hundred requests: it starts answering `429`, and
    when it is close to the limit it also closes the connection mid-body, which arrives
    as `IncompleteRead` rather than as an error status. Both mean the same thing — wait —
    so both are retried. Without this the first run lost 20 districts of 973 to a
    printed warning that scrolled past.
    """
    request = urllib.request.Request(
        API, data=json.dumps(payload).encode("utf-8"), headers=HEADERS, method="POST"
    )
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read().decode("utf-8")
            if body.lstrip().startswith("<"):
                raise RuntimeError(f"PTT HTML döndürdü (403 olabilir): {payload}")
            return json.loads(body)
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            if attempt == tries - 1:
                raise
            time.sleep(BACKOFF * 2**attempt)
    raise AssertionError("unreachable")


def districts(province_code: int) -> list[tuple[int, str]]:
    return [
        (row["kod"], row["ad"])
        for row in ask({"action": "ilceler", "il_kodu": str(province_code)})
        if row["kod"] != PLACEHOLDER
    ]


def rows(province_code: int, district_code: int) -> list[dict]:
    return ask(
        {
            "action": "postakodu",
            "il_kodu": str(province_code),
            "ilce_kodu": str(district_code),
        }
    )


COLUMNS = ["il", "ilce", "ilce_kodu", "mahalle", "sokak", "posta_kodu"]


def already_in(target: Path) -> set[int]:
    """District codes the file already holds, so a gap-filling run can skip them."""
    if not target.exists():
        return set()
    with target.open(encoding="utf-8", newline="") as handle:
        return {int(row["ilce_kodu"]) for row in csv.DictReader(handle)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"postakodu_{dt.datetime.now(tz=dt.UTC).date():%Y-%m-%d}.csv"
    # `--eksik` appends the districts a rate-limited run lost instead of starting over:
    # a full pass is 973 requests and the limit is what went wrong in the first place.
    filling = "--eksik" in sys.argv
    have = already_in(target) if filling else set()
    seen_districts = 0
    written = 0
    with target.open("a" if filling else "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if not filling:
            writer.writerow(COLUMNS)
        for name, code in PROVINCES.items():
            found = [d for d in districts(code) if d[0] not in have]
            if filling and not found:
                continue
            time.sleep(DELAY)
            for district_code, district_name in found:
                try:
                    payload = rows(code, district_code)
                except Exception as error:  # noqa: BLE001 — one district must not stop 973
                    print(f"  ! {name}/{district_name}: {error}", flush=True)
                    continue
                for row in payload:
                    writer.writerow(
                        [
                            row["İl_Adi"],
                            row["İlce_Adi"],
                            district_code,
                            row["mahalleAdi"],
                            row["sokakAdi"],
                            row["posta_Kodu"],
                        ]
                    )
                    written += 1
                seen_districts += 1
                time.sleep(DELAY)
            print(
                f"{name}: {len(found)} ilçe, toplam {written:,} satır",
                flush=True,
            )
    print(f"\n{seen_districts} ilçe, {written:,} satır -> {target}")
    total = len(already_in(target))
    print(f"dosyada toplam {total} ilçe")
    if total < 900:
        print(
            f"UYARI: 973 ilçe bekleniyordu, {total} var — --eksik ile tamamla",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
