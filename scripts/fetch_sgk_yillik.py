"""Download the SGK statistical yearbooks (İstatistik Yıllıkları), untouched.

sgk.gov.tr/Istatistik/Yillik lists one ZIP of Excel tables per year (2007 onwards). Each
download link is matched to the year written next to it on the page; a link without a
year, or a year seen twice, stops the run rather than guessing.

Output: `$VERIATLAS_RAW/sgk/yillik/<year>.zip` and `<year>/` with the ZIP extracted.
Years already on disk are skipped.

Run:  uv run python scripts/fetch_sgk_yillik.py
"""

from __future__ import annotations

import html
import io
import re
import sys
import warnings
import zipfile

import httpx

sys.path.insert(0, "src")

from veriatlas.config import RAW

PAGE = "https://www.sgk.gov.tr/Istatistik/Yillik/fcd5e59b-6af9-4d90-a451-ee7500eb1cb4/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "Chrome/126 Safari/537.36",
    "Accept-Language": "tr",
}


def main() -> None:
    warnings.filterwarnings("ignore")
    out = RAW / "sgk" / "yillik"
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        timeout=600, verify=False, follow_redirects=True, headers=HEADERS
    ) as client:
        page = client.get(PAGE).text
        links: dict[int, str] = {}
        # The year is inside the anchor ("2025 yılı istatistik bilgisi için tıklayınız").
        for match in re.finditer(
            r'href="(/download/downloadfile\?f=[^"]+\.zip[^"]*)"(.*?)</a>',
            page,
            re.DOTALL,
        ):
            inside = html.unescape(re.sub(r"<[^>]+>", " ", match.group(2)))
            years = re.findall(r"\b((?:19|20)\d\d)\b", inside)
            if not years:
                raise ValueError("yili okunamayan baglanti: " + match.group(1))
            year = int(years[-1])
            if year in links:
                raise ValueError(f"{year} iki kez")
            links[year] = "https://www.sgk.gov.tr" + html.unescape(match.group(1))
        print("yillar:", sorted(links))
        for year, url in sorted(links.items(), reverse=True):
            target = out / f"{year}.zip"
            if target.exists():
                continue
            response = client.get(url)
            response.raise_for_status()
            archive = zipfile.ZipFile(io.BytesIO(response.content))
            target.write_bytes(response.content)
            archive.extractall(out / str(year))
            print(
                year,
                len(response.content) // 1024,
                "KB,",
                len(archive.namelist()),
                "dosya",
            )


if __name__ == "__main__":
    main()
