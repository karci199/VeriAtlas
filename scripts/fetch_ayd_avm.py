r"""AYD's shopping-centre turnover index, read off the association's own monthly pages.

AYD (Alışveriş Merkezleri ve Yatırımcıları Derneği) and Akademetre publish a monthly index
of turnover per rentable square metre — base 2010 = 100 — plus the lira turnover per m² for
İstanbul, Anadolu and Türkiye, a visitor-count index, and the year-on-year change for eight
retail categories. Nobody else measures mall trade in Turkey, and TÜİK's retail series does
not separate it, so this is the only reading of it there is.

    https://ayd.org.tr/<ay>-<yıl>-ciro-endeksi      (ocak-2025 … temmuz-2026)

robots.txt is a 404 — nothing is disallowed. One request per month, a second apart.

The server sends an incomplete certificate chain, so verification is switched off here as
it is for BDDK and KGM (`fetch_bddk_finturk.py`). Nothing secret travels either way; the
alternative is not fetching a public page at all.

**The page is prose, not a table.** Every number is inside a sentence, so the reader works
on sentences: the index points and the per-m² figures are each pulled from the sentence
that names them, and a month whose sentence is missing yields nothing for that field
rather than a guess. The parser asserts it found the index point for every month it was
given; a rewritten page will therefore stop the run instead of silently thinning the series.

**Only nineteen months are published.** The archive holds 2025-01 onward; 2024 and earlier
return 404 (checked 2026-09-19, ten URL spellings). The index itself reaches back to 2010,
but AYD does not put the history on the site — it is in the association's own press
releases and is not collected here.

**Nominal, not real.** The index is not deflated. The pages quote TÜFE next to it and
compute the real change in prose; we store what is measured and leave the deflating to
whoever asks, since the store already holds CPI.

Run:  uv run python scripts/fetch_ayd_avm.py
Out:  C:\veri-ham\ayd\avm_endeks.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import sys
import time

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

BASE = "https://ayd.org.tr"
OUT = RAW / "ayd" / "avm_endeks.csv"
PAUSE = 1.0

MONTHS = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6,
    "temmuz": 7, "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
}
#: The archive's reach, measured rather than assumed: every earlier month is a 404.
FIRST, LAST = (2025, 1), (2026, 7)

TAG = re.compile(r"<[^>]+>")
NUMBER = r"([-−]?[\d.]+,?\d*)"
#: "3400 puana yükseldi", "5.169 puan olarak kaydedildi" — the index itself.
POINTS = re.compile(NUMBER + r"\s*puan")
#: "Türkiye genelinde 12.963 TL iken İstanbul'da 15.478 TL, Anadolu'da 11.286 TL"
PER_SQM = {
    "TR": re.compile(r"T[üu]rkiye[^.]{0,40}?" + NUMBER + r"\s*TL"),
    "istanbul": re.compile(r"İstanbul[^.]{0,20}?" + NUMBER + r"\s*TL"),
    "anadolu": re.compile(r"Anadolu[^.]{0,20}?" + NUMBER + r"\s*TL"),
}
#: The headline: "...nominal olarak yüzde 25,2 arttı"
HEADLINE = re.compile(r"nominal olarak y[üu]zde\s*" + NUMBER)
#: "ziyaret sayısı endeksinde yüzde -2'lik bir azalış ile 95 puana"
VISITORS = re.compile(r"ziyaret[^.]{0,80}?" + NUMBER + r"\s*puan")


def number(text: str) -> float:
    """`5.169` → 5169.0, `25,2` → 25.2. Thousands use a dot, decimals a comma."""
    return float(text.replace("−", "-").replace(".", "").replace(",", "."))


def text_of(html: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub(" ", html))


def months() -> list[tuple[int, int, str]]:
    out = []
    for year in range(FIRST[0], LAST[0] + 1):
        for name, month in MONTHS.items():
            if (year, month) < FIRST or (year, month) > LAST:
                continue
            out.append((year, month, f"{name}-{year}-ciro-endeksi"))
    return sorted(out)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VeriAtlas/1.0)"}
    with httpx.Client(
        base_url=BASE,
        headers=headers,
        timeout=60,
        follow_redirects=True,
        verify=False,
    ) as client:
        for year, month, slug in months():
            response = client.get("/" + slug)
            if response.status_code != 200:
                print(slug, response.status_code, "atlandi")
                continue
            body = text_of(response.text)
            points = POINTS.search(body)
            if not points:
                raise SystemExit(f"{slug}: endeks puani bulunamadi — sayfa degismis")
            row = {
                "period": f"{year}-{month:02d}",
                "index_points": number(points.group(1)),
                "yoy_percent": (
                    number(HEADLINE.search(body).group(1))
                    if HEADLINE.search(body)
                    else ""
                ),
                "visitor_points": (
                    number(VISITORS.search(body).group(1))
                    if VISITORS.search(body)
                    else ""
                ),
            }
            for area, pattern in PER_SQM.items():
                found = pattern.search(body)
                row[f"try_per_sqm_{area}"] = number(found.group(1)) if found else ""
            rows.append(row)
            print(row["period"], row["index_points"], row["try_per_sqm_TR"])
            time.sleep(PAUSE)

    if len(rows) < 12:
        raise SystemExit(f"yalniz {len(rows)} ay okundu, arsiv daralmis olabilir")
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(OUT, len(rows), "ay", dt.datetime.now(tz=dt.UTC).date())


if __name__ == "__main__":
    main()
