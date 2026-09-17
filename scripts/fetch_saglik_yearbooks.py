"""Download the Ministry of Health statistics yearbooks and dump their text layer.

sbsgm.saglik.gov.tr lists one page per yearbook (TR-93566); each page links the Turkish PDF on
dosyamerkez.saglik.gov.tr. The site answers plain HTTP clients with an empty JS shell, so the
links below were read in a browser on 2026-09-16; 2011-2016 are listed only on
www.saglik.gov.tr (TR-84930) and served from dosyasb.saglik.gov.tr.

PDFs go to C:/veri-ham/saglik/siy<year>.pdf (existing files are kept); the text, page by page,
to C:/veri-ham/saglik/siy<year>_text.json for `veriatlas.adapters.saglik_yearbook`.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pypdfium2

ROOT = Path("C:/veri-ham/saglik")
BASE = "https://dosyamerkez.saglik.gov.tr/Eklenti/"
PDFS = {
    2011: "https://dosyasb.saglik.gov.tr/Eklenti/23526/0/2011-yili3pdf.pdf",
    2012: "https://dosyasb.saglik.gov.tr/Eklenti/5111/0/istaturk2012pdf.pdf",
    2013: "https://dosyasb.saglik.gov.tr/Eklenti/5112/0/saglik-istatistik-yilligi-2013pdf.pdf",
    2014: "https://dosyasb.saglik.gov.tr/Eklenti/5119/0/yilliktrpdf.pdf",
    2015: "https://dosyasb.saglik.gov.tr/Eklenti/23530/0/2015-yili29pdf.pdf",
    2016: "https://dosyasb.saglik.gov.tr/Eklenti/13183/0/sy2016turkcepdf.pdf",
    2017: "31113/0/111turkcesiydijiv1pdf.pdf",
    2018: "47155/0/siy2018---turkcepdf.pdf",
    2019: "40564/0/saglik-istatistikleri-yilligi-2019pdf.pdf",
    2020: "44341/0/siy2020-trpdf.pdf",
    2021: "45316/0/siy2021-turkcepdf.pdf",
    2022: "48054/0/siy202205042024pdf.pdf",
    2023: "50500/0/siy202307032025pdf.pdf",
    2024: "52859/0/siy2024tr31122025pdf.pdf",
}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=600, follow_redirects=True
    )
    for year, path in PDFS.items():
        pdf = ROOT / f"siy{year}.pdf"
        if not pdf.exists():
            response = client.get(path if path.startswith("http") else BASE + path)
            response.raise_for_status()
            pdf.write_bytes(response.content)
        doc = pypdfium2.PdfDocument(pdf)
        pages = [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
        (ROOT / f"siy{year}_text.json").write_text(
            json.dumps(pages, ensure_ascii=False), encoding="utf-8"
        )
        print(
            year, len(pages), "sayfa", pdf.stat().st_size // 1_000_000, "MB", flush=True
        )


if __name__ == "__main__":
    main()
