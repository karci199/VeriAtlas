"""Minimum wage periods from the Ministry of Labour (ÇSGB).

The ministry's own table "Yıllar itibarıyla net ve brüt asgari ücretler" (PDF, 1996 to
the last completed year) plus the current year from its minimum-wage page. The PDF is
read with `pdftotext -table`: `-layout` shifts the gross and employer-cost columns of the
1996-2008 page one block down, so every one of those rows would pair the right net with
the wrong gross without any error.

Amounts before 2005 are in old lira and are divided by 1e6 here, so the file is in TL
throughout. Only the 16-and-over wage is kept; the under-16 wage ended in 2014.

Output: C:/veri-ham/ucret/asgari/asgari_ucret_donemler.json
Run: .venv/Scripts/python.exe scripts/fetch_minimum_wage.py
"""

import html
import json
import re
import subprocess
import sys
from pathlib import Path

import httpx

OUT = Path("C:/veri-ham/ucret/asgari")
PDF_URL = "https://www.csgb.gov.tr/Media/t2qlvwrg/asgari-%C3%BCcret-net-br%C3%BCt-i%C5%9Fverene-maliyet.pdf"
PAGE_URL = "https://www.csgb.gov.tr/poco-pages/asgari-ucret/"
ROW = re.compile(
    r"(\d\d\.\d\d\.\d{4})\s*-\s*(\d\d\.\d\d\.\d{4})\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)"
)


def number(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (veriatlas)"}
    pdf = OUT / "asgari_ucret_csgb.pdf"
    pdf.write_bytes(
        httpx.get(PDF_URL, headers=headers, timeout=60).raise_for_status().content
    )
    page = httpx.get(PAGE_URL, headers=headers, timeout=60).raise_for_status().text
    (OUT / "poco.html").write_text(page, encoding="utf-8")

    text = subprocess.run(
        ["pdftotext", "-table", str(pdf), "-"], capture_output=True, check=True
    ).stdout.decode("latin-1")
    rows = []
    for start, end, net, gross, cost in ROW.findall(text):
        scale = 1e6 if int(start[-4:]) < 2005 else 1
        rows.append(
            {
                "start": start,
                "end": end,
                "net": round(number(net) / scale, 2),
                "brut": round(number(gross) / scale, 2),
                "maliyet": round(number(cost) / scale, 2),
            }
        )
    if len(rows) < 50:
        raise SystemExit(
            f"PDF'ten yalnız {len(rows)} dönem okundu; tablo biçimi değişmiş olabilir"
        )

    # The current year is on the page only: the first table is gross -> net, the second
    # the employer cost with the manufacturing (-5 point) discount the PDF also uses.
    cells = [
        html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
        for c in re.findall(r"<td[^>]*>(.*?)</td>", page, flags=re.DOTALL)
    ]
    values = [number(c) for c in cells if re.fullmatch(r"[\d.]+,\d\d", c)]
    gross, net = values[0], values[4]
    cost = next(v for v in values if v > gross * 1.1)
    year = (
        int(re.search(r"(\d{4}) Net Asgari", page).group(1))
        if re.search(r"(\d{4}) Net Asgari", page)
        else None
    )
    last = int(rows[-1]["end"][-4:])
    if year is None:
        year = last + 1
    if year > last:
        rows.append(
            {
                "start": f"01.01.{year}",
                "end": f"31.12.{year}",
                "net": net,
                "brut": gross,
                "maliyet": cost,
            }
        )
    (OUT / "asgari_ucret_donemler.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(rows)} dönem, son: {rows[-1]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
