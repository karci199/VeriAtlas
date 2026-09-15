"""Download the BTK statistics PDFs and dump the market reports' text layer.

Pages (btk.gov.tr, Next.js; the file list sits in the page HTML as title + s3 url):
elektronik-haberlesme-pazar-verileri, iletisim-hizmetleri-istatistikleri,
elektronik-kimlik-bilgisini-haiz-cihazlara-dair-istatistikler, posta-sektoru-pazar-verileri-raporu.

PDFs go to C:/veri-ham/btk/pdf/<page>/<title>.pdf (existing files are kept); the market
reports' text, page by page, to C:/veri-ham/btk/pdf/text/<report>.json for
`veriatlas.adapters.btk_tables`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pdfplumber

ROOT = Path("C:/veri-ham/btk/pdf")
PAGES = [
    "elektronik-haberlesme-pazar-verileri",
    "iletisim-hizmetleri-istatistikleri",
    "elektronik-kimlik-bilgisini-haiz-cihazlara-dair-istatistikler",
    "posta-sektoru-pazar-verileri-raporu",
]


def main() -> None:
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=300, follow_redirects=True
    )
    for page in PAGES:
        html = client.get(f"https://www.btk.gov.tr/{page}").text.replace('\\"', '"')
        files = dict(
            (re.sub(r"[^\w\-. ]", "_", title).strip(), url)
            for title, url in re.findall(
                r'"title":"([^"]{1,90})"[^{}]{0,300}?"url":"([^"]+\.pdf)"', html
            )
        )
        folder = ROOT / page
        folder.mkdir(parents=True, exist_ok=True)
        for name, url in files.items():
            target = folder / f"{name}.pdf"
            if not target.exists():
                url = (
                    url
                    if url.startswith("http")
                    else "https://www.btk.gov.tr/" + url.lstrip("/")
                )
                target.write_bytes(client.get(url).content)
        print(page, len(files))
    text = ROOT / "text"
    text.mkdir(exist_ok=True)
    for pdf in sorted((ROOT / PAGES[0]).glob("*.pdf")):
        target = text / f"{pdf.stem}.json"
        if target.exists():
            continue
        with pdfplumber.open(pdf) as document:
            pages = [page.extract_text() or "" for page in document.pages]
        target.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        print(pdf.name, len(pages))


if __name__ == "__main__":
    main()
