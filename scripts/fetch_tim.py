"""Download TİM's provincial export workbooks.

tim.org.tr/tr/ihracat-rakamlari lists every monthly release since 2001 as plain links under
/files/downloads/rakamlar/<year>/.... File names change several times over the years
(`il_ihr_12_2014.xls`, `iller_bazinda_ihracat_rakamlari_Aralik_2018.xlsx`,
`2026-08-iller-bazinda-rakamlar.xlsx`), so every link whose name speaks of provinces is taken,
together with the yearly summary files, and kept under its own path.

Files go to C:/veri-ham/tim/<path under rakamlar>; existing files are kept. `index.tsv` lists
link text and path.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import httpx

ROOT = Path("C:/veri-ham/tim")
PAGE = "https://tim.org.tr/tr/ihracat-rakamlari"
SITE = "https://tim.org.tr"
#: names that carry provinces: il_, ilihr, iller, il-bazinda, ilsektor, ilulke
PROVINCIAL = re.compile(
    r"(^|[_\-/])(il|iller|ilihr|ilsektor|ilulke)[_\-.]|^il", re.IGNORECASE
)


def main() -> None:
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=120, follow_redirects=True
    )
    page = client.get(PAGE).text
    links = re.findall(
        r'<a href="(/files/downloads/rakamlar/[^"?]+\.xlsx?)(?:\?[^"]*)?"[^>]*>(.*?)</a>',
        page,
        re.IGNORECASE | re.DOTALL,
    )
    ROOT.mkdir(parents=True, exist_ok=True)
    index = []
    fetched = 0
    missing: list[str] = []
    for href, text in links:
        name = href.rsplit("/", 1)[-1]
        if not PROVINCIAL.search(name.lower()):
            continue
        rel = href.removeprefix("/files/downloads/rakamlar/")
        target = ROOT / rel
        label = html.unescape(re.sub(r"<[^>]+>|\s+", " ", text)).strip()
        index.append(f"{label}\t{rel}")
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        response = client.get(SITE + href)
        if response.status_code == 404:
            # some links point at files the site no longer has (2022-07 il × ülke)
            missing.append(rel)
            continue
        response.raise_for_status()
        target.write_bytes(response.content)
        fetched += 1
    (ROOT / "index.tsv").write_text("\n".join(index) + "\n", encoding="utf-8")
    (ROOT / "missing.txt").write_text("\n".join(missing) + "\n", encoding="utf-8")
    print(
        len(links),
        "bağlantı,",
        len(index),
        "il dosyası,",
        fetched,
        "indirildi,",
        len(missing),
        "yok",
    )


if __name__ == "__main__":
    main()
