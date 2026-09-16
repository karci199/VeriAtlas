r"""Download the yearly "enerji yatırımları" workbooks of the Ministry of Energy (EİGM).

enerji.gov.tr/eigm-raporlari links one workbook per year at a flat path,
`/Media/Dizin/EIGM/tr/Raporlar/EY/<year>.xls` (xlsx from 2014). Each lists the power plants
whose units were provisionally accepted that year: company, plant, province, source, unit
size, number of units and the capacity added, plus a small summary of the year's total by
source at the bottom.

Writes them to `C:\veri-ham\etkb\<year>.xls[x]`; 2003-2025 answered in 2026-09.
"""

from __future__ import annotations

from pathlib import Path

import httpx

FOLDER = Path("C:/veri-ham/etkb")
URL = "https://enerji.gov.tr//Media/Dizin/EIGM/tr/Raporlar/EY/{}.{}"


def main(first: int = 2003, last: int = 2026) -> None:
    FOLDER.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=120, follow_redirects=True
    )
    for year in range(first, last + 1):
        if any((FOLDER / f"{year}.{ext}").exists() for ext in ("xls", "xlsx")):
            continue
        for ext in ("xlsx", "xls"):
            response = client.get(URL.format(year, ext))
            if response.status_code == 200 and len(response.content) > 5000:
                (FOLDER / f"{year}.{ext}").write_bytes(response.content)
                print(year, ext, len(response.content) // 1000, "KB", flush=True)
                break
        else:
            print(year, "yok", flush=True)


if __name__ == "__main__":
    main()
