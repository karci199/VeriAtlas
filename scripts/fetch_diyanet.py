r"""Download the Diyanet statistics workbooks.

stratejigelistirme.diyanet.gov.tr/sayfa/57/istatistikler links eleven workbooks under
`/Documents/`, numbered by table (1.1 personnel … 6.1 budget). Only the 2023 edition is on
the page; the tables themselves carry 2013-2023 for the headline series and 2023 for the
provincial ones.

Writes them to `C:\veri-ham\diyanet\` under their own names.
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

import httpx

FOLDER = Path("C:/veri-ham/diyanet")
PAGE = "https://stratejigelistirme.diyanet.gov.tr/sayfa/57/istatistikler"
SITE = "https://stratejigelistirme.diyanet.gov.tr"


def main() -> None:
    FOLDER.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=180, follow_redirects=True
    )
    links = sorted(
        set(re.findall(r'href="(/Documents/[^"]+\.xlsx?)"', client.get(PAGE).text))
    )
    if len(links) < 11:
        raise RuntimeError(f"sayfada {len(links)} dosya bağlantısı var")
    for link in links:
        name = urllib.parse.unquote(link.split("/")[-1])
        response = client.get(SITE + link)
        response.raise_for_status()
        (FOLDER / name).write_bytes(response.content)
        print(len(response.content) // 1000, "KB", name, flush=True)


if __name__ == "__main__":
    main()
