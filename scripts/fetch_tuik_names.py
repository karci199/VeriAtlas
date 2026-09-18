r"""TÜİK's population portal: the 30 commonest names given to babies born in a year.

`nip.tuik.gov.tr` draws the table with DataTables, so the rows come from a POST that
answers with JSON and needs no browser. The page's own script names the endpoint and its
three parameters; nothing here is guessed:

    POST /Home/IlYilBebekIsimForTable   ilAdi, cinsiyet (1 erkek, 2 kadın), yil

The years on offer come from `POST /Home/GetYears` with `name=YeniDoganIsimleri`; today
that is 2018-2025. Two encodings live side by side: the JSON endpoints answer in UTF-8,
the HTML fragment that carries the province list in Windows-1254 with the Turkish letters
as entities. The rows arrive with the plate code, so no name matching is needed.

Every province-sex-year is cached as its own file, so a broken run resumes where it
stopped. Written to C:\veri-ham\tuik_isim\.
"""

from __future__ import annotations

import html
import json
import sys
import time
from pathlib import Path

import httpx

OUT = Path("C:/veri-ham/tuik_isim")
TABLE = "https://nip.tuik.gov.tr/Home/IlYilBebekIsimForTable"
YEARS_URL = "https://nip.tuik.gov.tr/Home/GetYears"
COLUMNS = ("DogumYil", "IlAdi", "Isim", "Cinsiyet", "Sayi", "Sira")
SEXES = {"1": "male", "2": "female"}


def client() -> httpx.Client:
    return httpx.Client(
        timeout=60,
        verify=False,
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://nip.tuik.gov.tr/?value=YeniDoganIsimleri",
        },
    )


def decode(response: httpx.Response) -> dict:
    return json.loads(response.content.decode("utf-8"))


def years(session: httpx.Client) -> list[int]:
    data = {"name": "YeniDoganIsimleri", "value[]": ["", "1"]}
    return sorted(decode(session.post(YEARS_URL, data=data))["data"])


def provinces(session: httpx.Client) -> list[str]:
    """The province names the portal itself offers, read from its own select box.

    The page fragment carries every select box on the page, so the two level options, the
    two sex options and "Hepsi" come with it and are dropped.
    """
    page = session.post("https://nip.tuik.gov.tr/Home/YeniDoganIsimleri")
    markup = html.unescape(page.content.decode("windows-1254"))
    skip = {"Hepsi", "TÜRKİYE", "Türkiye", "İL", "1", "2"}
    names: list[str] = []
    for chunk in markup.split('<option value="')[1:]:
        name = chunk.split('"')[0]
        if name not in skip and name not in names:
            names.append(name)
    if len(names) != 81:
        raise SystemExit(f"il listesi 81 değil, {len(names)} geldi")
    return names


def table_params(province: str, sex: str, year: int) -> dict[str, str]:
    """DataTables' server-side form. Without the column block the endpoint answers 500."""
    data = {
        "ilAdi": province,
        "cinsiyet": sex,
        "yil": str(year),
        "draw": "1",
        "start": "0",
        "length": "300",
        "search[value]": "",
        "search[regex]": "false",
    }
    for index, column in enumerate(COLUMNS):
        data[f"columns[{index}][data]"] = column
        data[f"columns[{index}][name]"] = column.upper()
        data[f"columns[{index}][searchable]"] = "true"
        data[f"columns[{index}][orderable]"] = "true"
        data[f"columns[{index}][search][value]"] = ""
        data[f"columns[{index}][search][regex]"] = "false"
    return data


def fetch() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with client() as session:
        span = years(session)
        places = ["TÜRKİYE", *provinces(session)]
        print(f"{len(places)} yer × {len(span)} yıl × 2 cinsiyet", flush=True)
        done = 0
        for place in places:
            for sex, label in SEXES.items():
                for year in span:
                    stem = f"{place}_{label}_{year}.json".replace("/", "-")
                    path = OUT / stem
                    if path.exists():
                        continue
                    rows = decode(
                        session.post(TABLE, data=table_params(place, sex, year))
                    )
                    path.write_text(
                        json.dumps(rows["data"], ensure_ascii=False), encoding="utf-8"
                    )
                    done += 1
                    if done % 50 == 0:
                        print(f"  {done} istek, son: {place} {year}", flush=True)
                    time.sleep(0.2)
        print(f"bitti: {done} yeni istek, {len(list(OUT.glob('*.json')))} dosya")


if __name__ == "__main__":
    sys.exit(fetch())
