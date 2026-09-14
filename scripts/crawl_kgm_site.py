"""Inventory the KGM (Karayolları Genel Müdürlüğü) website: pages and linked documents.

Breadth-first over www.kgm.gov.tr (Turkish site only), one request at a time with a pause.
Nothing is downloaded but the HTML pages; every link to a document (pdf, xls, xlsx, doc,
docx, zip, kmz, csv) is recorded with its link text and the page it was found on.

Output: `$VERIATLAS_RAW/kgm/site_pages.csv`, `$VERIATLAS_RAW/kgm/site_documents.csv`.
Resumable: pages already in site_pages.csv are not fetched again.

Run:  uv run python scripts/crawl_kgm_site.py [max_pages]
"""

from __future__ import annotations

import csv
import html
import re
import sys
import time
import warnings
from collections import deque
from urllib.parse import unquote, urldefrag, urljoin, urlparse

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

HOST = "www.kgm.gov.tr"
START = [
    "https://www.kgm.gov.tr/Sayfalar/KGM/SiteTr/Root/AnaSayfa.aspx",
    "https://www.kgm.gov.tr/Sayfalar/KGM/SiteTr/Trafik/KaraNoktalar.aspx",
    "https://www.kgm.gov.tr/Sayfalar/KGM/SiteTr/Istatistikler/Istatistikler.aspx",
]
DOC = re.compile(r"\.(pdf|xlsx?|docx?|zip|rar|kmz|kml|csv|pptx?)$", re.IGNORECASE)
SKIP = re.compile(
    r"/SiteEn/|/_layouts/|/Lists/|javascript:|mailto:|\.(jpe?g|png|gif|css|js|ico|svg|mp4)$",
    re.IGNORECASE,
)
PAUSE = 0.6


def links(page: str, base: str) -> list[tuple[str, str]]:
    out = []
    for match in re.finditer(
        r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', page, re.DOTALL | re.IGNORECASE
    ):
        href = html.unescape(match.group(1)).strip()
        text = re.sub(
            r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", match.group(2)))
        ).strip()
        url = urldefrag(urljoin(base, href))[0]
        out.append((url, text))
    return out


def main() -> None:
    warnings.filterwarnings("ignore")
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    out = RAW / "kgm"
    out.mkdir(parents=True, exist_ok=True)
    pages_path, docs_path = out / "site_pages.csv", out / "site_documents.csv"
    seen: set[str] = set()
    if pages_path.exists():
        with pages_path.open(encoding="utf-8") as f:
            seen = {row["url"] for row in csv.DictReader(f)}
    new_pages = not pages_path.exists()
    new_docs = not docs_path.exists()
    pages_f = pages_path.open("a", newline="", encoding="utf-8")
    docs_f = docs_path.open("a", newline="", encoding="utf-8")
    pw = csv.DictWriter(pages_f, ["url", "status", "title", "n_links", "n_docs"])
    dw = csv.DictWriter(docs_f, ["url", "ext", "text", "found_on"])
    if new_pages:
        pw.writeheader()
    if new_docs:
        dw.writeheader()
    queue = deque(u for u in START if u not in seen)
    queued = set(queue) | seen
    docs_seen: set[str] = set()
    fetched = 0
    with httpx.Client(
        timeout=60,
        verify=False,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 VeriAtlas envanter",
            "Accept-Language": "tr",
        },
    ) as client:
        while queue and fetched < limit:
            url = queue.popleft()
            try:
                response = client.get(url)
                status, body = response.status_code, response.text
                if "html" not in response.headers.get("content-type", ""):
                    body = ""
            except httpx.HTTPError as error:
                status, body = f"error:{type(error).__name__}", ""
            fetched += 1
            title = re.search(r"<title>(.*?)</title>", body, re.DOTALL | re.IGNORECASE)
            found = links(body, url) if body else []
            n_docs = 0
            for link, text in found:
                parsed = urlparse(link)
                if parsed.netloc.lower() != HOST or SKIP.search(link):
                    continue
                if DOC.search(unquote(parsed.path)):
                    n_docs += 1
                    if link not in docs_seen:
                        docs_seen.add(link)
                        dw.writerow(
                            {
                                "url": link,
                                "ext": DOC.search(unquote(parsed.path))
                                .group(1)
                                .lower(),
                                "text": text,
                                "found_on": url,
                            }
                        )
                elif (
                    parsed.path.lower().endswith(".aspx") and "/SiteTr/" in parsed.path
                ):
                    clean = link.split("?")[0]
                    if clean not in queued:
                        queued.add(clean)
                        queue.append(clean)
            pw.writerow(
                {
                    "url": url,
                    "status": status,
                    "title": re.sub(r"\s+", " ", title.group(1)).strip()
                    if title
                    else "",
                    "n_links": len(found),
                    "n_docs": n_docs,
                }
            )
            pages_f.flush()
            docs_f.flush()
            if fetched % 50 == 0:
                print(
                    fetched,
                    "sayfa,",
                    len(docs_seen),
                    "belge, kuyruk",
                    len(queue),
                    flush=True,
                )
            time.sleep(PAUSE)
    print(
        "bitti:", fetched, "sayfa,", len(docs_seen), "belge, kuyrukta kalan", len(queue)
    )


if __name__ == "__main__":
    main()
